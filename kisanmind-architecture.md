# KisanMind (किसानमाइंड) — Satellite-to-Voice Agricultural Intelligence

## Problem 5: Domain-Specialized AI Agents | ET AI Hackathon 2026

> *"India has 750 million agricultural field parcels. A farmer in Solan growing tomatoes and a farmer in Coorg growing coffee face completely different decisions — but both deserve the same quality of intelligence. KisanMind sees their field from space, understands their crop, checks today's mandi prices, reads tomorrow's weather, and speaks the answer in their language — all through a phone call."*

---

## 1. The Problem

India's 150 million farming households make daily decisions worth ₹45 lakh crore annually — what to plant, when to irrigate, when to harvest, where to sell. These decisions are made with:

- **No satellite visibility**: NDVI-based crop health monitoring exists in research papers but reaches zero smallholder farmers directly
- **Delayed market data**: Mandi prices fluctuate 30-40% daily across nearby markets; most farmers sell at the nearest mandi without comparing
- **Generic weather**: IMD forecasts cover districts, not fields — a 5km difference in Himachal means the difference between frost and no frost
- **Language barriers**: Advisory services operate in English or formal Hindi; a farmer in Tamil Nadu, Kerala, or Northeast India gets nothing actionable

**The gap KisanMind fills**: No existing tool combines satellite crop health monitoring + real-time mandi price arbitrage + hyperlocal weather + voice-first multilingual delivery into a single, phone-call-accessible system. Each piece exists in isolation. The fusion is the innovation.

---

## 2. What KisanMind Does

A farmer calls a number (or opens a web app). They say:

> *"Main Solan mein tamatar uga raha hoon. Meri fasal kaisi hai aur aaj kahan bechoon?"*
> *(I'm growing tomatoes in Solan. How's my crop and where should I sell today?)*

KisanMind responds in 15 seconds:

> *"Aapke area mein satellite se dekha — fasal ki health achhi hai, NDVI 0.72 hai jo tomatoes ke liye normal hai 45 din mein. Lekin agle 3 din mein barish aa rahi hai — agar harvest-ready hai toh kal subah tod lein. Aaj Solan mandi mein tamatar ₹1,800 quintal hai, lekin Shimla mein ₹2,400 — 60km door hai. Shimla bhejne mein ₹200 transport lagega, toh ₹400 per quintal zyada milega."*

This response required fusing four intelligence layers in real time:
1. **Satellite**: Earth Engine pulled Sentinel-2 imagery for Solan, computed NDVI
2. **Weather**: OpenWeatherMap forecast shows rain in 72 hours
3. **Market**: AgMarkNet API shows tomato prices across Himachal mandis
4. **Reasoning**: Gemini synthesized all signals into a harvest-timing and sell-location recommendation

---

## 3. System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        USER ACCESS LAYER                             │
│                                                                      │
│   📞 Voice Call           📱 WhatsApp          💻 Web Dashboard      │
│   (Any phone, any        (Text + Voice         (Map view, charts,    │
│    language)              messages)              satellite imagery)   │
│                                                                      │
│   Dialogflow CX  ←→  Cloud Functions  ←→  Cloud Run (Next.js)      │
│   (IVR + Voice)        (WhatsApp hook)      (Frontend)               │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│               AGENT ORCHESTRATION — Vertex AI Agent Engine           │
│               (Google ADK, Python, deployed on Agent Engine)         │
│                                                                      │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │                   KisanMind Brain                            │   │
│   │              (Orchestrator Agent)                            │   │
│   │                                                             │   │
│   │  • Routes user intent to specialist agents                  │   │
│   │  • Merges multi-agent outputs into single recommendation    │   │
│   │  • Maintains conversation context via Memory Bank           │   │
│   │  • Enforces guardrails (no pesticide dosage, no loan advice)│   │
│   └──────────────────────┬──────────────────────────────────────┘   │
│                          │                                           │
│          ┌───────────────┼───────────────┬───────────────┐          │
│          ▼               ▼               ▼               ▼          │
│   ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐  │
│   │ SatDrishti │  │ MandiMitra │  │ MausamGuru │  │ VaaniSetu  │  │
│   │ (Satellite │  │ (Market    │  │ (Weather   │  │ (Voice     │  │
│   │  Eye)      │  │  Friend)   │  │  Guru)     │  │  Bridge)   │  │
│   └────────────┘  └────────────┘  └────────────┘  └────────────┘  │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    INTELLIGENCE SERVICES                              │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │ Gemini 2.5   │  │ Earth Engine │  │ Cloud Speech-to-Text V2  │   │
│  │ Pro          │  │ (Sentinel-2  │  │ (Hindi, Tamil, Telugu,    │   │
│  │ (Reasoning + │  │  NDVI, EVI,  │  │  Bengali, Kannada,        │   │
│  │  Synthesis)  │  │  Imagery)    │  │  Marathi, Malayalam, etc.) │   │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘   │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │ Vertex AI    │  │ Cloud        │  │ Cloud Translation        │   │
│  │ Search       │  │ Text-to-     │  │ API v3                   │   │
│  │ (Crop KB +   │  │ Speech       │  │ (22 Indian languages)    │   │
│  │  Agri Guide) │  │ (Neural2)    │  │                          │   │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘   │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    EXTERNAL DATA SOURCES                              │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │ AgMarkNet    │  │ OpenWeather  │  │ Soil Health Card         │   │
│  │ (data.gov.in)│  │ Map API      │  │ (soilhealth.dac.gov.in)  │   │
│  │              │  │              │  │                          │   │
│  │ 3000+ mandis│  │ 5-day hourly │  │ Nutrient data by         │   │
│  │ 200+ crops  │  │ forecast     │  │ village/block            │   │
│  │ Daily prices │  │ Rain, temp,  │  │                          │   │
│  │              │  │ humidity,wind│  │                          │   │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘   │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐                                 │
│  │ Google Maps  │  │ Sentinel-2   │                                 │
│  │ Platform     │  │ (via Earth   │                                 │
│  │ (Geocoding + │  │  Engine)     │                                 │
│  │  Distance)   │  │ 10m res,     │                                 │
│  │              │  │ 5-day revisit│                                 │
│  └──────────────┘  └──────────────┘                                 │
└───────────────────────────┬──────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    DATA & STORAGE LAYER                               │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │ BigQuery     │  │ Firestore    │  │ Cloud Storage             │   │
│  │              │  │              │  │                          │   │
│  │ • Mandi price│  │ • Farmer     │  │ • Satellite image cache  │   │
│  │   history    │  │   profiles   │  │ • NDVI time-series       │   │
│  │ • Crop       │  │ • Session    │  │   thumbnails             │   │
│  │   calendars  │  │   state      │  │                          │   │
│  │ • Regional   │  │ • Advisory   │  │                          │   │
│  │   benchmarks │  │   history    │  │                          │   │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 4. The Four Specialist Agents

