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

const demoData = [
  { date: "Jan 1", ndvi: 0.25, stage: "Seedling" },
  { date: "Jan 15", ndvi: 0.32 },
  { date: "Feb 1", ndvi: 0.41 },
  { date: "Feb 15", ndvi: 0.55, stage: "Vegetative" },
  { date: "Mar 1", ndvi: 0.63 },
  { date: "Mar 15", ndvi: 0.71 },
  { date: "Apr 1", ndvi: 0.76, stage: "Flowering" },
  { date: "Apr 15", ndvi: 0.74 },
  { date: "May 1", ndvi: 0.72 },
  { date: "May 15", ndvi: 0.68, stage: "Fruiting" },
  { date: "Jun 1", ndvi: 0.65 },
  { date: "Jun 15", ndvi: 0.58, stage: "Harvest" },
];

interface NDVIChartProps {
  data?: typeof demoData;
}

export default function NDVIChart({ data = demoData }: NDVIChartProps) {
  return (
    <div className="glass-card p-4 sm:p-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-white/90">NDVI Trend</h3>
          <p className="text-xs text-white/40">3-month vegetation index</p>
        </div>
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
    </div>
  );
}
