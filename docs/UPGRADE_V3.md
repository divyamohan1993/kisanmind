# KisanMind v3 — Multi-Parameter Sensing, Prediction & Agentic Verification

Status: IN PROGRESS (autonomous build). Goal: upgrade from ~9 satellite signals to a
scientifically-grounded **15+ parameter** crop-growth model that **maps AND predicts**,
fuses **multiple satellite/open-data sources beyond Google Earth Engine**, computes **real
transport economics**, runs **agentic verification**, and speaks to farmers in their language.

---

## 1. The 80/20 parameter set (the ~20% of signals that explain ~80% of crop-growth mapping)

Grounded in remote-sensing agronomy literature. Each maps to a real, computable signal.

### A. Greenness / canopy density / biomass
1. **NDVI** (B8,B4) — canopy greenness/vigour. *(have)*
2. **EVI** (B8,B4,B2, L/C1/C2) — biomass, saturates less than NDVI in dense canopy. *(have — buggy, fix scaling)*
3. **SAVI** (B8,B4, L=0.5) — soil-adjusted greenness for sparse/early canopy. *(new)*
4. **MSAVI2** (B8,B4) — self-adjusting soil factor, best early-season. *(new)*
5. **LAI** — leaf area index (biophysical, empirical from SAVI/EVI). *(new)*
6. **FAPAR** — fraction of PAR absorbed by canopy = productivity driver. *(new)*

### B. Chlorophyll / nitrogen / stress (red-edge family)
7. **NDRE** (B8,B5) — red-edge, chlorophyll/nitrogen, sensitive in mid-late growth. *(new)*
8. **GNDVI** (B8,B3) — chlorophyll, green-based. *(new)*
9. **CIred-edge** (B7/B5−1) — canopy chlorophyll content. *(new)*
10. **PSRI** ((B4−B2)/B6) — plant senescence / ripening → harvest timing. *(new)*

### C. Water / moisture
11. **NDMI / NDWI-Gao** (B8,B11) — canopy water content / moisture stress. *(new; current "ndwi" is McFeeters B3,B8 — keep but relabel as open-water)*
12. **NMDI** (B8,B11,B12) — drought index. *(new)*
13. **SAR soil moisture** (Sentinel-1 VV/VH) — moisture through clouds. *(have)*
14. **Root-zone soil moisture** (SMAP L4 + NASA POWER GWETROOT + Open-Meteo profile). *(have + augment)*
15. **Actual ET / ET0** (NASA POWER EVPTRNS, Open-Meteo et0_fao) — crop water demand. *(new, no-key)*

### D. Energy / thermal / climate
16. **LST day/night + diurnal** (MODIS) — heat stress, fruit-set. *(have)*
17. **Solar radiation** (NASA POWER ALLSKY_SFC_SW_DWN) — photosynthesis driver. *(new, no-key)*
18. **VPD** (Open-Meteo) — atmospheric water-stress driver. *(new, no-key)*
19. **GDD / thermal time** (Open-Meteo history) — phenology. *(have)*
20. **Precipitation** (Open-Meteo + POWER) — water supply. *(have)*

> Ship ≥15 with farmer-language interpretation. Scale-sensitive indices (EVI, SAVI, MSAVI,
> anything with additive constant) MUST use reflectance (DN×1e-4 for S2_SR_HARMONIZED).
> Ratio/normalized-difference indices are scale-invariant.

## 2. Satellite/data sources — beyond Google Earth Engine
- **GEE** (existing): Sentinel-2, Sentinel-1, MODIS, SMAP. Keep as ONE provider.
- **NASA POWER** (NEW, no key, live-verified): ET, root/surface soil wetness, solar, precip, T2M. Satellite+model agroclimatology, global, India-covered.
- **Open-Meteo** (extend, no key, live-verified): layered soil moisture, ET0 FAO, VPD, soil temp.
- **Copernicus Data Space Ecosystem / Sentinel Hub Statistical API** (NEW, credential-gated `CDSE_CLIENT_ID/SECRET`): S2 index time-series direct from Copernicus, NO GEE dependency. Graceful fallback to EE/cache when creds absent.
- Provider abstraction: advisory degrades gracefully if any source is down.

## 3. Prediction (not just mapping)
- **Vegetation trajectory forecast**: trend on NDVI/EVI/LAI series → predicted health in 7/15 days, days-to-peak, harvest window.
- **Soil-water-balance forecast**: rootzone moisture + ET forecast − rain forecast → **days until irrigation needed** (genuinely predictive, actionable).
- **Price forecast**: 90-day history → trend + volatility band → sell-now vs hold.
- **Yield proxy**: season-integrated greenness (indicative only, no guarantee).

## 4. Real transport economics
Replace flat ₹3.5/km/q with explainable model: vehicle (tractor-trolley/mini-truck/tempo),
diesel price, capacity, distance+duration (Maps). Keep net-profit ranking.

## 5. Agentic verification
`backend/verification.py`: deterministic cross-parameter consistency pre-checks over all 15+
signals + LLM verifier that audits the drafted advisory against raw data, returns
{verdict, contradictions, corrected_advisory, confidence}. Pre-delivery gate with tight
timeout → never blocks the farmer (fall back to current behaviour).

## 6. Farmer-language delivery
Every new parameter has a farmer-friendly template (no jargon). Verification corrections flow
through translation + TTS unchanged.

---