### Agent 1: SatDrishti (सैटदृष्टि — Satellite Eye)

**Purpose**: Turns raw satellite imagery into actionable crop health intelligence for a specific location.

**GCloud Services**: Google Earth Engine (project: dmjone), Gemini 2.5 Pro (multimodal), Cloud Storage, Cloud Functions

**How It Works**:

```
Farmer provides: location (village name / GPS / "near Solan bus stand")
         │
         ▼
┌─────────────────────────────┐
│ Google Maps Geocoding API    │
│                             │──→ Lat: 30.9045, Lon: 77.0967
│ "Solan, Himachal Pradesh"   │     (precise coordinates)
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ Google Earth Engine          │
│ (Project: dmjone)            │
│                             │
│ 1. Pull Sentinel-2 imagery  │
│    for coordinates           │
│    (last 30 days, cloud-     │
│    masked composite)         │
│                             │
│ 2. Compute vegetation        │
│    indices:                  │
│    • NDVI = (NIR-Red)/       │
│            (NIR+Red)         │
│    • EVI = Enhanced          │
│      Vegetation Index        │
│    • NDWI = Water stress     │
│      indicator               │
│                             │
│ 3. Generate 500m × 500m     │
│    area analysis around      │
│    coordinates               │
│                             │
│ 4. Compute time-series       │
│    (NDVI trend over last     │
│    3 months)                 │
│                             │
│ Output:                      │
│ • NDVI value (0.0 to 1.0)   │
│ • Trend (improving/          │
│   declining/stable)          │
│ • False-color composite      │
│   image (for web dashboard)  │
│ • Anomaly flag if NDVI is    │
│   below regional average     │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ Gemini 2.5 Pro               │
│ (Multimodal Analysis)        │
│                             │
│ Input: satellite image +     │
│ NDVI values + crop type +    │
│ growth stage                 │
│                             │
│ Prompt: "This Sentinel-2     │
│ false-color composite shows  │
│ farmland near Solan, HP.     │
│ The farmer is growing        │
│ tomatoes, currently 45 days  │
│ after planting. NDVI is      │
│ 0.72, trend is stable.       │
│ What is the crop health      │
│ assessment? Any visible      │
│ stress patterns? What        │
│ actions should the farmer    │
│ take?"                       │
│                             │──→ "Crop health is good.
│                             │     NDVI 0.72 is normal
│                             │     for tomatoes at 45
│                             │     days. No visible
│                             │     stress patterns.
│                             │     Continue current
│                             │     irrigation schedule."
└─────────────────────────────┘
```

**Earth Engine Code (actual implementation)**:

```javascript
// Earth Engine script for crop health analysis
// Runs on project 'dmjone' (noncommercial, registered)

function analyzeCropHealth(lat, lon, days_back) {
  var point = ee.Geometry.Point([lon, lat]);
  var region = point.buffer(500); // 500m radius around point

  // Get Sentinel-2 imagery, cloud-masked
  var s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(region)
    .filterDate(
      ee.Date(Date.now() - days_back * 86400000),
      ee.Date(Date.now())
    )
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30))
    .map(function(img) {
      var ndvi = img.normalizedDifference(['B8', 'B4']).rename('NDVI');
      var evi = img.expression(
        '2.5 * ((NIR - RED) / (NIR + 6*RED - 7.5*BLUE + 1))',
        { NIR: img.select('B8'), RED: img.select('B4'),
          BLUE: img.select('B2') }
      ).rename('EVI');
      var ndwi = img.normalizedDifference(['B3', 'B8']).rename('NDWI');
      return img.addBands([ndvi, evi, ndwi]);
    });

  // Latest composite
  var latest = s2.sort('system:time_start', false).first();
  var ndvi_val = latest.select('NDVI').reduceRegion({
    reducer: ee.Reducer.mean(), geometry: region, scale: 10
  });

  // Time series for trend
  var ndvi_series = s2.select('NDVI').map(function(img) {
    var mean = img.reduceRegion({
      reducer: ee.Reducer.mean(), geometry: region, scale: 10
    });
    return ee.Feature(null, {
      'date': img.date().format('YYYY-MM-dd'),
      'ndvi': mean.get('NDVI')
    });
  });

  // False-color visualization for Gemini analysis
  var vis = latest.select(['B8', 'B4', 'B3']).getThumbURL({
    region: region, dimensions: 512,
    min: 0, max: 3000
  });

  return {
    ndvi: ndvi_val,
    time_series: ndvi_series,
    image_url: vis
  };
}
```

**NDVI Interpretation Table (pre-loaded in Gemini system prompt)**:

| NDVI Range | Interpretation | Action |
|------------|---------------|--------|
| 0.0 – 0.1 | Bare soil / No vegetation | Check if recently planted |
| 0.1 – 0.3 | Sparse / stressed vegetation | Investigate — possible disease, water stress, nutrient deficiency |
| 0.3 – 0.5 | Moderate vegetation | Normal for early growth or harvest-ready crops |
| 0.5 – 0.7 | Healthy vegetation | Good — maintain current practices |
| 0.7 – 0.9 | Very healthy / peak growth | Excellent — crop is thriving |

---

