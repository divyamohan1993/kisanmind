# KisanMind v2: Deep Advisory Engine — Design Spec

**Date:** 2026-03-29
**Status:** Draft
**Scope:** Enrich existing advisory pipeline with deeper data analysis, data transparency, conversational UX, and nearest KVK — NO new separate features

---

## 1. Philosophy

**One system, one job:** Help farmers make great decisions by translating research-grade satellite, weather, and market data into simple, honest, actionable advice spoken in their language.

**Core rules:**
- Raw data never reaches the farmer. Only cross-validated, actionable inferences do.
- Every inference states WHEN the data was captured and what it means NOW.
- Sensitive decisions (pest treatment, chemicals, loans) → always KVK referral.
- Conversation feels like talking to a knowledgeable neighbor, not a call center.
- All computation on backend. Farmer on 2G Twilio gets everything spoken.

---

## 2. What Changes (Backend: `backend/main.py`)

### 2.1 Historical Mandi Price Trends

**Current:** Fetches today's prices, picks best mandi by net profit.
**Enhanced:** Fetches multiple days of data, computes trend, gives sell-timing advice.

**Implementation:**
- AgMarkNet API supports date filtering. Fetch last 7 days of prices for the crop+state.
- Compute: `price_trend_percent = (today_price - 7_days_ago_price) / 7_days_ago_price * 100`
- Classify: `rising` (>5%), `falling` (<-5%), `stable` (within ±5%)
- Seasonal context: Compare current month's price to known seasonal patterns (Gemini knowledge from agricultural market reports).
- Pass to Gemini synthesis as pre-computed inference:
  ```
  PRICE TREND: Tomato at Azadpur rose 18% in 7 days (₹2,100 → ₹2,480).
  Trend: RISING. Historical pattern: Tomato prices in this region typically peak in first week of April.
  Arrivals today: Normal (no glut warning).
  ```
- Gemini converts to farmer language: "Tomato ka rate badh raha hai. Aaj 2,480 hai, ek hafta pehle 2,100 tha. April ke pehle hafte mein rate aur badh sakta hai. Agar storage hai toh 5 din aur ruk sakte ho."

**Guardrail:** "Yeh rate aaj ki AgMarkNet data ke hisaab se hai. Market mein koi bhi guarantee nahi hoti. Final faisla aapka hai."

### 2.2 Satellite Data Transparency & NDVI Trajectory

**Current:** Returns single NDVI value + "Healthy/Stressed". Farmer doesn't know what NDVI means or when the image was taken.
**Enhanced:** Multi-temporal trajectory, district benchmark, and honest data freshness.

**Implementation:**
- Fetch last 4-6 Sentinel-2 observations (not just latest). Already possible — Earth Engine filters by date range.
- Compute trajectory: linear regression over last 4+ points → `growth_rate_per_week`
- Classify: `accelerating` (growth rate positive + increasing), `plateauing` (growth rate near 0), `declining` (growth rate negative)
- District benchmark: Compute mean NDVI for a 10km radius around farmer → `district_avg_ndvi`. Compare: farmer's field vs district.
- Growth stage estimation: Use accumulated Growing Degree Days (GDD) from weather history. `GDD = sum(max(0, (T_max + T_min)/2 - T_base))` where T_base varies by crop (tomato=10°C, wheat=5°C, rice=10°C).
- Data freshness: Always include `image_date` and compute `days_since_image = today - image_date`.

**What gets passed to Gemini (pre-computed, not raw numbers):**
```
SATELLITE ASSESSMENT (data from 2026-03-25, i.e. 4 days old):
- Your field health: GOOD (NDVI 0.58)
- Growth trend over last 3 weeks: STABLE (plateauing — normal for tomato at fruit-setting stage)
- Compared to nearby fields: You are 8% ABOVE district average (good sign)
- Estimated growth stage: Fruit-setting (based on ~65 days since typical sowing for your region)
- NOTE: This satellite image is 4 days old. Anything you did in the last 4 days (irrigation, spraying) will NOT be reflected yet. Next satellite update expected in 2-3 days.
```

