# KisanMind Build Prompt

Copy everything below this line into a new Claude Code session:

---

You are building **KisanMind** — a multi-agent agricultural advisory system for the ET AI Hackathon 2026. The deadline is **29 March 2026** (tomorrow). Read all files in this repo first (`kisanmind-architecture.md`, `ET_AI_Hackathon_2026_Page.md`, `ET_AI_Hackathon_2026_PS.md`, `.env`) to understand the full architecture, then build the entire project.

## What KisanMind Does

A farmer calls/speaks (or uses a web dashboard) and says something like: "I'm growing tomatoes in Solan. How's my crop and where should I sell today?" KisanMind responds in Hindi with fused intelligence from 4 specialist agents: satellite crop health (NDVI), best mandi prices, weather forecast translated to farming actions, and voice I/O in Indian languages.

## Tech Stack

- **Backend**: Python 3.11 + FastAPI (serves agent API endpoints)
- **Frontend**: Next.js 14 (App Router) with TypeScript, Tailwind CSS, Recharts for charts
- **Multi-Agent Orchestration**: Claude Agent SDK (`pip install claude-agent-sdk`) with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` — use subagent architecture where the orchestrator (KisanMind Brain) dispatches to 4 specialist agents
- **LLM**: Claude API via `anthropic` Python SDK for the agent reasoning (intent extraction, agricultural synthesis, weather-to-action translation, response generation)
- **Database**: Firestore (farmer profiles, session state, cached prices)
- **Deployment**: Cloud Run (single container) → `kisanmind.dmj.one` custom domain. Must also work on a bare VM with `nginx + pm2` as fallback.
- **Region**: `asia-south1` (Mumbai)
- **GCloud Project**: `lmsforshantithakur` (Vertex AI, STT, TTS, Firestore, Maps, Weather API), `dmjone` (Earth Engine only)

## The 4 Specialist Agents

### 1. SatDrishti (Satellite Eye)
- Takes farmer location (village name → geocoded via Google Maps Geocoding API)
- Calls Google Earth Engine (project: `dmjone`) for Sentinel-2 NDVI/EVI/NDWI computation
- 500m radius analysis around coordinates, 3-month time series
- Claude interprets NDVI values using the interpretation table in the architecture doc
- Returns: NDVI value, trend (improving/declining/stable), false-color image URL, anomaly flag
- **Edge case**: Cloudy imagery → use last available clear image + warn farmer

### 2. MandiMitra (Market Friend)
- Fetches live mandi prices from AgMarkNet API (data.gov.in) for farmer's crop + state
- Calculates distance/travel time to each mandi via Google Maps Distance Matrix API
- Computes net profit per mandi: (price × quantity) - transport cost - commission - spoilage risk
- Returns: Ranked mandis by net profit, price trend analysis
- **Edge case**: AgMarkNet API down → serve last-cached prices from Firestore with timestamp

### 3. MausamGuru (Weather Guru)
- Fetches 5-day forecast from Google Weather API using the same `GOOGLE_MAPS_API_KEY`
- Claude translates raw weather into farming actions using the crop-weather rule matrix (in architecture doc)
- Returns: "DO harvest tomorrow", "DON'T spray today", "WARNING: ensure drainage"
- **Edge case**: Weather API failure → fallback to cached district-level forecast

### 4. VaaniSetu (Voice Bridge)
- Cloud Speech-to-Text V2 (Hindi, Tamil, Telugu + 6 more Indian languages, telephony model)
- Claude extracts intent: location, crop, intent type (crop_health/where_to_sell/weather/full_advisory)
- Cloud Text-to-Speech Neural2 for natural Hindi voice response
- Cloud Translation API v3 for cross-language support
- **Edge case**: Low STT confidence → ask to repeat, offer DTMF fallback

## Architecture — Single Container

```
Cloud Run container (or bare VM)
├── /api/*          → FastAPI (Python) — agent orchestration + external API calls
├── /              → Next.js frontend — satellite map, mandi charts, voice UI
└── Nginx (only on VM) reverse proxies both
```

Both services in one Docker container using a multi-stage build. FastAPI on port 8000, Next.js on port 3000. Cloud Run exposes port 3000 (Next.js handles API proxying to FastAPI via Next.js API routes or direct fetch).

## Project Structure

```
kisanmind/
├── .env                              # Already exists — has all API keys
├── .env.example                      # Already exists
├── Dockerfile                        # Multi-stage: Python + Node
├── docker-compose.yml                # Local dev
├── README.md                         # Setup instructions for judges
│
├── backend/
│   ├── requirements.txt
│   ├── main.py                       # FastAPI app entry
│   ├── config.py                     # Load .env, settings
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── orchestrator.py           # KisanMind Brain — routes to specialists, merges outputs
│   │   ├── sat_drishti.py            # Satellite agent — Earth Engine NDVI
│   │   ├── mandi_mitra.py            # Market agent — AgMarkNet + profit calc
│   │   ├── mausam_guru.py            # Weather agent — Weather API + crop rules
│   │   └── vaani_setu.py             # Voice agent — STT/TTS/Translation
│   ├── services/
│   │   ├── __init__.py
│   │   ├── earth_engine.py           # Earth Engine API wrapper
│   │   ├── agmarknet.py              # AgMarkNet API client
│   │   ├── weather.py                # Google Weather API client
│   │   ├── geocoding.py              # Google Maps Geocoding
│   │   ├── distance_matrix.py        # Google Maps Distance Matrix
│   │   ├── speech.py                 # Cloud STT/TTS
│   │   └── firestore_client.py       # Firestore operations
│   ├── guardrails/
│   │   ├── __init__.py
│   │   └── compliance.py             # Guardrail checks — no pesticide dosage, no loan advice, disclaimers
│   ├── prompts/
│   │   ├── system_prompt.py          # Master system prompt with NDVI table, crop-weather rules, guardrails
│   │   └── agent_prompts.py          # Per-agent prompts
│   └── models/
│       ├── __init__.py
│       └── schemas.py                # Pydantic models for request/response
│
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── next.config.js
│   ├── app/
│   │   ├── layout.tsx                # Root layout — Hindi/English toggle
│   │   ├── page.tsx                  # Home — satellite view + voice input + advisory cards
│   │   ├── globals.css
│   │   └── api/
│   │       ├── advisory/route.ts     # Proxy to FastAPI /api/advisory
│   │       ├── voice/route.ts        # Proxy to FastAPI /api/voice
│   │       └── mandi/route.ts        # Proxy to FastAPI /api/mandi
│   ├── components/
│   │   ├── SatelliteMap.tsx           # Google Maps + NDVI overlay (use Earth Engine getThumbURL)
│   │   ├── NDVIChart.tsx              # 3-month NDVI time-series line chart (Recharts)
│   │   ├── MandiComparison.tsx        # Bar chart of mandi prices sorted by net profit (Recharts)
│   │   ├── WeatherTimeline.tsx        # 5-day forecast cards with farming actions
│   │   ├── VoiceInput.tsx             # Mic button → MediaRecorder → send to /api/voice → play TTS audio
│   │   ├── AdvisoryCard.tsx           # Single advisory result card
│   │   ├── GuardrailBadge.tsx         # Shows compliance disclaimers
│   │   └── OnboardingFlow.tsx         # First-time farmer registration (location, crop, area)
│   └── lib/
│       └── api.ts                     # Fetch helpers for API routes
│
├── data/
│   ├── crop_calendar.json             # Crop timing data by region
│   ├── ndvi_benchmarks.json           # Regional NDVI averages for anomaly detection
│   ├── mandi_master.json              # Mandi list with geocoded coordinates
│   └── crop_weather_rules.json        # Crop-weather action matrix
│
├── infrastructure/
│   ├── setup.sh                       # Enable all GCloud APIs, create Firestore DB
│   └── deploy.sh                      # gcloud run deploy + domain mapping
│
└── architecture/
    └── system-architecture.md         # Copy of kisanmind-architecture.md (for submission)
```

## Key Implementation Details

### Orchestrator Flow (backend/agents/orchestrator.py)
```
User input → VaaniSetu extracts {location, crop, intent, language}
           → Geocoding resolves location to lat/lon
           → Parallel dispatch to SatDrishti + MandiMitra + MausamGuru
           → Orchestrator merges all results
           → Claude generates unified advisory in farmer's language
           → TTS converts to speech audio
           → Return {text, audio_url, satellite_image, mandi_data, weather_data}
```

### Claude Integration
Use `anthropic` Python SDK directly (NOT Vertex AI Gemini — we're using Claude):
```python
import anthropic
client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
```

Each agent uses Claude with tool use (function calling). The orchestrator calls Claude with tools for each specialist agent. Claude decides which tools to call based on user intent.

### Earth Engine Integration
- Use the Earth Engine REST API (not the Python client library) via service account on project `dmjone`
- Or use `ee` Python library: `pip install earthengine-api`
- Authenticate via service account: `ee.Initialize(credentials=credentials, project='dmjone')`
- The exact Earth Engine code is in `kisanmind-architecture.md` section 4, Agent 1

### Voice in Browser
- Use browser `MediaRecorder` API to capture audio
- Send audio blob to `/api/voice` endpoint
- Backend sends to Cloud STT V2, gets transcript
- Process through agent pipeline
- Generate response, send to Cloud TTS
- Return audio bytes to frontend, play via `<audio>` element

### Guardrails (CRITICAL for scoring)
Implement these in `backend/guardrails/compliance.py`:
- NEVER recommend specific pesticide brands or dosages → redirect to local KVK
- NEVER provide loan/credit advice → redirect to bank
- NEVER guarantee crop yields or prices → always add "based on current data" disclaimer
- ALWAYS cite data source ("AgMarkNet price as of today")
- ALWAYS show confidence level for satellite analysis
- ALWAYS log every recommendation with full reasoning chain (Cloud Logging)

### Edge Cases (CRITICAL for scoring)
Every agent must handle failures gracefully:
- Cloudy satellite → use last clear image + warn
- API down → serve cached data + show timestamp
- STT low confidence → ask to repeat
- Location not found → ask progressively (district → state)
- Crop not in database → be honest, offer partial data
- Design principle: **always return a result, even if degraded**

### Demo Data
Pre-cache demo data for 3 geographies to ensure the demo works flawlessly:
1. **Solan, Himachal Pradesh** — Tomatoes (primary demo)
2. **Coorg, Karnataka** — Coffee (shows different crop/state)
3. **Ludhiana, Punjab** — Wheat (shows pan-India reach)

### Frontend Design
- Clean, modern UI with Tailwind CSS
- Mobile-responsive (judges may test on phone)
- Hindi/English language toggle
- The satellite map is the "wow" screen — NDVI overlay on Google Maps
- Voice input button is prominent — one-tap to speak
- Show all 4 agent outputs as separate cards that populate in real-time
- Show guardrail badges when compliance rules are triggered
- Dark green + earth tones color scheme (agricultural theme)

## Deployment

### Plan A: Cloud Run
```bash
gcloud run deploy kisanmind \
  --source . \
  --region asia-south1 \
  --allow-unauthenticated \
  --memory 1Gi --cpu 1 \
  --min-instances 1 \
  --set-env-vars "$(cat .env | grep -v '^#' | grep -v '^$' | tr '\n' ',')"
```

Then map domain:
```bash
gcloud run domain-mappings create --service kisanmind --domain kisanmind.dmj.one --region asia-south1
# DNS: CNAME kisanmind → ghs.googlehosted.com
```

### Plan B: Bare VM fallback
```bash
# Same code, no Docker
sudo apt install -y nginx nodejs npm python3.11 python3.11-venv
# Python backend on :8000, Next.js on :3000, Nginx reverse proxy on :80
# certbot for HTTPS
# Point kisanmind.dmj.one A record to VM IP
```

## Build Order

1. **Backend first**: `config.py` → `services/*` (API wrappers) → `agents/*` (specialist agents) → `orchestrator.py` → `main.py` (FastAPI routes)
2. **Frontend second**: `page.tsx` (main page) → `components/*` → `api/` routes → styling
3. **Integration**: Wire frontend to backend, test end-to-end
4. **Demo data**: Pre-cache responses for the 3 demo geographies
5. **Infrastructure**: `setup.sh`, `deploy.sh`, `Dockerfile`
6. **Polish**: Error handling, loading states, mobile responsive, guardrail badges

## IMPORTANT NOTES

- Read `.env` file — all API keys are already there
- Read `kisanmind-architecture.md` for the FULL architecture details, Earth Engine code, SQL schemas, NDVI tables, crop-weather matrices, demo script, impact model
- This is a hackathon — prioritize working demo over perfect code
- Everything should be instant, feel like instant responses, O(1).
- use gemini 3.1 flash everywhere. 
- The submission is judged on: Code Quality, Creativity, Working Demo, Documentation, Business Impact
- Every agent decision must be auditable (logged with reasoning chain)
- The voice-first approach is the differentiator — make it work well in Hindi
- GCloud trial has $150 credit left — more than enough
