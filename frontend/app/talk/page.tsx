"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Phone, PhoneOff, Leaf, Volume2 } from "lucide-react";
import Link from "next/link";
import useGeolocation from "../hooks/useGeolocation";

/* ------------------------------------------------------------------ */
/*  Languages                                                          */
/* ------------------------------------------------------------------ */
const LANGUAGES = [
  { code: "hi", label: "हिन्दी" }, { code: "en", label: "English" },
  { code: "ta", label: "தமிழ்" }, { code: "te", label: "తెలుగు" },
  { code: "bn", label: "বাংলা" }, { code: "mr", label: "मराठी" },
  { code: "gu", label: "ગુજરાતી" }, { code: "kn", label: "ಕನ್ನಡ" },
  { code: "ml", label: "മലയാളം" }, { code: "pa", label: "ਪੰਜਾਬੀ" },
  { code: "or", label: "ଓଡ଼ିଆ" }, { code: "as", label: "অসমীয়া" },
  { code: "mai", label: "मैथिली" }, { code: "sa", label: "संस्कृतम्" },
  { code: "ne", label: "नेपाली" }, { code: "sd", label: "سنڌي" },
  { code: "doi", label: "डोगरी" }, { code: "ks", label: "كٲشُر" },
  { code: "kok", label: "कोंकणी" }, { code: "sat", label: "ᱥᱟᱱᱛᱟᱲᱤ" },
  { code: "brx", label: "বোড়ো" }, { code: "mni", label: "मणिपुरी" },
];

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */
interface ChatMessage {
  type: "farmer" | "kisanmind";
  text: string;
  text_en: string;  // English source — used for re-translation on language switch
  timestamp: Date;
  kind?: "conversation" | "advisory" | "status";
}

type CallState = "pre-call" | "connecting" | "in-call" | "ended";

/* ------------------------------------------------------------------ */
/*  PCM Audio Helpers                                                  */
/* ------------------------------------------------------------------ */

/** Convert Float32Array (Web Audio API) to Int16 PCM bytes */
function float32ToInt16(float32: Float32Array): ArrayBuffer {
  const int16 = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return int16.buffer;
}

