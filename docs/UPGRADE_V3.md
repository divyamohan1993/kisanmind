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
