"""
KisanMind Brain - Root Orchestrator Agent
==========================================
Coordinates specialist sub-agents (SatDrishti, MandiMitra, MausamGuru, VaaniSetu)
to produce unified agricultural advisories for Indian farmers.
"""

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import yaml
from google import genai
from google.adk import Agent, Runner
from google.adk.agents import SequentialAgent, ParallelAgent
from google.adk.tools import FunctionTool

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")

def _load_config() -> dict:
    with open(_CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

CONFIG = _load_config()

# ---------------------------------------------------------------------------
# Audit trail (in-memory; swap for Cloud Logging / BigQuery in prod)
# ---------------------------------------------------------------------------
AUDIT_TRAIL: dict[str, dict] = {}


def _log_audit(session_id: str, intent: str, agents_called: list[str],
               advisory: str, sources: list[str]) -> str:
    """Append an entry to the audit trail and return the entry ID."""
    entry_id = str(uuid.uuid4())
    AUDIT_TRAIL[entry_id] = {
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "intent": intent,
        "agents_called": agents_called,
        "advisory_snippet": advisory[:500],
        "data_sources": sources,
    }
    return entry_id


# ---------------------------------------------------------------------------
# Guardrails
# ---------------------------------------------------------------------------
GUARDRAIL_SYSTEM_PROMPT = """
You are KisanMind, an AI agricultural advisor for Indian farmers.

## STRICT GUARDRAILS -- NEVER VIOLATE
1. **No pesticide brand names or dosage**: Never recommend a specific pesticide
   product name or dosage amount. Instead, direct the farmer to their local
   Krishi Vigyan Kendra (KVK) or agricultural extension officer.
2. **No loan / credit / investment advice**: Never advise on loans, interest
   rates, credit schemes, or financial investments. Redirect to the nearest
   bank or NABARD office.
3. **No yield guarantees**: Never promise specific yield numbers or guaranteed
   income. All estimates must be clearly labelled as *indicative* and based on
   historical data.
4. **Always cite data sources**: Every advisory must mention which data sources
   were used (e.g. "Sentinel-2 NDVI dated 2025-03-15", "AgMarkNet prices as
   of 2025-03-20", "IMD forecast issued 2025-03-20").
5. **Always add a disclaimer**: End every advisory with:
   "Advisory is based on satellite data, weather models, and market trends.
   Always verify with local conditions and consult your agricultural extension
   officer."

## PERSONALITY
- Speak in simple, farmer-friendly language.
- Use analogies from rural life when helpful.
- Be empathetic and encouraging.
- When speaking in Hindi or regional languages, keep technical terms in English
  with a brief local-language explanation.

## RESPONSE FORMAT
Return a JSON object with the following structure:
{
  "summary": "<1-2 sentence headline>",
  "details": "<detailed advisory in markdown>",
  "action_items": ["<concrete step 1>", "..."],
  "data_sources": ["<source 1>", "..."],
  "disclaimer": "<standard disclaimer>"
}
"""


def _check_guardrails(text: str) -> str | None:
    """Return a guardrail warning if the text violates rules, else None."""
    prohibited = CONFIG.get("guardrails", {}).get("prohibited_topics", [])
    violations = []

    # Simple keyword-based pre-check (LLM-level filtering is in the prompt)
    pesticide_keywords = ["roundup", "bayer", "syngenta", "dhanuka", "tata rallis",
                          "ml/litre", "gm/litre", "spray dose"]
    loan_keywords = ["interest rate", "emi ", "loan amount", "credit score"]

    lower = text.lower()
    for kw in pesticide_keywords:
        if kw in lower:
            violations.append("no_pesticide_brands")
            break
    for kw in loan_keywords:
        if kw in lower:
            violations.append("no_loan_advice")
            break

    if violations:
        responses = {r["rule"]: r["response"] for r in prohibited}
        msgs = [responses.get(v, "") for v in violations]
        return " ".join(msgs)
    return None


# ---------------------------------------------------------------------------
# Intent classifier
# ---------------------------------------------------------------------------
INTENT_MAP = {
    "crop_health_check": ["crop health", "ndvi", "satellite", "leaf", "plant health",
                          "growth", "stress", "fasal ki sehat", "crop status"],
    "where_to_sell": ["mandi", "sell", "price", "market", "bechna", "rate",
                      "where to sell", "best price", "profit"],
    "weather_advisory": ["weather", "rain", "forecast", "mausam", "barish",
                         "frost", "temperature", "irrigation"],
    "full_advisory": ["full advisory", "complete", "poori salah", "everything",
                      "all advice", "comprehensive"],
}


def classify_intent(user_message: str) -> str:
    """Classify user intent from message text. Defaults to full_advisory."""
    lower = user_message.lower()
    scores: dict[str, int] = {}
    for intent, keywords in INTENT_MAP.items():
        scores[intent] = sum(1 for kw in keywords if kw in lower)
    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    return best if scores[best] > 0 else "full_advisory"


# ---------------------------------------------------------------------------
# Sub-agent stubs (these call into the real agent modules when available)
# ---------------------------------------------------------------------------

async def _call_sat_drishti(lat: float, lon: float, crop: str) -> dict:
    """Invoke SatDrishti for crop health analysis."""
    from agents.sat_drishti import analyze  # type: ignore[import]
    return await analyze(lat, lon, crop)


async def _call_mandi_mitra(lat: float, lon: float, crop: str,
                            quantity_qtl: float) -> dict:
    """Invoke MandiMitra for market intelligence."""
    from agents.mandi_mitra import find_best_mandi  # type: ignore[import]
    return await find_best_mandi(lat, lon, crop, quantity_qtl)


async def _call_mausam_guru(lat: float, lon: float) -> dict:
    """Invoke MausamGuru for weather advisory."""
    from agents.mausam_guru import get_advisory  # type: ignore[import]
    return await get_advisory(lat, lon)


# ---------------------------------------------------------------------------
# Orchestration logic
# ---------------------------------------------------------------------------

async def run_advisory(
    user_message: str,
    lat: float,
    lon: float,
    crop: str = "tomato",
    quantity_qtl: float = 10.0,
    language: str = "en",
    session_id: str | None = None,
) -> dict[str, Any]:
    """
    Main entry point. Classifies intent, dispatches to sub-agents (possibly in
    parallel), merges results, applies guardrails, and returns final advisory.
    """
    session_id = session_id or str(uuid.uuid4())
    intent = classify_intent(user_message)
    routing = CONFIG["intent_routing"][intent]
    agent_names = routing["agents"]
    run_parallel = routing.get("parallel", False)

    # ----- Dispatch to sub-agents -----
    agent_results: dict[str, dict] = {}
    tasks = []

    agent_dispatch = {
        "sat_drishti": lambda: _call_sat_drishti(lat, lon, crop),
        "mandi_mitra": lambda: _call_mandi_mitra(lat, lon, crop, quantity_qtl),
        "mausam_guru": lambda: _call_mausam_guru(lat, lon),
    }

    if run_parallel:
        coros = [agent_dispatch[a]() for a in agent_names if a in agent_dispatch]
        results = await asyncio.gather(*coros, return_exceptions=True)
        for name, res in zip(agent_names, results):
            if isinstance(res, Exception):
                agent_results[name] = {"error": str(res)}
            else:
                agent_results[name] = res
    else:
        for name in agent_names:
            if name in agent_dispatch:
                try:
                    agent_results[name] = await agent_dispatch[name]()
                except Exception as exc:
                    agent_results[name] = {"error": str(exc)}

    # ----- Merge & synthesise with Gemini 2.5 Pro -----
    synthesis_prompt = _build_synthesis_prompt(user_message, intent, agent_results, language)
    advisory_text = await _call_gemini_synthesis(synthesis_prompt)

    # ----- Guardrail post-check -----
    violation = _check_guardrails(advisory_text)
    if violation:
        advisory_text += f"\n\n**IMPORTANT**: {violation}"

    # ----- Collect data sources -----
    sources = []
    for res in agent_results.values():
        if isinstance(res, dict) and "data_source" in res:
            sources.append(res["data_source"])

    # ----- Audit log -----
    audit_id = _log_audit(session_id, intent, agent_names, advisory_text, sources)

    return {
        "session_id": session_id,
        "audit_id": audit_id,
        "intent": intent,
        "agents_invoked": agent_names,
        "agent_results": agent_results,
        "advisory": advisory_text,
        "data_sources": sources,
        "disclaimer": CONFIG["guardrails"]["mandatory_disclaimers"][0],
        "language": language,
    }


def _build_synthesis_prompt(user_message: str, intent: str,
                            agent_results: dict, language: str) -> str:
    """Compose the prompt sent to Gemini 2.5 Pro for final synthesis."""
    parts = [
        GUARDRAIL_SYSTEM_PROMPT,
        f"\n## Farmer's Question\n{user_message}\n",
        f"## Detected Intent\n{intent}\n",
        f"## Target Language\n{language}\n",
        "## Specialist Agent Outputs\n",
    ]
    for agent_name, result in agent_results.items():
        parts.append(f"### {agent_name}\n```json\n{json.dumps(result, indent=2, ensure_ascii=False)}\n```\n")
    parts.append(
        "\n## Your Task\n"
        "Synthesise the above agent outputs into a single, coherent, farmer-friendly advisory.\n"
        "Follow the JSON response format defined in your system prompt.\n"
        "Ensure all guardrails are respected.\n"
    )
    return "\n".join(parts)


async def _call_gemini_synthesis(prompt: str) -> str:
    """Call Gemini 2.5 Pro to synthesise the final advisory."""
    try:
        client = genai.Client()
        response = await client.aio.models.generate_content(
            model="gemini-3.1-pro",
            contents=prompt,
        )
        return response.text or ""
    except Exception as exc:
        # Graceful degradation: return a simple merge if Gemini is unavailable
        return (
            f"[Synthesis unavailable: {exc}] "
            "Based on the data gathered, please review the individual agent outputs above "
            "for crop health, market, and weather information. "
            "Advisory is indicative. Consult your local agricultural extension officer."
        )


# ---------------------------------------------------------------------------
# ADK Agent definition (for use with google.adk Runner)
# ---------------------------------------------------------------------------

def _get_advisory_tool(user_message: str, latitude: float, longitude: float,
                       crop: str = "tomato", quantity_quintals: float = 10.0,
                       language: str = "en") -> str:
    """
    Tool wrapper for the ADK agent. Runs the full advisory pipeline and returns
    the result as a JSON string.
    """
    result = asyncio.run(run_advisory(
        user_message=user_message,
        lat=latitude,
        lon=longitude,
        crop=crop,
        quantity_qtl=quantity_quintals,
        language=language,
    ))
    return json.dumps(result, indent=2, ensure_ascii=False)


# Build the ADK root agent
root_agent = Agent(
    name="kisanmind_brain",
    model="gemini-3.1-pro",
    description="KisanMind Brain: Root orchestrator for agricultural advisory",
    instruction=GUARDRAIL_SYSTEM_PROMPT,
    tools=[_get_advisory_tool],
)


# ---------------------------------------------------------------------------
# Convenience CLI for quick testing
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    msg = " ".join(sys.argv[1:]) or "My tomato crop leaves are turning yellow. I am in Solan, HP."
    result = asyncio.run(run_advisory(
        user_message=msg,
        lat=30.9045,
        lon=77.0967,
        crop="tomato",
    ))
    print(json.dumps(result, indent=2, ensure_ascii=False))
