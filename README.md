# KisanMind (किसानमाइंड) — Satellite-to-Voice Agricultural Intelligence

> **ET AI Hackathon 2026 — Problem Statement #5: Domain-Specialized AI Agents with Compliance Guardrails**

KisanMind is a multi-agent agricultural advisory system that fuses **satellite crop health monitoring** + **real-time mandi price arbitrage** + **hyperlocal weather intelligence** + **voice-first multilingual delivery** into a single platform accessible through a phone call in any Indian language.

A farmer calls, speaks in Hindi (or 8 other Indian languages), and gets:
- **Satellite analysis**: NDVI-based crop health from Sentinel-2 imagery via Google Earth Engine
- **Market intelligence**: Best mandi to sell at today, with net profit after transport costs
- **Weather advisory**: Farming-specific DO/DON'T actions based on 5-day forecast
- **All in 15 seconds**, through a voice response

---

## Architecture

```
User (Voice/Web) → VaaniSetu (Voice Bridge) → KisanMind Brain (Orchestrator)
                                                       │
                              ┌─────────────────────────┼─────────────────────────┐
                              ▼                         ▼                         ▼
                        SatDrishti                MandiMitra                MausamGuru
                    (Satellite Eye)            (Market Friend)           (Weather Guru)
                    Earth Engine NDVI          AgMarkNet Prices          Weather Forecast
                    Gemini Analysis            Profit Optimization       Crop-Weather Rules
```

### Four Specialist Agents

| Agent | Purpose | Data Sources |
|-------|---------|-------------|
| **SatDrishti** (सैटदृष्टि) | Crop health from satellite imagery | Google Earth Engine, Sentinel-2, Gemini 2.5 Pro |
| **MandiMitra** (मंडीमित्र) | Best mandi to sell at today | AgMarkNet (data.gov.in), Google Maps Distance Matrix |
| **MausamGuru** (मौसमगुरु) | Weather translated to farming actions | Google Weather API, crop-weather rule engine |
| **VaaniSetu** (वाणीसेतु) | Voice interface in 9 Indian languages | Cloud STT/TTS, Cloud Translation, Gemini Flash |

### Google Cloud Services (23 services)

Earth Engine, Vertex AI Agent Engine, ADK, Gemini 2.5 Pro/Flash, Cloud STT V2, Cloud TTS Neural2, Cloud Translation, Dialogflow CX, Vertex AI Search, BigQuery, Cloud Run, Cloud Functions, Firestore, Cloud Storage, Maps Geocoding, Maps Distance Matrix, Pub/Sub, Cloud Logging, Model Armor, Secret Manager, Cloud Scheduler, Identity Platform.

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+
- Google Cloud SDK (`gcloud`)
- A Google Cloud project with billing enabled

### 1. Clone and Setup

```bash
git clone <repo-url>
cd kisanmind

# Copy environment template and fill in your API keys
cp .env.example .env
# Edit .env with your keys

# Run automated setup (enables APIs, installs dependencies)
chmod +x infrastructure/setup.sh
./infrastructure/setup.sh
```

### 2. Configure API Keys

Edit `.env` with your keys:

```env
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_REGION=asia-south1
EE_PROJECT=your-earth-engine-project

GOOGLE_MAPS_API_KEY=your-maps-api-key
AGMARKNET_API_KEY=your-agmarknet-key
```