## Module plan (additive, graceful degradation, keep live app working)
- `backend/indices.py` — pure: 15+ index math + classification + interpretation + Pareto registry. **Unit-tested.**
- `backend/agroclimate.py` — async: NASA POWER + Open-Meteo soil/ET (no-key). **Live-probed.**
- `backend/copernicus.py` — async: CDSE Sentinel Hub Statistical (credential-gated).
- `backend/prediction.py` — pure: trajectory + soil-water-balance + price forecast. **Unit-tested.**
- `backend/logistics.py` — pure: transport fare model. **Unit-tested.**
- `backend/verification.py` — agentic verification gate.
- Wire into `_run_advisory`, `precompute_satellite.py`, `satellite_cache.py`, Gemini prompt.
- Update README / CHANGELOG / .env.example. Fix EVI scaling bug.

## Constraints
- Budget ₹0 → only free/no-key sources live; paid/credential sources graceful-optional.
- Don't break the running hackathon app. Every addition best-effort with fallback.
- Can't run full backend locally (no fastapi/EE/keys) → unit-test pure modules + live-probe no-key APIs + syntax-check integration.

---

# STATUS & DEPLOY RUNBOOK (read this first)

## Status — built overnight, autonomous
- **Branch:** `feat/v3-multiparam-sensing` — **committed, NOT pushed, NOT deployed.** `main` is untouched; the live app at kisanmind.dmj.one still runs v2.
- **Verified:** `python scripts/verify_v3.py` → **39/39** checks, including LIVE NASA POWER + Open-Meteo and a full enrichment+verification simulation. All backend modules `py_compile` clean. The EVI scaling bug is fixed and the legacy bad cache value is null-guarded.
- **NOT verified (no way to, tonight):** `main.py` was never run as a server — there is no `.env`, and `fastapi`/`earthengine`/`google-cloud`/`genai` are not installed locally. Wiring was checked by compile + code inspection + a simulation that mirrors `_run_advisory`. First real server run is step 3 below.

## What reaches farmers, precisely (no overclaim)
- **Live today on merge:** agro-climate parameters (ET, root/surface soil moisture, solar, VPD, soil temp — NASA POWER + Open-Meteo, no key) + base satellite (NDVI, SAR moisture, MODIS LST, SMAP) + **FAO-56 irrigation forecast** + diesel transport fare + agentic verification. That's ~9–11 mapped parameters per request, fetched fresh.
- **After the precompute rerun (step 4):** the full 14-index Sentinel-2 set for cached locations → 15–20+ parameters. Until then those extra optical indices appear only on live-EE cache-miss requests and via Copernicus.
- Every advisory returns `parameters_mapped` so coverage is honest at runtime.

## Deploy sequence (when you're awake)
1. **Review the diff:** `git log main..feat/v3-multiparam-sensing`, skim `backend/main.py` changes.
2. **Merge:** `git checkout main && git merge feat/v3-multiparam-sensing`.
3. **First real run (smoke test) with real `.env`:** start the backend, hit `GET /api/health`, then `POST /api/advisory` for a cached location (e.g. Solan 30.9,77.1, crop tomato). Confirm 200 + new fields (`indices`, `predictions.irrigation`, `agroclimate`, `parameters_mapped`). If anything 500s, the v3 blocks are all try/except → it degrades to v2; check logs for `v3 ... failed` warnings.
4. **Populate full 15+ for cached locations (needs EE creds):** `python scripts/precompute_satellite.py --all-india` (or per-region). This writes the new indices into `data/satellite_cache/latest.json` with correct EVI.
5. **Deploy** via the normal GitHub → VM path. Cloudflare proxy unchanged.

## Optional toggles (your call)
- **LLM-in-the-loop verifier:** the live gate runs deterministic cross-parameter + price-grounding + safety checks over all 15+ params and regenerates once on a grounding failure (the agentic verification). The extra *LLM* auditor in `verification.py` is wired but **off on the live path** (`gemini_call=None`) to avoid per-advisory latency; the existing background LLM fact-check still logs. To put the LLM in the blocking loop, pass a `gemini_call` that wraps `_gemini_generate` in `run_in_executor` (don't call it sync — it would block the event loop).
- **Copernicus Sentinel-2 + Sentinel-3 (one key):** set `CDSE_CLIENT_ID`/`CDSE_CLIENT_SECRET` (free at dataspace.copernicus.eu). Unlocks direct Sentinel-2 indices AND Sentinel-3 OLCI (OTCI chlorophyll + daily NDVI cloud gap-fill) — both straight from ESA, no GEE.
- **NASA Earthdata (independent soil/ET):** set `EARTHDATA_TOKEN` (free at urs.earthdata.nasa.gov). Adds GLDAS root-zone moisture, soil profile, ET and surface temp — a third independent water source that strengthens the verification gate.
- **Diesel price:** `DIESEL_PRICE_PER_L` tunes the transport fare model (defaults ~₹90/l).
- **Runtime parameter list:** `GET /api/parameters` returns all 22 parameters grouped by family with each source + which providers are configured. Verifiable smoke test after deploy.

> The two ESA/NASA clusters above are **credential-gated and untested until the keys exist** (same status as Copernicus). Each returns `{"available": false}` with zero network calls when its key is unset, so they cannot affect the app until enabled. Their no-key paths and parsers are unit-tested in `scripts/verify_v3.py`; their live paths run on first request after you add the key.

## Files added / changed
- New: `backend/indices.py`, `agroclimate.py`, `prediction.py`, `logistics.py`, `verification.py`, `copernicus.py` (Sentinel-2 + Sentinel-3), `earthdata.py` (NASA GLDAS); `scripts/verify_v3.py`; `docs/UPGRADE_V3.md`. New endpoint `GET /api/parameters`.
- Changed: `backend/main.py` (enrichment + prompt + verification gate + voice), `satellite_cache.py` (EVI guard + index passthrough), `scripts/precompute_satellite.py` (EVI fix + 14 indices), `tests/test_e2e.py`, `frontend/app/page.tsx` (copy), `README.md`, `CHANGELOG.md`, `.env.example`.