### Agent 2: MandiMitra (मंडीमित्र — Market Friend)

**Purpose**: Finds the best mandi to sell at RIGHT NOW — comparing live prices across nearby markets, factoring in transport costs and distance.

**GCloud Services**: BigQuery, Cloud Functions, Google Maps Distance Matrix API

**External API**: AgMarkNet (data.gov.in — government open data, NDSAP license)

**How It Works**:

```
Farmer says: "Tomatoes" + location "Solan"
         │
         ▼
┌─────────────────────────────┐
│ AgMarkNet API                │
│ (data.gov.in)                │
│                             │
│ GET /resource/daily-price    │
│ ?api-key=YOUR_KEY            │
│ &filters[commodity]=Tomato   │
│ &filters[state]=             │
│   Himachal Pradesh           │
│                             │──→ Returns prices from
│                             │     all mandis in state:
│                             │     Solan: ₹1,800/qtl
│                             │     Shimla: ₹2,400/qtl
│                             │     Mandi: ₹2,100/qtl
│                             │     Kullu: ₹2,200/qtl
│                             │     Chandigarh: ₹1,600/qtl
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ Google Maps Distance Matrix  │
│ API                          │
│                             │
│ Calculate distance + travel  │
│ time from farmer's location  │
│ to each mandi:               │
│                             │──→ Solan: 5km, 15min
│ Origins: Solan               │     Shimla: 62km, 2hr
│ Destinations: [all mandis]   │     Mandi: 150km, 4hr
│                             │     Kullu: 180km, 5hr
│                             │     Chandigarh: 68km, 2.5hr
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ Profit Optimization          │
│ (Cloud Function)             │
│                             │
│ For each mandi:              │
│ Net Profit =                 │
│   (Price × Quantity)         │
│   - Transport Cost           │
│   - Commission (typically    │
│     2-5% of sale)            │
│   - Spoilage risk factor     │
│     (perishability ×         │
│      travel time)            │
│                             │
│ Rank by net profit:          │──→ 1. Shimla: ₹2,400
│                             │       - ₹200 transport
│                             │       - ₹120 commission
│                             │       = ₹2,080 net
│                             │     2. Solan: ₹1,800
│                             │       - ₹50 transport
│                             │       - ₹90 commission
│                             │       = ₹1,660 net
│                             │     "Shimla gives ₹420
│                             │      more per quintal"
└─────────────────────────────┘
```

**Price Trend Analysis (BigQuery)**:

```sql
-- Historical price trend for harvest timing
SELECT
  commodity,
  market,
  DATE(arrival_date) as date,
  modal_price,
  AVG(modal_price) OVER (
    PARTITION BY market, commodity
    ORDER BY arrival_date
    ROWS BETWEEN 7 PRECEDING AND CURRENT ROW
  ) as moving_avg_7d,
  modal_price - LAG(modal_price, 7) OVER (
    PARTITION BY market, commodity
    ORDER BY arrival_date
  ) as price_change_7d
FROM `kisanmind.mandi.daily_prices`
WHERE commodity = 'Tomato'
  AND state = 'Himachal Pradesh'
  AND arrival_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
ORDER BY date DESC;

-- Price prediction signal
-- If price is rising AND below seasonal average → HOLD
-- If price is falling OR above seasonal average → SELL NOW
```

---

### Agent 3: MausamGuru (मौसमगुरु — Weather Guru)

**Purpose**: Hyperlocal weather intelligence translated into farming actions — not "rain expected" but "don't spray pesticide tomorrow, don't irrigate today, harvest before Thursday."

**GCloud Services**: Cloud Functions, BigQuery

**External API**: OpenWeatherMap (free tier: 1,000 calls/day, 5-day forecast)

**How It Works**:

```
Location coordinates from geocoding
         │
         ▼
┌─────────────────────────────┐
│ OpenWeatherMap API            │
│                             │
│ GET /data/3.0/onecall        │
│ ?lat=30.9045&lon=77.0967     │
│ &exclude=minutely            │
│                             │──→ Next 5 days, hourly:
│                             │     Day 1: 28°C, clear
│                             │     Day 2: 26°C, cloudy
│                             │     Day 3: 22°C, RAIN 15mm
│                             │     Day 4: 20°C, RAIN 8mm
│                             │     Day 5: 25°C, clear
│                             │
│                             │     Humidity: 78%
│                             │     Wind: 12 km/h
│                             │     Frost risk: None
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ Farming Action Translator    │
│ (Gemini 2.5 Flash)           │
│                             │
│ System prompt includes:      │
│ • Crop-specific weather      │
│   thresholds                 │
│ • Irrigation rules by        │
│   soil type and weather      │
│ • Spray timing rules         │
│   (no spray before rain)     │
│ • Frost/heat alerts by crop  │
│ • Harvest timing impact      │
│                             │
│ Input: weather data +        │
│ crop type + growth stage     │
│                             │──→ Advisory:
│                             │     "Rain in 2 days.
│                             │      DO: Harvest ripe
│                             │      tomatoes tomorrow.
│                             │      DON'T: Don't spray
│                             │      any chemicals today.
│                             │      DON'T: Skip
│                             │      irrigation today
│                             │      (rain will cover it).
│                             │      WARNING: Ensure
│                             │      drainage channels
│                             │      are clear."
└─────────────────────────────┘
```

**Crop-Weather Rule Matrix (in Vertex AI Search knowledge base)**:

| Crop | Temperature Alert | Rain Action | Humidity Alert | Wind Alert |
|------|------------------|-------------|---------------|------------|
| Tomato | <10°C frost damage, >40°C flower drop | >20mm: harvest ripe immediately | >85%: fungal risk, spray before rain | >40km/h: stake/support plants |
| Wheat | <5°C at flowering: yield loss | >30mm at harvest: grain damage | >90%: rust risk | >50km/h: lodging risk |
| Rice | <15°C: cold stress | Waterlog ok during vegetative | Normal for paddy | >30km/h: panicle damage |
| Apple | <-2°C: frost protection needed | >25mm at fruit stage: cracking | >80%: scab risk | >60km/h: fruit drop |
| Coffee | <10°C: berry damage | >50mm: root rot risk | <40%: irrigation needed | >40km/h: branch damage |

