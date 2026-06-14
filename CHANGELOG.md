# Changelog

All notable changes to KisanMind are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [3.1.0] - 2026-06-14

### Added
- **Doubled to 44 growth parameters** for denser fact mapping and prediction:
  - 10 new Sentinel-2 indices (`backend/indices.py`): CCCI (nitrogen decoupled from biomass),
    MTCI + S2REP (red-edge chlorophyll/position), ARI (anthocyanin stress), **DSWI**
    (disease-water stress → KVK trigger), ARVI + VARI (haze/RGB-robust greenness), WDRVI
    (late-season biomass), BSI (germination gaps), NDTI (residue/tillage).
  - 12 derived agronomy parameters (`backend/agronomy.py`, pure): **CWSI** + **ESI** (crop
    water stress from LST/air-temp/VPD and actual÷reference ET), field thermal anomaly,
    relative humidity (fungal-disease pressure), wind (spray/lodging), soil temperature,
    surface soil moisture, aridity index, photoperiod (flowering), chill hours (temperate
    fruit), heat-stress degree days, frost risk — each with farmer-language interpretation.
- NASA POWER fetch extended with relative humidity (RH2M) and wind (WS2M).
- `parameters_mapped` now reports up to 44; `GET /api/parameters` and the cache/precompute
  storage updated accordingly. Advisory + voice weave the new water-stress, disease, frost
  and spray-timing signals into plain language.
- **Multi-sensor fusion** (`backend/fusion.py`): combines the 44 parameters into cross-checked
  diagnoses (water / nitrogen / disease / heat / harvest) weighted by *physically independent*
  measurement basis — agreement across independent sensors raises confidence, correlated
  indices count once, and disagreement is flagged as a conflict rather than guessed. The
  advisory leads with this combined diagnosis; the verification gate flags advisories that
  ignore a high-confidence fused finding. Response adds a `fusion` block.

## [3.0.0] - 2026-06-14

### Added
- **15+ crop-growth parameters** (the 80/20 remote-sensing set) via `backend/indices.py`:
  NDVI, EVI, SAVI, MSAVI2, NDRE, GNDVI, CIred-edge, PSRI, NDMI, NMDI, NDWI, NBR, LAI, FAPAR,
  each with jargon-free farmer interpretation and a parameter registry.
- **Agro-climate layer beyond Earth Engine** (`backend/agroclimate.py`): live, no-key
  NASA POWER (ET, root/surface soil wetness, solar radiation, precip) + Open-Meteo
  (layered soil moisture, FAO ET0, VPD, soil temperature). Works for every farmer per request.
- **Direct Copernicus provider** (`backend/copernicus.py`): Sentinel-2 indices straight from
  the Copernicus Data Space Ecosystem (Sentinel Hub Statistical API) — no GEE. Credential-gated
  (`CDSE_CLIENT_ID`/`CDSE_CLIENT_SECRET`), graceful when absent.
- **Sentinel-3 OLCI cluster** (`backend/copernicus.py`): OTCI chlorophyll + 300m near-daily
  NDVI that gap-fills Sentinel-2's cloud cover. Same CDSE credentials, no GEE.
- **NASA Earthdata cluster** (`backend/earthdata.py`): GLDAS-Noah root-zone moisture, 3-layer
  soil profile, ET and surface temperature via GES DISC Data Rods — a third independent
  soil-water source for cross-validation. Token-gated (`EARTHDATA_TOKEN`), graceful when absent.
- `GET /api/parameters`: lists all 22 parameters by family with sources + provider status.
- **Prediction layer** (`backend/prediction.py`): FAO-56 soil-water-balance "days until
  irrigation" forecast (flagship), honest NDVI-trajectory regression (never extrapolates from
  one observation), short-horizon price guidance, harvest-window estimate.
- **Real transport economics** (`backend/logistics.py`): diesel + distance + vehicle fare
  model replacing the flat per-km rate; full breakdown shown to the farmer.
- **Agentic verification gate** (`backend/verification.py`): deterministic cross-parameter +
  price-grounding + safety checks on the advisory before delivery; optional LLM auditor that
  flags and triggers at most one real-pipeline regeneration, never a silent rewrite.
- New advisory response fields: `indices`, `index_assessment`, `parameters_mapped`,
  `agroclimate`, `predictions`, and `confidence.verification`.
- `scripts/verify_v3.py`: offline/no-key verification harness (39 checks incl. live APIs).

