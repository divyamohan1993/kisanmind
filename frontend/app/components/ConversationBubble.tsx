"use client";

import { useState } from "react";
import { Volume2, VolumeX } from "lucide-react";

interface ConversationBubbleProps {
  type: "farmer" | "kisanmind";
  text: string;
  language: string;
  timestamp?: Date;
  audioUrl?: string;
}

export default function ConversationBubble({
  type,
  text,
  language,
  timestamp,
  audioUrl,
}: ConversationBubbleProps) {
  const [playing, setPlaying] = useState(false);

  const isFarmer = type === "farmer";

  const playAudio = () => {
    if (!audioUrl) return;
    const audio = new Audio(audioUrl);
    audio.onplay = () => setPlaying(true);
    audio.onended = () => setPlaying(false);
    audio.onerror = () => setPlaying(false);
    audio.play().catch(() => setPlaying(false));
  };

  const timeStr = timestamp
    ? timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : "";

  return (
    <div className={`flex w-full ${isFarmer ? "justify-start" : "justify-end"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 ${
          isFarmer
            ? "bg-white/10 rounded-bl-sm"
            : "bg-healthy/20 border border-healthy/20 rounded-br-sm"
        }`}
      >
        {/* Language label */}
        <div className="mb-1 flex items-center gap-2">
          <span
            className={`text-[10px] font-semibold uppercase tracking-wider ${
              isFarmer ? "text-sky/60" : "text-healthy/60"
            }`}
          >
            {isFarmer ? "You" : "KisanMind"} -- {language}
          </span>
          {timeStr && (
            <span className="text-[10px] text-white/30">{timeStr}</span>
          )}
        </div>

        {/* Message text */}
        <p className="text-sm leading-relaxed text-white/90">{text}</p>

        {/* Play button for KisanMind responses */}
        {!isFarmer && audioUrl && (
          <button
            onClick={playAudio}
            className="mt-2 flex items-center gap-1.5 rounded-lg bg-healthy/20 px-3 py-1.5 text-xs font-medium text-healthy transition-colors hover:bg-healthy/30"
          >
            {playing ? <VolumeX size={14} /> : <Volume2 size={14} />}
            {playing ? "Playing..." : "Play again"}
          </button>
        )}
      </div>
    </div>
  );
}