---

### Agent 4: VaaniSetu (वाणीसेतु — Voice Bridge)

**Purpose**: Makes the entire system accessible through a phone call in any Indian language. This is the agent that multiplies KisanMind's reach from "people who download apps" to "anyone with a phone."

**GCloud Services**: Cloud Speech-to-Text V2, Cloud Text-to-Speech (Neural2), Cloud Translation API v3, Dialogflow CX

**Supported Languages (all native GCloud)**:

| Language | Speech-to-Text | Text-to-Speech | Code |
|----------|---------------|----------------|------|
| Hindi | Yes (V2) | Yes (Neural2) | hi-IN |
| Tamil | Yes (V2) | Yes (Neural2) | ta-IN |
| Telugu | Yes (V2) | Yes (Neural2) | te-IN |
| Bengali | Yes (V2) | Yes (Neural2) | bn-IN |
| Kannada | Yes (V2) | Yes (Neural2) | kn-IN |
| Malayalam | Yes (V2) | Yes (Neural2) | ml-IN |
| Marathi | Yes (V2) | Yes (Neural2) | mr-IN |
| Gujarati | Yes (V2) | Yes (Neural2) | gu-IN |
| English | Yes (V2) | Yes (Neural2) | en-IN |

**Voice Interaction Flow**:

```
Farmer calls → Dialogflow CX answers
         │
         ▼
┌─────────────────────────────┐
│ Dialogflow CX                │
│ (Welcome Flow)               │
│                             │
│ "Namaste! KisanMind mein     │
│  aapka swagat hai.           │
│  Apni bhasha mein baat       │
│  karein — Hindi, Tamil,      │
│  Telugu, Bengali, ya koi     │
│  bhi bhasha."                │
│                             │
│ [Auto-detects language       │
│  from first utterance]       │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ Cloud Speech-to-Text V2      │
│                             │
│ Model: latest_long           │
│ Adaptation: farming terms    │──→ Transcript + language ID
│ Code-mixing: Hindi-English   │
│ Enhanced: telephony model    │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ Intent Extraction            │
│ (Gemini 2.5 Flash)           │
│                             │
│ From transcript, extract:    │
│ • Location (village/city/    │──→ { location: "Solan",
│   district)                  │     crop: "tomato",
│ • Crop name                  │     intent: "sell_advice",
│ • Intent:                    │     language: "hi-IN" }
│   - crop_health_check        │
│   - where_to_sell            │
│   - weather_advisory         │
│   - what_to_plant            │
│   - full_advisory            │
└──────────┬──────────────────┘
           │
           ▼
  Routes to specialist agents
           │
           ▼
┌─────────────────────────────┐
│ Response Generation          │
│ (Gemini 2.5 Pro)             │
│                             │
│ System prompt:               │
│ "Respond in {language}.      │
│  Use simple, conversational  │
│  language a farmer would     │
│  understand. Avoid technical │
│  jargon. Use local units     │
│  (quintal, bigha, kattha).   │
│  Keep response under 30      │
│  seconds of speech. Give     │
│  specific numbers, not       │
│  vague advice."              │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ Cloud Text-to-Speech          │
│                             │
│ Voice: hi-IN-Neural2-D       │──→ Natural speech output
│ Speaking rate: 0.85          │     (slightly slower for
│ SSML: emphasize prices       │      phone clarity)
│ and action items             │
└─────────────────────────────┘
```

---

## 5. Compliance Guardrails

### What KisanMind Will NOT Do:

```
┌─────────────────────────────────────────────────────────┐
│                    GUARDRAIL FRAMEWORK                    │
│                                                          │
│  NEVER:                                                  │
│  ✗ Recommend specific pesticide brands or dosages        │
│    (liability risk — always say "consult your local      │
│     Krishi Vigyan Kendra for pesticide guidance")        │
│                                                          │
│  ✗ Provide loan or credit advice                         │
│    (SEBI/RBI regulated territory)                        │
│                                                          │
│  ✗ Guarantee crop yields or prices                       │
│    ("based on current data" disclaimer always added)     │
│                                                          │
│  ✗ Override farmer's local knowledge                     │
│    ("You know your soil best — this is satellite data    │
│     to supplement your experience")                      │
│                                                          │
│  ALWAYS:                                                 │
│  ✓ Cite data source ("AgMarkNet price as of today")      │
│  ✓ Show confidence level for satellite analysis          │
│  ✓ Add weather forecast uncertainty                      │
│  ✓ Log every recommendation with full reasoning chain    │
│  ✓ Use Model Armor for prompt injection defense          │
│  ✓ Mask any personal data (PII) via Cloud DLP            │
└─────────────────────────────────────────────────────────┘
```

### Audit Trail (Cloud Logging):

Every advisory generates a log entry:
```json
{
  "session_id": "ks-20260328-001",
  "timestamp": "2026-03-28T16:30:00Z",
  "farmer_location": "30.9045, 77.0967",
  "language": "hi-IN",
  "crop": "tomato",
  "intent": "sell_advice",
  "data_sources": {
    "satellite": { "source": "Sentinel-2", "date": "2026-03-26", "ndvi": 0.72 },
    "mandi": { "source": "AgMarkNet", "date": "2026-03-28", "prices": {...} },
    "weather": { "source": "OpenWeatherMap", "time": "2026-03-28T16:00Z" }
  },
  "recommendation": "Sell at Shimla mandi (₹2,400/qtl vs ₹1,800 at Solan)",
  "confidence": 0.85,
  "guardrails_triggered": [],
  "disclaimer_added": true
}
```

### Edge Cases & Error Handling

Problem 5 explicitly evaluates "edge-case handling." KisanMind handles every failure gracefully:

