# Changelog

All notable changes to KisanMind are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
