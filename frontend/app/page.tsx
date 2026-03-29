"use client";

import { useState, useCallback, useEffect } from "react";
import {
  Satellite,
  TrendingUp,
  CloudSun,
  Store,
  Leaf,
  Search,
  AlertCircle,
} from "lucide-react";
import SatelliteMap from "./components/SatelliteMap";
import NDVIChart from "./components/NDVIChart";
import MandiComparison from "./components/MandiComparison";
import VoiceInput from "./components/VoiceInput";
import WeatherTimeline from "./components/WeatherTimeline";
import AdvisoryCard from "./components/AdvisoryCard";
import type { Advisory } from "./components/AdvisoryCard";
import type { ForecastDay } from "./components/WeatherTimeline";
import useGeolocation from "./hooks/useGeolocation";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface ApiResponse {
  location?: { location_name?: string; state?: string };
  crop?: string;
  mandi_prices?: Array<{
    market: string;
    modal_price: number;
    distance_km: number;
    net_profit_per_quintal: number;
    transport_cost_per_quintal?: number;
    commission_per_quintal?: number;
  }>;
  best_mandi?: { market: string; modal_price: number; distance_km: number; net_profit_per_quintal?: number };
  local_mandi?: { market: string; modal_price: number };
  weather?: {
    daily_forecast?: Array<{
      date: string;
      max_temp_c: number;
      min_temp_c: number;
      precipitation_mm: number;
      condition?: string;
      humidity?: number;
      wind_kph?: number;
    }>;
    summary?: string;
  };
  satellite?: {
    ndvi?: number;
    health?: string;
    trend?: string;
    true_color_url?: string;
    ndvi_color_url?: string;
  };
  advisory?: string;
  sources?: Record<string, unknown>;
  error?: string;
}

function mapApiToState(api: ApiResponse) {
  const locationName = api.location
    ? `${api.location.location_name || "Unknown"}, ${api.location.state || ""}`
    : "Unknown";

  // Build satellite data — prefer structured satellite response, fall back to parsing advisory text
  const satNdvi = api.satellite?.ndvi;
  const ndviFromText = api.advisory?.match(/NDVI[:\s]*([0-9.]+)/i);
  const ndviValue = satNdvi != null ? satNdvi : ndviFromText ? parseFloat(ndviFromText[1]) : 0.65;
  const ndviStatus: "healthy" | "moderate" | "stressed" =
    ndviValue >= 0.6 ? "healthy" : ndviValue >= 0.3 ? "moderate" : "stressed";
  const trueColorUrl = api.satellite?.true_color_url;
  const ndviColorUrl = api.satellite?.ndvi_color_url;

  // Map mandi data
  const bestMandi = api.best_mandi;
  const mandiChartData = (api.mandi_prices || []).map((m) => ({
    name: m.market,
    netProfit: m.net_profit_per_quintal || 0,
    price: m.modal_price,
    transport: m.transport_cost_per_quintal || 0,
    commission: m.commission_per_quintal || 0,
    distance: m.distance_km,
  }));

  // Map weather forecast
  const forecastDays: ForecastDay[] = (api.weather?.daily_forecast || []).map(
    (d, i) => {
      const dayLabels = ["Today", "Tomorrow", "Day 3", "Day 4", "Day 5"];
      const cond = (d.condition || "").toLowerCase();
      const icon: ForecastDay["icon"] = cond.includes("rain")
        ? "rain"
        : cond.includes("cloud") || cond.includes("partly") || cond.includes("overcast")
        ? "cloud"
        : cond.includes("snow")
        ? "snow"
        : "sun";
      return {
        day: dayLabels[i] || `Day ${i + 1}`,
        date: d.date,
        icon,
        tempHigh: d.max_temp_c,
        tempLow: d.min_temp_c,
        humidity: d.humidity ?? 50,
        rain_mm: d.precipitation_mm,
        windSpeed: d.wind_kph ?? 0,
        condition: d.condition,
      };
    }
  );

  // Get current weather from first forecast day
  const today = api.weather?.daily_forecast?.[0];
  const currentWeather = today
    ? {
        temp: today.max_temp_c,
        humidity: today.humidity ?? 50,
        condition: today.condition || "Clear",
      }
    : { temp: 0, humidity: 0, condition: "--" };

  // Parse advisory into action items
  const advisories: Advisory[] = [];
  if (api.advisory) {
    // Simple heuristic: split advisory into sentences and classify
    const sentences = api.advisory.split(/[.।]+/).filter((s) => s.trim().length > 10);
    for (const s of sentences.slice(0, 4)) {
      const lower = s.toLowerCase();
      const isDont = lower.includes("do not") || lower.includes("avoid") || lower.includes("mat") || lower.includes("na ") || lower.includes("don't") || lower.includes("nahi");
      const isWarning = lower.includes("risk") || lower.includes("warn") || lower.includes("alert") || lower.includes("khatr") || lower.includes("savdhan");
      advisories.push({
        type: isDont ? "dont" : isWarning ? "warning" : "do",
        title: s.trim().slice(0, 80),
        description: s.trim(),
        urgency: isDont || isWarning ? "high" : "medium",
      });
    }
  }

  return {
    location: locationName,
    crop: api.crop || "Tomato",
    satellite: { ndvi: ndviValue, status: ndviStatus, trend: "stable" as const, trueColorUrl, ndviColorUrl },
    mandi: {
      bestMandi: bestMandi?.market || "N/A",
      bestPrice: bestMandi?.modal_price || 0,
    },
    weather: { current: currentWeather },
    advisories,
    combinedAdvisory: api.advisory || "",
    combinedAdvisoryEn: api.advisory || "",
    mandiChartData,
    forecastDays,
  };
}