| Failure | Detection | Fallback |
|---------|-----------|----------|
| **Cloudy satellite imagery** (no usable Sentinel-2 in last 30 days) | Earth Engine returns null/low-quality composite | Use last available clear image + warn farmer: "Satellite data is 3 weeks old due to cloud cover. Next clear image expected in 2-3 days." |
| **AgMarkNet API down** | HTTP timeout / error response | Serve last-cached prices from BigQuery (refreshed daily via Cloud Scheduler) with timestamp: "Prices as of yesterday — live data temporarily unavailable." |
| **OpenWeatherMap API failure** | HTTP error | Fall back to Google Maps weather data (available via Maps Platform) or serve IMD district-level forecast from cached data |
| **Speech-to-Text can't understand accent/dialect** | Low confidence score (<0.6) from STT | Ask farmer to repeat, offer DTMF fallback ("Press 1 for tomato, 2 for wheat..."), or switch to SMS mode |
| **Location not recognized** | Geocoding returns no results | Ask progressively: "Which district?" → "Which state?" → use district centroid for satellite analysis |
| **Crop not in our database** | Crop name not matched | Respond honestly: "I don't have specific data for [crop]. I can still show you weather and nearby mandi prices. For crop-specific advice, contact your local KVK." |
| **Earth Engine quota exceeded** | 429/quota error from EE API | Serve pre-computed daily NDVI snapshots for major districts from Cloud Storage cache |

**Design principle**: Every agent returns a result, even if degraded. The orchestrator merges whatever data is available and clearly communicates what's missing. A partial answer ("I have mandi prices and weather, but satellite data is unavailable today") is always better than no answer.

### First-Time Onboarding Flow

When a farmer calls for the first time, VaaniSetu runs a 60-second onboarding:

```
VaaniSetu: "Namaste! KisanMind mein aapka swagat hai.
            Pehli baar aa rahe hain — kuch sawal puchna chahenge
            taaki aapko sahi salah de sakein."

Step 1:    "Aapka gaon ya sheher kya hai?"
Farmer:    "Solan"
           → Geocoded → lat/lon stored in Firestore

Step 2:    "Kaunsi fasal uga rahe hain abhi?"
Farmer:    "Tamatar"
           → Crop registered, growth calendar auto-set

Step 3:    "Kitne area mein? Bigha ya hectare mein batayein"
Farmer:    "Do bigha"
           → Stored for yield estimation and mandi quantity calc

VaaniSetu: "Shukriya! Ab se jab bhi call karenge,
            aapki fasal aur jagah yaad rahegi.
            Chaliye, aaj ki salah dete hain..."
           → Routes to full advisory flow
```

Returning callers are identified by phone number (Firestore lookup) and skip onboarding entirely.

---

## 6. Low-Connectivity Design — Graceful Degradation

The Problem 5 statement specifically requires solutions that work "even in low-connectivity environments." KisanMind addresses this through a five-tier degradation model — every tier delivers value, no tier is a dead end.

### Tier 1: Smartphone + 4G/5G (~35% of farmers)
Full web dashboard — satellite map with NDVI overlay, mandi price charts, voice + text chat, interactive visualizations. The richest experience.

### Tier 2: Basic phone + 2G voice call (~60% of farmers) — PRIMARY MODE
**This is KisanMind's default interface.** A voice call requires zero data, zero internet, zero smartphone. The farmer speaks on a 2G call at 9.6 kbps. All heavy computation (Earth Engine NDVI, Gemini reasoning, AgMarkNet price lookup, OpenWeatherMap forecast) runs entirely in the cloud. The farmer's phone does nothing except transmit voice. Works on any ₹500 feature phone.

### Tier 3: SMS fallback (~98% of farmers)
When voice calls are unreliable (poor signal, noisy environment), farmers can send a simple SMS:

```
Farmer sends: "TOMATO SOLAN"
System replies (160 chars):
"Solan ₹1800 Shimla ₹2400(best) Rain 2d
NDVI OK. Harvest tmrw. Transport ₹200"
```

**Implementation**: Cloud Functions receives SMS via Twilio/MSG91 webhook → parses crop + location → runs same agent pipeline in text mode → compresses response to 160 characters → sends SMS reply. Cost: ~₹0.25 per SMS.

### Tier 4: Missed call trigger (~99% of farmers)
Zero cost to farmer. Farmer gives a missed call to the KisanMind number. Cloud Scheduler has already pre-computed their daily advisory (registered crop + location). System calls back within 2 minutes with a 30-second voice advisory. This is the proven mKisan model that already works across India.

### Tier 5: Proactive daily SMS push (100% of registered farmers)
No farmer action needed. Every morning at 6 AM, Cloud Scheduler triggers a batch job:

```
For each registered farmer:
  1. Fetch latest mandi prices for their crop + district
  2. Check weather forecast for their coordinates
  3. Check if NDVI changed significantly (weekly satellite refresh)
  4. Generate 160-char SMS advisory
  5. Send via SMS gateway
```

The intelligence comes TO the farmer. Works even with intermittent connectivity — the SMS arrives whenever signal becomes available.

### GCloud services for low-connectivity tiers

| Tier | GCloud Services Used |
|------|---------------------|
| Voice (2G) | Dialogflow CX + Cloud STT/TTS (all cloud-side) |
| SMS | Cloud Functions + Pub/Sub + SMS gateway (Twilio/MSG91) |
| Missed call | Cloud Scheduler + Cloud Functions + TTS |
| Proactive push | Cloud Scheduler + BigQuery (batch query) + SMS gateway |

**Hackathon scope**: Tiers 1, 2, and 3 are implemented in the prototype. Tiers 4 and 5 are documented in the architecture as production roadmap.

---

## 7. Google Cloud Service Map