**What farmer hears (Gemini converts):**
"Aapki fasal ki sehat achhi hai. Pichle 3 hafton mein growth stable hai — tomato ke fruit-setting stage mein yeh normal hai. Aapke aas-paas ke khetoon se aapki fasal 8% behtar hai. Yeh 4 din purani satellite image se hai — agar aapne 2 din pehle paani diya tha toh uska asar abhi dikhai nahi dega. 2-3 din mein naya data aayega."

**Guardrail:** If NDVI is declining AND weather shows adequate rain → don't guess the cause. Say: "Fasal mein kuch dikkat ho sakti hai. Apne nazdeeki KVK se sampark karein."

### 2.3 Weather-Crop Interaction (Growth Stage Aware)

**Current:** Raw 5-day forecast + generic crop rules.
**Enhanced:** Cross-reference weather with estimated growth stage + NDVI + recent conditions.

**Implementation:**
- Already have crop-specific weather rules in `agents/mausam_guru/crop_weather_rules.py`. Enhance these rules to be growth-stage-aware.
- Compute GDD-based growth stage (same as 2.2) and pass it to weather rules.
- Cross-reference:
  - Rain forecast + flowering stage = "Don't spray, don't irrigate. Pollination may be affected — this is natural, don't worry."
  - Rain forecast + harvest-ready (NDVI plateau) = "Harvest BEFORE the rain. Wet tomatoes spoil faster."
  - No rain + high temp + vegetative stage = "Irrigate tomorrow morning before 8 AM. Afternoon irrigation wastes 30% to evaporation."
  - Frost warning + any stage = "Cover your crop tonight. Frost expected."

**What gets passed to Gemini:**
```
WEATHER-CROP INTERACTION:
- Crop: Tomato, estimated stage: Fruit-setting (~65 days)
- Next 3 days: Clear, 28-34°C, no rain
- Day 4-5: Rain expected (15mm Thursday, 8mm Friday)
- ACTION: Do NOT irrigate Wednesday — rain coming Thursday.
- ACTION: If fruits are reddening, harvest before Thursday rain.
- WARNING: Humidity will be 85%+ after rain — fungal risk. If you see spots on leaves after rain, contact KVK immediately.
- NOTE: Weather is a forecast, not a guarantee. Based on Open-Meteo data as of today.
```

### 2.4 Spoilage-Aware Profit Calculation

**Current:** `net_profit = modal_price - transport_cost - commission`
**Enhanced:** Factor in perishability, transit time, and time-of-day.

**Implementation:**
- Spoilage rates (from agricultural research, hardcoded per crop category):
  ```python
  SPOILAGE_RATE = {  # % value loss per hour without cold chain
      "tomato": 0.5, "strawberry": 0.8, "mango": 0.4, "banana": 0.3,
      "leafy_greens": 1.0, "capsicum": 0.4, "grapes": 0.6,
      "potato": 0.05, "onion": 0.05, "wheat": 0.01, "rice": 0.01,
  }
  ```
- Transit time already available from Google Maps Distance Matrix (duration_minutes).
- Adjusted formula: `spoilage_loss = modal_price * spoilage_rate * transit_hours`
- `net_profit = modal_price - transport_cost - commission - spoilage_loss`
- Time-of-day factor: If transit > 4 hours AND crop is perishable AND max_temp > 35°C, add warning: "Leave before 5 AM to avoid afternoon heat. Spoilage doubles above 35°C."

**What farmer hears:**
"Azadpur mein rate achha hai — 3,100 rupaye. Lekin 7 ghante ka safar hai. Tomato garam mein kharab hota hai — 4% maal kharab ho sakta hai raaste mein. Transport aur commission ke baad aapko 2,680 milega. Solan mandi mein 2,400 hai lekin sirf 1 ghante ka raasta — aapko 2,280 milega. Azadpur abhi bhi 400 rupaye zyada dega. Subah 4 baje niklo toh garmi se bachoge."

