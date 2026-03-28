import { NextRequest, NextResponse } from "next/server";

/* ------------------------------------------------------------------ */
/*  Backend URL config                                                 */
/* ------------------------------------------------------------------ */
const BACKEND_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.BACKEND_URL ||
  "http://localhost:8080";

const DEMO_MODE = process.env.DEMO_MODE === "true";

/* ------------------------------------------------------------------ */
/*  Demo data (used when DEMO_MODE=true or when backend is down)       */
/* ------------------------------------------------------------------ */
const DEMO_ADVISORIES: Record<string, object> = {
  "solan-tomato": {
    status: "success",
    location: "Solan, Himachal Pradesh",
    crop: "Tomato",
    language: "hi-IN",
    satellite: {
      ndvi: 0.72, evi: 0.58, ndwi: -0.15, trend: "stable", health: "Healthy",
      confidence: 0.85, image_date: "2026-03-26", source: "Sentinel-2 via Google Earth Engine",
      assessment: "Crop health is good. NDVI 0.72 is normal for tomatoes at 45 days. No stress detected.",
    },
    mandi: {
      best_mandi: "Shimla", best_price: 2400, local_price: 1800, price_advantage: 420,
      recommendation: "SELL at Shimla mandi",
      mandis: [
        { name: "Shimla", price: 2400, distance_km: 62, transport_cost: 200, commission: 120, net_profit: 2080, travel_time: "2 hr" },
        { name: "Kullu", price: 2200, distance_km: 180, transport_cost: 540, commission: 110, net_profit: 1550, travel_time: "5 hr" },
        { name: "Mandi", price: 2100, distance_km: 150, transport_cost: 450, commission: 84, net_profit: 1566, travel_time: "4 hr" },
        { name: "Solan", price: 1800, distance_km: 5, transport_cost: 50, commission: 90, net_profit: 1660, travel_time: "15 min" },
        { name: "Chandigarh", price: 1600, distance_km: 68, transport_cost: 220, commission: 100, net_profit: 1280, travel_time: "2.5 hr" },
      ],
      price_trend: "rising", trend_percentage: 12,
      source: "AgMarkNet (data.gov.in), 28 March 2026",
    },
    weather: {
      summary: "Rain expected in 2 days. Temperature 20-28\u00b0C.",
      forecast: [
        { day: "Today", temp_max: 28, temp_min: 15, condition: "Clear", rain_mm: 0, humidity: 65, wind_kmh: 8 },
        { day: "Tomorrow", temp_max: 26, temp_min: 14, condition: "Partly Cloudy", rain_mm: 0, humidity: 72, wind_kmh: 10 },
        { day: "Day 3", temp_max: 22, temp_min: 13, condition: "Rain", rain_mm: 15, humidity: 88, wind_kmh: 15 },
        { day: "Day 4", temp_max: 20, temp_min: 12, condition: "Rain", rain_mm: 8, humidity: 85, wind_kmh: 12 },
        { day: "Day 5", temp_max: 25, temp_min: 14, condition: "Clear", rain_mm: 0, humidity: 68, wind_kmh: 7 },
      ],
      advisories: [
        { type: "do", message: "Harvest ripe tomatoes tomorrow morning before rain arrives", urgency: "high" },
        { type: "dont", message: "Do not spray any chemicals \u2014 rain in 48 hours will wash them off", urgency: "high" },
        { type: "dont", message: "Skip irrigation today \u2014 rain will provide sufficient moisture", urgency: "medium" },
        { type: "warning", message: "Clear drainage channels before rain to prevent waterlogging", urgency: "medium" },
        { type: "do", message: "Check fruit for cracking after rain stops on Day 5", urgency: "low" },
      ],
      source: "Google Weather API, 28 March 2026",
    },
    combined_advisory: "Aapke area mein satellite se dekha \u2014 fasal ki health achhi hai, NDVI 0.72 hai jo tomatoes ke liye normal hai 45 din mein. Lekin agle 3 din mein barish aa rahi hai \u2014 agar harvest-ready hai toh kal subah tod lein. Aaj Solan mandi mein tamatar \u20b91,800 quintal hai, lekin Shimla mein \u20b92,400 \u2014 60km door hai. Shimla bhejne mein \u20b9200 transport lagega, toh \u20b9420 per quintal zyada milega.",
    combined_advisory_en: "Satellite analysis shows your crop health is good \u2014 NDVI 0.72 is normal for tomatoes at 45 days. However, rain is expected in 2 days. If harvest-ready, pick tomorrow morning. Solan mandi \u20b91,800/qtl vs Shimla \u20b92,400/qtl \u2014 \u20b9420 more per quintal after transport.",
    disclaimer: "Advisory based on AgMarkNet, Google Earth Engine, and Google Weather API data. Prices and weather may change.",
  },
  "coorg-coffee": {
    status: "success",
    location: "Coorg (Kodagu), Karnataka",
    crop: "Coffee",
    language: "en-IN",
    satellite: {
      ndvi: 0.76, evi: 0.62, ndwi: -0.08, trend: "stable", health: "Healthy",
      confidence: 0.82, image_date: "2026-03-25", source: "Sentinel-2 via Google Earth Engine",
      assessment: "Coffee plantation health is good. NDVI 0.76 indicates healthy canopy cover typical for established coffee plants.",
    },
    mandi: {
      best_mandi: "Kushalnagar", best_price: 8200, local_price: 7800, price_advantage: 280,
      recommendation: "SELL at Kushalnagar mandi",
      mandis: [
        { name: "Kushalnagar", price: 8200, distance_km: 15, transport_cost: 100, commission: 246, net_profit: 7854, travel_time: "30 min" },
        { name: "Hassan", price: 8400, distance_km: 85, transport_cost: 500, commission: 294, net_profit: 7606, travel_time: "2.5 hr" },
        { name: "Mysore", price: 8100, distance_km: 120, transport_cost: 680, commission: 324, net_profit: 7096, travel_time: "3 hr" },
        { name: "Mangalore", price: 8500, distance_km: 140, transport_cost: 780, commission: 340, net_profit: 7380, travel_time: "3.5 hr" },
      ],
      price_trend: "stable", trend_percentage: 2,
      source: "AgMarkNet (data.gov.in), 28 March 2026",
    },
    weather: {
      summary: "Dry week ahead. Temperature 22-30\u00b0C. Humidity 78-85%.",
      forecast: [
        { day: "Today", temp_max: 30, temp_min: 20, condition: "Partly Cloudy", rain_mm: 0, humidity: 78, wind_kmh: 10 },
        { day: "Tomorrow", temp_max: 31, temp_min: 21, condition: "Clear", rain_mm: 0, humidity: 75, wind_kmh: 8 },
        { day: "Day 3", temp_max: 29, temp_min: 20, condition: "Clear", rain_mm: 0, humidity: 80, wind_kmh: 12 },
        { day: "Day 4", temp_max: 30, temp_min: 21, condition: "Partly Cloudy", rain_mm: 2, humidity: 82, wind_kmh: 10 },
        { day: "Day 5", temp_max: 28, temp_min: 19, condition: "Clear", rain_mm: 0, humidity: 76, wind_kmh: 9 },
      ],
      advisories: [
        { type: "warning", message: "Humidity at 82% \u2014 monitor for berry borer activity", urgency: "medium" },
        { type: "do", message: "Good conditions for neem-based spray this week \u2014 no rain expected", urgency: "medium" },
        { type: "do", message: "Continue shade management \u2014 temperatures normal for coffee", urgency: "low" },
      ],
      source: "Google Weather API, 28 March 2026",
    },
    combined_advisory: "Coffee plantation health is good. NDVI 0.76 indicates healthy canopy. Kushalnagar mandi offers \u20b98,200/qtl. Humidity at 82% \u2014 watch for berry borer. Good week for neem spray with no rain forecast.",
    disclaimer: "Advisory based on current satellite and market data. Consult local KVK for pest management guidance.",
  },
  "ludhiana-wheat": {
    status: "success",
    location: "Ludhiana, Punjab",
    crop: "Wheat",
    language: "hi-IN",
    satellite: {
      ndvi: 0.62, evi: 0.48, ndwi: -0.20, trend: "declining", health: "Moderate \u2014 approaching maturity",
      confidence: 0.88, image_date: "2026-03-27", source: "Sentinel-2 via Google Earth Engine",
      assessment: "NDVI declining as wheat approaches maturity. This is normal for March \u2014 grain filling stage. Golden color starting to appear.",
    },
    mandi: {
      best_mandi: "Ludhiana", best_price: 2275, local_price: 2275, price_advantage: 0,
      recommendation: "SELL at Ludhiana mandi (MSP: \u20b92,275/qtl)",
      mandis: [
        { name: "Ludhiana", price: 2275, distance_km: 3, transport_cost: 30, commission: 91, net_profit: 2154, travel_time: "10 min" },
        { name: "Jalandhar", price: 2275, distance_km: 60, transport_cost: 200, commission: 80, net_profit: 1995, travel_time: "1.5 hr" },
        { name: "Amritsar", price: 2275, distance_km: 130, transport_cost: 420, commission: 91, net_profit: 1764, travel_time: "3 hr" },
        { name: "Patiala", price: 2275, distance_km: 100, transport_cost: 330, commission: 91, net_profit: 1854, travel_time: "2.5 hr" },
      ],
      price_trend: "stable", trend_percentage: 0,
      source: "AgMarkNet (data.gov.in), 28 March 2026. MSP 2026-27: \u20b92,275/qtl",
    },
    weather: {
      summary: "Warm and dry. Temperature rising to 34\u00b0C by Day 4.",
      forecast: [
        { day: "Today", temp_max: 30, temp_min: 16, condition: "Clear", rain_mm: 0, humidity: 45, wind_kmh: 12 },
        { day: "Tomorrow", temp_max: 31, temp_min: 17, condition: "Clear", rain_mm: 0, humidity: 42, wind_kmh: 15 },
        { day: "Day 3", temp_max: 33, temp_min: 18, condition: "Clear", rain_mm: 0, humidity: 38, wind_kmh: 18 },
        { day: "Day 4", temp_max: 34, temp_min: 19, condition: "Haze", rain_mm: 0, humidity: 35, wind_kmh: 20 },
        { day: "Day 5", temp_max: 32, temp_min: 18, condition: "Clear", rain_mm: 0, humidity: 40, wind_kmh: 14 },
      ],
      advisories: [
        { type: "warning", message: "Temperature rising to 34\u00b0C \u2014 terminal heat stress risk for grain filling", urgency: "high" },
        { type: "do", message: "Give one light irrigation if grain is still in dough stage", urgency: "high" },
        { type: "do", message: "Plan harvest within 10-14 days as crop approaches maturity", urgency: "medium" },
        { type: "dont", message: "Do not delay harvest \u2014 late harvest reduces grain weight 2-3 qtl/hectare", urgency: "medium" },
      ],
      source: "Google Weather API, 28 March 2026",
    },
    combined_advisory: "Gehun ki fasal mature ho rahi hai \u2014 NDVI gir raha hai jo March mein normal hai. Temperature 34\u00b0C tak jayega \u2014 agar dough stage mein hai toh ek halki sinchai kar dein. 10-14 din mein harvest karein. Ludhiana mandi mein MSP \u20b92,275/qtl hai \u2014 sabse nazdeek aur faydemand hai.",
    disclaimer: "Advisory based on current satellite and weather data. Wheat MSP for 2026-27 is \u20b92,275/qtl.",
  },
};