| # | Service | Role | Project |
|---|---------|------|---------|
| 1 | **Google Earth Engine** | Sentinel-2 satellite imagery, NDVI/EVI/NDWI computation, time-series analysis | dmjone (noncommercial) |
| 2 | **Vertex AI Agent Engine** | Multi-agent orchestration, deployment, Memory Bank, observability | lmsforshantithakur |
| 3 | **Agent Development Kit (ADK)** | Build agent logic in Python, <100 lines per agent | lmsforshantithakur |
| 4 | **Gemini 2.5 Pro** | Complex agricultural reasoning, multimodal satellite image analysis, response synthesis | lmsforshantithakur |
| 5 | **Gemini 2.5 Flash** | Fast intent classification, weather-to-action translation, language detection | lmsforshantithakur |
| 6 | **Cloud Speech-to-Text V2** | Voice input in 9 Indian languages, telephony model, code-mixing | lmsforshantithakur |
| 7 | **Cloud Text-to-Speech** | Neural2 voices for natural responses in Indian languages, SSML for emphasis | lmsforshantithakur |
| 8 | **Cloud Translation API v3** | Real-time translation across 22 Indian languages, agricultural glossary | lmsforshantithakur |
| 9 | **Dialogflow CX** | Conversation flow management, IVR for phone gateway, $600 free trial credit | lmsforshantithakur |
| 10 | **Vertex AI Search** | RAG over crop knowledge base, government advisory documents, pest/disease guides | lmsforshantithakur |
| 11 | **BigQuery** | Mandi price history, crop calendars, regional NDVI benchmarks, analytics | lmsforshantithakur |
| 12 | **Cloud Run** | Host Next.js web dashboard (satellite map view, charts, recommendations) | lmsforshantithakur |
| 13 | **Cloud Functions** | Event-driven: geocoding, price fetch, profit calculation, NDVI extraction | lmsforshantithakur |
| 14 | **Firestore** | Farmer profiles, session state, advisory history, crop registry | lmsforshantithakur |
| 15 | **Cloud Storage** | Satellite image cache, NDVI thumbnails, knowledge base documents | lmsforshantithakur |
| 16 | **Google Maps Geocoding API** | Convert village/city names to lat/lon coordinates | lmsforshantithakur |
| 17 | **Google Maps Distance Matrix** | Calculate distance and travel time to nearby mandis | lmsforshantithakur |
| 18 | **Pub/Sub** | Decouple voice pipeline from agent processing, async satellite analysis | lmsforshantithakur |
| 19 | **Cloud Logging** | Full advisory audit trail, decision logging | lmsforshantithakur |
| 20 | **Model Armor** | Prompt injection defense, content safety for agricultural advice | lmsforshantithakur |
| 21 | **Secret Manager** | Store API keys (AgMarkNet, OpenWeatherMap) | lmsforshantithakur |
| 22 | **Cloud Scheduler** | Daily mandi price refresh, weekly NDVI batch updates for registered farmers | lmsforshantithakur |
| 23 | **Identity Platform** | Phone-number authentication for farmer profiles | lmsforshantithakur |

**Total: 23 GCloud services across 2 projects**

---

## 8. Data Architecture

### Pre-loaded Reference Data (BigQuery)

```sql
-- Crop calendar with region-specific timings
CREATE TABLE kisanmind.reference.crop_calendar (
  crop STRING,
  variety STRING,
  region STRING,         -- e.g., "Himachal_mid_hills"
  season STRING,         -- kharif, rabi, zaid
  sowing_start DATE,
  sowing_end DATE,
  harvest_start DATE,
  harvest_end DATE,
  growth_days INT64,
  optimal_temp_min FLOAT64,
  optimal_temp_max FLOAT64,
  water_requirement_mm INT64,
  ndvi_peak_expected FLOAT64
);

-- NDVI regional benchmarks (for anomaly detection)
CREATE TABLE kisanmind.reference.ndvi_benchmarks (
  region STRING,
  crop STRING,
  month INT64,
  avg_ndvi FLOAT64,
  stddev_ndvi FLOAT64,
  percentile_25 FLOAT64,
  percentile_75 FLOAT64
);

-- Mandi master list with geocoding
CREATE TABLE kisanmind.reference.mandis (
  mandi_code STRING,
  mandi_name STRING,
  state STRING,
  district STRING,
  latitude FLOAT64,
  longitude FLOAT64,
  commodities ARRAY<STRING>,
  commission_rate FLOAT64  -- typical commission %
);
```

### Vertex AI Search Knowledge Base

```
Knowledge Base: Crop Advisory Corpus
├── ICAR crop production guides (public domain)
├── KVK advisory bulletins by state
├── Pest/disease identification guides with symptoms
├── Organic farming practices (NPOP certified methods)
├── Government scheme information (PM-KISAN, PMFBY, etc.)
└── Regional best practices by agro-climatic zone
```

---

## 9. Web Dashboard Design

The web dashboard serves two purposes: a rich visual experience for demo, and a practical tool for farmers with smartphones.

### Dashboard Screens:

**Screen 1: Satellite View (the "wow" screen)**
```
┌──────────────────────────────────────────────────┐
│  KisanMind                          🌐 Hindi ▼  │
├──────────────────────────────────────────────────┤
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │                                            │  │
│  │     [Google Maps / Earth Engine            │  │
│  │      Satellite View]                       │  │
│  │                                            │  │
│  │     • Shows user's area                    │  │
│  │     • NDVI overlay (green = healthy,       │  │
│  │       yellow = moderate, red = stressed)   │  │
│  │     • Clickable to zoom                    │  │
│  │                                            │  │
│  └────────────────────────────────────────────┘  │
│                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐ │
│  │ NDVI     │ │ Weather  │ │ Best Mandi       │ │
│  │ 0.72     │ │ Rain in  │ │ Shimla           │ │
│  │ Healthy  │ │ 2 days   │ │ ₹2,400/qtl       │ │
│  └──────────┘ └──────────┘ └──────────────────┘ │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │ 🎤 "Meri fasal ke baare mein batao..."    │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

**Screen 2: Mandi Price Comparison**
```
┌──────────────────────────────────────────────────┐
│  Tomato Prices Today (Mar 28, 2026)              │
├──────────────────────────────────────────────────┤
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │ [Bar chart: mandi prices sorted by net     │  │
│  │  profit after transport]                   │  │
│  │                                            │  │
│  │  Shimla    ████████████████████  ₹2,080    │  │
│  │  Kullu     ██████████████████   ₹1,900    │  │
│  │  Mandi     █████████████████    ₹1,820    │  │
│  │  Solan     ███████████████      ₹1,660    │  │
│  │  Chndgrh   █████████████        ₹1,380    │  │
│  │                                            │  │
│  │  * Net of transport + commission           │  │
│  └────────────────────────────────────────────┘  │
│                                                  │
│  ┌────────────────────────────────────────────┐  │
│  │ 30-Day Price Trend [line chart]            │  │
│  │ Prices trending UP ↑ 12% this week        │  │
│  │ Recommendation: SELL NOW — above seasonal  │  │
│  │ average                                    │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

