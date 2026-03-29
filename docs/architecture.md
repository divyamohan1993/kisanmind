# KisanMind System Architecture

> Comprehensive technical architecture of the KisanMind multi-agent agricultural advisory platform.

---

## Table of Contents

1. [High-Level System Overview](#1-high-level-system-overview)
2. [Agent Roles & Responsibilities](#2-agent-roles--responsibilities)
3. [Agent Communication & Orchestration](#3-agent-communication--orchestration)
4. [Tool Integrations & External APIs](#4-tool-integrations--external-apis)
5. [Data Flow: End-to-End Request Lifecycle](#5-data-flow-end-to-end-request-lifecycle)
6. [Voice Pipeline Architecture](#6-voice-pipeline-architecture)
7. [Caching Architecture](#7-caching-architecture)
8. [Error Handling & Resilience](#8-error-handling--resilience)
9. [Frontend-Backend Communication](#9-frontend-backend-communication)
10. [Deployment Architecture](#10-deployment-architecture)
11. [Security & Guardrails](#11-security--guardrails)

---

## 1. High-Level System Overview

KisanMind is a **voice-first, multi-agent agricultural advisory system** serving 150M Indian farmers across 22 languages. It fuses satellite imagery, mandi (market) prices, weather forecasts, and voice I/O into a single platform accessible via phone call or web app.

```mermaid
graph TB
    subgraph "User Interfaces"
        WEB["Web App<br/>(Next.js 16 + React 19)"]
        PHONE["Phone Call<br/>(Twilio Voice)"]
    end

    subgraph "Backend Layer"
        API["FastAPI Server<br/>(Port 8081)"]
        WS["WebSocket Server<br/>(/ws/chat)"]
        GLIVE["Gemini Live<br/>Session Manager"]
    end

    subgraph "Agent Layer (Google ADK)"
        BRAIN["KisanMind Brain<br/>(Orchestrator)"]
        SAT["SatDrishti<br/>(Satellite Eye)"]
        MANDI["MandiMitra<br/>(Market Friend)"]
        WEATHER["MausamGuru<br/>(Weather Guru)"]
        VOICE["VaaniSetu<br/>(Voice Bridge)"]
    end

    subgraph "External Data Sources"
        EE["Google Earth Engine<br/>(Sentinel-2)"]
        AGMARK["AgMarkNet<br/>(data.gov.in)"]
        GWEATHER["Google Weather API"]
        GMAPS["Google Maps APIs"]
        GSTT["Cloud Speech-to-Text V2"]
        GTTS["Cloud Text-to-Speech"]
        GEMINI["Gemini 3.x Models"]
    end

    subgraph "Storage & Cache"
        L1["L1: In-Memory Cache"]
        L2["L2: GCS Cache Bucket"]
        SATCACHE["Satellite Cache<br/>(Pre-computed NDVI)"]
    end

    WEB --> API
    PHONE --> API
    WEB --> WS
    WS --> GLIVE
    GLIVE --> GEMINI

    API --> BRAIN
    BRAIN --> SAT
    BRAIN --> MANDI
    BRAIN --> WEATHER
    API --> VOICE

    SAT --> EE
    MANDI --> AGMARK
    MANDI --> GMAPS
    WEATHER --> GWEATHER
    VOICE --> GSTT
    VOICE --> GTTS
    BRAIN --> GEMINI

    API --> L1
    API --> L2
    API --> SATCACHE

    style BRAIN fill:#4A90D9,stroke:#2C5F8A,color:#fff
    style SAT fill:#6BBF59,stroke:#3D8B2F,color:#fff
    style MANDI fill:#F5A623,stroke:#C47D10,color:#fff
    style WEATHER fill:#7B68EE,stroke:#5A4CB3,color:#fff
    style VOICE fill:#E74C3C,stroke:#B03A2E,color:#fff
```

**Tech Stack Summary:**

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16.2.1 + React 19 + Tailwind CSS |
| Backend | FastAPI + Uvicorn (Python 3.11+) |
| Agent Framework | Google ADK (Agent Development Kit) |
| LLM | Gemini 3.1 Pro (orchestrator) + Gemini 3 Flash (agents) |
| Satellite | Google Earth Engine (Sentinel-2, Sentinel-1, MODIS, SMAP) |
| Market Data | AgMarkNet / data.gov.in REST API |
| Weather | Google Maps Weather API |
| Voice | Cloud Speech V2 + Cloud TTS + Gemini Live |
| Phone | Twilio Voice + SMS |
| Cache | In-memory dict (L1) + GCS (L2) |
| Deployment | Docker multi-stage + Google Cloud Run |

---

## 2. Agent Roles & Responsibilities

The system uses a **hierarchical agent architecture** with one orchestrator and four specialist agents. Each agent has a distinct domain, its own Gemini model instance, and a set of tools.

```mermaid
graph TB
    subgraph "Orchestrator"
        BRAIN["KisanMind Brain<br/>━━━━━━━━━━━━━<br/>Model: Gemini 3.1 Pro<br/>Max Tokens: 4096<br/>Temperature: 0.3<br/>━━━━━━━━━━━━━<br/>Responsibilities:<br/>- Intent classification<br/>- Agent routing<br/>- Result synthesis<br/>- Guardrail enforcement<br/>- Audit logging"]
    end

    subgraph "Specialist Agents"
        SAT["SatDrishti (Satellite Eye)<br/>━━━━━━━━━━━━━<br/>Model: Gemini 3 Flash<br/>━━━━━━━━━━━━━<br/>- NDVI/EVI/NDWI analysis<br/>- Crop stress detection<br/>- Growth stage assessment<br/>- Temporal trend analysis<br/>- Regional benchmarking"]

        MANDI["MandiMitra (Market Friend)<br/>━━━━━━━━━━━━━<br/>Model: Gemini 3 Flash<br/>━━━━━━━━━━━━━<br/>- Live mandi price lookup<br/>- Transport cost calculation<br/>- Spoilage estimation<br/>- Net profit ranking<br/>- Price trend analysis"]

        WEATHER["MausamGuru (Weather Guru)<br/>━━━━━━━━━━━━━<br/>Model: Gemini 3 Flash<br/>━━━━━━━━━━━━━<br/>- 5-day forecast retrieval<br/>- Crop-weather rule engine<br/>- DO/DON'T/WARNING advisories<br/>- Frost & heat alerts<br/>- Spray window detection"]

        VOICE["VaaniSetu (Voice Bridge)<br/>━━━━━━━━━━━━━<br/>Model: Gemini 3 Flash<br/>━━━━━━━━━━━━━<br/>- Speech-to-Text (22 langs)<br/>- Intent + entity extraction<br/>- Text-to-Speech generation<br/>- Crop name normalization<br/>- Language detection"]
    end

    BRAIN -->|"crop_health_check"| SAT
    BRAIN -->|"where_to_sell"| MANDI
    BRAIN -->|"weather_advisory"| WEATHER
    BRAIN -->|"all intents<br/>(pre/post processing)"| VOICE

    style BRAIN fill:#4A90D9,stroke:#2C5F8A,color:#fff
    style SAT fill:#6BBF59,stroke:#3D8B2F,color:#fff
    style MANDI fill:#F5A623,stroke:#C47D10,color:#fff
    style WEATHER fill:#7B68EE,stroke:#5A4CB3,color:#fff
    style VOICE fill:#E74C3C,stroke:#B03A2E,color:#fff
```

### Agent Detail Cards

#### KisanMind Brain (Orchestrator)
- **File:** `agents/brain/orchestrator.py`
- **Config:** `agents/brain/config.yaml`
- **Model:** `gemini-3.1-pro-preview` (higher reasoning for synthesis)
- **Tool:** `_get_advisory_tool()` - wraps the entire advisory pipeline
- **System Prompt Personality:** Simple farmer-friendly language, rural analogies, empathetic tone
- **Guardrails:** No pesticide brands, no loan advice, no yield guarantees, mandatory disclaimers

#### SatDrishti (Satellite Eye)
- **File:** `agents/sat_drishti/agent.py`
- **Supporting:** `earth_engine.py`, `ndvi_interpreter.py`
- **Tool:** `analyze_crop_health(lat, lon, crop, region, benchmarks)`
- **Data Source:** Sentinel-2 via Google Earth Engine
- **NDVI Categories:** bare_soil (0-0.1), stressed (0.1-0.3), moderate (0.3-0.5), healthy (0.5-0.7), peak (0.7-0.9)

#### MandiMitra (Market Friend)
- **File:** `agents/mandi_mitra/agent.py`
- **Supporting:** `agmarknet_client.py`, `profit_optimizer.py`
- **Tools:** `get_mandi_recommendation()`, `get_crop_prices()`
- **Data Sources:** AgMarkNet API + Google Maps Distance Matrix
- **Profit Formula:** `Net = Modal Price - Transport (₹3.50/km/qtl) - Commission (4%) - Spoilage`

#### MausamGuru (Weather Guru)
- **File:** `agents/mausam_guru/agent.py`
- **Supporting:** `openweather_client.py`, `crop_weather_rules.py`
- **Tool:** `get_weather_advisory(lat, lon, crop, growth_stage)`
- **Advisory Types:** DO, DON'T, WARNING (with HIGH/MEDIUM/LOW urgency)
- **Supported Crops:** tomato, wheat, rice, apple, coffee (with per-stage rules)

#### VaaniSetu (Voice Bridge)
- **File:** `agents/vaani_setu/agent.py`
- **Supporting:** `stt_handler.py`, `tts_handler.py`, `intent_extractor.py`
- **Tools:** `process_voice_input()`, `process_text_input()`, `generate_voice_response()`, `get_routing_target()`
- **Crop Normalization:** 80+ mappings (Hindi/Tamil/Telugu regional names to English)
- **Voice Rules:** Simple language, local units (bigha/quintal/rupaye), 3-5 sentences max, address as "kisan bhai/behan"

---

## 3. Agent Communication & Orchestration

### Intent-Based Routing

The orchestrator classifies farmer queries into intents and routes to the appropriate specialist agents. For `full_advisory`, all three data agents execute **in parallel** using `asyncio.gather`.

```mermaid
flowchart TD
    INPUT["Farmer Query<br/>(Voice or Text)"]
    CLASSIFY["Intent Classification<br/>(Keyword + Gemini)"]

    INPUT --> CLASSIFY

    CLASSIFY -->|"crop_health_check"| R1["Route: Sequential"]
    CLASSIFY -->|"where_to_sell"| R2["Route: Sequential"]
    CLASSIFY -->|"weather_advisory"| R3["Route: Sequential"]
    CLASSIFY -->|"full_advisory<br/>(default)"| R4["Route: Parallel"]

    R1 --> SAT["SatDrishti Only"]
    R2 --> MANDI["MandiMitra Only"]
    R3 --> WEATHER["MausamGuru Only"]

    R4 --> PAR{"asyncio.gather()"}
    PAR --> SAT2["SatDrishti"]
    PAR --> MANDI2["MandiMitra"]
    PAR --> WEATHER2["MausamGuru"]

    SAT --> SYNTH["Gemini Synthesis<br/>(3.1 Pro)"]
    MANDI --> SYNTH
    WEATHER --> SYNTH
    SAT2 --> MERGE["Merge Results"]
    MANDI2 --> MERGE
    WEATHER2 --> MERGE
    MERGE --> SYNTH

    SYNTH --> GUARD["Guardrail Post-Check"]
    GUARD --> AUDIT["Audit Log<br/>(session_id, timestamp,<br/>intent, sources)"]
    AUDIT --> RESPONSE["Final Advisory"]

    style PAR fill:#FFD700,stroke:#B8860B,color:#000
    style SYNTH fill:#4A90D9,stroke:#2C5F8A,color:#fff
    style GUARD fill:#E74C3C,stroke:#B03A2E,color:#fff
```

### Parallel Execution Model

```mermaid
sequenceDiagram
    participant F as Farmer
    participant BE as FastAPI Backend
    participant BR as Brain Orchestrator
    participant SD as SatDrishti
    participant MM as MandiMitra
    participant MG as MausamGuru
    participant GEM as Gemini 3.1 Pro

    F->>BE: POST /api/advisory
    BE->>BR: run_advisory(query, lat, lon, crop)
    BR->>BR: classify_intent(query) → full_advisory

    par Parallel Agent Execution
        BR->>SD: analyze_crop_health(lat, lon, crop)
        SD-->>BR: {ndvi: 0.62, health: "healthy", trend: "improving"}
    and
        BR->>MM: get_mandi_recommendation(crop, lat, lon, state, qty)
        MM-->>BR: {best_mandi: "Solan", net_profit: "₹2,847/qtl"}
    and
        BR->>MG: get_weather_advisory(lat, lon, crop, stage)
        MG-->>BR: {forecast: [...], advisories: [{type: "DO", msg: "irrigate"}]}
    end

    BR->>GEM: Synthesize(satellite + market + weather results)
    GEM-->>BR: Unified farmer-friendly advisory
    BR->>BR: apply_guardrails()
    BR->>BR: audit_log()
    BR-->>BE: Complete advisory JSON
    BE-->>F: {advisory, sources, confidence, disclaimer}
```

### Agent Registration (config.yaml)

```yaml
sub_agents:
  sat_drishti:
    triggers: ["crop_health_check", "full_advisory"]
    capabilities: ["ndvi_analysis", "crop_stress_detection", "growth_stage_assessment"]

  mandi_mitra:
    triggers: ["where_to_sell", "full_advisory"]
    capabilities: ["mandi_price_lookup", "profit_calculation", "transport_route_optimization"]

  mausam_guru:
    triggers: ["weather_advisory", "full_advisory"]
    capabilities: ["weather_forecast", "frost_alert", "irrigation_scheduling", "spray_window_detection"]

  vaani_setu:
    triggers: ["all"]
    capabilities: ["speech_to_text", "text_to_speech", "language_translation"]
```

---

## 4. Tool Integrations & External APIs

Each agent wraps one or more external APIs through dedicated tool functions. The backend also directly calls some APIs for the REST/WebSocket paths.

```mermaid
graph LR
    subgraph "SatDrishti Tools"
        ST1["analyze_crop_health()"]
    end

    subgraph "MandiMitra Tools"
        MT1["get_mandi_recommendation()"]
        MT2["get_crop_prices()"]
    end

    subgraph "MausamGuru Tools"
        WT1["get_weather_advisory()"]
    end

    subgraph "VaaniSetu Tools"
        VT1["process_voice_input()"]
        VT2["process_text_input()"]
        VT3["generate_voice_response()"]
        VT4["get_routing_target()"]
    end

    subgraph "Backend Direct Calls"
        BT1["reverse_geocode()"]
        BT2["fetch_mandi_prices()"]
        BT3["fetch_weather_data()"]
        BT4["compute_ndvi_live()"]
        BT5["find_nearest_kvk()"]
    end

    subgraph "External APIs"
        EE["Google Earth Engine<br/>Sentinel-2 Imagery"]
        AG["AgMarkNet API<br/>data.gov.in"]
        GW["Google Weather API<br/>weather.googleapis.com"]
        GM["Google Maps<br/>Geocoding + Distance Matrix"]
        STT["Cloud Speech V2<br/>gRPC"]
        TTS["Cloud TTS<br/>gRPC"]
        TR["Cloud Translation V2"]
        GEN["Gemini API<br/>generativelanguage.googleapis.com"]
        TWI["Twilio Voice"]
    end

    ST1 --> EE
    MT1 --> AG
    MT1 --> GM
    MT2 --> AG
    WT1 --> GW
    VT1 --> STT
    VT1 --> GEN
    VT3 --> TTS
    BT1 --> GM
    BT2 --> AG
    BT3 --> GW
    BT4 --> EE
    BT5 --> GM

    style EE fill:#6BBF59,stroke:#3D8B2F,color:#fff
    style AG fill:#F5A623,stroke:#C47D10,color:#fff
    style GW fill:#7B68EE,stroke:#5A4CB3,color:#fff
    style GEN fill:#4A90D9,stroke:#2C5F8A,color:#fff
```

### API Integration Details

| API | Endpoint | Auth | Agent/Module | Data Returned |
|-----|----------|------|-------------|---------------|
| **Google Earth Engine** | Python `ee` library | Service Account | SatDrishti / `earth_engine.py` | NDVI, EVI, NDWI, thumbnail URL |
| **AgMarkNet** | `api.data.gov.in/resource/9ef84268-...` | API Key | MandiMitra / `agmarknet_client.py` | Commodity prices by mandi |
| **Google Weather** | `weather.googleapis.com/v1/forecast/hours:lookup` | API Key | MausamGuru / `openweather_client.py` | 120-hour hourly forecast |
| **Google Maps Geocoding** | `maps.googleapis.com/maps/api/geocode/json` | API Key | Backend / `main.py` | Lat/lon from address |
| **Google Maps Distance** | `maps.googleapis.com/maps/api/distancematrix/json` | API Key | MandiMitra / `profit_optimizer.py` | Travel distance & time |
| **Cloud Speech V2** | gRPC service | Service Account | VaaniSetu / `stt_handler.py` | Transcript + language |
| **Cloud TTS** | gRPC service | Service Account | VaaniSetu / `tts_handler.py` | Audio bytes (WAV/MP3) |
| **Cloud Translation** | gRPC service | Service Account | Backend / `main.py` | Translated text |
| **Gemini API** | `generativelanguage.googleapis.com` | API Key | All agents + Backend | Generated text/audio |
| **Gemini Live** | WebSocket | API Key | Backend / `gemini_live.py` | Streaming audio + text |
| **Twilio Voice** | REST API | Account SID + Token | Backend / `main.py` | Phone call management |

### Cloud Functions (Serverless)

Five Google Cloud Functions provide standalone API wrappers:

```mermaid
graph TB
    subgraph "cloud_functions/"
        CF1["compute_ndvi/<br/>main.py"]
        CF2["fetch_mandi_prices/<br/>main.py"]
        CF3["fetch_weather/<br/>main.py"]
        CF4["geocode/<br/>main.py"]
        CF5["calculate_profit/<br/>main.py"]
    end

    CF1 --> EE["Earth Engine"]
    CF2 --> AG["AgMarkNet API"]
    CF3 --> GW["Google Weather API"]
    CF4 --> GM["Google Maps Geocoding"]
    CF5 -.->|"local computation"| CF5

    style CF1 fill:#6BBF59,stroke:#3D8B2F,color:#fff
    style CF2 fill:#F5A623,stroke:#C47D10,color:#fff
    style CF3 fill:#7B68EE,stroke:#5A4CB3,color:#fff
    style CF4 fill:#4A90D9,stroke:#2C5F8A,color:#fff
    style CF5 fill:#95A5A6,stroke:#7F8C8D,color:#fff
```

---

## 5. Data Flow: End-to-End Request Lifecycle

### Full Advisory Request (REST)

```mermaid
flowchart TD
    A["Farmer sends query<br/>(text + GPS + language)"] --> B["POST /api/advisory"]
    B --> C{"L1 Cache Hit?"}
    C -->|"Yes (< 15 min)"| Z["Return cached advisory"]
    C -->|"No"| D{"L2 GCS Cache Hit?"}
    D -->|"Yes"| Z
    D -->|"No"| E["Start parallel tasks"]

    E --> F1["Task 1: Reverse Geocode<br/>(lat,lon → district, state)"]
    E --> F2["Task 2: Satellite Lookup<br/>(pre-computed NDVI cache)"]
    E --> F3["Task 3: Weather Fetch<br/>(Google Weather API)"]
    E --> F4["Task 4: Mandi Prices<br/>(AgMarkNet API)"]
    E --> F5["Task 5: Nearest KVK<br/>(Google Maps)"]

    F1 --> G["Merge all data"]
    F2 --> G
    F3 --> G
    F4 --> G
    F5 --> G

    G --> H["Cross-validate data sources"]
    H --> I["Compute confidence scores"]
    I --> J["Build Gemini synthesis prompt"]
    J --> K["Gemini 3 Flash generates advisory<br/>(in farmer's language)"]
    K --> L["Apply guardrail post-check"]
    L --> M["Background: hallucination verification"]
    L --> N["Cache result (L1 + L2)"]
    N --> Z2["Return advisory JSON"]

    F2 -.->|"Cache miss?"| F2B["Live Earth Engine query<br/>(8s timeout)"]
    F2B -.-> G

    style A fill:#E8F5E9,stroke:#2E7D32
    style Z fill:#E3F2FD,stroke:#1565C0
    style Z2 fill:#E3F2FD,stroke:#1565C0
    style K fill:#4A90D9,stroke:#2C5F8A,color:#fff
```

### Advisory Response Structure

```json
{
  "advisory": "Farmer-friendly text in their language...",
  "satellite": {
    "ndvi": 0.62, "health": "healthy", "trend": "improving",
    "confidence": "HIGH", "image_date": "2026-03-27"
  },
  "weather": {
    "forecast_days": [...],
    "advisories": [{"type": "DO", "msg": "irrigate", "urgency": "HIGH"}]
  },
  "mandi": {
    "best_mandi": "Solan", "net_profit_per_quintal": 2847,
    "alternatives": [...]
  },
  "kvk": {"name": "KVK Solan", "distance_km": 12, "phone": "..."},
  "confidence": {"overall": 0.82, "satellite": 0.9, "weather": 0.8, "price": 0.75},
  "sources": ["Sentinel-2 (2026-03-27)", "AgMarkNet", "Google Weather API"],
  "disclaimer": "Advisory is indicative. Verify with local conditions."
}
```

---

## 6. Voice Pipeline Architecture

### Web Voice Call Flow

```mermaid
sequenceDiagram
    participant F as Farmer (Browser)
    participant FE as Next.js Frontend
    participant BE as FastAPI Backend
    participant GL as Gemini Live Session
    participant GEM as Gemini 3.1 Flash Live

    Note over F,GEM: Call Initiation
    F->>FE: Click "Call KisanMind" + select language
    FE->>FE: Get GPS coordinates (useGeolocation)
    FE->>BE: WebSocket /ws/chat
    FE->>BE: {type: "config", language: "hi", lat: 30.9, lon: 77.1}

    BE->>GL: create_session(language, lat, lon)
    GL->>GEM: Connect WebSocket (Gemini Live API)
    GEM-->>GL: Session established
    GL-->>BE: session_id
    BE-->>FE: {type: "session_started"}

    Note over F,GEM: Conversation Loop
    loop Until call_complete
        F->>FE: Speak into microphone
        FE->>FE: Web Speech API → transcript
        FE->>BE: {type: "text", text: "tamatar ki fasal..."}
        BE->>GL: send_text(text)
        GL->>GEM: Forward to Gemini

        alt Gemini needs data
            GEM->>GL: tool_call: fetch_farm_data(crop, ...)
            GL->>BE: on_tool_call callback
            BE->>BE: Fetch satellite + mandi + weather
            BE-->>GL: tool_response(data)
            GL-->>GEM: Function result
        end

        GEM-->>GL: Audio response (PCM 24kHz)
        GL-->>BE: on_audio callback
        BE-->>FE: {type: "audio", data: "<base64>"}
        FE->>F: Play audio response

        GEM-->>GL: Transcript
        GL-->>BE: on_transcript callback
        BE-->>FE: {type: "transcript", speaker: "kisanmind", text: "..."}
    end

    Note over F,GEM: Call Summary
    FE->>BE: POST /api/summarize
    BE->>GEM: Summarize conversation
    BE-->>FE: {summary: "...", action_items: [...]}
    FE->>F: Display call summary card
```

### Twilio Phone Call Flow

```mermaid
flowchart LR
    PHONE["Farmer dials<br/>Twilio Number"] --> TW["Twilio Webhook<br/>POST /api/voice/incoming"]
    TW --> TWIML["Generate TwiML<br/>(greeting + gather)"]
    TWIML --> RECORD["Record farmer speech"]
    RECORD --> STT["Cloud Speech V2<br/>(auto language detect)"]
    STT --> INTENT["Gemini Intent Extraction"]
    INTENT --> ADVISORY["Run Advisory Pipeline"]
    ADVISORY --> TTS["Cloud TTS<br/>(farmer's language)"]
    TTS --> PLAY["Play audio to farmer"]
    PLAY --> RECORD
```

### Language Support Matrix

| Language | Code | STT | TTS Voice | Gemini Native |
|----------|------|-----|-----------|---------------|
| Hindi | hi-IN | V2 Native | Wavenet-D | Yes |
| English | en-IN | V2 Native | Wavenet-D | Yes |
| Tamil | ta-IN | V2 Native | Wavenet-D | Yes |
| Telugu | te-IN | V2 Native | Standard-A | Yes |
| Bengali | bn-IN | V2 Native | Wavenet-D | Yes |
| Marathi | mr-IN | V2 Native | Wavenet-A | Yes |
| Gujarati | gu-IN | V2 Native | Wavenet-A | Yes |
| Kannada | kn-IN | V2 Native | Wavenet-A | Yes |
| Malayalam | ml-IN | V2 Native | Wavenet-A | Yes |
| Punjabi | pa-IN | V2 Native | Wavenet-A | Yes |
| Odia | or-IN | V2 Native | Standard-A | Via Hindi fallback |
| Assamese | as-IN | V2 Native | Via Hindi TTS | Via Hindi fallback |
| + 10 more | - | Via Hindi | Via Hindi TTS | Via Hindi fallback |

---

## 7. Caching Architecture

The system implements a **two-tier caching strategy** optimized for rural connectivity (where latency matters most) plus a specialized satellite data cache.

```mermaid
graph TD
    REQ["Incoming Request"] --> L1{"L1: In-Memory Dict"}
    L1 -->|"HIT"| RES1["Return (0.13s)"]
    L1 -->|"MISS"| L2{"L2: GCS Bucket<br/>(kisanmind-cache)"}
    L2 -->|"HIT"| PROMOTE["Promote to L1"]
    PROMOTE --> RES2["Return (~200ms)"]
    L2 -->|"MISS"| LIVE["Live API Calls<br/>(2-8 seconds)"]
    LIVE --> STORE["Store in L1 + L2"]
    STORE --> RES3["Return"]

    subgraph "TTL Configuration"
        TTL1["Advisory: 15 min<br/>(prices shift intraday)"]
        TTL2["NDVI: 6 hours<br/>(satellite updates weekly)"]
        TTL3["Mandi Raw: 1 hour<br/>(daily auction cycles)"]
        TTL4["KVK Data: 30 days<br/>(semi-static)"]
    end

    subgraph "Satellite Cache (Special)"
        SC["Pre-computed Grid<br/>(India 0.1° spacing)<br/>~96,000 points"]
        SC --> GRID{"Grid Lookup<br/>(nearest point)"}
        GRID -->|"> 5km from exact"| REFINE["Background<br/>Live EE Refinement"]
        GRID -->|"< 5km"| EXACT["Return cached"]
        REFINE --> GCS2["Persist to GCS<br/>(exact location)"]
    end

    style L1 fill:#E8F5E9,stroke:#2E7D32
    style L2 fill:#E3F2FD,stroke:#1565C0
    style LIVE fill:#FFF3E0,stroke:#E65100
```

### Cache Key Strategy

| Data Type | Key Pattern | Example |
|-----------|------------|---------|
| Advisory | `adv:{lat:.2f}:{lon:.2f}:{crop}:{lang}` | `adv:30.91:77.10:tomato:hi` |
| NDVI | `ndvi:{lat:.4f}:{lon:.4f}` | `ndvi:30.9100:77.0969` |
| Mandi Prices | `mandi:{commodity}:{state}` | `mandi:tomato:himachal_pradesh` |
| Weather | `wx:{lat:.2f}:{lon:.2f}` | `wx:30.91:77.10` |
| KVK | `kvk:{lat:.1f}:{lon:.1f}` | `kvk:30.9:77.1` |
| Geocode | `geo:{lat:.4f}:{lon:.4f}` | `geo:30.9100:77.0969` |

---

## 8. Error Handling & Resilience

### Error Handling Strategy

The system follows a **graceful degradation** philosophy: every external dependency has a fallback path, and no single API failure prevents an advisory from being generated.

```mermaid
flowchart TD
    subgraph "Satellite Data"
        S1["Pre-computed Cache"] -->|"miss"| S2["Live Earth Engine<br/>(8s timeout)"]
        S2 -->|"timeout/error"| S3["Neighbor Grid Point<br/>(within 10km)"]
        S3 -->|"miss"| S4["District Average"]
        S4 -->|"miss"| S5["Advisory without<br/>satellite data<br/>(confidence: LOW)"]
    end

    subgraph "Mandi Prices"
        M1["GCS Cached Prices"] -->|"stale/miss"| M2["AgMarkNet API<br/>(5s timeout)"]
        M2 -->|"error"| M3["AgMarkNet Alternate<br/>Endpoint"]
        M3 -->|"error"| M4["Hardcoded<br/>Commodity List"]
        M4 -->|"still empty"| M5["Advisory without<br/>price data"]
    end

    subgraph "Weather Data"
        W1["Google Weather API<br/>(5s timeout)"] -->|"error"| W2["Cached Weather<br/>(if < 3hrs old)"]
        W2 -->|"miss"| W3["Advisory without<br/>weather data"]
    end

    subgraph "Voice Pipeline"
        V1["Speech-to-Text"] -->|"confidence < 0.6"| V2["Retry prompt:<br/>'Please repeat'"]
        V2 -->|"2nd failure"| V3["Fall back to<br/>text input"]
        V4["Text-to-Speech"] -->|"error"| V5["Return text-only<br/>response"]
    end

    subgraph "Gemini LLM"
        G1["Gemini API Call"] -->|"rate limit/error"| G2["Retry with<br/>exponential backoff"]
        G2 -->|"3 failures"| G3["Template-based<br/>advisory fallback"]
    end

    style S5 fill:#FFF3E0,stroke:#E65100
    style M5 fill:#FFF3E0,stroke:#E65100
    style W3 fill:#FFF3E0,stroke:#E65100
    style V3 fill:#FFF3E0,stroke:#E65100
    style G3 fill:#FFF3E0,stroke:#E65100
```

### Error Handling Patterns by Layer

```mermaid
graph TB
    subgraph "Pattern 1: Timeout Protection"
        TP1["asyncio.wait_for(task, timeout=8.0)"]
        TP2["except asyncio.TimeoutError"]
        TP3["log.warning + proceed without data"]
        TP1 --> TP2 --> TP3
    end

    subgraph "Pattern 2: Credential Fallback Chain"
        CF1["ENV var JSON string"]
        CF2["File path from ENV"]
        CF3["Application Default Credentials"]
        CF1 -->|"fail"| CF2 -->|"fail"| CF3
    end

    subgraph "Pattern 3: API Retry with Variants"
        AR1["Primary endpoint"]
        AR2["Alternate endpoint/params"]
        AR3["Cached fallback"]
        AR4["Hardcoded defaults"]
        AR1 -->|"fail"| AR2 -->|"fail"| AR3 -->|"fail"| AR4
    end

    subgraph "Pattern 4: Error as Data"
        ED1["Agent tool raises exception"]
        ED2["Return {error: str, advice: 'fallback text'}"]
        ED3["Orchestrator handles gracefully"]
        ED1 --> ED2 --> ED3
    end

    subgraph "Pattern 5: Confidence Gating"
        CG1["Score each data source (0-1)"]
        CG2{"Confidence Level"}
        CG3["HIGH → Clear directive"]
        CG4["MEDIUM → Hedged language"]
        CG5["LOW → Skip or 'consult KVK'"]
        CG1 --> CG2
        CG2 --> CG3
        CG2 --> CG4
        CG2 --> CG5
    end
```

### Confidence Scoring System

Every advisory includes transparency about data quality:

```
Confidence Score = weighted_average(satellite, weather, price)

satellite_score:
  - Base: 0.5
  - Bonus: +0.3 if image ≤ 3 days old
  - Bonus: +0.1 if image ≤ 7 days old
  - Penalty: -0.2 if image > 7 days old

weather_score: 0.7-0.8 (5-day forecast inherent uncertainty)

price_score:
  - HIGH (0.8): ≥ 5 data points, < 24 hrs old
  - MEDIUM (0.6): 2-4 data points
  - LOW (0.4): ≤ 1 data point or stale

overall_confidence = (sat * 0.35 + weather * 0.30 + price * 0.35)
```

### Cross-Validation Logic

The backend cross-validates data sources for consistency (`cross_validate_data_sources()`):

- **Weather vs Satellite:** If satellite shows stress but weather shows adequate rain → CAVEAT
- **Price vs Weather:** If heavy rain forecast and prices rising → WARNING (supply disruption)
- **NDVI vs Growth Stage:** If NDVI below benchmark for current stage → CONFLICT alert

---

## 9. Frontend-Backend Communication

```mermaid
graph LR
    subgraph "Frontend (Next.js, Port 8080)"
        UI["React UI<br/>(page.tsx)"]
        PROXY["API Route Proxy<br/>(api/advisory/route.ts)"]
        WSC["WebSocket Client"]
    end

    subgraph "Backend (FastAPI, Port 8081)"
        REST["REST Endpoints<br/>(14 routes)"]
        WSS["WebSocket Server<br/>(/ws/chat)"]
    end

    UI -->|"fetch()"| PROXY
    PROXY -->|"POST"| REST
    UI -->|"new WebSocket()"| WSC
    WSC -->|"ws://localhost:8081"| WSS

    subgraph "REST Endpoints"
        E1["POST /api/advisory"]
        E2["POST /api/chat"]
        E3["POST /api/tts"]
        E4["POST /api/stt"]
        E5["POST /api/extract-intent"]
        E6["POST /api/translate"]
        E7["POST /api/summarize"]
        E8["POST /api/geocode-name"]
        E9["POST /api/ndvi"]
        E10["POST /api/voice/incoming"]
        E11["GET /api/health"]
        E12["GET /api/beep"]
    end

    REST --- E1
    REST --- E2
    REST --- E3
    REST --- E4
    REST --- E5
    REST --- E6
    REST --- E7
    REST --- E8
    REST --- E9
    REST --- E10
    REST --- E11
    REST --- E12
```

### WebSocket Message Protocol

```
Client → Server:
  {"type": "config", "language": "hi", "latitude": 30.9, "longitude": 77.1}
  {"type": "text", "text": "tamatar ki fasal kaisi hai?"}
  {"type": "audio", "data": "<base64 PCM 16kHz mono>"}
  {"type": "end"}

Server → Client:
  {"type": "session_started", "session_id": "uuid"}
  {"type": "audio", "data": "<base64 PCM 24kHz>"}
  {"type": "transcript", "speaker": "farmer|kisanmind", "text": "..."}
  {"type": "status", "status": "fetching_data|ready"}
  {"type": "turn_complete"}
  {"type": "error", "message": "..."}
```

### Frontend Component Architecture

```mermaid
graph TD
    PAGE["page.tsx<br/>(Main Voice Interface)"]

    PAGE --> VC["VoiceInput.tsx<br/>Mic + Text Input"]
    PAGE --> CB["ConversationBubble.tsx<br/>Chat Messages"]
    PAGE --> AC["AdvisoryCard.tsx<br/>Structured Advisory"]
    PAGE --> WT["WeatherTimeline.tsx<br/>5-Day Forecast"]
    PAGE --> NC["NDVIChart.tsx<br/>Crop Health Chart"]
    PAGE --> MC["MandiComparison.tsx<br/>Market Rankings"]
    PAGE --> SM["SatelliteMap.tsx<br/>Satellite Imagery"]

    PAGE --> HOOK["useGeolocation.ts<br/>GPS Hook"]

    style PAGE fill:#4A90D9,stroke:#2C5F8A,color:#fff
```

---

## 10. Deployment Architecture

```mermaid
graph TB
    subgraph "Google Cloud Platform (asia-south1)"
        subgraph "Cloud Run"
            CR["KisanMind Container<br/>━━━━━━━━━━━━━<br/>Memory: 2Gi<br/>CPU: 2 vCPU<br/>Timeout: 300s<br/>Min Instances: 1"]
        end

        subgraph "Inside Container"
            ENT["entrypoint.sh"]
            ENT --> BK["Backend (Uvicorn)<br/>Port 8081"]
            ENT --> NK["Frontend (Next.js)<br/>Port 8080"]
            ENT -.->|"health check<br/>(30s timeout)"| BK
        end

        subgraph "Google Cloud Services"
            GCS["Cloud Storage<br/>(kisanmind-cache)"]
            GSTT2["Speech-to-Text V2"]
            GTTS2["Text-to-Speech"]
            GTR["Cloud Translation"]
            GEE["Earth Engine"]
            GSM["Secret Manager"]
        end

        subgraph "Cloud Functions"
            CF["5 Serverless Functions<br/>(compute_ndvi, fetch_mandi,<br/>fetch_weather, geocode,<br/>calculate_profit)"]
        end
    end

    subgraph "External Services"
        TWI2["Twilio<br/>(Voice/SMS)"]
        AGMARK2["AgMarkNet<br/>(data.gov.in)"]
    end

    INTERNET["Internet / Farmer"] --> CR
    CR --> GCS
    CR --> GSTT2
    CR --> GTTS2
    CR --> GTR
    CR --> GEE
    CR --> GSM
    CR --> CF
    CR --> TWI2
    CR --> AGMARK2

    style CR fill:#4A90D9,stroke:#2C5F8A,color:#fff
```

### Docker Build (Multi-Stage)

```
Stage 1: Frontend Build (Node.js 20)
├── npm install
└── npm run build → .next/ static output

Stage 2: Production Image (Python 3.11)
├── Install system deps + Node.js 20
├── pip install requirements.txt
├── Copy: backend/, agents/, cloud_functions/, data/, scripts/
├── Copy: .next/ from Stage 1
├── ENV: PORT=8080, PYTHONUNBUFFERED=1
└── CMD: infrastructure/entrypoint.sh
```

### Startup Sequence

```
1. entrypoint.sh starts
2. Launch Uvicorn (backend, port 8081) in background
3. Wait for /api/health to return 200 (30s timeout)
4. Launch Next.js server (frontend, port 8080)
5. Wait for either process to exit
```

---

## 11. Security & Guardrails

### Content Safety Guardrails

```mermaid
graph TD
    INPUT["Farmer Query"] --> PRE["Pre-Check<br/>(Keyword Detection)"]

    PRE -->|"pesticide brand detected"| BLOCK1["BLOCKED: Redirect to KVK<br/>'Contact your nearest KVK<br/>for pesticide advice'"]

    PRE -->|"loan/credit detected"| BLOCK2["BLOCKED: Redirect to NABARD<br/>'Contact your bank for<br/>financial advice'"]

    PRE -->|"clean"| PROCESS["Process Advisory"]

    PROCESS --> POST["Post-Generation Check"]
    POST -->|"yield guarantee detected"| SOFTEN["Soften to 'indicative estimate'"]
    POST -->|"missing disclaimer"| ADD["Add standard disclaimer"]
    POST -->|"clean"| DELIVER["Deliver to Farmer"]

    SOFTEN --> DELIVER
    ADD --> DELIVER

    DELIVER --> BG["Background:<br/>Hallucination Verification<br/>(async Gemini check)"]

    style BLOCK1 fill:#E74C3C,stroke:#B03A2E,color:#fff
    style BLOCK2 fill:#E74C3C,stroke:#B03A2E,color:#fff
```

### Guardrail Rules

| Rule | Enforcement | Redirect |
|------|-------------|----------|
| No pesticide brand names | Keyword filter + LLM system prompt | Local KVK (1800-180-1551) |
| No loan/credit/investment advice | Keyword filter + LLM system prompt | Bank / NABARD |
| No yield guarantees | Post-generation check | Marked as "indicative" |
| Data source citations | Mandatory in synthesis prompt | Always included |
| Standard disclaimer | Template appended | Every advisory |
| Audit logging | Every session logged | UUID-tracked |
| Confidence transparency | Computed per data source | Shown to farmer |

### API Key Management

```
Credential Loading Priority:
1. Environment variable (JSON string)    ← Preferred in Cloud Run
2. Environment variable (file path)      ← Local development
3. Application Default Credentials       ← GCE/Cloud Run auto-detect
```

All API keys are loaded from environment variables (`.env` file locally, Secret Manager in production). No secrets are hardcoded in application code.

---

## Appendix: File Map

```
kisanmind/
├── backend/
│   ├── main.py                    # FastAPI server (3400+ lines, all endpoints)
│   ├── gemini_live.py             # Gemini Live WebSocket session manager
│   ├── satellite_cache.py         # Two-tier NDVI cache (L1 + L2)
│   ├── requirements.txt           # Python dependencies
│   └── Dockerfile
├── frontend/
│   ├── app/
│   │   ├── page.tsx               # Main voice-first UI (23KB)
│   │   ├── layout.tsx             # Root layout
│   │   ├── globals.css            # Tailwind styles
│   │   ├── components/
│   │   │   ├── AdvisoryCard.tsx
│   │   │   ├── ConversationBubble.tsx
│   │   │   ├── MandiComparison.tsx
│   │   │   ├── NDVIChart.tsx
│   │   │   ├── SatelliteMap.tsx
│   │   │   ├── VoiceInput.tsx
│   │   │   └── WeatherTimeline.tsx
│   │   ├── hooks/useGeolocation.ts
│   │   └── api/advisory/route.ts  # Backend proxy
│   ├── package.json
│   └── Dockerfile
├── agents/
│   ├── brain/
│   │   ├── orchestrator.py        # Root orchestrator
│   │   └── config.yaml            # Agent routing config
│   ├── sat_drishti/
│   │   ├── agent.py               # Satellite analysis agent
│   │   ├── earth_engine.py        # Earth Engine integration
│   │   └── ndvi_interpreter.py    # NDVI classification
│   ├── mandi_mitra/
│   │   ├── agent.py               # Market price agent
│   │   ├── agmarknet_client.py    # AgMarkNet API client
│   │   └── profit_optimizer.py    # Net profit ranking
│   ├── mausam_guru/
│   │   ├── agent.py               # Weather advisory agent
│   │   ├── openweather_client.py  # Weather API client
│   │   └── crop_weather_rules.py  # Crop-weather thresholds
│   └── vaani_setu/
│       ├── agent.py               # Voice bridge agent
│       ├── intent_extractor.py    # Intent + entity extraction
│       ├── stt_handler.py         # Speech-to-Text
│       └── tts_handler.py         # Text-to-Speech
├── cloud_functions/               # 5 serverless API wrappers
├── data/
│   ├── bigquery/                  # Reference CSVs (crop calendar, mandis, benchmarks)
│   ├── earth_engine/              # EE JavaScript scripts
│   ├── knowledge_base/            # Crop guides, schemes, pest info
│   └── satellite_cache/           # Pre-computed NDVI JSONs (~16 files)
├── infrastructure/
│   ├── setup.sh                   # One-command project setup
│   ├── deploy.sh                  # Cloud Run deployment
│   └── entrypoint.sh              # Docker entrypoint
├── scripts/
│   ├── precompute_satellite.py    # India grid NDVI pre-computation
│   └── refresh_mandi_cache.py     # Market price cache refresh
├── Dockerfile                     # Multi-stage production build
└── .env                           # Environment configuration
```
