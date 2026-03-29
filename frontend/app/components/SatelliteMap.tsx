"use client";

import { MapPin, Satellite } from "lucide-react";

interface SatelliteMapProps {
  location?: string;
  ndvi?: number;
  status?: "healthy" | "moderate" | "stressed";
  imageUrl?: string;
}

export default function SatelliteMap({
  location,
  ndvi,
  status,
  imageUrl,
}: SatelliteMapProps) {
  if (!location && !imageUrl && ndvi == null) {
    return (
      <div className="relative overflow-hidden rounded-2xl border border-white/5">
        <div className="flex h-64 sm:h-80 lg:h-96 items-center justify-center bg-kisan-dark-2 text-sm text-white/30">
          <div className="text-center">
            <Satellite size={32} className="mx-auto mb-2 text-white/20" />
            <p>Waiting for satellite data...</p>
          </div>
        </div>
      </div>
    );
  }
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
      {/* Satellite field imagery */}
      <div className={`relative h-64 sm:h-80 lg:h-96 ${!imageUrl ? 'ndvi-field' : 'bg-black'}`}>
        {/* Real satellite image (when available) */}
        {imageUrl && (
          <img
            src={imageUrl}
            alt={`Sentinel-2 satellite imagery near ${location}`}
            className="absolute inset-0 h-full w-full object-cover"
          />
        )}

        {/* Scan line effect */}
        <div className="scan-line" />

        {/* Loading placeholder when no real satellite image */}
        {!imageUrl && (
          <div className="absolute inset-0 flex items-center justify-center">
            <p className="text-xs text-white/20">Satellite image loading...</p>
          </div>
        )}

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
              {ndvi != null ? ndvi.toFixed(2) : "--"}
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
