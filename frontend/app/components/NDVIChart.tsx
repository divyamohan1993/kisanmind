"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Area,
  ComposedChart,
} from "recharts";

interface NDVIChartProps {
  data?: Array<{ date: string; ndvi: number; stage?: string }>;
  trajectory?: string;
  benchmarkComparison?: string;
  districtAvg?: number;
}

export default function NDVIChart({ data, trajectory, benchmarkComparison, districtAvg }: NDVIChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="glass-card p-4 sm:p-6">
        <h3 className="text-sm font-semibold text-white/90">NDVI Trend</h3>
        <div className="flex h-56 items-center justify-center text-sm text-white/30">
          No satellite data available yet
        </div>
      </div>
    );
  }

  return (
    <div className="glass-card p-4 sm:p-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-white/90">NDVI Trend</h3>
          <p className="text-xs text-white/40">3-month vegetation index</p>
        </div>
        {trajectory && (
          <div className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${
            trajectory.toLowerCase().includes("improv") ? "bg-healthy/10 text-healthy" :
            trajectory.toLowerCase().includes("declin") ? "bg-stressed/10 text-stressed" :
            "bg-moderate/10 text-moderate"
          }`}>
            {trajectory.toLowerCase().includes("improv") ? "\u2191" :
             trajectory.toLowerCase().includes("declin") ? "\u2193" : "\u2192"}{" "}
            {trajectory}
          </div>
        )}
        <div className="flex items-center gap-3 text-[10px]">
          <span className="flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-full bg-healthy" />
            Healthy (&gt;0.6)
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-full bg-moderate" />
            Moderate
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-full bg-stressed" />
            Stressed (&lt;0.3)
          </span>
        </div>
      </div>
      <div className="h-56 sm:h-64">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 5, right: 5, bottom: 5, left: -20 }}>
            <defs>
              <linearGradient id="ndviGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#22c55e" stopOpacity={0.3} />
                <stop offset="100%" stopColor="#22c55e" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: "rgba(255,255,255,0.4)" }}
              axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
              tickLine={false}
            />
            <YAxis
              domain={[0, 1]}
              tick={{ fontSize: 10, fill: "rgba(255,255,255,0.4)" }}
              axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
              tickLine={false}
            />
            <Tooltip
              contentStyle={{
                background: "rgba(13,17,23,0.95)",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: "12px",
                fontSize: "12px",
                color: "#e6edf3",
              }}
              formatter={(value) => [Number(value).toFixed(2), "NDVI"]}
            />
            <ReferenceLine
              y={0.6}
              stroke="rgba(34,197,94,0.4)"
              strokeDasharray="5 5"
              label={{
                value: "Healthy",
                position: "right",
                fill: "rgba(34,197,94,0.5)",
                fontSize: 10,
              }}
            />
            <ReferenceLine
              y={0.3}
              stroke="rgba(239,68,68,0.4)"
              strokeDasharray="5 5"
              label={{
                value: "Stressed",
                position: "right",
                fill: "rgba(239,68,68,0.5)",
                fontSize: 10,
              }}
            />
            {districtAvg != null && (
              <ReferenceLine
                y={districtAvg}
                stroke="rgba(168,85,247,0.6)"
                strokeDasharray="4 4"
                label={{
                  value: `Dist. Avg (${districtAvg.toFixed(2)})`,
                  position: "left",
                  fill: "rgba(168,85,247,0.7)",
                  fontSize: 10,
                }}
              />
            )}
            <Area
              type="monotone"
              dataKey="ndvi"
              fill="url(#ndviGradient)"
              stroke="none"
            />
            <Line
              type="monotone"
              dataKey="ndvi"
              stroke="#22c55e"
              strokeWidth={2.5}
              dot={{ fill: "#22c55e", r: 3, strokeWidth: 0 }}
              activeDot={{ r: 6, fill: "#22c55e", stroke: "#0d1117", strokeWidth: 2 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      {benchmarkComparison && (
        <p className="mt-3 text-xs text-white/50">{benchmarkComparison}</p>
      )}
    </div>
  );
}
