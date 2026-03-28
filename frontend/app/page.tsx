"use client";

import { useState, useCallback } from "react";
import {
  Satellite,
  TrendingUp,
  CloudSun,
  Store,
  Leaf,
  Search,
} from "lucide-react";
import SatelliteMap from "./components/SatelliteMap";
import NDVIChart from "./components/NDVIChart";
import MandiComparison from "./components/MandiComparison";
import VoiceInput from "./components/VoiceInput";
import WeatherTimeline from "./components/WeatherTimeline";
import AdvisoryCard from "./components/AdvisoryCard";
import type { Advisory } from "./components/AdvisoryCard";

// Default demo data so the page works standalone
const DEFAULT_DATA = {
  location: "Solan, Himachal Pradesh",
  crop: "Tomato",
  satellite: { ndvi: 0.72, status: "healthy" as const, trend: "stable" },
  mandi: { bestMandi: "Shimla", bestPrice: 2400 },
  weather: { current: { temp: 28, humidity: 45, condition: "sunny" } },
  advisories: [
    {
      type: "do" as const,
      title: "Harvest tomatoes tomorrow",
      description:
        "Heavy rain forecast for Sunday. Harvest ripe tomatoes by Saturday evening to prevent damage.",
      urgency: "high" as const,
    },
    {
      type: "do" as const,
      title: "Sell at Shimla mandi",
      description:
        "Best net profit of Rs 2,040/quintal at Shimla vs Rs 1,560 at local Solan mandi.",
      urgency: "medium" as const,
    },
    {
      type: "dont" as const,
      title: "Do not spray pesticides this week",
      description:
        "Rain on Sunday-Monday will wash away any spray. Wait until Tuesday.",
      urgency: "high" as const,
    },
    {
      type: "warning" as const,
      title: "Late blight risk increasing",
      description:
        "High humidity combined with rain creates ideal conditions for late blight. Apply Mancozeb after rains.",
      urgency: "medium" as const,
    },
  ] as Advisory[],
  combinedAdvisory:
    "किसान भाई, आपकी टमाटर की फसल स्वस्थ है (NDVI: 0.72)। रविवार को भारी बारिश की संभावना है, इसलिए कल तक पके टमाटर काट लें। शिमला मंडी में ₹2,400/क्विंटल का भाव मिल रहा है जो सबसे अच्छा है। इस हफ्ते छिड़काव न करें।",
  combinedAdvisoryEn:
    "Your tomato crop is healthy (NDVI: 0.72). Heavy rain expected Sunday - harvest by tomorrow. Shimla mandi offers the best price at Rs 2,400/quintal. Do not spray this week.",
};

export default function Dashboard() {
  const [data, setData] = useState(DEFAULT_DATA);
  const [isLoading, setIsLoading] = useState(false);
  const [searchLocation, setSearchLocation] = useState("");
  const [searchCrop, setSearchCrop] = useState("");
  const [showEnglish, setShowEnglish] = useState(false);

  const fetchAdvisory = useCallback(
    async (text?: string, language?: string) => {
      setIsLoading(true);
      try {
        const res = await fetch("/api/advisory", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            location: searchLocation || "Solan",
            crop: searchCrop || "Tomato",
            intent: text || "full advisory",
            language: language || "hi-IN",
          }),
        });
        const result = await res.json();
        setData({
          ...DEFAULT_DATA,
          ...result,
          satellite: { ...DEFAULT_DATA.satellite, ...result.satellite },
          mandi: { ...DEFAULT_DATA.mandi, ...result.mandi },
          weather: { ...DEFAULT_DATA.weather, ...result.weather },
          advisories: result.advisories || DEFAULT_DATA.advisories,
          combinedAdvisory:
            result.combinedAdvisory || DEFAULT_DATA.combinedAdvisory,
          combinedAdvisoryEn:
            result.combinedAdvisoryEn || DEFAULT_DATA.combinedAdvisoryEn,
        });
      } catch {
        // Keep demo data on error
      }
      setIsLoading(false);
    },
    [searchLocation, searchCrop]
  );

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
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
            Live Data -- {data.location}
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

        {/* Satellite View */}
        <SatelliteMap
          location={data.location}
          ndvi={data.satellite.ndvi}
          status={data.satellite.status}
        />
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
          <div className="text-3xl font-bold tabular-nums text-healthy">
            {data.satellite.ndvi.toFixed(2)}
          </div>
          <div className="mt-1 text-xs capitalize text-white/50">
            {data.satellite.status} -- Trend: {data.satellite.trend}
          </div>
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
          <div className="text-3xl font-bold tabular-nums text-sky">
            {data.weather.current.temp}°C
          </div>
          <div className="mt-1 text-xs text-white/50">
            Humidity {data.weather.current.humidity}% --{" "}
            {data.weather.current.condition}
          </div>
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
          <div className="text-3xl font-bold tabular-nums text-moderate">
            ₹{data.mandi.bestPrice.toLocaleString()}
          </div>
          <div className="mt-1 text-xs text-white/50">
            {data.mandi.bestMandi} -- per quintal
          </div>
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
        <p className="text-sm leading-relaxed text-white/70">
          {showEnglish ? data.combinedAdvisoryEn : data.combinedAdvisory}
        </p>
        {isLoading && <div className="mt-3 h-1 w-full shimmer rounded-full" />}
      </div>

      {/* Charts Grid */}
      <div className="mb-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <NDVIChart />
        <MandiComparison />
      </div>

      {/* Weather Timeline */}
      <div className="mb-8">
        <h2 className="mb-4 text-lg font-bold text-white/90">
          5-Day Weather Forecast
        </h2>
        <WeatherTimeline />
      </div>

      {/* Advisory Cards */}
      <div className="mb-8">
        <h2 className="mb-4 text-lg font-bold text-white/90">
          Action Items
        </h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {data.advisories.map((adv, i) => (
            <AdvisoryCard key={i} {...adv} />
          ))}
        </div>
      </div>
    </div>
  );
}
