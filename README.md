<p align="center">
  <img src="https://img.shields.io/badge/ET_AI_Hackathon-2026-22c55e?style=for-the-badge" alt="ET AI Hackathon 2026" />
  <img src="https://img.shields.io/badge/Problem_5-Domain_AI_Agents-38bdf8?style=for-the-badge" alt="Problem 5" />
  <img src="https://img.shields.io/badge/Status-Live-22c55e?style=for-the-badge" alt="Live" />
</p>

<h1 align="center">KisanMind (किसानमाइंड)</h1>
<h3 align="center">Satellite-to-Voice Agricultural Intelligence for 150M Indian Farmers</h3>

<p align="center">
  <b>Real Sentinel-2 NDVI</b> + <b>Live Mandi Prices</b> + <b>Weather Forecasts</b> + <b>Voice in 22 Languages</b>
</p>

<p align="center">
  <a href="https://kisanmind-409924770511.asia-south1.run.app/talk"><img src="https://img.shields.io/badge/Try_Voice_Call-22c55e?style=for-the-badge&logo=phone&logoColor=white" alt="Voice Call" /></a>
  <a href="https://kisanmind-409924770511.asia-south1.run.app/demo"><img src="https://img.shields.io/badge/One_Click_Demo-6366f1?style=for-the-badge&logo=play&logoColor=white" alt="Demo" /></a>
  <a href="https://kisanmind-409924770511.asia-south1.run.app"><img src="https://img.shields.io/badge/Dashboard-38bdf8?style=for-the-badge&logo=chart-bar&logoColor=white" alt="Dashboard" /></a>
</p>

---

## The Problem

India's **150 million farming households** make daily decisions worth **45 lakh crore annually** with:

- Zero satellite visibility on crop health
- No real-time mandi price comparison across markets
- Generic weather forecasts that don't translate to farming actions
- Advisory services only in English — useless for most farmers

**KisanMind** fuses satellite imagery + mandi prices + weather + voice into one system accessible through **a phone call in any Indian language**.

---

## Live Demo

