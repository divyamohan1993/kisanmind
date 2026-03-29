"use client";

import { useState, useEffect, useCallback } from "react";
import WeatherTimeline from "../components/WeatherTimeline";
import AdvisoryCard from "../components/AdvisoryCard";
import useGeolocation from "../hooks/useGeolocation";
import { AlertCircle, AlertTriangle, Phone, MapPin, Sprout } from "lucide-react";

import type { ForecastDay } from "../components/WeatherTimeline";
import type { Advisory } from "../components/AdvisoryCard";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface GrowthStage {
  stage_name?: string;
  day_number?: number;
  total_days?: number;
  description?: string;
}

interface CrossValidation {
  warnings?: string[];
  flags?: string[];
  confidence?: string;
}

interface NearestKVK {
  name?: string;
  distance_km?: number;
  phone?: string;
  district?: string;
}

interface ApiResponse {
  crop?: string;
  location?: { location_name?: string; state?: string };
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
  advisory?: string;
  error?: string;
  growth_stage?: GrowthStage;
  cross_validation?: CrossValidation;
  nearest_kvk?: NearestKVK;
}

const CROPS = ["Tomato", "Wheat", "Rice", "Apple", "Coffee"];

export default function WeatherPage() {
  const geo = useGeolocation();
  const [crop, setCrop] = useState("Tomato");
  const [apiData, setApiData] = useState<ApiResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      if (!geo.latitude || !geo.longitude) {
        throw new Error("Location not available. Please allow GPS access.");
      }
      const body: Record<string, unknown> = {
        crop,
        intent: "weather advisory",
        language: "hi-IN",
        latitude: geo.latitude,
        longitude: geo.longitude,
      };

      const res = await fetch(`${API_BASE}/api/advisory`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.error || `Request failed (${res.status})`);
      }

      const result: ApiResponse = await res.json();
      if (result.error) throw new Error(result.error);
      setApiData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch weather data");
    }
    setIsLoading(false);
  }, [crop, geo.latitude, geo.longitude]);

  useEffect(() => {
    if (!geo.loading) {
      fetchData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geo.loading, crop]);

  // Map API weather to ForecastDay[]
  const forecast: ForecastDay[] = (apiData?.weather?.daily_forecast || []).map(
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
        alert:
          d.precipitation_mm > 10
            ? `Heavy rain (${d.precipitation_mm}mm) -- protect crops!`
            : undefined,
      };
    }
  );

  // Derive weather summary stats
  const allTempsHigh = forecast.map((f) => f.tempHigh ?? 0);
  const allTempsLow = forecast.map((f) => f.tempLow ?? 0);
  const totalRain = forecast.reduce((sum, f) => sum + (f.rain_mm ?? 0), 0);
  const allHumidity = forecast.map((f) => f.humidity);
  const allWind = forecast.map((f) => f.windSpeed ?? 0);
  const tempMin = allTempsLow.length ? Math.min(...allTempsLow) : 0;
  const tempMax = allTempsHigh.length ? Math.max(...allTempsHigh) : 0;
  const humidityMin = allHumidity.length ? Math.min(...allHumidity) : 0;
  const humidityMax = allHumidity.length ? Math.max(...allHumidity) : 0;
  const windMin = allWind.length ? Math.min(...allWind) : 0;
  const windMax = allWind.length ? Math.max(...allWind) : 0;

  // Parse advisory text into action items
  const advisories: Advisory[] = [];
  if (apiData?.advisory) {
    const sentences = apiData.advisory.split(/[.।]+/).filter((s) => s.trim().length > 10);
    for (const s of sentences.slice(0, 6)) {
      const lower = s.toLowerCase();
      const isDont =
        lower.includes("do not") || lower.includes("avoid") || lower.includes("don't") ||
        lower.includes("mat ") || lower.includes("na ") || lower.includes("nahi") || lower.includes("skip");
      const isWarning =
        lower.includes("risk") || lower.includes("warn") || lower.includes("alert") ||
        lower.includes("khatr") || lower.includes("savdhan") || lower.includes("drain");
      advisories.push({
        type: isDont ? "dont" : isWarning ? "warning" : "do",
        title: s.trim().slice(0, 80),
        description: s.trim(),
        urgency: isDont || isWarning ? "high" : "medium",
      });
    }
  }

  const locationLabel = apiData?.location
    ? `${apiData.location.location_name || "Unknown"}, ${apiData.location.state || ""}`
    : "Loading...";

  return (
    <div className="min-h-screen text-white">
      <main className="max-w-7xl mx-auto px-4 py-8 space-y-8">
        {/* Title + Crop Selector */}
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h2 className="text-3xl font-bold">Weather Advisory</h2>
            <p className="text-white/50 mt-1">{locationLabel} — 5-day forecast</p>
          </div>
          <select
            value={crop}
            onChange={(e) => setCrop(e.target.value)}
            className="bg-white/10 border border-white/20 rounded-xl px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
          >
            {CROPS.map((c) => (
              <option key={c} value={c} className="bg-gray-900">
                {c}
              </option>
            ))}
          </select>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="flex items-center gap-3 rounded-xl border border-stressed/30 bg-stressed/10 px-4 py-3 text-sm text-stressed">
            <AlertCircle size={18} />
            <span>{error}</span>
            <button
              onClick={fetchData}
              className="ml-auto rounded-lg bg-stressed/20 px-3 py-1 text-xs font-medium hover:bg-stressed/30"
            >
              Retry
            </button>
          </div>
        )}

        {/* Cross-Validation Weather Alerts */}
        {!isLoading && apiData?.cross_validation && (() => {
          const allAlerts = [
            ...(apiData.cross_validation.warnings || []),
            ...(apiData.cross_validation.flags || []),
          ];
          if (allAlerts.length === 0) return null;
          return (
            <div className="space-y-2">
              {allAlerts.map((alert, i) => (
                <div key={i} className="flex items-center gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-400">
                  <AlertTriangle size={18} className="shrink-0" />
                  <span>{alert.replace(/_/g, " ")}</span>
                </div>
              ))}
            </div>
          );
        })()}

        {/* Growth Stage */}
        {!isLoading && apiData?.growth_stage && (
          <div className="bg-gradient-to-r from-lime-500/15 to-emerald-600/15 border border-lime-500/30 rounded-2xl p-5">
            <div className="flex items-center gap-3 mb-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-lime-500/20">
                <Sprout size={22} className="text-lime-400" />
              </div>
              <div>
                <p className="text-xs text-white/50 uppercase tracking-wider">Crop Stage</p>
                <p className="text-xl font-bold text-lime-300">
                  {apiData.growth_stage.stage_name || "Unknown"}
                  {apiData.growth_stage.day_number != null && (
                    <span className="text-base font-normal text-white/50 ml-2">(Day {apiData.growth_stage.day_number})</span>
                  )}
                </p>
              </div>
            </div>
            {apiData.growth_stage.description && (
              <p className="text-sm text-white/60 mb-3">{apiData.growth_stage.description}</p>
            )}
            {apiData.growth_stage.day_number != null && apiData.growth_stage.total_days != null && apiData.growth_stage.total_days > 0 && (
              <div className="mt-2">
                <div className="flex justify-between text-xs text-white/40 mb-1">
                  <span>Day {apiData.growth_stage.day_number}</span>
                  <span>{apiData.growth_stage.total_days} days total</span>
                </div>
                <div className="w-full h-2.5 rounded-full bg-white/10">
                  <div
                    className="h-2.5 rounded-full bg-gradient-to-r from-lime-500 to-emerald-400 transition-all"
                    style={{ width: `${Math.min(100, (apiData.growth_stage.day_number / apiData.growth_stage.total_days) * 100)}%` }}
                  />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Weather Summary Banner */}
        {isLoading ? (
          <div className="h-28 rounded-2xl shimmer" />
        ) : forecast.length > 0 ? (
          <div className="bg-gradient-to-r from-sky-500/20 to-blue-600/20 border border-sky-500/30 rounded-2xl p-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p className="text-white/50 text-xs uppercase tracking-wider">Temperature</p>
                <p className="text-2xl font-bold">{tempMin}° — {tempMax}°C</p>
              </div>
              <div>
                <p className="text-white/50 text-xs uppercase tracking-wider">Rain Expected</p>
                <p className="text-2xl font-bold text-sky-400">{totalRain.toFixed(0)}mm</p>
                {apiData?.weather?.summary && (
                  <p className="text-xs text-white/40">{apiData.weather.summary}</p>
                )}
              </div>
              <div>
                <p className="text-white/50 text-xs uppercase tracking-wider">Humidity</p>
                <p className="text-2xl font-bold">{humidityMin}-{humidityMax}%</p>
              </div>
              <div>
                <p className="text-white/50 text-xs uppercase tracking-wider">Wind</p>
                <p className="text-2xl font-bold">{windMin}-{windMax} km/h</p>
              </div>
            </div>
          </div>
        ) : null}

        {/* 5-Day Forecast Timeline */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
          <h3 className="text-xl font-semibold mb-4">5-Day Forecast</h3>
          {isLoading ? (
            <div className="flex gap-3">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="min-w-[150px] h-48 rounded-xl shimmer" />
              ))}
            </div>
          ) : forecast.length > 0 ? (
            <WeatherTimeline forecast={forecast} />
          ) : (
            <p className="text-white/40 text-sm">No forecast data available.</p>
          )}
        </div>

        {/* Farming Advisories */}
        <div>
          <h3 className="text-xl font-semibold mb-4">Farming Actions for {crop}</h3>
          {isLoading ? (
            <div className="grid gap-4 md:grid-cols-2">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="h-24 rounded-xl shimmer" />
              ))}
            </div>
          ) : advisories.length > 0 ? (
            <div className="grid gap-4 md:grid-cols-2">
              {advisories.map((a, i) => (
                <AdvisoryCard key={i} type={a.type} title={a.title} description={a.description} urgency={a.urgency} />
              ))}
            </div>
          ) : (
            <p className="text-white/40 text-sm">No advisories available.</p>
          )}
        </div>

        {/* Crop-Weather Thresholds */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
          <h3 className="text-lg font-semibold mb-3">{crop} Weather Thresholds</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-3">
              <p className="text-red-400 font-medium text-xs uppercase">Frost Damage</p>
              <p className="text-white mt-1">&lt; 10°C</p>
            </div>
            <div className="bg-orange-500/10 border border-orange-500/20 rounded-xl p-3">
              <p className="text-orange-400 font-medium text-xs uppercase">Heat Stress</p>
              <p className="text-white mt-1">&gt; 40°C</p>
            </div>
            <div className="bg-sky-500/10 border border-sky-500/20 rounded-xl p-3">
              <p className="text-sky-400 font-medium text-xs uppercase">Heavy Rain</p>
              <p className="text-white mt-1">&gt; 20mm → harvest</p>
            </div>
            <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-xl p-3">
              <p className="text-yellow-400 font-medium text-xs uppercase">Fungal Risk</p>
              <p className="text-white mt-1">&gt; 85% humidity</p>
            </div>
          </div>
        </div>

        {/* Nearest KVK */}
        {apiData?.nearest_kvk && (
          <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
            <div className="flex items-center gap-3 mb-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-sky-500/20">
                <MapPin size={20} className="text-sky-400" />
              </div>
              <div>
                <h3 className="text-lg font-semibold">Nearest KVK</h3>
                <p className="text-xs text-white/40">Krishi Vigyan Kendra</p>
              </div>
            </div>
            <div className="space-y-2 text-sm">
              {apiData.nearest_kvk.name && (
                <p className="text-white/90 font-medium">{apiData.nearest_kvk.name}</p>
              )}
              {apiData.nearest_kvk.district && (
                <p className="text-white/50">District: {apiData.nearest_kvk.district}</p>
              )}
              {apiData.nearest_kvk.distance_km != null && (
                <p className="text-white/50">{apiData.nearest_kvk.distance_km} km away</p>
              )}
              {apiData.nearest_kvk.phone && (
                <a
                  href={`tel:${apiData.nearest_kvk.phone}`}
                  className="inline-flex items-center gap-2 mt-2 rounded-lg bg-sky-500/20 border border-sky-500/30 px-4 py-2 text-sky-400 hover:bg-sky-500/30 transition"
                >
                  <Phone size={14} />
                  {apiData.nearest_kvk.phone}
                </a>
              )}
            </div>
          </div>
        )}

        {/* Source */}
        <p className="text-xs text-white/30 text-center">
          Source: Google Weather API. Forecast accuracy decreases beyond 3 days. Always combine with local observation.
        </p>
      </main>
    </div>
  );
}