/** Downsample from source sample rate to 16kHz */
function downsample(buffer: Float32Array, fromRate: number, toRate: number): Float32Array {
  if (fromRate === toRate) return buffer;
  const ratio = fromRate / toRate;
  const newLength = Math.round(buffer.length / ratio);
  const result = new Float32Array(newLength);
  for (let i = 0; i < newLength; i++) {
    const idx = Math.round(i * ratio);
    result[i] = buffer[Math.min(idx, buffer.length - 1)];
  }
  return result;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */
export default function TalkPage() {
  const [language, setLanguageRaw] = useState(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("kisanmind_lang") || "hi";
    }
    return "hi";
  });
  const setLanguage = (lang: string) => {
    setLanguageRaw(lang);
    if (typeof window !== "undefined") localStorage.setItem("kisanmind_lang", lang);
  };

  const [callState, setCallState] = useState<CallState>("pre-call");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [showLangPicker, setShowLangPicker] = useState(false);
  const [statusText, setStatusText] = useState("");

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const callActiveRef = useRef(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const geo = useGeolocation();

  // Auto-scroll
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Re-translate all messages when language changes
  useEffect(() => {
    if (messages.length === 0) return;
    if (language === "en") {
      // English — just use text_en directly
      setMessages((prev) => prev.map((m) => ({ ...m, text: m.text_en })));
      return;
    }
    // Batch translate all English source texts to new language
    const texts = messages.map((m) => m.text_en);
    fetch(`${API_BASE}/api/translate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ texts, target_language: language }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.translated && data.translated.length === messages.length) {
          setMessages((prev) =>
            prev.map((m, i) => ({ ...m, text: data.translated[i] }))
          );
        }
      })
      .catch(() => {}); // keep existing text on failure
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [language]);

  const addMessage = useCallback((type: "farmer" | "kisanmind", text: string, kind?: "conversation" | "advisory" | "status", textEn?: string) => {
    setMessages((prev) => [...prev, { type, text, text_en: textEn || text, timestamp: new Date(), kind }]);
  }, []);

  /* ---- PCM playback: play Gemini's audio chunks ---- */
  const playPcmChunk = useCallback((base64Pcm: string) => {
    const ctx = audioContextRef.current;
    if (!ctx) return;

    // Decode base64 to Int16 PCM (24kHz from Gemini)
    const raw = atob(base64Pcm);
    const bytes = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    const int16 = new Int16Array(bytes.buffer);

    // Convert Int16 to Float32 for Web Audio API
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) float32[i] = int16[i] / 0x7fff;

    // Create AudioBuffer at 24kHz (Gemini output rate)
    const audioBuffer = ctx.createBuffer(1, float32.length, 24000);
    audioBuffer.getChannelData(0).set(float32);

    // Queue and play
    const source = ctx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(ctx.destination);
    source.start();
  }, []);

  /* ---- Start call: open WebSocket, start mic streaming ---- */
  const startCall = useCallback(async () => {
    callActiveRef.current = true;
    setMessages([]);
    setCallState("connecting");
    setStatusText("");

    try {
      // Set up AudioContext
      const ctx = new AudioContext({ sampleRate: 16000 });
      audioContextRef.current = ctx;

      // Open WebSocket
      const wsUrl = API_BASE.replace(/^http/, "ws") + "/ws/chat";
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        // Send config
        ws.send(JSON.stringify({
          type: "config",
          language,
          latitude: geo.latitude || 0,
          longitude: geo.longitude || 0,
        }));
      };

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);

        switch (msg.type) {
          case "session_started":
            setCallState("in-call");
            setStatusText("");
            break;

          case "audio":
            playPcmChunk(msg.data);
            break;

          case "transcript":
            addMessage(
              msg.speaker === "farmer" ? "farmer" : "kisanmind",
              msg.text,
              "conversation",
              msg.text_en || msg.text
            );
            break;

          case "status":
            if (msg.status === "fetching_data") {
              setStatusText("\uD83D\uDD0D");
            } else {
              setStatusText("");
            }
            break;

          case "turn_complete":
            break;
        }
      };

      ws.onerror = () => {
        setCallState("ended");
        setStatusText("");
      };

      ws.onclose = () => {
        if (callActiveRef.current) {
          callActiveRef.current = false;
          setCallState("ended");
        }
      };

      // Start mic and stream PCM
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: true }
      });
      streamRef.current = stream;

      const source = ctx.createMediaStreamSource(stream);
      const processor = ctx.createScriptProcessor(4096, 1, 1);
      processorRef.current = processor;

      processor.onaudioprocess = (e) => {
        if (!callActiveRef.current || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
        const input = e.inputBuffer.getChannelData(0);
        const downsampled = downsample(input, ctx.sampleRate, 16000);
        const pcmBytes = float32ToInt16(downsampled);
        const base64 = btoa(String.fromCharCode(...new Uint8Array(pcmBytes)));
        wsRef.current.send(JSON.stringify({ type: "audio", data: base64 }));
      };

      source.connect(processor);
      processor.connect(ctx.destination);

    } catch (err) {
      console.error("Failed to start call:", err);
      setCallState("ended");
    }
  }, [language, geo.latitude, geo.longitude, addMessage, playPcmChunk]);

  /* ---- End call ---- */
  const endCall = useCallback(() => {
    callActiveRef.current = false;

    if (wsRef.current) {
      try { wsRef.current.send(JSON.stringify({ type: "end" })); } catch {}
      wsRef.current.close();
      wsRef.current = null;
    }

    processorRef?.current?.disconnect();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;

    audioContextRef.current?.close();
    audioContextRef.current = null;

    setCallState("ended");
    setStatusText("");
  }, []);

  /* ---- UI ---- */
  const isInCall = callState === "in-call" || callState === "connecting";
  const currentLang = LANGUAGES.find((l) => l.code === language) || LANGUAGES[0];

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[#0a0f14] text-white">
      {/* Top bar */}
      <div className="flex items-center justify-between px-4 py-3 bg-[#0d1117]/90 border-b border-white/5">
        <Link href="/" className="flex items-center gap-2">
          <span className="text-xl">{"\uD83C\uDF3E"}</span>
          <span className="text-base font-bold gradient-text">KisanMind</span>
        </Link>

        {!isInCall && (
          <button
            onClick={() => setShowLangPicker(!showLangPicker)}
            className="flex items-center gap-1.5 rounded-full bg-white/10 px-4 py-2 text-sm font-medium hover:bg-white/15"
          >
            <Volume2 size={14} />
            {currentLang.label}
          </button>
        )}

        {isInCall && (
          <div className="flex items-center gap-2 text-sm">
            <span className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
            <span className="text-white/60">{currentLang.label}</span>
            {statusText && <span className="text-white/40 text-xs">{statusText}</span>}
          </div>
        )}

        <Link href="/" className="rounded-lg bg-white/5 px-3 py-2 text-xs text-white/60 hover:bg-white/10">
          Dashboard
        </Link>
      </div>

      {/* Language picker */}
      {showLangPicker && !isInCall && (
        <div className="absolute top-14 left-0 right-0 z-50 bg-[#0d1117] border-b border-white/10 px-4 py-4 shadow-2xl">
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2 max-w-2xl mx-auto">
            {LANGUAGES.map((lang) => (
              <button
                key={lang.code}
                onClick={() => { setLanguage(lang.code); setShowLangPicker(false); }}
                className={`rounded-xl px-3 py-3 text-sm font-medium min-h-[52px] ${
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

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {callState === "pre-call" && (
          <div className="flex flex-col items-center justify-center h-full text-center opacity-50">
            <Leaf size={48} className="mb-4" />
            <p className="text-lg">{"\uD83C\uDF3E"} KisanMind</p>
            <p className="text-sm mt-2 text-white/40">Tap the green button to start</p>
          </div>
        )}

        {callState === "connecting" && (
          <div className="flex justify-center mt-8">
            <div className="bg-emerald-600/10 border border-emerald-500/20 rounded-2xl px-6 py-4">
              <div className="flex gap-1.5 justify-center">
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-bounce" />
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-bounce [animation-delay:150ms]" />
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          </div>
        )}

        {/* Messages */}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.type === "farmer" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] rounded-2xl px-4 py-3 leading-relaxed ${
              msg.type === "farmer"
                ? "bg-blue-600/20 border border-blue-500/20 text-white/90 text-sm"
                : msg.kind === "status"
                ? "bg-white/5 border border-white/10 text-white/60 text-xs italic"
                : "bg-emerald-600/10 border border-emerald-500/20 text-white/90 text-sm"
            }`}>
              <div className="text-[10px] text-white/30 mb-1">
                {msg.type === "farmer" ? "You" : "KisanMind"} · {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </div>
              {msg.text}
            </div>
          </div>
        ))}

        <div ref={chatEndRef} />
      </div>

      {/* Call controls */}
      <div className="flex flex-col items-center gap-4 px-4 py-6 bg-[#0d1117]/80 border-t border-white/5">
        {callState === "pre-call" && (
          <button
            onClick={startCall}
            className="flex h-20 w-20 items-center justify-center rounded-full bg-gradient-to-br from-emerald-500 to-emerald-700 shadow-lg shadow-emerald-500/30 hover:scale-105 active:scale-95 transition-transform"
          >
            <Phone size={32} className="text-white" />
          </button>
        )}

        {isInCall && (
          <button
            onClick={endCall}
            className="flex h-16 w-16 items-center justify-center rounded-full bg-gradient-to-br from-red-500 to-red-700 shadow-lg shadow-red-500/30 hover:scale-105 active:scale-95 transition-transform"
          >
            <PhoneOff size={28} className="text-white" />
          </button>
        )}

        {callState === "ended" && (
          <button
            onClick={() => { setCallState("pre-call"); setMessages([]); }}
            className="flex h-20 w-20 items-center justify-center rounded-full bg-gradient-to-br from-emerald-500 to-emerald-700 shadow-lg shadow-emerald-500/30 hover:scale-105 active:scale-95 transition-transform"
          >
            <Phone size={32} className="text-white" />
          </button>
        )}

        {isInCall && (
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs text-white/40">Live</span>
          </div>
        )}
      </div>
    </div>
  );
}
