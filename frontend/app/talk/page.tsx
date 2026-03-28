"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Mic, MicOff, Sun, CloudRain, Cloud, Leaf, Volume2 } from "lucide-react";
import Link from "next/link";
import useGeolocation from "../hooks/useGeolocation";
import ConversationBubble from "../components/ConversationBubble";

/* ------------------------------------------------------------------ */
/*  Languages — 22 scheduled languages in native script               */
/* ------------------------------------------------------------------ */
const LANGUAGES = [
  { code: "hi", label: "\u0939\u093f\u0928\u094d\u0926\u0940" },
  { code: "en", label: "English" },
  { code: "ta", label: "\u0ba4\u0bae\u0bbf\u0bb4\u0bcd" },
  { code: "te", label: "\u0c24\u0c46\u0c32\u0c41\u0c17\u0c41" },
  { code: "bn", label: "\u09ac\u09be\u0982\u09b2\u09be" },
  { code: "mr", label: "\u092e\u0930\u093e\u0920\u0940" },
  { code: "gu", label: "\u0a97\u0ac1\u0a9c\u0ab0\u0abe\u0aa4\u0ac0" },
  { code: "kn", label: "\u0c95\u0ca8\u0ccd\u0ca8\u0ca1" },
  { code: "ml", label: "\u0d2e\u0d32\u0d2f\u0d3e\u0d33\u0d02" },
  { code: "pa", label: "\u0a2a\u0a70\u0a1c\u0a3e\u0a2c\u0a40" },
  { code: "or", label: "\u0b13\u0b21\u0b3c\u0b3f\u0b06" },
  { code: "as", label: "\u0985\u09b8\u09ae\u09c0\u09af\u09bc\u09be" },
  { code: "mai", label: "\u092e\u0948\u0925\u093f\u0932\u0940" },
  { code: "sa", label: "\u0938\u0902\u0938\u094d\u0915\u0943\u0924\u092e\u094d" },
  { code: "ne", label: "\u0928\u0947\u092a\u093e\u0932\u0940" },
  { code: "sd", label: "\u0633\u0646\u068c\u064a" },
  { code: "doi", label: "\u0921\u094b\u0917\u0930\u0940" },
  { code: "ks", label: "\u06a9\u0672\u0634\u064f\u0631" },
  { code: "kok", label: "\u0915\u094b\u0902\u0915\u0923\u0940" },
  { code: "sat", label: "\u1c65\u1c5f\u1c71\u1c5f\u1c5f\u1c72\u1c64" },
  { code: "brx", label: "\u09ac\u09cb\u09a1\u09bc\u09cb" },
  { code: "mni", label: "\u092e\u0923\u093f\u092a\u0941\u0930\u0940" },
];

const TAP_LABELS: Record<string, string> = {
  hi: "\u091f\u0948\u092a \u0915\u0930\u0947\u0902 \u0914\u0930 \u092c\u094b\u0932\u0947\u0902",
  en: "Tap and speak",
  ta: "\u0ba4\u0bdf\u0bb5\u0bc1 \u0b9a\u0bc6\u0baf\u0bcd\u0ba4\u0bc1 \u0baa\u0bc7\u0b9a\u0bc1\u0b99\u0bcd\u0b95\u0bb3\u0bcd",
  te: "\u0c1f\u0c3e\u0c2a\u0c4d \u0c1a\u0c47\u0c38\u0c3f \u0c2e\u0c3e\u0c1f\u0c4d\u0c32\u0c3e\u0c21\u0c02\u0c21\u0c3f",
  bn: "\u099f\u09cd\u09af\u09be\u09aa \u0995\u09b0\u09c1\u09a8 \u098f\u09ac\u0982 \u09ac\u09b2\u09c1\u09a8",
  mr: "\u091f\u0945\u092a \u0915\u0930\u093e \u0906\u0923\u093f \u092c\u094b\u0932\u093e",
  gu: "\u0a9f\u0ac7\u0aaa \u0a95\u0ab0\u0acb \u0a85\u0aa8\u0ac7 \u0aac\u0acb\u0ab2\u0acb",
  kn: "\u0c9f\u0ccd\u0caf\u0cbe\u0caa\u0ccd \u0cae\u0cbe\u0ca1\u0cbf \u0cae\u0cbe\u0ca4\u0ca8\u0cbe\u0ca1\u0cbf",
  ml: "\u0d1f\u0d3e\u0d2a\u0d4d\u0d2a\u0d4d \u0d1a\u0d46\u0d2f\u0d4d\u0d24\u0d4d \u0d38\u0d02\u0d38\u0d3e\u0d30\u0d3f\u0d15\u0d4d\u0d15\u0d41\u0d15",
  pa: "\u0a1f\u0a48\u0a2a \u0a15\u0a30\u0a4b \u0a05\u0a24\u0a47 \u0a2c\u0a4b\u0a32\u0a4b",
};

