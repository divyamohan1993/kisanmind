"use client";

import { useState, useEffect, useCallback } from "react";
import MandiComparison from "../components/MandiComparison";
import NDVIChart from "../components/NDVIChart";
import useGeolocation from "../hooks/useGeolocation";
import { AlertCircle } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface MandiEntry {
  market: string;
  modal_price: number;
  distance_km: number;
  net_profit_per_quintal: number;
  transport_cost_per_quintal?: number;
  commission_per_quintal?: number;
  travel_time?: string;
}

interface ApiResponse {
  crop?: string;
  location?: { location_name?: string; state?: string };
  mandi_prices?: MandiEntry[];
  best_mandi?: { market: string; modal_price: number; net_profit_per_quintal?: number };
  local_mandi?: { market: string; modal_price: number };
  advisory?: string;
  error?: string;
}

export default function MandiPage() {
  const geo = useGeolocation();
  const [crop] = useState("Tomato");
  const [apiData, setApiData] = useState<ApiResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        location: "Solan",
        crop,
        intent: "mandi prices",
        language: "hi-IN",
      };
      if (geo.latitude && geo.longitude) {
        body.latitude = geo.latitude;
        body.longitude = geo.longitude;
      }

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
      setError(err instanceof Error ? err.message : "Failed to fetch mandi data");
    }
    setIsLoading(false);
  }, [crop, geo.latitude, geo.longitude]);

  useEffect(() => {
    if (!geo.loading) {
      fetchData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geo.loading]);

  // Map API mandi_prices to chart format
  const chartData = (apiData?.mandi_prices || []).map((m) => ({
    name: m.market,
    netProfit: m.net_profit_per_quintal || 0,
    price: m.modal_price,
    transport: m.transport_cost_per_quintal || 0,
    commission: m.commission_per_quintal || 0,
    distance: m.distance_km,
  }));

  // Table data sorted by net profit
  const tableData = (apiData?.mandi_prices || [])
    .map((m) => ({
      name: m.market,
      price: m.modal_price,
      distance_km: m.distance_km,
      transport_cost: m.transport_cost_per_quintal || 0,
      commission: m.commission_per_quintal || 0,
      netProfit: m.net_profit_per_quintal || 0,
      travel_time: m.travel_time || `${Math.round(m.distance_km / 40)} hr`,
    }))
    .sort((a, b) => b.netProfit - a.netProfit);

  const bestMandiEntry = tableData[0];
  const localMandi = apiData?.local_mandi;
  const bestMandi = apiData?.best_mandi;

  const priceAdvantage =
    bestMandi && localMandi
      ? (bestMandi.net_profit_per_quintal || bestMandi.modal_price) -
        (localMandi.modal_price || 0)
      : bestMandiEntry && tableData.length > 1
      ? bestMandiEntry.netProfit - tableData[tableData.length - 1].netProfit
      : 0;

  const locationLabel = apiData?.location
    ? `${apiData.location.location_name || ""}, ${apiData.location.state || ""}`
    : "Himachal Pradesh";

  return (
    <div className="min-h-screen text-white">
      <main className="max-w-7xl mx-auto px-4 py-8 space-y-8">
        {/* Title */}
        <div>
          <h2 className="text-3xl font-bold">{apiData?.crop || crop} Prices Today</h2>
          <p className="text-white/50 mt-1">{locationLabel} mandis</p>
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

        {/* Recommendation Banner */}
        {isLoading ? (
          <div className="h-28 rounded-2xl shimmer" />
        ) : bestMandiEntry ? (
          <div className="bg-gradient-to-r from-emerald-500/20 to-green-600/20 border border-emerald-500/30 rounded-2xl p-6">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-3 h-3 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-emerald-400 font-semibold text-lg">SELL NOW</span>
            </div>
            <p className="text-white/80">
              {bestMandiEntry.name} mandi offers the best net profit of{" "}
              <span className="text-emerald-400 font-bold">
                ₹{bestMandiEntry.netProfit.toLocaleString()}/quintal
              </span>
              {priceAdvantage > 0 && (
                <>
                  {" "}— that&apos;s{" "}
                  <span className="text-emerald-400 font-bold">
                    ₹{priceAdvantage.toLocaleString()} more
                  </span>{" "}
                  per quintal after transport.
                  For 10 quintals, that&apos;s{" "}
                  <span className="text-emerald-400 font-bold">
                    ₹{(priceAdvantage * 10).toLocaleString()} extra
                  </span>.
                </>
              )}
            </p>
          </div>
        ) : null}

        {/* Mandi Comparison Chart */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
          <h3 className="text-xl font-semibold mb-4">Net Profit by Mandi (₹/quintal)</h3>
          {isLoading ? (
            <div className="h-64 rounded-xl shimmer" />
          ) : chartData.length > 0 ? (
            <MandiComparison data={chartData} />
          ) : (
            <p className="text-white/40 text-sm">No mandi data available.</p>
          )}
        </div>

        {/* Detailed Table */}
        <div className="bg-white/5 border border-white/10 rounded-2xl p-6 overflow-x-auto">
          <h3 className="text-xl font-semibold mb-4">Detailed Comparison</h3>
          {isLoading ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-10 rounded shimmer" />
              ))}
            </div>
          ) : tableData.length > 0 ? (
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
                {tableData.map((m, i) => (
                  <tr key={m.name} className={`border-b border-white/5 ${i === 0 ? "bg-emerald-500/10" : ""}`}>
                    <td className="py-3 px-2 font-medium">{i === 0 ? "🏆 " : ""}{m.name}</td>
                    <td className="text-right py-3 px-2">₹{m.price.toLocaleString()}</td>
                    <td className="text-right py-3 px-2 text-white/60">{m.distance_km} km</td>
                    <td className="text-right py-3 px-2 text-red-400/70">-₹{m.transport_cost.toLocaleString()}</td>
                    <td className="text-right py-3 px-2 text-red-400/70">-₹{m.commission.toLocaleString()}</td>
                    <td className="text-right py-3 px-2 font-bold text-emerald-400">₹{m.netProfit.toLocaleString()}</td>
                    <td className="text-right py-3 px-2 text-white/60">{m.travel_time}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-white/40 text-sm">No mandi data available.</p>
          )}
        </div>

        {/* Source */}
        <p className="text-xs text-white/30 text-center">
          Source: AgMarkNet (data.gov.in) — Government of India Open Data.
          Transport costs estimated at ₹3.5/km/quintal. Commission rates: 3.5-5%.
        </p>
      </main>
    </div>
  );
}
