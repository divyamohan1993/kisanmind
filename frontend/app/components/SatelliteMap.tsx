"use client";

import { MapPin, Satellite } from "lucide-react";

interface SatelliteMapProps {
  location?: string;
  ndvi?: number;
  status?: "healthy" | "moderate" | "stressed";
}

export default function SatelliteMap({
  location = "Solan, Himachal Pradesh",
  ndvi = 0.72,
  status = "healthy",
}: SatelliteMapProps) {
  const statusColor =
    status === "healthy"
      ? "text-healthy"
      : status === "moderate"
      ? "text-moderate"
      : "text-stressed";

  const statusBg =
    status === "healthy"
      ? "bg-healthy/20 border-healthy/30"
      : status === "moderate"
      ? "bg-moderate/20 border-moderate/30"
      : "bg-stressed/20 border-stressed/30";

  return (
    <div className="relative overflow-hidden rounded-2xl border border-white/5">
      {/* Satellite field imagery simulation */}
      <div className="ndvi-field relative h-64 sm:h-80 lg:h-96">
        {/* Scan line effect */}
        <div className="scan-line" />

        {/* Field grid overlay */}
        <svg
          className="absolute inset-0 h-full w-full opacity-20"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            <pattern
              id="field-grid"
              width="60"
              height="60"
              patternUnits="userSpaceOnUse"
            >
              <path
                d="M 60 0 L 0 0 0 60"
                fill="none"
                stroke="rgba(34,197,94,0.3)"
                strokeWidth="0.5"
              />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#field-grid)" />
        </svg>

        {/* Field parcel outlines */}
        <svg
          className="absolute inset-0 h-full w-full"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 400 300"
          preserveAspectRatio="none"
        >
          <polygon
            points="50,80 180,60 200,160 70,180"
            fill="rgba(34,197,94,0.15)"
            stroke="rgba(34,197,94,0.4)"
            strokeWidth="1"
          />
          <polygon
            points="200,50 340,70 350,180 210,160"
            fill="rgba(34,197,94,0.1)"
            stroke="rgba(34,197,94,0.3)"
            strokeWidth="1"
          />
          <polygon
            points="60,190 200,170 220,260 80,270"
            fill="rgba(234,179,8,0.12)"
            stroke="rgba(234,179,8,0.35)"
            strokeWidth="1"
          />
          <polygon
            points="230,170 360,190 370,270 240,260"
            fill="rgba(239,68,68,0.08)"
            stroke="rgba(239,68,68,0.25)"
            strokeWidth="1"
          />
        </svg>

        {/* Corner coordinates display */}
        <div className="absolute left-3 top-3 flex items-center gap-1.5 rounded-lg bg-black/60 px-2.5 py-1.5 text-[10px] font-mono text-white/60 backdrop-blur-sm">
          <Satellite size={12} className="text-satellite" />
          Sentinel-2 | 10m res
        </div>

        {/* Location pin */}
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
          <div className="float-anim flex flex-col items-center">
            <MapPin size={28} className={statusColor} fill="currentColor" fillOpacity={0.3} />
            <div className="mt-1 rounded-full bg-black/70 px-2 py-0.5 text-[10px] font-medium text-white backdrop-blur-sm">
              {location}
            </div>
          </div>
        </div>

        {/* NDVI value overlay */}
        <div className="absolute bottom-3 right-3 flex flex-col items-end gap-2">
          <div
            className={`rounded-xl border ${statusBg} px-4 py-2.5 backdrop-blur-sm`}
          >
            <div className="text-[10px] font-medium uppercase tracking-wider text-white/50">
              NDVI Index
            </div>
            <div className={`text-3xl font-bold tabular-nums ${statusColor}`}>
              {ndvi.toFixed(2)}
            </div>
            <div className={`text-xs font-medium capitalize ${statusColor}`}>
              {status}
            </div>
          </div>
        </div>

        {/* NDVI Legend */}
        <div className="absolute bottom-3 left-3 flex items-center gap-2 rounded-lg bg-black/60 px-3 py-2 backdrop-blur-sm">
          <div className="flex h-3 w-24 overflow-hidden rounded-full">
            <div className="flex-1 bg-stressed" />
            <div className="flex-1 bg-moderate" />
            <div className="flex-1 bg-healthy" />
          </div>
          <span className="text-[10px] text-white/50">0 -- 1.0</span>
        </div>
      </div>
    </div>
  );
}
