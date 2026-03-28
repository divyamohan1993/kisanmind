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
} from "recharts";

const demoData = [
  {
    name: "Shimla",
    netProfit: 2040,
    price: 2400,
    transport: 200,
    commission: 160,
    distance: 45,
  },
  {
    name: "Chandigarh",
    netProfit: 1850,
    price: 2200,
    transport: 180,
    commission: 170,
    distance: 120,
  },
  {
    name: "Solan",
    netProfit: 1560,
    price: 1800,
    transport: 80,
    commission: 160,
    distance: 12,
  },
  {
    name: "Karnal",
    netProfit: 1480,
    price: 2000,
    transport: 350,
    commission: 170,
    distance: 200,
  },
  {
    name: "Ambala",
    netProfit: 1650,
    price: 2100,
    transport: 280,
    commission: 170,
    distance: 150,
  },
];

interface MandiComparisonProps {
  data?: typeof demoData;
}

export default function MandiComparison({
  data = demoData,
}: MandiComparisonProps) {
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
              formatter={(value, name) => [
                `₹${value}`,
                name === "netProfit" ? "Net Profit" : String(name),
              ]}
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
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
