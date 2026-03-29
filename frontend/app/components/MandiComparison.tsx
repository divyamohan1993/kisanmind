"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
  LabelList,
} from "recharts";

interface MandiComparisonProps {
  data?: Array<{
    name: string;
    netProfit: number;
    price: number;
    transport: number;
    commission: number;
    distance: number;
    spoilage?: number; // Rs per quintal
  }>;
}

export default function MandiComparison({
  data,
}: MandiComparisonProps) {
  if (!data || data.length === 0) {
    return (
      <div className="glass-card p-4 sm:p-6">
        <h3 className="text-sm font-semibold text-white/90">Mandi Net Profit Comparison</h3>
        <div className="flex h-56 items-center justify-center text-sm text-white/30">
          No mandi data available yet
        </div>
      </div>
    );
  }
  const sorted = [...data].sort((a, b) => b.netProfit - a.netProfit);
  const bestMandi = sorted[0]?.name;

  return (
    <div className="glass-card p-4 sm:p-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-white/90">
            Mandi Net Profit Comparison
          </h3>
          <p className="text-xs text-white/40">
            Per quintal after transport + commission
          </p>
        </div>
        <div className="rounded-lg bg-healthy/10 px-3 py-1.5 text-xs font-semibold text-healthy">
          Best: {bestMandi}
        </div>
      </div>
      <div className="h-56 sm:h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={sorted}
            layout="vertical"
            margin={{ top: 5, right: 30, bottom: 5, left: 10 }}
          >
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgba(255,255,255,0.05)"
              horizontal={false}
            />
            <XAxis
              type="number"
              tick={{ fontSize: 10, fill: "rgba(255,255,255,0.4)" }}
              axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
              tickLine={false}
              tickFormatter={(v) => `₹${v}`}
            />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ fontSize: 11, fill: "rgba(255,255,255,0.7)" }}
              axisLine={false}
              tickLine={false}
              width={80}
            />
            <Tooltip
              contentStyle={{
                background: "rgba(13,17,23,0.95)",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: "12px",
                fontSize: "12px",
                color: "#e6edf3",
              }}
              content={({ active, payload }) => {
                if (!active || !payload || !payload.length) return null;
                const entry = payload[0]?.payload;
                return (
                  <div style={{
                    background: "rgba(13,17,23,0.95)",
                    border: "1px solid rgba(255,255,255,0.1)",
                    borderRadius: "12px",
                    fontSize: "12px",
                    color: "#e6edf3",
                    padding: "8px 12px",
                  }}>
                    <div style={{ fontWeight: 600, marginBottom: 4 }}>{entry.name}</div>
                    <div>Net Profit: ₹{entry.netProfit}</div>
                    {entry.spoilage != null && entry.spoilage > 0 && (
                      <div style={{ color: "#ef4444", marginTop: 2 }}>
                        Spoilage Loss: ₹{entry.spoilage}/q
                      </div>
                    )}
                  </div>
                );
              }}
            />
            <Bar dataKey="netProfit" radius={[0, 6, 6, 0]} barSize={28}>
              {sorted.map((entry) => (
                <Cell
                  key={entry.name}
                  fill={
                    entry.name === bestMandi
                      ? "#22c55e"
                      : "rgba(99, 102, 241, 0.6)"
                  }
                />
              ))}
              <LabelList
                dataKey="spoilage"
                position="right"
                content={(props) => {
                  const { x, y, width, height, value } = props as Record<string, number>;
                  if (!value || value <= 50) return <></>;
                  return (
                    <circle
                      cx={(x ?? 0) + (width ?? 0) + 8}
                      cy={(y ?? 0) + (height ?? 0) / 2}
                      r={4}
                      fill="#ef4444"
                      stroke="#0d1117"
                      strokeWidth={1}
                    />
                  );
                }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