### 2.5 Confidence-Gated Output

**Current:** All data gets synthesized equally.
**Enhanced:** Each inference has a confidence score. Only high-confidence reaches farmer.

**Implementation:**
- Each pre-computed inference block includes a confidence tag:
  ```
  HIGH_CONFIDENCE: Multiple data sources agree (e.g., NDVI declining + no rain = water stress)
  MEDIUM_CONFIDENCE: Single data source, plausible inference (e.g., price trend from 7 days data)
  LOW_CONFIDENCE: Data is old/sparse, inference is speculative
  ```
- Rules for Gemini:
  - HIGH → State as fact: "Paani ki kami lag rahi hai. Kal subah paani dein."
  - MEDIUM → Hedge: "Rate badh rahe hain, shayad 3-4 din aur badh sakte hain. Lekin guarantee nahi hai."
  - LOW → Don't state. Or: "Is baare mein pakka kehna mushkil hai. KVK se puchh lein."
- Confidence calculation logic:
  - Satellite data < 3 days old = +0.3, 3-7 days = +0.1, >7 days = -0.2
  - Weather forecast Day 1-2 = +0.3, Day 3-4 = +0.1, Day 5 = -0.1
  - Price trend from 7+ data points = +0.2, from <3 data points = -0.2
  - Multiple sources agreeing = +0.2 bonus

### 2.6 Nearest KVK with Every Advisory

