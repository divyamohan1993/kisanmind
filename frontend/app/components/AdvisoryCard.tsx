"use client";

import { CheckCircle, XCircle, AlertTriangle } from "lucide-react";

export interface Advisory {
  type: "do" | "dont" | "warning";
  title?: string;
  description?: string;
  message?: string;
  reason?: string;
  urgency?: "low" | "medium" | "high";
}

const typeConfig = {
  do: {
    icon: CheckCircle,
    bg: "bg-healthy/5",
    border: "border-healthy/20",
    iconColor: "text-healthy",
    label: "DO",
    labelBg: "bg-healthy/20 text-healthy",
  },
  dont: {
    icon: XCircle,
    bg: "bg-stressed/5",
    border: "border-stressed/20",
    iconColor: "text-stressed",
    label: "DON'T",
    labelBg: "bg-stressed/20 text-stressed",
  },
  warning: {
    icon: AlertTriangle,
    bg: "bg-moderate/5",
    border: "border-moderate/20",
    iconColor: "text-moderate",
    label: "WARNING",
    labelBg: "bg-moderate/20 text-moderate",
  },
};

const urgencyConfig = {
  low: "bg-white/10 text-white/50",
  medium: "bg-moderate/20 text-moderate",
  high: "bg-stressed/20 text-stressed",
};

export default function AdvisoryCard({ type, title, description, message, reason, urgency }: Advisory) {
  const config = typeConfig[type];
  const Icon = config.icon;
  const displayTitle = title || message || "";
  const displayDescription = description || reason || "";

  return (
    <div
      className={`glass-card glass-card-hover flex gap-3 p-4 ${config.bg} border ${config.border}`}
    >
      <div className="shrink-0 pt-0.5">
        <Icon size={20} className={config.iconColor} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span
            className={`rounded-md px-1.5 py-0.5 text-[10px] font-bold ${config.labelBg}`}
          >
            {config.label}
          </span>
          {urgency && (
            <span
              className={`rounded-md px-1.5 py-0.5 text-[10px] font-medium ${urgencyConfig[urgency]}`}
            >
              {urgency.toUpperCase()}
            </span>
          )}
        </div>
        <h4 className="text-sm font-semibold text-white/90">{displayTitle}</h4>
        {displayDescription && (
          <p className="mt-0.5 text-xs leading-relaxed text-white/50">
            {displayDescription}
          </p>
        )}
      </div>
    </div>
  );
}
