"use client";

import { useState } from "react";
import WeatherTimeline from "../components/WeatherTimeline";
import AdvisoryCard from "../components/AdvisoryCard";

import type { ForecastDay } from "../components/WeatherTimeline";

const FORECAST: ForecastDay[] = [
  { day: "Today", date: "Mar 28", icon: "sun", tempHigh: 28, tempLow: 15, humidity: 65, rainProb: 5, windSpeed: 8 },
  { day: "Tomorrow", date: "Mar 29", icon: "cloud", tempHigh: 26, tempLow: 14, humidity: 72, rainProb: 20, windSpeed: 10 },
  { day: "Day 3", date: "Mar 30", icon: "rain", tempHigh: 22, tempLow: 13, humidity: 88, rainProb: 85, windSpeed: 15, alert: "Heavy rain — harvest ripe tomatoes!" },
  { day: "Day 4", date: "Mar 31", icon: "rain", tempHigh: 20, tempLow: 12, humidity: 85, rainProb: 70, windSpeed: 12, alert: "Do not spray pesticides" },
  { day: "Day 5", date: "Apr 1", icon: "cloud", tempHigh: 25, tempLow: 14, humidity: 68, rainProb: 15, windSpeed: 7 },
];

const ADVISORIES = [
  { type: "do" as const, title: "Harvest ripe tomatoes tomorrow morning", description: "15mm rain forecast on Day 3 can cause fruit cracking and spoilage. Pick all harvest-ready tomatoes before rain arrives.", urgency: "high" as const },
  { type: "dont" as const, title: "Do not spray any chemicals today or tomorrow", description: "Rain in 48 hours will wash off sprayed chemicals, wasting money and contaminating soil runoff.", urgency: "high" as const },
  { type: "dont" as const, title: "Skip irrigation today and tomorrow", description: "23mm total rain forecast over Days 3-4 will provide sufficient moisture for tomato plants.", urgency: "medium" as const },
  { type: "warning" as const, title: "Clear drainage channels before Day 3", description: "Waterlogged soil can cause root rot in tomato plants. Ensure proper drainage before heavy rain.", urgency: "medium" as const },
  { type: "do" as const, title: "Check fruit for cracking after Day 5", description: "Heavy rain followed by sun causes tomato fruit to crack, reducing market value by 30-40%.", urgency: "low" as const },
  { type: "do" as const, title: "Good spray window after Day 5", description: "3+ dry days after Day 5 provides good conditions for any needed pesticide application. Consult local KVK.", urgency: "low" as const },
];

const CROPS = ["Tomato", "Wheat", "Rice", "Apple", "Coffee"];

export default function WeatherPage() {
  const [crop, setCrop] = useState("Tomato");

  return (
    <div className="min-h-screen text-white">
      <main className="max-w-7xl mx-auto px-4 py-8 space-y-8">
        {/* Title + Crop Selector */}
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h2 className="text-3xl font-bold">Weather Advisory</h2>
            <p className="text-white/50 mt-1">Solan, Himachal Pradesh — 5-day forecast</p>
          </div>
          <select
            value={crop}
            onChange={(e) => setCrop(e.target.value)}
            className="bg-white/10 border border-white/20 rounded-xl px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
          >
            {CROPS.map(c => <option key={c} value={c} className="bg-gray-900">{c}</option>)}
          </select>
        </div>

        {/* Weather Summary Banner */}
        <div className="bg-gradient-to-r from-sky-500/20 to-blue-600/20 border border-sky-500/30 rounded-2xl p-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-white/50 text-xs uppercase tracking-wider">Temperature</p>
              <p className="text-2xl font-bold">15° — 28°C</p>
            </div>
            <div>
              <p className="text-white/50 text-xs uppercase tracking-wider">Rain Expected</p>
              <p className="text-2xl font-bold text-sky-400">23mm</p>
              <p className="text-xs text-white/40">Days 3-4</p>
            </div>
            <div>
              <p className="text-white/50 text-xs uppercase tracking-wider">Humidity</p>
              <p className="text-2xl font-bold">65-88%</p>
            </div>
            <div>
              <p className="text-white/50 text-xs uppercase tracking-wider">Wind</p>
              <p className="text-2xl font-bold">7-15 km/h</p>
            </div>
          </div>
        </div>

        {/* 5-Day Forecast Timeline */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
          <h3 className="text-xl font-semibold mb-4">5-Day Forecast</h3>
          <WeatherTimeline forecast={FORECAST} />
        </div>

        {/* Farming Advisories */}
        <div>
          <h3 className="text-xl font-semibold mb-4">Farming Actions for {crop}</h3>
          <div className="grid gap-4 md:grid-cols-2">
            {ADVISORIES.map((a, i) => (
              <AdvisoryCard key={i} type={a.type} title={a.title} description={a.description} urgency={a.urgency} />
            ))}
          </div>
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

        {/* Source */}
        <p className="text-xs text-white/30 text-center">
          Source: Google Weather API. Forecast accuracy decreases beyond 3 days. Always combine with local observation.
        </p>
      </main>
    </div>
  );
}
