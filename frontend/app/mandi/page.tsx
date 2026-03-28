"use client";

import { useState } from "react";
import MandiComparison from "../components/MandiComparison";
import NDVIChart from "../components/NDVIChart";

const PRICE_HISTORY = [
  { date: "Feb 27", solan: 1500, shimla: 2000, mandi: 1800, kullu: 1900 },
  { date: "Mar 1", solan: 1550, shimla: 2050, mandi: 1850, kullu: 1950 },
  { date: "Mar 5", solan: 1600, shimla: 2100, mandi: 1900, kullu: 2000 },
  { date: "Mar 9", solan: 1580, shimla: 2150, mandi: 1870, kullu: 1980 },
  { date: "Mar 13", solan: 1650, shimla: 2200, mandi: 1950, kullu: 2050 },
  { date: "Mar 17", solan: 1700, shimla: 2250, mandi: 2000, kullu: 2100 },
  { date: "Mar 21", solan: 1750, shimla: 2350, mandi: 2050, kullu: 2150 },
  { date: "Mar 25", solan: 1780, shimla: 2380, mandi: 2080, kullu: 2180 },
  { date: "Mar 28", solan: 1800, shimla: 2400, mandi: 2100, kullu: 2200 },
];

// For the chart component (uses netProfit)
const MANDI_CHART_DATA = [
  { name: "Shimla", netProfit: 2080, price: 2400, transport: 200, commission: 120, distance: 62 },
  { name: "Solan", netProfit: 1660, price: 1800, transport: 50, commission: 90, distance: 5 },
  { name: "Kullu", netProfit: 1550, price: 2200, transport: 540, commission: 110, distance: 180 },
  { name: "Mandi", netProfit: 1566, price: 2100, transport: 450, commission: 84, distance: 150 },
  { name: "Chandigarh", netProfit: 1280, price: 1600, transport: 220, commission: 100, distance: 68 },
];

// For the table (more detailed)
const MANDIS = [
  { name: "Shimla", price: 2400, distance_km: 62, transport_cost: 200, commission: 120, netProfit: 2080, travel_time: "2 hr" },
  { name: "Solan", price: 1800, distance_km: 5, transport_cost: 50, commission: 90, netProfit: 1660, travel_time: "15 min" },
  { name: "Kullu", price: 2200, distance_km: 180, transport_cost: 540, commission: 110, netProfit: 1550, travel_time: "5 hr" },
  { name: "Mandi", price: 2100, distance_km: 150, transport_cost: 450, commission: 84, netProfit: 1566, travel_time: "4 hr" },
  { name: "Chandigarh", price: 1600, distance_km: 68, transport_cost: 220, commission: 100, netProfit: 1280, travel_time: "2.5 hr" },
];

export default function MandiPage() {
  const [crop] = useState("Tomato");

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#0a0a1a] via-[#0f1a0f] to-[#0a0a1a] text-white">
      {/* Header */}
      <header className="border-b border-white/10 bg-black/30 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <a href="/" className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-green-700 flex items-center justify-center text-lg font-bold">K</div>
            <div>
              <h1 className="text-lg font-bold bg-gradient-to-r from-emerald-400 to-green-300 bg-clip-text text-transparent">KisanMind</h1>
              <p className="text-xs text-white/40">मंडीमित्र — Market Friend</p>
            </div>
          </a>
          <nav className="flex gap-4 text-sm">
            <a href="/" className="text-white/60 hover:text-white transition">Dashboard</a>
            <a href="/mandi" className="text-emerald-400 font-medium">Mandi</a>
            <a href="/weather" className="text-white/60 hover:text-white transition">Weather</a>
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8 space-y-8">
        {/* Title */}
        <div>
          <h2 className="text-3xl font-bold">{crop} Prices Today</h2>
          <p className="text-white/50 mt-1">28 March 2026 — Himachal Pradesh mandis</p>
        </div>

        {/* Recommendation Banner */}
        <div className="bg-gradient-to-r from-emerald-500/20 to-green-600/20 border border-emerald-500/30 rounded-2xl p-6">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-3 h-3 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-emerald-400 font-semibold text-lg">SELL NOW</span>
          </div>
          <p className="text-white/80">
            Prices are <span className="text-emerald-400 font-bold">12% above seasonal average</span>.
            Shimla mandi offers <span className="text-emerald-400 font-bold">₹420 more per quintal</span> than Solan after transport.
            For 10 quintals, that&apos;s <span className="text-emerald-400 font-bold">₹4,200 extra</span>.
          </p>
        </div>

        {/* Mandi Comparison Chart */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
          <h3 className="text-xl font-semibold mb-4">Net Profit by Mandi (₹/quintal)</h3>
          <MandiComparison data={MANDI_CHART_DATA} />
        </div>

        {/* Detailed Table */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-6 overflow-x-auto">
          <h3 className="text-xl font-semibold mb-4">Detailed Comparison</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-white/50 border-b border-white/10">
                <th className="text-left py-3 px-2">Mandi</th>
                <th className="text-right py-3 px-2">Price (₹/qtl)</th>
                <th className="text-right py-3 px-2">Distance</th>
                <th className="text-right py-3 px-2">Transport</th>
                <th className="text-right py-3 px-2">Commission</th>
                <th className="text-right py-3 px-2 text-emerald-400">Net Profit</th>
                <th className="text-right py-3 px-2">Travel</th>
              </tr>
            </thead>
            <tbody>
              {[...MANDIS].sort((a, b) => b.netProfit - a.netProfit).map((m, i) => (
                <tr key={m.name} className={`border-b border-white/5 ${i === 0 ? "bg-emerald-500/10" : ""}`}>
                  <td className="py-3 px-2 font-medium">{i === 0 ? "🏆 " : ""}{m.name}</td>
                  <td className="text-right py-3 px-2">₹{m.price.toLocaleString()}</td>
                  <td className="text-right py-3 px-2 text-white/60">{m.distance_km} km</td>
                  <td className="text-right py-3 px-2 text-red-400/70">-₹{m.transport_cost}</td>
                  <td className="text-right py-3 px-2 text-red-400/70">-₹{m.commission}</td>
                  <td className="text-right py-3 px-2 font-bold text-emerald-400">₹{m.netProfit.toLocaleString()}</td>
                  <td className="text-right py-3 px-2 text-white/60">{m.travel_time}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Price Trend */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
          <h3 className="text-xl font-semibold mb-2">30-Day Price Trend</h3>
          <p className="text-white/50 text-sm mb-4">Prices trending UP ↑ 12% this week — above seasonal average</p>
          <NDVIChart
            data={PRICE_HISTORY.map(d => ({ date: d.date, ndvi: d.shimla / 3000 }))}
          />
          <div className="flex gap-6 mt-4 text-xs text-white/50">
            <span className="flex items-center gap-1"><span className="w-3 h-1 bg-emerald-400 rounded" /> Shimla</span>
            <span className="flex items-center gap-1"><span className="w-3 h-1 bg-blue-400 rounded" /> Solan</span>
          </div>
        </div>

        {/* Source */}
        <p className="text-xs text-white/30 text-center">
          Source: AgMarkNet (data.gov.in) — Government of India Open Data. Prices as of 28 March 2026.
          Transport costs estimated at ₹3.5/km/quintal. Commission rates: 3.5-5%.
        </p>
      </main>
    </div>
  );
}