export default function Dashboard() {
  const geo = useGeolocation();
  const [data, setData] = useState<ReturnType<typeof mapApiToState> | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchLocation, setSearchLocation] = useState("");
  const [searchCrop, setSearchCrop] = useState("");
  const [showEnglish, setShowEnglish] = useState(false);
  const [hasFetched, setHasFetched] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);

  // Loading step labels shown during initial fetch
  const LOADING_STEPS = [
    { label: "Detecting your location...", icon: "pin" },
    { label: "Fetching mandi prices from AgMarkNet...", icon: "mandi" },
    { label: "Getting 5-day weather forecast...", icon: "weather" },
    { label: "Analyzing satellite crop health...", icon: "satellite" },
    { label: "Generating personalized advisory...", icon: "advisory" },
  ];

  const fetchAdvisory = useCallback(
    async (text?: string, language?: string) => {
      setIsLoading(true);
      setError(null);
      setLoadingStep(0);
      // Animate through loading steps to show progress
      const stepTimer = setInterval(() => {
        setLoadingStep((prev) => (prev < 4 ? prev + 1 : prev));
      }, 2500);
      try {
        const body: Record<string, unknown> = {
          location: searchLocation || "Solan",
          crop: searchCrop || "Tomato",
          intent: text || "full advisory",
          language: language || "hi-IN",
        };
        if (geo.latitude && geo.longitude) {
          body.latitude = geo.latitude;
          body.longitude = geo.longitude;
        }

        // Fire advisory and NDVI requests in parallel
        const advisoryPromise = fetch(`${API_BASE}/api/advisory`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });

        const ndviBody = {
          latitude: (body.latitude as number) ?? 30.9,
          longitude: (body.longitude as number) ?? 77.1,
        };
        const ndviPromise = fetch(`${API_BASE}/api/ndvi`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(ndviBody),
        }).catch(() => null); // NDVI is optional — don't fail advisory if it errors

        const [res, ndviRes] = await Promise.all([advisoryPromise, ndviPromise]);

        if (!res.ok) {
          const errBody = await res.json().catch(() => ({}));
          throw new Error(errBody.error || `Request failed (${res.status})`);
        }

        const result: ApiResponse = await res.json();
        if (result.error) {
          throw new Error(result.error);
        }

        // Merge NDVI satellite URLs into result if advisory didn't already have them
        if (ndviRes && ndviRes.ok) {
          try {
            const ndviData = await ndviRes.json();
            if (!result.satellite) {
              result.satellite = {};
            }
            if (ndviData.true_color_url && !result.satellite.true_color_url) {
              result.satellite.true_color_url = ndviData.true_color_url;
            }
            if (ndviData.ndvi_color_url && !result.satellite.ndvi_color_url) {
              result.satellite.ndvi_color_url = ndviData.ndvi_color_url;
            }
            if (ndviData.ndvi != null && result.satellite.ndvi == null) {
              result.satellite.ndvi = ndviData.ndvi;
            }
            if (ndviData.health && !result.satellite.health) {
              result.satellite.health = ndviData.health;
            }
            if (ndviData.trend && !result.satellite.trend) {
              result.satellite.trend = ndviData.trend;
            }
          } catch {
            // ignore NDVI parse errors
          }
        }

        clearInterval(stepTimer);
        setData(mapApiToState(result));
        setHasFetched(true);
      } catch (err) {
        clearInterval(stepTimer);
        setError(err instanceof Error ? err.message : "Failed to fetch advisory");
      }
      setIsLoading(false);
    },
    [searchLocation, searchCrop, geo.latitude, geo.longitude]
  );

  // Auto-fetch on first load once geo is ready
  useEffect(() => {
    if (!geo.loading && !hasFetched && !isLoading) {
      fetchAdvisory();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geo.loading]);

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
      {/* Voice-First Banner */}
      <a
        href="/talk"
        className="group mb-8 flex items-center gap-4 rounded-2xl border-2 border-healthy/30 bg-gradient-to-r from-healthy/10 via-healthy/5 to-transparent p-5 sm:p-6 transition-all hover:border-healthy/50 hover:shadow-[0_0_40px_rgba(34,197,94,0.15)] active:scale-[0.99]"
      >
        <div className="flex h-16 w-16 sm:h-20 sm:w-20 shrink-0 items-center justify-center rounded-full bg-healthy/20 text-3xl sm:text-4xl group-hover:bg-healthy/30 transition-colors pulse-ring">
          🎤
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-xl sm:text-2xl font-bold text-white leading-tight">
            किसान भाई, यहाँ टैप करें
          </div>
          <div className="text-base sm:text-lg text-healthy mt-1">
            बोलकर सलाह पाएं — Tap here, speak and get advice
          </div>
          <div className="text-xs text-white/40 mt-1">
            Voice-first advisory in 22 Indian languages
          </div>
        </div>
        <div className="hidden sm:flex h-12 w-12 items-center justify-center rounded-full bg-healthy text-kisan-dark text-xl font-bold">
          →
        </div>
      </a>

      {/* Hero */}
      <div className="mb-8">
        <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
              <span className="gradient-text">Farm Intelligence</span>
            </h1>
            <p className="mt-1 text-sm text-white/40">
              Satellite + Weather + Mandi = Smart Farming Decisions
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs text-white/40">
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-healthy" />
            {data ? `Live Data -- ${data.location}` : "Loading..."}
          </div>
        </div>

        {/* Search bar */}
        <div className="mb-6 flex flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <Search
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30"
            />
            <input
              type="text"
              placeholder="Location (e.g., Solan, Coorg, Punjab)"
              value={searchLocation}
              onChange={(e) => setSearchLocation(e.target.value)}
              className="w-full rounded-xl border border-white/10 bg-white/5 py-3 pl-10 pr-4 text-sm text-white placeholder-white/30 outline-none transition-colors focus:border-healthy/40"
            />
          </div>
          <div className="relative flex-1">
            <Leaf
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30"
            />
            <input
              type="text"
              placeholder="Crop (e.g., Tomato, Wheat, Coffee)"
              value={searchCrop}
              onChange={(e) => setSearchCrop(e.target.value)}
              className="w-full rounded-xl border border-white/10 bg-white/5 py-3 pl-10 pr-4 text-sm text-white placeholder-white/30 outline-none transition-colors focus:border-healthy/40"
            />
          </div>
          <button
            onClick={() => fetchAdvisory()}
            disabled={isLoading}
            className="flex items-center justify-center gap-2 rounded-xl bg-healthy px-6 py-3 text-sm font-semibold text-kisan-dark transition-all hover:bg-healthy/90 disabled:opacity-50"
          >
            {isLoading ? (
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-kisan-dark border-t-transparent" />
            ) : (
              <Satellite size={16} />
            )}
            Analyze
          </button>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="mb-6 flex items-center gap-3 rounded-xl border border-stressed/30 bg-stressed/10 px-4 py-3 text-sm text-stressed">
            <AlertCircle size={18} />
            <span>{error}</span>
            <button
              onClick={() => fetchAdvisory()}
              className="ml-auto rounded-lg bg-stressed/20 px-3 py-1 text-xs font-medium hover:bg-stressed/30"
            >
              Retry
            </button>
          </div>
        )}

        {/* Loading progress indicator */}
        {isLoading && !data ? (
          <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-kisan-dark-2 p-6 sm:p-8">
            <div className="mb-4 text-sm font-medium text-white/60">Loading real data...</div>
            <div className="space-y-3">
              {LOADING_STEPS.map((s, i) => (
                <div key={i} className="flex items-center gap-3">
                  <div className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full transition-all duration-500 ${
                    i < loadingStep ? "bg-healthy/20" : i === loadingStep ? "bg-healthy/30 ring-2 ring-healthy/40" : "bg-white/5"
                  }`}>
                    {i < loadingStep ? (
                      <svg className="h-3.5 w-3.5 text-healthy" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}><path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" /></svg>
                    ) : i === loadingStep ? (
                      <div className="h-2.5 w-2.5 rounded-full bg-healthy animate-pulse" />
                    ) : (
                      <div className="h-2 w-2 rounded-full bg-white/20" />
                    )}
                  </div>
                  <span className={`text-sm transition-colors duration-500 ${
                    i < loadingStep ? "text-healthy/70" : i === loadingStep ? "text-white/90 font-medium" : "text-white/30"
                  }`}>{s.label}</span>
                </div>
              ))}
            </div>
            <div className="mt-5 h-1.5 w-full rounded-full bg-white/5 overflow-hidden">
              <div className="h-full rounded-full bg-gradient-to-r from-healthy to-sky transition-all duration-700 ease-out" style={{ width: `${((loadingStep + 1) / LOADING_STEPS.length) * 100}%` }} />
            </div>
          </div>
        ) : (
          <SatelliteMap
            location={data?.location || "Loading..."}
            ndvi={data?.satellite.ndvi ?? 0}
            status={data?.satellite.status ?? "moderate"}
            imageUrl={data?.satellite.trueColorUrl}
          />
        )}
      </div>

      {/* Stat Cards */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div className="glass-card glass-card-hover glow-green p-5">
          <div className="mb-3 flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-healthy/10">
              <TrendingUp size={16} className="text-healthy" />
            </div>
            <span className="text-xs font-medium uppercase tracking-wider text-white/40">
              NDVI Index
            </span>
          </div>
          {isLoading && !data ? (
            <div className="h-9 w-20 rounded-lg shimmer" />
          ) : (
            <>
              <div className="text-3xl font-bold tabular-nums text-healthy">
                {(data?.satellite.ndvi ?? 0).toFixed(2)}
              </div>
              <div className="mt-1 text-xs capitalize text-white/50">
                {data?.satellite.status || "--"} -- Trend: {data?.satellite.trend || "--"}
              </div>
            </>
          )}
        </div>

        <div className="glass-card glass-card-hover glow-blue p-5">
          <div className="mb-3 flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky/10">
              <CloudSun size={16} className="text-sky" />
            </div>
            <span className="text-xs font-medium uppercase tracking-wider text-white/40">
              Weather
            </span>
          </div>
          {isLoading && !data ? (
            <div className="h-9 w-20 rounded-lg shimmer" />
          ) : (
            <>
              <div className="text-3xl font-bold tabular-nums text-sky">
                {data?.weather.current.temp ?? "--"}°C
              </div>
              <div className="mt-1 text-xs text-white/50">
                Humidity {data?.weather.current.humidity ?? "--"}% --{" "}
                {data?.weather.current.condition || "--"}
              </div>
            </>
          )}
        </div>

        <div className="glass-card glass-card-hover p-5" style={{ boxShadow: "0 0 20px rgba(234,179,8,0.1)" }}>
          <div className="mb-3 flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-moderate/10">
              <Store size={16} className="text-moderate" />
            </div>
            <span className="text-xs font-medium uppercase tracking-wider text-white/40">
              Best Mandi
            </span>
          </div>
          {isLoading && !data ? (
            <div className="h-9 w-24 rounded-lg shimmer" />
          ) : (
            <>
              <div className="text-3xl font-bold tabular-nums text-moderate">
                {data?.mandi.bestPrice ? `₹${data.mandi.bestPrice.toLocaleString()}` : "--"}
              </div>
              <div className="mt-1 text-xs text-white/50">
                {data?.mandi.bestMandi || "--"} -- per quintal
              </div>
            </>
          )}
        </div>
      </div>

      {/* Voice Input */}
      <div className="mb-8">
        <VoiceInput onSubmit={fetchAdvisory} isLoading={isLoading} />
      </div>

      {/* Combined Advisory */}
      <div className="mb-8 glass-card p-5 sm:p-6 border border-healthy/10">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-bold text-white/90">
            🌾 AI Advisory Summary
          </h2>
          <button
            onClick={() => setShowEnglish(!showEnglish)}
            className="rounded-lg bg-white/5 px-3 py-1.5 text-xs font-medium text-white/50 transition-colors hover:bg-white/10 hover:text-white/70"
          >
            {showEnglish ? "हिंदी" : "English"}
          </button>
        </div>
        {isLoading && !data ? (
          <div className="space-y-2">
            <div className="h-4 w-full rounded shimmer" />
            <div className="h-4 w-3/4 rounded shimmer" />
          </div>
        ) : (
          <p className="text-sm leading-relaxed text-white/70">
            {data?.combinedAdvisory || "Click Analyze to get advisory."}
          </p>
        )}
        {isLoading && <div className="mt-3 h-1 w-full shimmer rounded-full" />}
      </div>

      {/* Charts Grid */}
      <div className="mb-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <NDVIChart />
        {data?.mandiChartData && data.mandiChartData.length > 0 ? (
          <MandiComparison data={data.mandiChartData} />
        ) : (
          <MandiComparison />
        )}
      </div>

      {/* Weather Timeline */}
      <div className="mb-8">
        <h2 className="mb-4 text-lg font-bold text-white/90">
          5-Day Weather Forecast
        </h2>
        {isLoading && !data ? (
          <div className="flex gap-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="min-w-[150px] h-48 rounded-xl shimmer" />
            ))}
          </div>
        ) : data?.forecastDays && data.forecastDays.length > 0 ? (
          <WeatherTimeline forecast={data.forecastDays} />
        ) : (
          <WeatherTimeline />
        )}
      </div>

      {/* Advisory Cards */}
      <div className="mb-8">
        <h2 className="mb-4 text-lg font-bold text-white/90">
          Action Items
        </h2>
        {isLoading && !data ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-24 rounded-xl shimmer" />
            ))}
          </div>
        ) : data?.advisories && data.advisories.length > 0 ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {data.advisories.map((adv, i) => (
              <AdvisoryCard key={i} {...adv} />
            ))}
          </div>
        ) : (
          <p className="text-sm text-white/40">No action items yet. Click Analyze to get advice.</p>
        )}
      </div>
    </div>
  );
}