/* ------------------------------------------------------------------ */
/*  API base URL                                                       */
/* ------------------------------------------------------------------ */
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */
interface ChatMessage {
  type: "farmer" | "kisanmind";
  text: string;
  language: string;
  timestamp: Date;
  audioUrl?: string;
}

interface AdvisorySummary {
  mandiName: string;
  mandiPrice: number;
  weatherCondition: string;
  cropStatus: string;
}

type Stage =
  | "idle"
  | "recording"
  | "transcribing"
  | "thinking"
  | "speaking"
  | "done";

/* ------------------------------------------------------------------ */
/*  Weather icon helper                                                */
/* ------------------------------------------------------------------ */
function WeatherIcon({ condition }: { condition: string }) {
  const c = condition.toLowerCase();
  if (c.includes("rain") || c.includes("storm")) return <CloudRain size={40} className="text-sky" />;
  if (c.includes("cloud") || c.includes("overcast")) return <Cloud size={40} className="text-white/60" />;
  return <Sun size={40} className="text-moderate" />;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */
export default function TalkPage() {
  const [language, setLanguage] = useState("hi");
  const [stage, setStage] = useState<Stage>("idle");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [summary, setSummary] = useState<AdvisorySummary | null>(null);
  const [showLangPicker, setShowLangPicker] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const geo = useGeolocation();

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  /* ---- Recording ---- */
  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // Prefer webm/opus, fall back to whatever the browser supports
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : "audio/mp4";

      const recorder = new MediaRecorder(stream, { mimeType });
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      mediaRecorderRef.current = recorder;
      recorder.start(250); // collect chunks every 250ms
      setStage("recording");
    } catch {
      alert("Microphone access denied. Please allow microphone access and try again.");
    }
  }, []);

  const stopRecording = useCallback((): Promise<Blob> => {
    return new Promise((resolve) => {
      const recorder = mediaRecorderRef.current;
      if (!recorder || recorder.state === "inactive") {
        resolve(new Blob());
        return;
      }
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType });
        // Stop all tracks to release mic
        streamRef.current?.getTracks().forEach((t) => t.stop());
        resolve(blob);
      };
      recorder.stop();
    });
  }, []);

  /* ---- Full voice pipeline ---- */
  const handleMicTap = useCallback(async () => {
    if (stage === "recording") {
      // Stop and process
      const audioBlob = await stopRecording();
      if (audioBlob.size === 0) {
        setStage("idle");
        return;
      }

      // 1. Transcribe
      setStage("transcribing");
      let transcript = "";
      try {
        const formData = new FormData();
        formData.append("audio", audioBlob, "recording.webm");
        formData.append("language", language);

        const sttRes = await fetch(`${API_BASE}/api/stt`, {
          method: "POST",
          body: formData,
        });
        const sttData = await sttRes.json();
        transcript = sttData.transcript || sttData.text || "";
      } catch {
        transcript = "";
      }

      if (!transcript.trim()) {
        setStage("idle");
        return;
      }

      // Add farmer message
      setMessages((prev) => [
        ...prev,
        { type: "farmer", text: transcript, language, timestamp: new Date() },
      ]);

      // 2. Extract intent
      setStage("thinking");
      let crop = "";
      let location = "";
      try {
        const intentRes = await fetch(`${API_BASE}/api/extract-intent`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: transcript, language }),
        });
        const intentData = await intentRes.json();
        crop = intentData.crop || "";
        location = intentData.location || "";
      } catch {
        // Continue with just transcript
      }

      // 3. Get advisory
      let advisoryText = "";
      let advisoryData: Record<string, unknown> = {};
      try {
        const advisoryRes = await fetch(`${API_BASE}/api/advisory`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            location: location || "auto",
            crop: crop || "auto",
            intent: transcript,
            language,
            latitude: geo.latitude,
            longitude: geo.longitude,
          }),
        });
        advisoryData = await advisoryRes.json();
        advisoryText =
          (advisoryData.combined_advisory as string) ||
          (advisoryData.combinedAdvisory as string) ||
          (advisoryData.advisory as string) ||
          "Advisory received.";

        // Extract summary
        const mandi = advisoryData.mandi as Record<string, unknown> | undefined;
        const weather = advisoryData.weather as Record<string, unknown> | undefined;
        const satellite = advisoryData.satellite as Record<string, unknown> | undefined;
        const forecast = (weather?.forecast as Array<Record<string, unknown>>) || [];
        setSummary({
          mandiName: (mandi?.best_mandi as string) || (mandi?.bestMandi as string) || "--",
          mandiPrice: (mandi?.best_price as number) || (mandi?.bestPrice as number) || 0,
          weatherCondition: (forecast[0]?.condition as string) || "Clear",
          cropStatus: (satellite?.health as string) || (satellite?.status as string) || "OK",
        });
      } catch {
        advisoryText = "Sorry, could not fetch advisory. Please try again.";
      }

      // 4. Get TTS audio
      setStage("speaking");
      let audioUrl = "";
      try {
        const ttsRes = await fetch(`${API_BASE}/api/tts`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: advisoryText, language }),
        });
        if (ttsRes.ok) {
          const ttsBlob = await ttsRes.blob();
          audioUrl = URL.createObjectURL(ttsBlob);
        }
      } catch {
        // No audio — that is fine, we still show text
      }

      // Add kisanmind message
      setMessages((prev) => [
        ...prev,
        {
          type: "kisanmind",
          text: advisoryText,
          language,
          timestamp: new Date(),
          audioUrl,
        },
      ]);

      // Auto-play audio
      if (audioUrl) {
        try {
          const audio = new Audio(audioUrl);
          await audio.play();
          audio.onended = () => setStage("done");
        } catch {
          setStage("done");
        }
      } else {
        setStage("done");
      }
    } else if (stage === "idle" || stage === "done") {
      // Start recording
      await startRecording();
    }
    // If in other stages (transcribing/thinking/speaking), ignore tap
  }, [stage, stopRecording, startRecording, language, geo.latitude, geo.longitude]);

  /* ---- Derived UI state ---- */
  const isRecording = stage === "recording";
  const isProcessing = stage === "transcribing" || stage === "thinking" || stage === "speaking";
  const canTap = stage === "idle" || stage === "recording" || stage === "done";
  const tapLabel =
    TAP_LABELS[language] || TAP_LABELS["hi"];

  const currentLang = LANGUAGES.find((l) => l.code === language) || LANGUAGES[0];

  /* ---- Status text by stage ---- */
  const stageLabels: Record<Stage, string> = {
    idle: tapLabel,
    recording: language === "en" ? "Listening..." : "\u0938\u0941\u0928 \u0930\u0939\u0947 \u0939\u0948\u0902...",
    transcribing: language === "en" ? "Understanding..." : "\u0938\u092e\u091d \u0930\u0939\u0947 \u0939\u0948\u0902...",
    thinking: language === "en" ? "Preparing advice..." : "\u0938\u0932\u093e\u0939 \u0924\u0948\u092f\u093e\u0930 \u0915\u0930 \u0930\u0939\u0947 \u0939\u0948\u0902...",
    speaking: language === "en" ? "Listen..." : "\u0938\u0941\u0928\u093f\u090f...",
    done: tapLabel,
  };

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[#0a0f14] text-white">
      {/* ---- Top bar ---- */}
      <div className="flex items-center justify-between px-4 py-3 bg-[#0d1117]/90 border-b border-white/5">
        <Link href="/" className="flex items-center gap-2">
          <span className="text-xl">🌾</span>
          <span className="text-base font-bold gradient-text">KisanMind</span>
        </Link>

        <button
          onClick={() => setShowLangPicker(!showLangPicker)}
          className="flex items-center gap-1.5 rounded-full bg-white/10 px-4 py-2 text-sm font-medium transition-colors hover:bg-white/15"
        >
          <Volume2 size={14} />
          {currentLang.label}
        </button>

        <Link
          href="/"
          className="rounded-lg bg-white/5 px-3 py-2 text-xs text-white/60 hover:bg-white/10 hover:text-white/80 transition-colors"
        >
          Dashboard
        </Link>
      </div>

      {/* ---- Language picker (overlay) ---- */}
      {showLangPicker && (
        <div className="absolute top-14 left-0 right-0 z-50 bg-[#0d1117] border-b border-white/10 px-4 py-4 shadow-2xl">
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2 max-w-2xl mx-auto">
            {LANGUAGES.map((lang) => (
              <button
                key={lang.code}
                onClick={() => {
                  setLanguage(lang.code);
                  setShowLangPicker(false);
                }}
                className={`rounded-xl px-3 py-3 text-sm font-medium transition-all min-h-[52px] ${
                  language === lang.code
                    ? "bg-healthy/20 text-healthy border-2 border-healthy/40"
                    : "bg-white/5 text-white/70 border-2 border-transparent hover:bg-white/10"
                }`}
              >
                {lang.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ---- Chat history ---- */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {messages.length === 0 && stage === "idle" && (
          <div className="flex flex-col items-center justify-center h-full text-center opacity-40">
            <Leaf size={48} className="mb-4" />
            <p className="text-lg">
              {language === "en"
                ? "Your farming advisor is ready"
                : "\u0906\u092a\u0915\u093e \u0916\u0947\u0924\u0940 \u0938\u0932\u093e\u0939\u0915\u093e\u0930 \u0924\u0948\u092f\u093e\u0930 \u0939\u0948"}
            </p>
          </div>
        )}
        {messages.map((msg, i) => (
          <ConversationBubble
            key={i}
            type={msg.type}
            text={msg.text}
            language={currentLang.label}
            timestamp={msg.timestamp}
            audioUrl={msg.audioUrl}
          />
        ))}

        {/* Visual summary card */}
        {summary && (stage === "speaking" || stage === "done") && (
          <div className="mx-auto max-w-sm rounded-2xl bg-white/5 border border-white/10 p-5 space-y-4">
            {/* Mandi price — big */}
            <div className="text-center">
              <div className="text-xs text-white/40 uppercase tracking-wider mb-1">
                {language === "en" ? "Best Mandi" : "\u0938\u092c\u0938\u0947 \u0905\u091a\u094d\u091b\u0940 \u092e\u0902\u0921\u0940"}
              </div>
              <div className="text-3xl font-bold text-moderate">
                {summary.mandiName}
              </div>
              <div className="text-2xl font-bold text-healthy">
                {summary.mandiPrice > 0 ? `\u20b9${summary.mandiPrice.toLocaleString()}/qtl` : "--"}
              </div>
            </div>
            {/* Weather */}
            <div className="flex items-center justify-center gap-3">
              <WeatherIcon condition={summary.weatherCondition} />
              <span className="text-lg text-white/70">{summary.weatherCondition}</span>
            </div>
            {/* Crop status */}
            <div className="text-center">
              <div className="flex items-center justify-center gap-2">
                <Leaf size={20} className="text-healthy" />
                <span className="text-lg font-medium text-white/80">{summary.cropStatus}</span>
              </div>
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* ---- Bottom: Mic button area ---- */}
      <div className="flex flex-col items-center pb-8 pt-4 bg-gradient-to-t from-[#0a0f14] via-[#0a0f14] to-transparent">
        {/* Processing indicator */}
        {isProcessing && (
          <div className="mb-4 flex items-center gap-3">
            <div className="h-3 w-3 animate-pulse rounded-full bg-healthy" />
            <div className="h-3 w-3 animate-pulse rounded-full bg-healthy [animation-delay:150ms]" />
            <div className="h-3 w-3 animate-pulse rounded-full bg-healthy [animation-delay:300ms]" />
          </div>
        )}

        {/* Giant mic button */}
        <button
          onClick={handleMicTap}
          disabled={!canTap}
          className={`relative flex items-center justify-center rounded-full transition-all duration-300 ${
            isRecording
              ? "h-[170px] w-[170px] bg-stressed/90 shadow-[0_0_60px_rgba(239,68,68,0.4)]"
              : isProcessing
                ? "h-[150px] w-[150px] bg-white/10 cursor-wait"
                : "h-[170px] w-[170px] bg-healthy/80 shadow-[0_0_60px_rgba(34,197,94,0.3)] hover:shadow-[0_0_80px_rgba(34,197,94,0.5)] active:scale-95"
          }`}
          aria-label={isRecording ? "Stop recording" : "Start recording"}
        >
          {/* Pulse rings when idle/done */}
          {(stage === "idle" || stage === "done") && (
            <>
              <span className="absolute inset-0 rounded-full bg-healthy/30 animate-ping [animation-duration:2s]" />
              <span className="absolute inset-[-12px] rounded-full border-2 border-healthy/20 animate-ping [animation-duration:2.5s]" />
            </>
          )}
          {/* Pulse rings when recording */}
          {isRecording && (
            <>
              <span className="absolute inset-0 rounded-full bg-stressed/30 animate-ping [animation-duration:1s]" />
              <span className="absolute inset-[-12px] rounded-full border-2 border-stressed/20 animate-ping [animation-duration:1.3s]" />
            </>
          )}
          {/* Spinner when processing */}
          {isProcessing ? (
            <div className="h-16 w-16 animate-spin rounded-full border-4 border-healthy/30 border-t-healthy" />
          ) : isRecording ? (
            <MicOff size={56} className="relative z-10 text-white" />
          ) : (
            <Mic size={56} className="relative z-10 text-white" />
          )}
        </button>

        {/* Status label */}
        <p className="mt-4 text-lg font-medium text-white/70 animate-pulse">
          {stageLabels[stage]}
        </p>
      </div>
    </div>
  );
}
