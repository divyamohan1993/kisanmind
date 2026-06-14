"""
KisanMind — agentic verification gate.

Audits the drafted advisory against ALL the raw signals (15+ parameters, prices, forecasts)
BEFORE it reaches the farmer. Two layers:

  1. Deterministic cross-parameter checks (pure, fast, always run) — the backbone. They catch
     hallucinated prices, internal contradictions between sensors, and unsafe content with
     zero LLM cost or latency.
  2. An optional LLM auditor (injected, so this module tests without any model). It only
     FLAGS, and can trigger exactly ONE regeneration through the *real* advisory pipeline.
     It never silently substitutes its own text for the advice — a hallucinated "correction"
     on the critical path is a worse failure than the issue it claims to fix.

The gate is best-effort and time-boxed by the caller: if anything here is slow or errors, the
caller delivers the original advisory (current behaviour). Verification raises confidence; it
never blocks the farmer.
"""

from __future__ import annotations

import logging
import re
from typing import Callable, Optional

log = logging.getLogger("kisanmind.verification")

_RS_NUMBER = re.compile(r"(?:rs\.?|₹|inr)\s*([0-9][0-9,]{1,7})", re.IGNORECASE)
_LOAN_WORDS = re.compile(r"\b(loan|credit|insurance|emi|interest rate)\b", re.IGNORECASE)


def _money_set(payload: dict) -> set:
    """Every monetary figure the advisory is allowed to state, from real source data."""
    allowed = set()
    for m in (payload.get("best_mandi"), payload.get("local_mandi")):
        if not m:
            continue
        for k in ("modal_price", "net_profit_per_quintal", "min_price", "max_price"):
            v = m.get(k)
            if isinstance(v, (int, float)) and v > 0:
                allowed.add(round(float(v)))
    for m in payload.get("mandis", [])[:8]:
        for k in ("modal_price", "net_profit_per_quintal"):
            v = m.get(k)
            if isinstance(v, (int, float)) and v > 0:
                allowed.add(round(float(v)))
    pa = payload.get("price_advantage")
    if isinstance(pa, (int, float)):
        allowed.add(round(abs(pa)))
    # Quantity totals (price x quintals), if the farmer gave a quantity.
    qty = payload.get("quantity_quintals") or 0
    if qty:
        for base in list(allowed):
            allowed.add(round(base * qty))
    return allowed


def _is_grounded_amount(amount: float, allowed: set) -> bool:
    """True if `amount` is within rounding/tolerance of some real figure."""
    if not allowed:
        return True  # nothing to check against — don't manufacture a failure
    tol = max(5.0, 0.03 * amount)
    return any(abs(amount - a) <= tol for a in allowed)