---

## 10. Demo Script (2.5 minutes)

### Opening (15 seconds)
*[Screen: India map with 750 million field parcels statistic]*

"India has 150 million farming households making decisions worth 45 lakh crore rupees every year — with zero satellite intelligence, delayed market data, and advice only in English. KisanMind changes that."

### Demo 1: The Satellite View (45 seconds)
*[Screen: Web dashboard]*

1. Type "Solan, Himachal Pradesh" + "Tomato" into the search
2. Satellite view zooms into the area around Solan
3. NDVI overlay renders — green areas (healthy), yellow patches (moderate)
4. Dashboard shows: NDVI 0.72, Trend: Stable, Crop Health: Good
5. Switch to 3-month NDVI time-series chart — shows the crop growth curve
6. "In 10 seconds, KisanMind analyzed satellite imagery covering this entire farming area and computed vegetation health indices that would take a researcher hours to calculate."

### Demo 2: The Mandi Price Arbitrage (30 seconds)
*[Screen: Mandi comparison]*

1. Shows today's tomato prices across 5 mandis in Himachal
2. Bar chart shows net profit after transport and commission
3. "Shimla mandi pays ₹420 MORE per quintal than the local Solan mandi. For a farmer selling 10 quintals, that's ₹4,200 extra — just by driving 60 kilometers further. KisanMind finds this in seconds."
4. Shows 30-day price trend: "Prices are 12% above the seasonal average — recommendation is to sell now before the expected dip."

### Demo 3: The Voice Call (45 seconds)
*[Screen: Voice interface with live transcript]*

1. Click the microphone button
2. Speak in Hindi: "Main Coorg mein coffee uga raha hoon. Mausam kaisa rahega is hafte?"
3. Show real-time transcript appearing
4. System switches to coffee context — entirely different crop rules
5. Response comes back in Hindi voice:
   - "Coorg mein agle 5 din mein baarish nahi hogi, temperature 22-28°C rahega. Coffee ke liye ye accha hai. Lekin humidity 82% hai — berry borer ka risk hai. Agle hafte neem-based spray lagana sahi rahega. Aur Kushalnagar mandi mein aaj coffee ₹8,200 per quintal hai."
6. "Same system. Different state. Different crop. Different language. That's the power of domain-specialized agents."

### Demo 4: Pan-India Capability (15 seconds)
*[Screen: Split view showing 3 different locations]*

Quick flashes:
- Apple orchards in Shimla (NDVI showing healthy green)
- Rice paddies in Andhra (NDWI showing water levels)
- Wheat fields in Punjab (harvest-time golden NDVI)

"One platform. Every crop. Every state. Every language."

### Closing (15 seconds)
"India's farmers don't need another app. They need intelligence that meets them where they are — on a phone call, in their language, with data they can't get anywhere else. That's KisanMind."

---

## 11. Impact Model

| Metric | Year 1 (Conservative) | Year 3 | Year 5 |
|--------|----------------------|--------|--------|
| Farmers reached | 100,000 | 2,000,000 | 20,000,000 |
| Avg price gain from mandi arbitrage | ₹2,000/season | ₹3,000/season | ₹3,500/season |
| Total income improvement | ₹20 Cr | ₹600 Cr | ₹7,000 Cr |
| Crop loss prevented (early weather alerts) | 5% | 8% | 12% |
| Pesticide reduction (targeted advice) | 10% | 20% | 25% |
| Languages actively served | 5 | 9 | 15+ |

### Assumptions
- Average Indian farmer sells 20-50 quintals per season
- Mandi price arbitrage of ₹200-500/quintal is consistently available within 100km
- Weather-triggered harvest timing prevents 5-15% post-harvest losses
- Voice-first approach reaches farmers without smartphones (estimated 40% of farming households)

### Show the Math — One Farmer's Story

A tomato farmer near Solan, HP, grows on 2 bigha (~0.5 acre) and produces ~30 quintals per harvest, 2 harvests per year.

**Without KisanMind**: Sells at nearest Solan mandi at ₹1,800/qtl. Revenue = 30 × ₹1,800 = **₹54,000 per harvest**.

**With KisanMind**:
- MandiMitra finds Shimla mandi at ₹2,400/qtl, 62km away
- Transport cost: ₹200/qtl × 30 qtl = ₹6,000
- Commission difference: negligible (both ~4%)
- Net at Shimla: (₹2,400 × 30) − ₹6,000 = **₹66,000 per harvest**
- MausamGuru prevented 1 harvest of rain damage per year by timing the pick correctly, saving ~₹10,000 in spoilage

**Annual gain**: (₹12,000 × 2 harvests) + ₹10,000 saved = **₹34,000/year** — an increase of roughly 30% on a ₹1,08,000 baseline. That's 2 months of a rural family's expenses.

### ET Revenue Alignment
- KisanMind extends ET's reach to rural India — 150M new potential users
- Data moat: satellite + mandi + weather fusion creates proprietary intelligence
- Partnership opportunities: agri-input companies, crop insurance (PMFBY), rural banking

---

## 12. 24-Hour Build Timeline