### Fixed
- **EVI scaling bug**: EVI was computed on raw Sentinel-2 DN, producing impossible values
  (~2.0). Now computed on reflectance in live Earth Engine, the precompute, and the index
  module; legacy out-of-range cached EVI is null-guarded.

### Changed
- `precompute_satellite.py` now samples raw Sentinel-2 bands and computes the full 14-index set
  via the shared module, so a cache rebuild populates all parameters.
- Advisory and voice (Gemini Live) prompts now lead with the water forecast and weave in the
  additional growth signals in plain language.

## [2.1.0] - 2026-03-30

### Changed
- Optimized entire codebase for VM-only deployment (removed Cloud Run dependencies)
- Replaced blocking sync calls with `run_in_executor` in TTS, STT, summarize endpoints
- Replaced deprecated `asyncio.get_event_loop()` with `asyncio.get_running_loop()`
- Deduplicated chat contents builder, locale map, and inline imports
- Parameterized `GCS_CACHE_BUCKET` and `EE_PROJECT` via environment variables
- Simplified frontend structure (flattened hooks/ directory)
- Cleaned CSS to light theme only, removed 13 unused animation classes
- Rebuilt Dockerfile and deploy scripts for Docker/VM deployment

### Removed
- Deleted 16,000+ lines of dead code across 80+ files
- Removed `agents/` directory (3,447 lines never imported by backend)
- Removed `cloud_functions/` (superseded by FastAPI backend)
- Removed 7 unused frontend components (VoiceInput, AdvisoryCard, SatelliteMap, etc.)
- Removed 9 unused Python packages (google-adk, flask, bigquery, firestore, etc.)
- Removed 2 unused npm packages (lamejs, recharts)
- Removed duplicate satellite cache files (kept only latest.json)

### Added
- Session cleanup to prevent unbounded memory growth (`_cleanup_sessions`)
- MIT License, CONTRIBUTING.md, .dockerignore, GitHub FUNDING.yml
- Tech stack badges in README

### Fixed
- `_gcs_set` no longer blocks the event loop (wrapped in executor)
- Removed dead `use_pro` parameter, dead `crop_lower` variable, unused `sys` import
- Fixed `ignoreBuildErrors: true` in Next.js config (was masking TypeScript errors)

## [2.0.0] - 2026-03-29

### Added
- Multi-satellite intelligence: Sentinel-1 SAR, MODIS LST, NASA SMAP root-zone moisture
- Cross-validation engine: detects conflicts between satellite, weather, and price data
- Growing Degree Days (GDD) estimation from 120-day historical weather
- Pre-computed satellite cache: 3,788 points across India (O(1) grid-snap lookup)
- Gemini Live WebSocket streaming for real-time voice conversations
- Gemini-powered call summary (3-5 key points after call ends)
- Price trend analysis (rising/falling/stable with confidence levels)
- Crop-specific spoilage rates for net profit calculation
- Background satellite refinement for coarse cache hits (>5km)
- Advisory confidence scoring per data source

### Changed
- Full rewrite to single FastAPI backend (replaced Cloud Functions architecture)
- Switched weather from Google Weather API to Open-Meteo (free, no key required)
- All advisory generation in English first, then translated (better quality)

## [1.5.0] - 2026-03-29

### Added
- Twilio Voice integration: farmers call +1 260-254-7946 for voice advisory
- SMS summary sent after voice call with best mandi and weather alert
- Returning caller recognition (7-day session memory)
- Native multilingual generation in 22 Indian languages
- GOI-style white UI with tricolor accents

### Fixed
- Gemini overload handling with permanent red banner
- Graceful degradation when Gemini returns None

## [1.0.0] - 2026-03-28

### Added
- Real Sentinel-2 NDVI/EVI/NDWI via Google Earth Engine
- Live mandi prices from AgMarkNet (data.gov.in) with 106+ crops
- Google Maps driving distances and net profit ranking
- Open-Meteo 5-day weather forecast
- Voice-first interface with Chrome Web Speech API
- Google Cloud TTS (Wavenet) in 10 Indian languages
- Google Cloud STT V2 for speech recognition
- KVK (Krishi Vigyan Kendra) nearest center lookup via Google Places
- 2-tier persistent cache (in-memory L1 + GCS L2)
- Anti-hallucination guardrails (Gemini Flash fact-checking)

## [0.1.0] - 2026-03-27

### Added
- Initial project setup with Next.js 16 + FastAPI
- Basic voice interface prototype
- Earth Engine integration proof of concept