def run_deterministic_checks(advisory_text: str, payload: dict) -> list[dict]:
    """Pure cross-parameter + grounding + safety checks. Returns a list of findings,
    each {check, severity (HIGH|MEDIUM|INFO), passed (bool), detail}."""
    findings = []
    text = advisory_text or ""

    # 1. Numeric price grounding (anti-hallucination).
    allowed = _money_set(payload)
    ungrounded = []
    for m in _RS_NUMBER.finditer(text):
        try:
            amount = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        if amount >= 50 and not _is_grounded_amount(amount, allowed):
            ungrounded.append(round(amount))
    findings.append({
        "check": "price_grounding",
        "severity": "HIGH",
        "passed": not ungrounded,
        "detail": ("All stated prices trace to source data." if not ungrounded
                   else f"Advisory states Rs {ungrounded} not found in source mandi data."),
    })

    # 2. Water-signal consistency across independent sensors.
    indices = payload.get("indices", {}) or {}
    extras = payload.get("satellite_extras", {}) or {}
    agro = payload.get("agroclimate", {}) or {}
    irr = payload.get("irrigation_forecast", {}) or {}
    ndmi_stress = (payload.get("ndmi_status") in ("water_stress", "mild_stress"))
    root_wet = None
    smap_root = extras.get("smap", {}).get("rootzone_class")
    if smap_root in ("wet", "adequate"):
        root_wet = True
    elif agro.get("rootzone_wetness") is not None:
        root_wet = agro["rootzone_wetness"] >= 0.3
    if ndmi_stress and root_wet:
        findings.append({
            "check": "water_sensor_agreement", "severity": "MEDIUM", "passed": False,
            "detail": "Canopy water (NDMI) reads stressed but root-zone moisture reads adequate — "
                      "surface vs deep mismatch; advisory should hedge irrigation timing.",
        })

    # 3. Advisory urges irrigation while the soil-water balance says it can wait.
    urges_irrigation = bool(re.search(r"\b(irrigat|water the crop|paani|watering now)\b", text, re.I))
    if urges_irrigation and irr.get("status") == "sufficient":
        findings.append({
            "check": "irrigation_vs_balance", "severity": "MEDIUM", "passed": False,
            "detail": "Advisory recommends watering, but the soil-water balance projects moisture "
                      "is sufficient for the forecast horizon. Reconcile or hedge.",
        })

    # 4. Greenness healthy but red-edge nitrogen low (greenness can mask deficiency).
    if payload.get("ndvi_status") in ("healthy", "very_healthy") and \
            payload.get("ndre_status") in ("low", "deficient"):
        findings.append({
            "check": "nitrogen_masked", "severity": "INFO", "passed": False,
            "detail": "Canopy looks green but red-edge suggests low nitrogen — advisory should not "
                      "over-reassure on crop nutrition.",
        })

    # 5. Senescence signal at an early stage = likely artifact, not real ripening.
    stage = (payload.get("growth_stage", {}) or {}).get("stage", "")
    if payload.get("psri_status") == "senescing" and stage in (
            "seedling", "sprouting", "vegetative", "tillering", "germination"):
        findings.append({
            "check": "senescence_stage_mismatch", "severity": "MEDIUM", "passed": False,
            "detail": "Leaf-ageing signal at an early growth stage is probably soil/cloud noise; "
                      "advisory must not suggest harvest.",
        })

    # 6. Safety: no loan/credit/insurance advice.
    findings.append({
        "check": "no_financial_advice",
        "severity": "HIGH",
        "passed": not bool(_LOAN_WORDS.search(text)),
        "detail": "No loan/credit/insurance content." if not _LOAN_WORDS.search(text)
                  else "Advisory contains financial-advice terms — must be removed.",
    })

    # 7. Pest/disease cross-validation must route to KVK.
    refers_kvk_needed = any(cv.get("action") == "REFER_KVK" for cv in payload.get("cross_validation", []))
    if refers_kvk_needed:
        findings.append({
            "check": "kvk_referral_present",
            "severity": "MEDIUM",
            "passed": bool(re.search(r"kvk|krishi", text, re.I)),
            "detail": "A pest/disease conflict was flagged; advisory should mention KVK.",
        })

    # 8. Combined multi-sensor diagnosis coverage — the advisory must not ignore a
    # high-confidence fused finding (the whole point of fusing the parameters).
    for f in (payload.get("fusion", {}) or {}).get("findings", []):
        diag, verdict, conf = f.get("diagnosis"), f.get("verdict"), f.get("confidence")
        if diag == "water" and verdict == "water_stress" and conf == "HIGH":
            findings.append({
                "check": "fused_water_addressed", "severity": "MEDIUM",
                "passed": bool(re.search(r"\b(irrigat|water|paani|moist)\b", text, re.I)),
                "detail": "Independent sensors agree on water stress, but the advisory does not "
                          "mention watering.",
            })
        if diag == "biotic_stress" and verdict == "possible_disease":
            findings.append({
                "check": "fused_disease_to_kvk", "severity": "MEDIUM",
                "passed": bool(re.search(r"kvk|krishi", text, re.I)),
                "detail": "Combined signals point to possible disease, but the advisory does not "
                          "refer to KVK.",
            })

    return findings