**How to get keys:**
- **Google Maps API Key**: [Cloud Console → APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials). Enable Geocoding API, Distance Matrix API, Weather API.
- **AgMarkNet API Key**: [data.gov.in](https://data.gov.in) → Register → Request API key for commodity prices.
- **Earth Engine**: Register at [earthengine.google.com](https://earthengine.google.com) → Non-commercial use.

### 3. Run Locally

**Backend (Python agents):**
```bash
source venv/bin/activate
python -m agents.brain.orchestrator
```

**Frontend (Next.js dashboard):**
```bash
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

### 4. Deploy to Cloud Run

```bash
chmod +x infrastructure/deploy.sh
./infrastructure/deploy.sh
```

---

## Project Structure

```
├── agents/                    # Multi-agent backend (Python, ADK)
│   ├── brain/                 # Orchestrator agent
│   │   ├── orchestrator.py    # Routes intent → specialist agents
│   │   └── config.yaml        # Agent configuration
│   ├── sat_drishti/           # Satellite analysis agent
│   │   ├── agent.py           # ADK agent definition
│   │   ├── earth_engine.py    # Earth Engine NDVI computation
│   │   └── ndvi_interpreter.py
│   ├── mandi_mitra/           # Market intelligence agent
│   │   ├── agent.py
│   │   ├── agmarknet_client.py
│   │   └── profit_optimizer.py
│   ├── mausam_guru/           # Weather advisory agent
│   │   ├── agent.py
│   │   ├── openweather_client.py
│   │   └── crop_weather_rules.py
│   └── vaani_setu/            # Voice interface agent
│       ├── agent.py
│       ├── stt_handler.py
│       ├── tts_handler.py
│       └── intent_extractor.py
│
├── cloud_functions/           # Event-driven microservices
│   ├── geocode/               # Location → lat/lon
│   ├── fetch_mandi_prices/    # AgMarkNet API caller
│   ├── fetch_weather/         # Weather API caller
│   ├── compute_ndvi/          # Earth Engine NDVI caller
│   └── calculate_profit/      # Transport + commission calc
│
├── data/
│   ├── bigquery/              # Reference data (CSVs)
│   │   ├── crop_calendar.csv
│   │   ├── ndvi_benchmarks.csv
│   │   └── mandi_master.csv
│   ├── knowledge_base/        # RAG corpus for Vertex AI Search
│   └── earth_engine/          # Earth Engine scripts
│
├── frontend/                  # Next.js web dashboard
│   ├── app/
│   │   ├── page.tsx           # Satellite view + voice input
│   │   ├── mandi/page.tsx     # Mandi price comparison
│   │   ├── weather/page.tsx   # Weather advisory
│   │   └── components/        # React components
│   └── public/demo-data/      # Standalone demo data
│
├── infrastructure/
│   ├── setup.sh               # One-command project setup
│   └── deploy.sh              # One-command Cloud Run deployment
│
├── demo/                      # Demo video script + sample queries
├── Dockerfile                 # Multi-stage Docker build
├── requirements.txt           # Python dependencies
└── .env.example               # API key template
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent Framework | Google ADK (Agent Development Kit) |
| LLM | Gemini 2.5 Pro (reasoning), Gemini 2.5 Flash (classification) |
| Satellite | Google Earth Engine + Sentinel-2 |
| Voice | Cloud Speech-to-Text V2 + Cloud Text-to-Speech Neural2 |
| Frontend | Next.js 15, TypeScript, Tailwind CSS, Recharts |
| Data | BigQuery, Firestore, Cloud Storage |
| Deployment | Cloud Run, Cloud Functions |
| External APIs | AgMarkNet (data.gov.in), Google Maps Platform |

---

## Compliance Guardrails

KisanMind enforces strict domain guardrails:

| Never | Always |
|-------|--------|
| Recommend specific pesticide brands/dosages | Cite data source and date |
| Provide loan or credit advice | Show confidence level |
| Guarantee crop yields or prices | Add weather forecast uncertainty |
| Override farmer's local knowledge | Log every recommendation with reasoning |

---

## Edge Case Handling

| Failure | Graceful Fallback |
|---------|------------------|
| Cloudy satellite imagery | Use last clear image + warn farmer |
| AgMarkNet API down | Serve cached prices from BigQuery with timestamp |
| Weather API failure | Fall back to Google Maps weather data |
| Speech recognition fails | Ask to repeat, offer DTMF fallback, or SMS mode |
| Location not recognized | Progressive narrowing: village → district → state |
| Unknown crop | Provide weather + mandi data, refer to local KVK |

---

## Impact Model

| Metric | Year 1 | Year 3 | Year 5 |
|--------|--------|--------|--------|
| Farmers reached | 100,000 | 2,000,000 | 20,000,000 |
| Avg price gain (mandi arbitrage) | ₹2,000/season | ₹3,000/season | ₹3,500/season |
| Total income improvement | ₹20 Cr | ₹600 Cr | ₹7,000 Cr |

**One farmer's math**: A Solan tomato farmer gains ₹34,000/year — ₹12,000/harvest from mandi arbitrage (Shimla vs Solan) + ₹10,000 saved from weather-timed harvesting. That's a **30% income increase**.

---

## Low-Connectivity Design

| Tier | Interface | Coverage |
|------|-----------|----------|
| Tier 1 | Full web dashboard (4G/5G) | ~35% of farmers |
| **Tier 2** | **Voice call (2G)** — primary mode | **~60% of farmers** |
| Tier 3 | SMS fallback | ~98% of farmers |
| Tier 4 | Missed call trigger | ~99% of farmers |
| Tier 5 | Proactive daily SMS push | 100% registered |

---

## Team

Built for the ET AI Hackathon 2026 — Phase II Prototype Submission.

## License

MIT
