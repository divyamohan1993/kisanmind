"use client";

import { Sun, Cloud, CloudRain, Wind, CloudSnow, Droplets } from "lucide-react";

export interface ForecastDay {
  day: string;
  date?: string;
  icon?: "sun" | "cloud" | "rain" | "wind" | "snow";
  tempHigh?: number;
  tempLow?: number;
  temp_max?: number;
  temp_min?: number;
  humidity: number;
  rainProb?: number;
  rain_mm?: number;
  windSpeed?: number;
  wind_kmh?: number;
  condition?: string;
  alert?: string;
}

const iconMap = {
  sun: Sun,
  cloud: Cloud,
  rain: CloudRain,
  wind: Wind,
  snow: CloudSnow,
};

interface WeatherTimelineProps {
  forecast?: ForecastDay[];
  growthStage?: string;
}

export default function WeatherTimeline({
  forecast,
  growthStage,
}: WeatherTimelineProps) {
  if (!forecast || forecast.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center text-sm text-white/30">
        No forecast data available yet
      </div>
    );
  }

  return (
    <div>
      {growthStage && (
        <div className="mb-3 rounded-lg bg-white/5 px-3 py-2 text-xs font-medium text-white/70">
          Crop Stage: <span className="text-white/90">{growthStage}</span>
        </div>
      )}
    <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-thin">
      {forecast.map((day, i) => {
        // Support both prop name conventions
        const tempHigh = day.tempHigh ?? day.temp_max ?? 0;
        const tempLow = day.tempLow ?? day.temp_min ?? 0;
        const rainProb = day.rainProb ?? (day.rain_mm != null ? (day.rain_mm > 0 ? 80 : 5) : 0);
        const windSpeed = day.windSpeed ?? day.wind_kmh ?? 0;
        const condition = day.condition?.toLowerCase() ?? "";
        const iconKey = day.icon ?? (condition.includes("rain") ? "rain" : condition.includes("cloud") || condition.includes("partly") ? "cloud" : "sun");
        const Icon = iconMap[iconKey] || Cloud;
        const hasAlert = !!day.alert;

        return (
          <div
            key={i}
            className={`glass-card glass-card-hover flex min-w-[150px] flex-col items-center gap-2 p-4 ${
              hasAlert ? "border-moderate/30 ring-1 ring-moderate/20" : ""
            }`}
          >
            <div className="text-xs font-semibold text-white/70">{day.day}</div>
            <div className="text-[10px] text-white/40">{day.date}</div>

            <Icon
              size={32}
              className={
                iconKey === "sun"
                  ? "text-moderate"
                  : iconKey === "rain"
                  ? "text-sky"
                  : "text-white/50"
              }
            />

            <div className="flex items-baseline gap-1">
              <span className="text-lg font-bold text-white">
                {tempHigh}°
              </span>
              <span className="text-xs text-white/40">{tempLow}°</span>
            </div>

            <div className="flex w-full flex-col gap-1 text-[10px]">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1 text-white/40">
                  <Droplets size={10} /> Humidity
                </span>
                <span className="text-white/60">{day.humidity}%</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1 text-white/40">
                  <CloudRain size={10} /> Rain
                </span>
                <span
                  className={
                    rainProb > 60 ? "font-semibold text-sky" : "text-white/60"
                  }
                >
                  {day.rain_mm != null ? `${day.rain_mm}mm` : `${rainProb}%`}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1 text-white/40">
                  <Wind size={10} /> Wind
                </span>
                <span className="text-white/60">{windSpeed} km/h</span>
              </div>
            </div>

            {hasAlert && (() => {
              const alertLower = (day.alert ?? "").toLowerCase();
              const isCritical = alertLower.includes("harvest") || alertLower.includes("frost");
              return (
                <div className={`mt-1 w-full rounded-lg px-2 py-1.5 text-[10px] font-medium ${
                  isCritical
                    ? "bg-red-500/15 text-red-400 border border-red-500/20"
                    : "bg-moderate/10 text-moderate"
                }`}>
                  {isCritical ? "\u{1F6A8}" : "\u26A0"} {day.alert}
                </div>
              );
            })()}
          </div>
        );
      })}
    </div>
    </div>
  );
}