| Interface | URL | For Whom |
|-----------|-----|----------|
| **Voice Call** | [/talk](https://kisanmind-409924770511.asia-south1.run.app/talk) | Farmers (tap one button, speak, hear advice) |
| **One-Click Demo** | [/demo](https://kisanmind-409924770511.asia-south1.run.app/demo) | Judges (shows all data sources + value points) |
| **Dashboard** | [/](https://kisanmind-409924770511.asia-south1.run.app) | Educated users (satellite map, charts, search) |
| **Mandi Prices** | [/mandi](https://kisanmind-409924770511.asia-south1.run.app/mandi) | Price comparison with net profit ranking |
| **Weather** | [/weather](https://kisanmind-409924770511.asia-south1.run.app/weather) | Crop-specific weather advisories |
| **API** | [/api/health](https://kisanmind-api-409924770511.asia-south1.run.app/api/health) | Backend health check |

---

## How It Works

A farmer calls or taps the app. They say:

> *"Main Solan mein tamatar uga raha hoon"*
> *(I'm growing tomatoes in Solan)*

KisanMind responds in **their language** with real data:

> *"Aapki GPS location se pata chala ki aap Solan mein hain. Kullu mandi mein tamatar ka bhav 2500 rupaye per quintal chal raha hai, jo yahan se 237 km door hai. Lekin transport nikaalke Solan ki apni mandi zyada faydemand hai — 2100 rupaye mein bhi aapko 1430 rupaye ka shudh munafa milega. Agle 2 din mein halki baarish hai, toh aaj harvest kar lein. Satellite se dekha — fasal mein thoda tanaav hai, sinchai kar dein."*

This required fusing **5 real data sources** in real-time:
1. **GPS** — Browser geolocation detected farmer's exact coordinates
2. **Sentinel-2** — Earth Engine computed NDVI for crop health
3. **AgMarkNet** — Government mandi prices from data.gov.in
4. **Google Maps** — Real driving distances to each mandi
5. **Open-Meteo** — 5-day hyperlocal weather forecast
6. **Gemini 3.1 Pro** — Synthesized everything into conversational Hindi advice

---

## Architecture

```
Farmer (Voice/Web/Phone) ──→ KisanMind Backend (FastAPI on Cloud Run)
                                    │
                    ┌───────────────┼───────────────┐───────────────┐
                    ▼               ▼               ▼               ▼
              Google Earth    AgMarkNet API    Open-Meteo      Google Maps
              Engine NDVI     (data.gov.in)   Weather API     Distance Matrix
              (Sentinel-2)    (Live Prices)   (5-day forecast) (Real driving km)
                    │               │               │               │
                    └───────────────┴───────────────┴───────────────┘
                                    │
                              Gemini 3.1 Pro ──→ Conversational Advisory
                                    │
                              Cloud TTS ──→ Voice Response (22 languages)
```

### Data Flow — Zero Fake Data

| Data | Source | Update Frequency |
|------|--------|------------------|
| Crop Health (NDVI/EVI/NDWI) | Sentinel-2 via Google Earth Engine (project: dmjone) | Weekly (satellite revisit) |
| Mandi Prices | AgMarkNet / data.gov.in + GCS cache | Daily (government data) |
| Driving Distances | Google Maps Distance Matrix API | Real-time |
| Weather Forecast | Open-Meteo API | Hourly |
| Advisory Generation | Gemini 3.1 Pro (with hallucination verification) | Per request |
| Voice I/O | Google Cloud STT V2 + TTS Neural2/Wavenet | Real-time |
| Translation | Google Cloud Translation API v3 | Real-time |

---

## Key Features

### Voice-First for Illiterate Farmers
- **ONE tap** starts a phone-like conversation
- Farmer speaks in any of **22 official Indian languages**
- GPS auto-detects location — farmer only needs to say their crop
- Advisory spoken back as natural conversation
- Call ends automatically with full summary displayed

### Real Satellite Intelligence
- Sentinel-2 imagery via Google Earth Engine
- Real NDVI, EVI, NDWI values for the farmer's exact GPS coordinates
- True-color and NDVI-overlay satellite thumbnail images
- Crop health classified as Healthy / Moderate / Stressed with trend

### Smart Mandi Price Arbitrage
- Live prices from AgMarkNet (data.gov.in) for 10+ crops
- Real Google Maps driving distance to every mandi
- Net profit = Price - Transport (3.5/km/qtl) - Commission (4%)
- Ranked by net profit — farmer sees which mandi actually pays most

### Anti-Hallucination Guardrails
- Gemini 3.1 Flash Lite fact-checks every advisory against source data
- If FAIL detected, regenerates with stricter prompt
- Never recommends pesticide brands/dosages — refers to KVK (1800-180-1551)
- Never claims farmer said something they didn't
- Every response cites data sources and freshness

### 2-Tier Persistent Cache
- L1: In-memory (instant, lost on restart)
- L2: Google Cloud Storage (persistent across deploys, ~200ms)
- Advisory: 15-min TTL | NDVI: 6-hour TTL | Mandi raw: 1-hour TTL
- Every response includes `data_age_minutes` and `freshness_note`
- Cached: **0.13s** | Fresh: **15-25s**

### Phone Call Support (Twilio-Ready)
- `POST /api/voice/incoming` — Twilio webhook for incoming calls
- `POST /api/voice/process` — Processes farmer's speech, returns TwiML advisory
- Multi-turn conversation support
- Connect any Twilio phone number and farmers can call

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **LLM** | Gemini 3.1 Pro (advisory) + Gemini 3.1 Flash Lite (intent/fact-check) |
| **Satellite** | Google Earth Engine + Sentinel-2 (project: dmjone) |
| **Voice** | Cloud Speech-to-Text V2 + Cloud TTS Wavenet/Neural2 |
| **Translation** | Cloud Translation API v3 (22 Indian languages) |
| **Frontend** | Next.js 16, TypeScript, Tailwind CSS, Recharts |
| **Backend** | FastAPI, Python 3.12, async/await |
| **Data** | AgMarkNet (data.gov.in), Open-Meteo, Google Maps Platform |
| **Cache** | In-memory L1 + Google Cloud Storage L2 |
| **Deployment** | Cloud Run (asia-south1), min-instances=1 |
| **Phone** | Twilio voice webhooks (TwiML) |

**Google Cloud Services Used**: Earth Engine, Cloud Run, Cloud STT V2, Cloud TTS, Cloud Translation, Cloud Storage, Secret Manager, Artifact Registry, Cloud Build

---

## Supported Languages (22 Scheduled Languages of India)

| Language | Native Script | TTS Voice | STT |
|----------|--------------|-----------|-----|
| Hindi | हिन्दी | Wavenet-D | V2 |
| English | English | Wavenet-D | V2 |
| Tamil | தமிழ் | Wavenet-D | V2 |
| Telugu | తెలుగు | Standard-A | V2 |
| Bengali | বাংলা | Wavenet-D | V2 |
| Marathi | मराठी | Wavenet-A | V2 |
| Gujarati | ગુજરાતી | Wavenet-A | V2 |
| Kannada | ಕನ್ನಡ | Wavenet-A | V2 |
| Malayalam | മലയാളം | Wavenet-A | V2 |
| Punjabi | ਪੰਜਾਬੀ | Wavenet-A | V2 |
| Odia | ଓଡ଼ିଆ | Standard-A | V2 |
| Assamese | অসমীয়া | Standard-A | V2 |
| Maithili | मैथिली | via Hindi | via Hindi |
| Sanskrit | संस्कृतम् | via Hindi | via Hindi |
| Nepali | नेपाली | via Hindi | via Hindi |
| Sindhi | سنڌي | via Hindi | via Hindi |
| Dogri | डोगरी | via Hindi | via Hindi |
| Kashmiri | كٲشُر | via Hindi | via Hindi |
| Konkani | कोंकणी | via Hindi | via Hindi |
| Santali | ᱥᱟᱱᱛᱟᱲᱤ | via Hindi | via Hindi |
| Bodo | বোড়ো | via Hindi | via Hindi |
| Manipuri | मणिपुरी | via Hindi | via Hindi |

Languages without native TTS are auto-translated to Hindi for speech synthesis.

---

## Quick Start

### Prerequisites
- Python 3.12+ | Node.js 22+ | Google Cloud SDK

### 1. Clone & Configure

```bash
git clone https://github.com/divyamohan1993/kisanmind.git
cd kisanmind
cp .env.example .env
# Fill in: GOOGLE_MAPS_API_KEY, AGMARKNET_API_KEY, GEMINI_API_KEY
```

### 2. Run Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8080
```

### 3. Run Frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

### 4. Deploy to Cloud Run

```bash
# Backend
cd backend && gcloud run deploy kisanmind-api --source . --region asia-south1

# Frontend
cd frontend && gcloud run deploy kisanmind --source . --region asia-south1
```

---

## Project Structure

```
kisanmind/
├── backend/
│   ├── main.py              # FastAPI — all endpoints, all real APIs
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── talk/page.tsx     # Voice-first farmer interface
│   │   ├── demo/page.tsx     # One-click judge demo
│   │   ├── page.tsx          # Dashboard with real data
│   │   ├── mandi/page.tsx    # Mandi price comparison
│   │   ├── weather/page.tsx  # Weather advisory
│   │   ├── api/advisory/     # API proxy route
│   │   ├── hooks/            # useGeolocation
│   │   └── components/       # SatelliteMap, Charts, VoiceInput, etc.
│   └── Dockerfile
├── agents/                   # ADK agent definitions (reference)
├── cloud_functions/          # Standalone function implementations
├── data/                     # CSV data, knowledge base, EE scripts
├── demo/                     # Demo script, sample queries
└── infrastructure/           # setup.sh, deploy.sh
```

---

## Compliance Guardrails

| Rule | Implementation |
|------|---------------|
| No pesticide brand/dosage recommendations | Gemini system prompt + fact-check |
| No loan/credit advice | Blocked in prompt |
| No yield guarantees | "Based on current data" disclaimer always added |
| Data source citation | Every response cites AgMarkNet, EE, Open-Meteo |
| Hallucination detection | Flash Lite verifies advisory against source data |
| KVK referral | Pest/disease queries directed to KVK helpline 1800-180-1551 |
| Audit trail | Every request logged with sources, timestamps, reasoning |

---

## Impact Model

| Metric | Conservative (Year 1) |
|--------|----------------------|
| Farmers reached | 100,000 |
| Avg mandi arbitrage gain | 2,000/season per farmer |
| Crop loss prevented | 5% (weather-timed harvesting) |
| Languages served | 22 (all scheduled) |

**One farmer's math**: Solan tomato farmer gains **34,000/year** — 12,000/harvest from mandi arbitrage + 10,000 saved from weather-timed harvesting = **30% income increase**.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/advisory` | Full advisory (mandi + weather + satellite + Gemini) |
| `POST` | `/api/ndvi` | Sentinel-2 NDVI/EVI/NDWI with thumbnail URLs |
| `POST` | `/api/tts` | Text-to-speech (22 languages, Wavenet voices) |
| `POST` | `/api/stt` | Speech-to-text (multipart audio or base64 JSON) |
| `POST` | `/api/extract-intent` | Gemini-powered intent extraction from speech |
| `POST` | `/api/voice/incoming` | Twilio webhook — incoming call handler |
| `POST` | `/api/voice/process` | Twilio webhook — process speech, return advisory |
| `GET` | `/api/health` | Service health + API status |

---

## Contact

Built for the **ET AI Hackathon 2026** — Phase II Prototype Submission

**Contact**: contact@dmj.one

---

<p align="center">
  <sub>100% real data. Zero fake. Every data point from a real API call.</sub>
</p>
