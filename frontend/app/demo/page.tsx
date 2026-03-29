"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import {
  Play, Loader2, MapPin, TrendingUp, CloudRain, Sun, Cloud, Satellite,
  Phone, Shield, Globe, Leaf, Volume2, CheckCircle, ChevronRight,
  Thermometer, Droplets, ShieldCheck, Info, Activity, Radio,
} from "lucide-react";
import Link from "next/link";
import useGeolocation from "../hooks/useGeolocation";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */
interface MandiPrice {
  market: string;
  district?: string;
  modal_price: number;
  distance_km: number;
  duration_text?: string;
  net_profit_per_quintal: number;
  transport_cost_per_quintal?: number;
  commission_per_quintal?: number;
}

interface DailyForecast {
  date: string;
  max_temp_c: number;
  min_temp_c: number;
  precipitation_mm: number;
}

interface ApiData {
  location: { location_name: string; state: string; formatted_address?: string };
  crop: string;
  mandi_prices: MandiPrice[];
  best_mandi: MandiPrice;
  local_mandi: MandiPrice;
  weather: { daily_forecast: DailyForecast[]; summary: string; source: string };
  advisory: string;
  satellite?: { ndvi: number; evi: number; ndwi: number; health: string; trend: string; image_date: string; source: string };
  sources: Record<string, string>;
  price_trend?: {
    direction?: string;
    percentage?: number;
    period_days?: number;
  };
  growth_stage?: {
    stage?: string;
    days_since_sowing?: number;
    confidence?: string;
  };
  confidence?: string;
  nearest_kvk?: {
    name?: string;
    distance_km?: number;
    phone?: string;
    district?: string;
  };
  cross_validation?: Array<{
    type: string;
    message: string;
    source?: string;
  }>;
  satellite_extras?: {
    sar?: {
      moisture_class?: string;
      backscatter_db?: number;
    };
    lst?: {
      surface_temp_c?: number;
      heat_stress?: string;
    };
    smap?: {
      rootzone_class?: string;
      soil_moisture?: number;
    };
  };
}

type DemoStep =
  | "ready"       // waiting for user to tap
  | "locating"    // getting GPS
  | "fetching"    // calling all APIs
  | "narrating"   // playing voice advisory
  | "done";       // showing full results