def summarize_verdict(findings: list[dict]) -> dict:
    """Roll findings into a verdict + confidence adjustment."""
    highs = [f for f in findings if f["severity"] == "HIGH" and not f["passed"]]
    meds = [f for f in findings if f["severity"] == "MEDIUM" and not f["passed"]]
    if highs:
        verdict = "FAIL"
        adj = -0.3
    elif meds:
        verdict = "REVIEW"
        adj = -0.1
    else:
        verdict = "PASS"
        adj = 0.0
    return {
        "verdict": verdict,
        "confidence_adjustment": adj,
        "high_issues": [f["check"] for f in highs],
        "medium_issues": [f["check"] for f in meds],
        "should_regenerate": bool(highs),
        "checks": findings,
    }


async def verify_advisory(
    advisory_text: str,
    payload: dict,
    gemini_call: Optional[Callable] = None,
    regenerate: Optional[Callable] = None,
) -> dict:
    """Run the gate. Returns {final_text, verdict, checks, regenerated, llm_audit}.

    - gemini_call(prompt:str)->str : optional LLM auditor (sync; caller wraps in executor).
    - regenerate(issues:list)->str : optional async re-run of the REAL advisory prompt.
    Never substitutes LLM free-text for the advice; regeneration goes through `regenerate`.
    """
    findings = run_deterministic_checks(advisory_text, payload)
    verdict = summarize_verdict(findings)
    final_text = advisory_text
    regenerated = False
    llm_audit = None

    # Optional LLM audit — purely advisory; we log it and fold its grounding flag in.
    if gemini_call is not None:
        try:
            llm_audit = _run_llm_audit(advisory_text, payload, gemini_call)
            if llm_audit and llm_audit.get("grounded") is False:
                verdict["should_regenerate"] = True
                verdict["llm_flagged"] = True
        except Exception as e:
            log.info(f"LLM audit skipped: {e}")

    # Exactly one regeneration, through the real pipeline, when grounding failed.
    if verdict["should_regenerate"] and regenerate is not None:
        try:
            issues = [f["detail"] for f in findings if f["severity"] in ("HIGH", "MEDIUM") and not f["passed"]]
            candidate = await regenerate(issues)
            if candidate:
                recheck = summarize_verdict(run_deterministic_checks(candidate, payload))
                # Keep the regenerated text only if it is no worse on grounding.
                if recheck["verdict"] != "FAIL":
                    final_text = candidate
                    regenerated = True
                    verdict["recheck"] = recheck["verdict"]
        except Exception as e:
            log.warning(f"Advisory regeneration failed, keeping original: {e}")

    return {
        "final_text": final_text,
        "verdict": verdict["verdict"],
        "regenerated": regenerated,
        "confidence_adjustment": verdict["confidence_adjustment"],
        "checks": findings,
        "llm_audit": llm_audit,
    }


def _run_llm_audit(advisory_text: str, payload: dict, gemini_call: Callable) -> Optional[dict]:
    """Ask the model whether every claim traces to the data. Returns {grounded, issues}."""
    best = payload.get("best_mandi", {}) or {}
    local = payload.get("local_mandi", {}) or {}
    facts = (
        f"best_mandi={best.get('market')} modal=Rs{best.get('modal_price')} net=Rs{best.get('net_profit_per_quintal')}; "
        f"local_mandi={local.get('market')} modal=Rs{local.get('modal_price')}; "
        f"ndvi_status={payload.get('ndvi_status')}; ndmi_status={payload.get('ndmi_status')}; "
        f"irrigation={payload.get('irrigation_forecast', {}).get('status')}"
    )
    prompt = (
        "You are a strict fact-checker for a farmer advisory. Using ONLY these source facts:\n"
        f"{facts}\n\nAdvisory:\n\"{advisory_text[:600]}\"\n\n"
        "Does every price, mandi name and recommendation trace to the facts? "
        "Reply exactly: GROUNDED or UNGROUNDED:<short reason>."
    )
    raw = (gemini_call(prompt) or "").strip()
    grounded = raw.upper().startswith("GROUNDED")
    return {"grounded": grounded, "raw": raw[:200]}