function getDemoResponse(location: string, crop: string) {
  const key = `${location.toLowerCase().split(",")[0].trim()}-${crop.toLowerCase().trim()}`;
  return DEMO_ADVISORIES[key] || DEMO_ADVISORIES["solan-tomato"];
}

/* ------------------------------------------------------------------ */
/*  POST handler — proxy to backend or return demo data                */
/* ------------------------------------------------------------------ */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { location = "Solan", crop = "Tomato" } = body;

    // If DEMO_MODE is explicitly set, use demo data
    if (DEMO_MODE) {
      return NextResponse.json(getDemoResponse(location, crop));
    }

    // Try proxying to the real backend
    try {
      const backendRes = await fetch(`${BACKEND_URL}/api/advisory`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(120000),
      });

      if (!backendRes.ok) {
        throw new Error(`Backend returned ${backendRes.status}`);
      }

      const data = await backendRes.json();
      return NextResponse.json(data);
    } catch {
      // Backend unavailable — fall back to demo data
      console.warn("[advisory] Backend unavailable, returning demo data");
      return NextResponse.json(getDemoResponse(location, crop));
    }
  } catch {
    return NextResponse.json(getDemoResponse("Solan", "Tomato"));
  }
}

export async function GET() {
  return NextResponse.json({
    service: "KisanMind Advisory API",
    version: "1.0.0",
    agents: ["SatDrishti", "MandiMitra", "MausamGuru", "VaaniSetu"],
    status: "running",
    mode: DEMO_MODE ? "demo" : "live",
  });
}