| Hours | Task | Deliverable |
|-------|------|-------------|
| **0–2** | Project setup: enable all APIs on lmsforshantithakur, verify Earth Engine on dmjone, get AgMarkNet API key, OpenWeatherMap key, create BigQuery datasets | Working GCloud environment |
| **2–5** | **SatDrishti agent**: Earth Engine script for NDVI/EVI computation from Sentinel-2, Cloud Function wrapper that takes lat/lon and returns health data, test with Solan coordinates | Satellite analysis pipeline working |
| **5–8** | **MandiMitra agent**: AgMarkNet API integration via Cloud Function, BigQuery table for price history, Google Maps Distance Matrix for transport cost, profit ranking logic | Mandi price comparison working |
| **8–10** | **MausamGuru agent**: OpenWeatherMap integration, crop-weather rule matrix in Vertex AI Search, Gemini prompt for weather-to-action translation | Weather advisory working |
| **10–13** | **VaaniSetu agent**: Cloud Speech-to-Text + Text-to-Speech pipeline, language detection, Gemini intent extraction, voice response generation | Voice interaction working |
| **13–16** | **Agent orchestration**: Wire all 4 agents together using ADK, deploy on Vertex AI Agent Engine, test multi-agent flow end-to-end | Full pipeline working |
| **16–19** | **Web dashboard**: Next.js app on Cloud Run — map view with Earth Engine tiles, NDVI overlay, mandi price charts, voice input button | Web app deployed |
| **19–21** | **Polish**: Demo data for 3 geographies (Himachal/Coorg/Punjab), error handling, loading states, mobile responsiveness, guardrail disclaimers | Production-quality demo |
| **21–23** | **Record demo video**: 2.5-minute walkthrough covering all 4 demo scenarios, screen recording with voiceover | Demo video ready |
| **23–24** | **Submission**: GitHub cleanup, README with setup instructions, architecture diagram PDF, documentation | Submission complete |

### Parallel Track (if team has >1 person)
- Person 1: Agents + backend (Hours 0–16)
- Person 2: Frontend + demo data (Hours 5–21)
- Together: Integration testing + video (Hours 21–24)

---

## 13. Repository Structure

```
kisanmind/
├── README.md                         # Setup instructions, architecture overview
├── architecture/
│   ├── system-architecture.pdf       # Architecture diagram
│   └── architecture-document.md      # This document
│
├── agents/
│   ├── brain/
│   │   ├── orchestrator.py           # ADK orchestrator agent
│   │   └── config.yaml
│   ├── sat_drishti/
│   │   ├── agent.py                  # Satellite analysis agent
│   │   ├── earth_engine.py           # EE NDVI/EVI computation
│   │   └── ndvi_interpreter.py       # NDVI-to-advice logic
│   ├── mandi_mitra/
│   │   ├── agent.py                  # Market intelligence agent
│   │   ├── agmarknet_client.py       # AgMarkNet API wrapper
│   │   └── profit_optimizer.py       # Net profit calculator
│   ├── mausam_guru/
│   │   ├── agent.py                  # Weather advisory agent
│   │   ├── openweather_client.py     # Weather API wrapper
│   │   └── crop_weather_rules.py     # Action translator
│   └── vaani_setu/
│       ├── agent.py                  # Voice interface agent
│       ├── stt_handler.py            # Speech-to-text
│       ├── tts_handler.py            # Text-to-speech
│       └── intent_extractor.py       # Language + intent detection
│
├── data/
│   ├── bigquery/
│   │   ├── crop_calendar.csv         # Crop timing data
│   │   ├── ndvi_benchmarks.csv       # Regional NDVI averages
│   │   └── mandi_master.csv          # Mandi geocoded list
│   ├── knowledge_base/
│   │   ├── crop_guides/              # ICAR crop production guides
│   │   ├── pest_disease/             # Pest identification guides
│   │   └── government_schemes/       # PM-KISAN, PMFBY info
│   └── earth_engine/
│       └── ndvi_analysis.js          # Earth Engine script
│
├── frontend/
│   ├── app/                          # Next.js app
│   │   ├── page.tsx                  # Home — satellite view + voice
│   │   ├── mandi/page.tsx            # Mandi price comparison
│   │   ├── weather/page.tsx          # Weather advisory
│   │   └── components/
│   │       ├── SatelliteMap.tsx       # Earth Engine tile overlay
│   │       ├── NDVIChart.tsx          # Time-series chart
│   │       ├── MandiComparison.tsx    # Price bar chart
│   │       ├── VoiceInput.tsx         # Microphone button + transcript
│   │       └── WeatherTimeline.tsx    # 5-day forecast cards
│   └── public/
│       └── demo-data/                # Pre-cached demo data
│
├── cloud_functions/
│   ├── geocode/                      # Location → lat/lon
│   ├── fetch_mandi_prices/           # AgMarkNet API caller
│   ├── fetch_weather/                # OpenWeatherMap caller
│   ├── compute_ndvi/                 # Earth Engine API caller
│   └── calculate_profit/             # Transport + commission calc
│
├── infrastructure/
│   ├── setup.sh                      # One-command project setup
│   └── deploy.sh                     # One-command deployment
│
├── demo/
│   ├── demo-video-script.md
│   └── sample-queries/               # Pre-tested voice queries
│
├── Dockerfile
├── requirements.txt
└── .env.example                      # Required API keys template
```

---

## 14. Why KisanMind Wins the Top 20

| Criterion (20% each) | KisanMind's Edge |
|----------------------|-----------------|
| **Innovation** | Only hackathon project fusing satellite imagery + mandi prices + weather + voice. Google Earth Engine usage alone sets it apart from 95% of submissions. |
| **Technical Implementation** | 23 GCloud services including Earth Engine (unique to Google), Vertex AI Agent Engine with ADK, multi-agent architecture with 4 specialist agents, deterministic guardrails. |
| **Practical Impact** | 150 million farming households. ₹2,000-5,000 income improvement per farmer per season from mandi arbitrage alone. Voice-first reaches farmers without smartphones. |
| **User Experience** | Zero-download access via phone call. Works in 9 Indian languages. Satellite visuals on web dashboard. Response in under 15 seconds. |
| **Pitch Quality** | Satellite zooming into a real field + NDVI overlay + live mandi price comparison + Hindi voice response — four "wow moments" in 2.5 minutes. Pan-India demo across 3 states proves scalability. |