**Implementation:**
- Use Google Places API (New) `searchText` with query `"Krishi Vigyan Kendra"` near farmer's lat/lon.
- API: `POST https://places.googleapis.com/v1/places:searchText`
- Headers: `X-Goog-Api-Key`, `X-Goog-FieldMask: places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.location`
- Body: `{ "textQuery": "Krishi Vigyan Kendra", "locationBias": { "circle": { "center": {"latitude": lat, "longitude": lon}, "radius": 50000.0 } } }`
- Parse first result: name, address, phone, lat/lon.
- Calculate distance from farmer using existing Google Maps Distance Matrix.
- Cache result per farmer location (KVKs don't move) — TTL: 30 days.
- Always append to advisory output.

**What farmer hears (end of every call):**
"Agar koi bhi fasal ki samasya ho — kida, bimari, ya koi bhi sawaal — toh aapka sabse nazdeeki KVK [name] hai, [X] kilometer door, [address]. Unka number hai [phone]. Ya phir toll-free number 1800-180-1551 pe call karein."

---

## 3. Conversational UX (Twilio Voice Flow)

### 3.1 Natural Conversation, Not Questionnaire

**Current flow:**
```
System: "Namaste! KisanMind mein swagat hai. Apni bhasha mein boliye — kaunsi fasal uga rahe hain aur kahaan?"
[Farmer speaks]
[System processes, gives advisory, call ends]
```

**Enhanced flow — feels like talking to a neighbor:**
```
System: "Namaste bhai! Main KisanMind hoon. Aap batao, kya haal hai fasal ka?"
[Farmer speaks freely — "tomato laga rakha hai, Solan mein hoon, rate kya chal raha hai?"]
[System extracts: crop=tomato, location=Solan, intent=where_to_sell]
[System gives advisory]
System: "Aur kuch jaanna hai? Mausam ke baare mein, ya koi aur fasal ka rate? Boliye, main sun raha hoon."
[Farmer can ask follow-up OR hang up]
[If farmer asks: process again with same location context]
[If silence: "Achha bhai, dhanyavaad! Kal bhi call kar lena. Jai Jawaan Jai Kisaan!"]
```

**Key changes:**
- Greeting is warm and informal — "Aap batao, kya haal hai fasal ka?" not "Apni bhasha mein boliye"
- After advisory, ALWAYS offer follow-up — don't end the call
- Follow-up retains context (same crop, same location)
- Graceful exit on silence with an encouraging sign-off
- Detect dialect naturally — if farmer says "tamatar" or "tamaatar" or "thakkali", system understands all
- Never say "main samajh nahi paya" (I didn't understand) — instead say "Ek baar aur boliye bhai, network thoda weak hai" (Say again, network is weak) — blame the network, not the farmer

### 3.2 Multi-Turn Context Retention

**Implementation:**
- After first advisory, store in-memory context: `{phone_number: {crop, lat, lon, state, language, last_advisory_data}}`
- On follow-up in same call: reuse all context, only process the new question
- Follow-up intents: "mausam batao" (weather), "aur koi mandi?" (other mandis), "kab bechun?" (when to sell), "KVK kahaan hai?" (where's KVK)
- On new call from same number (within 24 hours): "Namaste phir se! Pichli baar aapne tomato ke baare mein puchha tha Solan se. Aaj ka update chahiye ya koi naya sawaal hai?"

### 3.3 Returning Caller Recognition

**Implementation:**
- Store `{phone_number: {crop, lat, lon, language, last_call_timestamp}}` in L1 cache (TTL: 7 days) + L2 GCS cache
- On incoming call, check if phone number exists in cache
- If returning within 7 days: skip intro questions, offer direct update
- Greeting: "Namaste [bhai/behan]! Aapke Solan wale tomato ke khet ka aaj ka update suniye..."
- Then proceed directly to advisory with cached crop+location

### 3.4 Tight Spoken Output Format

**Every advisory spoken in this exact structure (5 lines, ~30 seconds):**
1. **Crop health** (1 sentence): "Aapki fasal achhi hai, growth normal chal raha hai."
2. **Weather action** (1 sentence): "Kal baarish aa sakti hai, aaj paani mat dena."
3. **Best mandi + price** (1 sentence): "Sabse achha rate Azadpur mein hai, 3,100 rupaye quintal, 6 ghante ka raasta."
4. **Timing advice** (1 sentence): "Rate badh raha hai, 3 din aur ruk sakte ho."
5. **KVK** (1 sentence): "Koi dikkat ho toh Solan KVK 12 kilometer door hai, number 1800-180-1551."

Then: "Aur kuch jaanna hai?"

---

## 4. Data Transparency Rules

### 4.1 Always State Data Age

Every advisory MUST include:
- Satellite: "Yeh [X] din purani satellite image se hai" (from [date])
- Weather: "Yeh aaj ka mausam anumaan hai" (today's forecast)
- Mandi: "Yeh aaj ke [time] tak ke rate hain" (prices as of [time])

### 4.2 Explain What Data CAN'T Show

If satellite data is >3 days old, explicitly say:
"Satellite image [X] din purani hai. Agar aapne haal hi mein paani diya ya dawai chhidki toh uska asar is data mein nahi dikhega. Naya satellite data [Y] din mein aayega."

### 4.3 Cross-Validation Transparency

When data sources conflict:
- NDVI says healthy BUT farmer reports issue → "Satellite mein fasal achhi dikh rahi hai, lekin agar aapko khet mein dikkat dikh rahi hai toh satellite data [X] din purana hai. KVK se jaanch karwa lein."
- Price rising BUT high arrivals → "Rate badh raha hai lekin mandi mein maal bhi zyada aa raha hai. Rate gir bhi sakta hai. Apna faisla samajhdaari se lein."

---

## 5. Enhanced Gemini System Prompt

The synthesis prompt gets all pre-computed inferences (not raw data). Key additions to prompt:

```
RULES FOR SPEAKING TO FARMER:
1. You are a knowledgeable farming neighbor, not a government officer or AI.
2. Use informal, warm Hindi/regional language. Say "bhai" (brother). Be encouraging.
3. NEVER say raw numbers like NDVI, EVI, NDWI. Convert to "fasal ki sehat achhi/theek/kamzor hai".
4. ALWAYS state when the data was captured: "4 din purani satellite image", "aaj ka mausam", "aaj ke rate".
5. If satellite data is old (>5 days), explicitly say: "Yeh purani image hai. Agar aapne haal mein kuch kiya toh wo ismein nahi dikhega."
6. For HIGH confidence inferences: state as advice. "Kal paani dein."
7. For MEDIUM confidence inferences: hedge. "Shayad 3 din mein rate badh sakta hai, lekin pakka nahi hai."
8. For LOW confidence: don't state OR say "Is baare mein KVK se puchh lein."
9. NEVER recommend pesticide brands. NEVER guarantee yields. NEVER give loan advice.
10. ALWAYS end with nearest KVK name, distance, and helpline number.
11. Keep total response under 150 words. Farmer is standing in a field, not reading a document.
12. ALWAYS end with disclaimer: "Yeh aaj ki data ke hisaab se hai. Final faisla aapka hai."
```

---

## 6. What Does NOT Change

- Frontend pages (/, /talk, /demo, /mandi, /weather) — they continue to work as-is
- Frontend gets enriched response data (more fields) but existing fields stay backward-compatible
- All existing API endpoints stay the same
- NDVI, weather, mandi fetching functions stay the same — we ADD processing on top
- Guardrails only get stricter, not relaxed
- No new separate features/agents — everything flows through existing `/api/advisory` and `/api/voice/*`

---

## 7. Implementation Scope (all in backend/main.py)

| Change | Type | Estimated Lines |
|--------|------|----------------|
| Historical mandi price trend fetching | New function | ~40 lines |
| Price trend analysis (compute direction, rate) | New function | ~30 lines |
| NDVI trajectory (multi-temporal + benchmark) | Enhance `_compute_ndvi_sync` | ~50 lines |
| GDD-based growth stage estimation | New function | ~30 lines |
| Spoilage-aware profit calculation | Enhance `calculate_net_profits` | ~20 lines |
| Confidence scoring for each data block | New function | ~40 lines |
| Nearest KVK via Google Places API | New async function | ~40 lines |
| Enhanced Gemini prompt (all pre-computed inferences) | Modify `generate_advisory_with_gemini` | ~60 lines |
| Data transparency in prompt (dates, caveats) | Part of prompt enhancement | ~20 lines |
| Multi-turn Twilio conversation | Enhance `/api/voice/process` | ~60 lines |
| Returning caller recognition | Enhance `/api/voice/incoming` | ~30 lines |
| Natural conversational greeting | Modify Twilio greeting text | ~10 lines |
| Follow-up context retention | New in-memory dict + logic | ~30 lines |
| **Total new/modified** | | **~460 lines** |

---

## 8. Data Sources (all existing, no new APIs needed)

| Source | Already Have? | Used For |
|--------|-------------|----------|
| AgMarkNet (data.gov.in) | ✅ Yes | Historical price trends (query multiple dates) |
| Sentinel-2 via Earth Engine | ✅ Yes | NDVI trajectory (already fetches time series) |
| Open-Meteo | ✅ Yes | Weather forecast + historical temps for GDD |
| Google Maps Distance Matrix | ✅ Yes | Transit time for spoilage calculation |
| Google Maps Geocoding | ✅ Yes | Reverse geocode for state/district |
| Google Places API (New) | ✅ Key exists | Nearest KVK search |
| Google Cloud Translate | ✅ Yes | Advisory translation |
| Google Cloud TTS/STT | ✅ Yes | Voice I/O |
| Gemini 3.1 Pro/Flash | ✅ Yes | Advisory synthesis with enhanced prompt |

---

## 9. Testing Criteria

- Advisory for Solan tomato farmer includes: price trend, satellite age, weather-crop advice, nearest KVK
- Satellite data age is explicitly stated in spoken advisory
- Price trend shows direction with timeframe
- Spoilage-adjusted profit differs from raw profit for perishable crops
- Low-confidence inferences are hedged or omitted
- Twilio call allows follow-up question after first advisory
- Returning caller (same phone within 7 days) gets personalized greeting
- Greeting sounds natural, not robotic
- Advisory is under 150 words when spoken
- KVK name, distance, and phone number included in every response