/* ------------------------------------------------------------------ */
/*  TTS helper                                                         */
/* ------------------------------------------------------------------ */
async function playTTS(text: string, lang: string): Promise<HTMLAudioElement | null> {
  try {
    const res = await fetch(`${API_BASE}/api/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, language: lang }),
    });
    if (!res.ok) return null;
    const d = await res.json();
    if (!d.audio_base64) return null;
    const audio = new Audio(`data:audio/mp3;base64,${d.audio_base64}`);
    audio.play();
    return audio;
  } catch { return null; }
}

function waitEnd(a: HTMLAudioElement | null): Promise<void> {
  if (!a) return Promise.resolve();
  return new Promise(r => { a.onended = () => r(); a.onerror = () => r(); });
}

/* ------------------------------------------------------------------ */
/*  Value points for judges                                            */
/* ------------------------------------------------------------------ */
const VALUE_POINTS = [
  { icon: Satellite, label: "Sentinel-2 NDVI", detail: "Real satellite crop health via Earth Engine" },
  { icon: TrendingUp, label: "AgMarkNet Prices", detail: "Live government mandi data from data.gov.in" },
  { icon: MapPin, label: "Distance Matrix", detail: "Real driving distance + transport costs" },
  { icon: Thermometer, label: "5-Day Weather", detail: "Open-Meteo hyperlocal forecast" },
  { icon: Globe, label: "22 Languages", detail: "All scheduled Indian languages supported" },
  { icon: Phone, label: "2G Voice Call", detail: "Works on any phone via Twilio webhook" },
  { icon: Shield, label: "Compliance Guardrails", detail: "No pesticide brands, data citations, disclaimers" },
  { icon: Volume2, label: "Gemini 3.1 Pro", detail: "Conversational advisory in farmer's language" },
  { icon: Radio, label: "SAR Soil Moisture", detail: "Sentinel-1 C-band radar soil wetness" },
  { icon: Thermometer, label: "MODIS LST", detail: "Land surface temperature + heat stress" },
  { icon: Droplets, label: "SMAP Root Zone", detail: "NASA soil moisture active-passive data" },
  { icon: ShieldCheck, label: "Cross-Validation", detail: "Multi-source conflict detection engine" },
  { icon: Activity, label: "Historical GDD", detail: "Growth stage via accumulated degree days" },
];

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */
export default function DemoPage() {
  const geo = useGeolocation();
  const [step, setStep] = useState<DemoStep>("ready");
  const [data, setData] = useState<ApiData | null>(null);
  const [error, setError] = useState("");
  const [elapsed, setElapsed] = useState(0);
  const [statusText, setStatusText] = useState("");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Elapsed timer
  useEffect(() => {
    if (step === "fetching") {
      const start = Date.now();
      timerRef.current = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 500);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [step]);

  /* ---- The one-click demo ---- */
  const runDemo = useCallback(async () => {
    setError("");
    setData(null);

    // 1. GPS
    setStep("locating");
    setStatusText("Detecting your location via GPS...");

    // Wait for geo if still loading
    let lat = geo.latitude;
    let lon = geo.longitude;
    if (!lat || !lon) {
      await new Promise(r => setTimeout(r, 3000));
      lat = geo.latitude;
      lon = geo.longitude;
    }
    if (!lat || !lon) {
      setError("GPS location required. Please allow location access and try again.");
      setStep("ready");
      return;
    }

    // 2. Fetch everything
    setStep("fetching");
    setElapsed(0);
    setStatusText("Calling AgMarkNet + Earth Engine + Weather + Gemini 3.1...");

    try {
      const res = await fetch(`${API_BASE}/api/advisory`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          latitude: lat, longitude: lon,
          crop: "Tomato", language: "hi",
          intent: "full_advisory",
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `API error ${res.status}`);
      }

      const result: ApiData = await res.json();
      setData(result);

      // 3. Also fetch NDVI separately if not in response
      if (!result.satellite) {
        try {
          const ndviRes = await fetch(`${API_BASE}/api/ndvi`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ latitude: lat, longitude: lon }),
          });
          if (ndviRes.ok) {
            const ndviData = await ndviRes.json();
            result.satellite = ndviData;
            setData({ ...result });
          }
        } catch { /* NDVI is optional */ }
      }

      // 4. Narrate
      setStep("narrating");
      setStatusText("Speaking advisory...");
      const audio = await playTTS(result.advisory, "hi");
      audioRef.current = audio;
      await waitEnd(audio);

      setStep("done");
      setStatusText("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Demo failed");
      setStep("ready");
    }
  }, [geo.latitude, geo.longitude]);

  const stopNarration = () => {
    audioRef.current?.pause();
    setStep("done");
  };

  const bestMandi = data?.best_mandi;
  const localMandi = data?.local_mandi;
  const priceAdv = bestMandi && localMandi ? bestMandi.modal_price - localMandi.modal_price : 0;

  return (
    <div className="min-h-screen text-white">
      <main className="max-w-4xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold gradient-text mb-2">KisanMind Demo</h1>
          <p className="text-white/50">One click. Real data. Your exact location.</p>
        </div>

        {/* Value points grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          {VALUE_POINTS.map((vp, i) => (
            <div key={i} className="glass-card glass-card-hover p-4 text-center group">
              <div className="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-xl bg-healthy/10 group-hover:bg-healthy/20 transition-colors">
                <vp.icon size={20} className="text-healthy" />
              </div>
              <div className="text-xs font-bold text-white/90">{vp.label}</div>
              <div className="text-[10px] text-white/40 mt-1 leading-relaxed">{vp.detail}</div>
            </div>
          ))}
        </div>

        {/* Big demo button */}
        {step === "ready" && (
          <div className="flex flex-col items-center mb-8">
            <button
              onClick={runDemo}
              className="relative flex items-center justify-center h-40 w-40 rounded-full bg-healthy/80 shadow-[0_0_80px_rgba(34,197,94,0.4)] hover:shadow-[0_0_100px_rgba(34,197,94,0.6)] active:scale-95 transition-all"
            >
              <span className="absolute inset-0 rounded-full bg-healthy/30 animate-ping [animation-duration:2s]" />
              <Play size={64} className="relative z-10 text-white ml-2" />
            </button>
            <p className="mt-4 text-lg font-medium text-white/70">Tap to run full demo</p>
            <p className="text-sm text-white/40 mt-1">
              GPS: {geo.latitude ? `${geo.latitude.toFixed(4)}, ${geo.longitude?.toFixed(4)}` : "Detecting..."}
            </p>
          </div>
        )}

        {/* Loading states */}
        {(step === "locating" || step === "fetching") && (
          <div className="flex flex-col items-center mb-8 py-8">
            <Loader2 size={48} className="text-healthy animate-spin mb-4" />
            <p className="text-lg font-medium text-white/80">{statusText}</p>
            {step === "fetching" && (
              <div className="mt-4 space-y-2 text-sm text-white/50">
                <div className="flex items-center gap-2">
                  {elapsed >= 0 && <CheckCircle size={14} className="text-healthy" />}
                  <span>GPS: {geo.latitude?.toFixed(4)}, {geo.longitude?.toFixed(4)}</span>
                </div>
                <div className="flex items-center gap-2">
                  {elapsed >= 1 && <CheckCircle size={14} className="text-healthy" />}
                  {elapsed < 1 && <Loader2 size={14} className="animate-spin text-white/30" />}
                  <span>Reverse geocoding location...</span>
                </div>
                <div className="flex items-center gap-2">
                  {elapsed >= 3 && <CheckCircle size={14} className="text-healthy" />}
                  {elapsed < 3 && <Loader2 size={14} className="animate-spin text-white/30" />}
                  <span>Fetching AgMarkNet mandi prices...</span>
                </div>
                <div className="flex items-center gap-2">
                  {elapsed >= 3 && <CheckCircle size={14} className="text-healthy" />}
                  {elapsed < 3 && <Loader2 size={14} className="animate-spin text-white/30" />}
                  <span>Fetching 5-day weather forecast...</span>
                </div>
                <div className="flex items-center gap-2">
                  {elapsed >= 5 && <CheckCircle size={14} className="text-healthy" />}
                  {elapsed < 5 && <Loader2 size={14} className="animate-spin text-white/30" />}
                  <span>Computing driving distances to each mandi...</span>
                </div>
                <div className="flex items-center gap-2">
                  {elapsed >= 7 && <CheckCircle size={14} className="text-healthy" />}
                  {elapsed < 7 && <Loader2 size={14} className="animate-spin text-white/30" />}
                  <span>Gemini 3.1 Pro generating conversational advisory...</span>
                </div>
                <div className="mt-2 text-xs text-white/30">{elapsed}s elapsed</div>
              </div>
            )}
          </div>
        )}

        {/* Narrating */}
        {step === "narrating" && (
          <div className="flex flex-col items-center mb-8 py-4">
            <div className="flex items-center gap-2 mb-4">
              <Volume2 size={24} className="text-healthy animate-pulse" />
              <span className="text-lg font-medium text-healthy">Speaking advisory in Hindi...</span>
            </div>
            <button onClick={stopNarration} className="text-sm text-white/40 hover:text-white/60">
              Skip to results →
            </button>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mb-6 rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-400 text-center">
            {error}
            <button onClick={runDemo} className="ml-3 underline">Retry</button>
          </div>
        )}

        {/* Results */}
        {data && (step === "narrating" || step === "done") && (
          <div className="space-y-6">
            {/* Location card */}
            <div className="glass-card p-5">
              <div className="flex items-center gap-3 mb-3">
                <MapPin size={20} className="text-sky" />
                <h3 className="font-bold text-lg">Location (Real GPS)</h3>
              </div>
              <div className="text-2xl font-bold">{data.location.location_name}, {data.location.state}</div>
              <div className="text-sm text-white/40 mt-1">{data.location.formatted_address}</div>
              <div className="text-xs text-white/30 mt-1">Coordinates: {geo.latitude?.toFixed(4)}, {geo.longitude?.toFixed(4)}</div>
            </div>

            {/* Satellite NDVI */}
            {data.satellite && (
              <div className="glass-card p-5 border border-emerald-500/20">
                <div className="flex items-center gap-3 mb-3">
                  <Satellite size={20} className="text-emerald-400" />
                  <h3 className="font-bold text-lg">Satellite Crop Health (Real Sentinel-2)</h3>
                  {data.growth_stage?.stage && (
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 text-[10px] font-semibold text-emerald-400">
                      <Leaf size={10} />
                      {data.growth_stage.stage}
                      {data.growth_stage.days_since_sowing != null && <span className="text-white/40 ml-0.5">Day {data.growth_stage.days_since_sowing}</span>}
                      {data.growth_stage.confidence && (
                        <span className={`font-bold ml-0.5 ${data.growth_stage.confidence === "HIGH" ? "text-emerald-400" : data.growth_stage.confidence === "MEDIUM" ? "text-yellow-400" : "text-red-400"}`}>
                          {data.growth_stage.confidence}
                        </span>
                      )}
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <div className="text-3xl font-bold text-emerald-400">{data.satellite.ndvi.toFixed(4)}</div>
                    <div className="text-xs text-white/40">NDVI</div>
                  </div>
                  <div>
                    <div className="text-xl font-bold">{data.satellite.health}</div>
                    <div className="text-xs text-white/40">Status — Trend: {data.satellite.trend}</div>
                  </div>
                  <div>
                    <div className="text-sm text-white/60">{data.satellite.image_date}</div>
                    <div className="text-xs text-white/30">{data.satellite.source}</div>
                  </div>
                </div>
                {/* Satellite Extras */}
                {data.satellite_extras && (
                  <div className="mt-3 flex flex-wrap gap-2 pt-3 border-t border-white/5">
                    {data.satellite_extras.sar?.moisture_class && (
                      <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium border ${
                        data.satellite_extras.sar.moisture_class.toLowerCase().includes("moist") || data.satellite_extras.sar.moisture_class.toLowerCase().includes("wet")
                          ? "bg-sky-500/10 border-sky-500/20 text-sky-400" : "bg-amber-500/10 border-amber-500/20 text-amber-400"
                      }`}>
                        <Radio size={12} />
                        SAR Soil: {data.satellite_extras.sar.moisture_class}
                      </span>
                    )}
                    {data.satellite_extras.lst?.surface_temp_c != null && (
                      <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium border ${
                        data.satellite_extras.lst.heat_stress === "high" || data.satellite_extras.lst.heat_stress === "extreme"
                          ? "bg-red-500/10 border-red-500/20 text-red-400" : "bg-amber-500/10 border-amber-500/20 text-amber-400"
                      }`}>
                        <Thermometer size={12} />
                        Surface: {data.satellite_extras.lst.surface_temp_c}°C
                        {data.satellite_extras.lst.heat_stress && ` (${data.satellite_extras.lst.heat_stress})`}
                      </span>
                    )}
                    {data.satellite_extras.smap?.rootzone_class && (
                      <span className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium border bg-sky-500/10 border-sky-500/20 text-sky-400">
                        <Droplets size={12} />
                        Root Zone: {data.satellite_extras.smap.rootzone_class}
                      </span>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Best Mandi */}
            <div className="glass-card p-5 border border-yellow-500/20">
              <div className="flex items-center gap-3 mb-3">
                <TrendingUp size={20} className="text-yellow-400" />
                <h3 className="font-bold text-lg">Best Mandi (Real AgMarkNet Prices)</h3>
                {data.price_trend?.direction && (
                  <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-bold ${
                    data.price_trend.direction === "rising" ? "bg-emerald-500/10 border border-emerald-500/20 text-emerald-400" :
                    data.price_trend.direction === "falling" ? "bg-red-500/10 border border-red-500/20 text-red-400" :
                    "bg-white/5 border border-white/10 text-white/50"
                  }`}>
                    {data.price_trend.direction === "rising" ? "↑" : data.price_trend.direction === "falling" ? "↓" : "→"}
                    {" "}{data.price_trend.direction}
                    {data.price_trend.percentage != null && ` ${data.price_trend.percentage.toFixed(1)}%`}
                  </span>
                )}
              </div>
              <div className="flex items-end gap-4 mb-3">
                <div>
                  <div className="text-3xl font-bold text-yellow-400">{bestMandi?.market}</div>
                  <div className="text-2xl font-bold text-emerald-400">₹{bestMandi?.modal_price?.toLocaleString()}/qtl</div>
                </div>
                <div className="text-sm text-white/50">
                  {bestMandi?.distance_km?.toFixed(0)} km away · {bestMandi?.duration_text}
                </div>
              </div>
              {localMandi && priceAdv > 0 && (
                <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/20 p-3 text-sm">
                  vs local {localMandi.market} at ₹{localMandi.modal_price?.toLocaleString()}/qtl →
                  <span className="text-emerald-400 font-bold ml-1">₹{priceAdv.toLocaleString()} more/qtl</span>
                  <span className="text-white/40 ml-1">(₹{(priceAdv * 10).toLocaleString()} extra for 10 quintals)</span>
                </div>
              )}

              {/* All mandis table */}
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-white/40 border-b border-white/10">
                      <th className="text-left py-2">Mandi</th>
                      <th className="text-right py-2">Price</th>
                      <th className="text-right py-2">Distance</th>
                      <th className="text-right py-2">Transport</th>
                      <th className="text-right py-2 text-emerald-400">Net Profit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data.mandi_prices || []).sort((a, b) => b.net_profit_per_quintal - a.net_profit_per_quintal).map((m, i) => (
                      <tr key={i} className={`border-b border-white/5 ${i === 0 ? "bg-emerald-500/10" : ""}`}>
                        <td className="py-2 font-medium">{i === 0 ? "🏆 " : ""}{m.market}</td>
                        <td className="text-right py-2">₹{m.modal_price?.toLocaleString()}</td>
                        <td className="text-right py-2 text-white/50">{m.distance_km?.toFixed(0)} km</td>
                        <td className="text-right py-2 text-red-400/60">₹{m.transport_cost_per_quintal?.toFixed(0)}</td>
                        <td className="text-right py-2 font-bold text-emerald-400">₹{m.net_profit_per_quintal?.toFixed(0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Weather */}
            <div className="glass-card p-5 border border-sky-500/20">
              <div className="flex items-center gap-3 mb-3">
                <Thermometer size={20} className="text-sky-400" />
                <h3 className="font-bold text-lg">5-Day Weather (Real Open-Meteo)</h3>
              </div>
              <div className="flex gap-3 overflow-x-auto pb-1">
                {data.weather.daily_forecast.map((d, i) => (
                  <div key={i} className="flex-shrink-0 text-center bg-white/5 rounded-xl px-4 py-3 min-w-[90px]">
                    <div className="text-xs text-white/40 mb-1">{d.date.split("-").slice(1).join("/")}</div>
                    {d.precipitation_mm > 0 ? (
                      <CloudRain size={24} className="mx-auto mb-1 text-sky-400" />
                    ) : (
                      <Sun size={24} className="mx-auto mb-1 text-amber-400" />
                    )}
                    <div className="text-sm font-bold">{d.max_temp_c}°</div>
                    <div className="text-xs text-white/40">{d.min_temp_c}°</div>
                    {d.precipitation_mm > 0 && (
                      <div className="text-xs text-sky-400 mt-0.5">
                        <Droplets size={10} className="inline mr-0.5" />{d.precipitation_mm}mm
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Advisory */}
            <div className="glass-card p-5 border border-emerald-500/20">
              <div className="flex items-center gap-3 mb-3">
                <Volume2 size={20} className="text-emerald-400" />
                <h3 className="font-bold text-lg">Gemini 3.1 Pro Advisory (Hindi)</h3>
                {data.confidence && (
                  <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide ${
                    data.confidence === "HIGH" ? "bg-emerald-500/15 border border-emerald-500/25 text-emerald-400" :
                    data.confidence === "MEDIUM" ? "bg-yellow-500/15 border border-yellow-500/25 text-yellow-400" :
                    "bg-red-500/15 border border-red-500/25 text-red-400"
                  }`}>
                    <ShieldCheck size={10} />
                    {data.confidence} Confidence
                  </span>
                )}
              </div>
              <div className="text-sm leading-relaxed text-white/80 whitespace-pre-wrap">
                {data.advisory}
              </div>
              <button
                onClick={() => playTTS(data.advisory, "hi")}
                className="mt-3 flex items-center gap-2 rounded-lg bg-emerald-500/20 border border-emerald-500/30 px-4 py-2 text-sm text-emerald-400 hover:bg-emerald-500/30"
              >
                <Volume2 size={14} /> Play again
              </button>
            </div>

            {/* Cross-Validation Alerts */}
            {data.cross_validation && data.cross_validation.length > 0 && (
              <div className="space-y-2">
                {data.cross_validation.map((cv, i) => {
                  const colorMap: Record<string, string> = {
                    WARNING: "border-amber-500/30 bg-amber-500/10 text-amber-400",
                    CONFLICT: "border-red-500/30 bg-red-500/10 text-red-400",
                    AGREEMENT: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400",
                    CAVEAT: "border-sky-500/30 bg-sky-500/10 text-sky-400",
                  };
                  const colors = colorMap[cv.type] || colorMap.CAVEAT;
                  return (
                    <div key={i} className={`flex items-start gap-3 rounded-xl border p-4 text-sm ${colors}`}>
                      <Info size={16} className="mt-0.5 shrink-0" />
                      <div>
                        <span className="font-bold text-[10px] uppercase tracking-wider mr-2">{cv.type}</span>
                        {cv.message}
                        {cv.source && <span className="ml-1 text-[10px] opacity-60">({cv.source})</span>}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Nearest KVK */}
            {data.nearest_kvk?.name && (
              <div className="glass-card p-5 border border-sky-500/10">
                <div className="flex items-center gap-3 mb-3">
                  <Phone size={20} className="text-sky-400" />
                  <h3 className="font-bold text-lg">Nearest KVK (Krishi Vigyan Kendra)</h3>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
                  <div>
                    <div className="font-semibold text-white/90">{data.nearest_kvk.name}</div>
                    {data.nearest_kvk.district && <div className="text-xs text-white/40">{data.nearest_kvk.district}</div>}
                    {data.nearest_kvk.distance_km != null && (
                      <div className="text-xs text-white/40 mt-0.5">{data.nearest_kvk.distance_km.toFixed(1)} km away</div>
                    )}
                  </div>
                  <div className="space-y-1">
                    {data.nearest_kvk.phone && (
                      <div className="text-xs text-white/60">
                        KVK: <a href={`tel:${data.nearest_kvk.phone}`} className="text-sky-400 underline">{data.nearest_kvk.phone}</a>
                      </div>
                    )}
                    <div className="text-xs text-white/60">
                      Kisan Helpline: <a href="tel:18001801551" className="text-sky-400 underline">1800-180-1551</a> (Toll Free)
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Data sources */}
            <div className="glass-card p-5">
              <h3 className="font-bold text-sm mb-3 text-white/60">Data Sources — All Real, Zero Fake</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-white/40">
                {Object.entries(data.sources || {}).map(([key, val]) => (
                  <div key={key} className="flex items-center gap-2">
                    <CheckCircle size={12} className="text-emerald-400 shrink-0" />
                    <span className="text-white/60">{key}:</span> {val}
                  </div>
                ))}
              </div>
            </div>

            {/* CTA */}
            <div className="flex flex-col sm:flex-row gap-3">
              <button onClick={runDemo} className="flex-1 flex items-center justify-center gap-2 rounded-xl bg-healthy/20 border border-healthy/30 py-4 text-lg font-bold text-healthy hover:bg-healthy/30">
                <Play size={20} /> Run Again
              </button>
              <Link href="/talk" className="flex-1 flex items-center justify-center gap-2 rounded-xl bg-sky/20 border border-sky/30 py-4 text-lg font-bold text-sky hover:bg-sky/30">
                <Phone size={20} /> Try Voice Call
              </Link>
              <Link href="/" className="flex-1 flex items-center justify-center gap-2 rounded-xl bg-white/5 border border-white/10 py-4 text-lg font-bold text-white/60 hover:bg-white/10">
                <ChevronRight size={20} /> Dashboard
              </Link>
            </div>
          </div>
        )}
        {/* Powered by footer */}
        <div className="mt-12 mb-4 text-center">
          <div className="text-[10px] uppercase tracking-widest text-white/25 mb-3">Powered by</div>
          <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-xs text-white/40">
            <span className="flex items-center gap-1.5"><Satellite size={12} className="text-emerald-400" /> Google Earth Engine</span>
            <span className="flex items-center gap-1.5"><Volume2 size={12} className="text-sky" /> Gemini 2.5 Pro</span>
            <span className="flex items-center gap-1.5"><TrendingUp size={12} className="text-yellow-400" /> AgMarkNet</span>
            <span className="flex items-center gap-1.5"><Globe size={12} className="text-white/50" /> Cloud TTS</span>
          </div>
        </div>
      </main>
    </div>
  );
}
