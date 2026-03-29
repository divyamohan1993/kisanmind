"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Mic, Phone, PhoneOff, Leaf, Volume2 } from "lucide-react";
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
  { code: "brx", label: "বোড়ো" }, { code: "mni", label: "मणিपुरी" },
];

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */
interface ChatMessage {
  type: "farmer" | "kisanmind";
  text: string;
  text_en: string;
  timestamp: Date;
  kind?: "conversation" | "advisory" | "status";
}

type CallState = "pre-call" | "connecting" | "listening" | "processing" | "speaking" | "ended";

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */
async function playTTS(text: string, language: string): Promise<HTMLAudioElement | null> {
  try {
    const res = await fetch(`${API_BASE}/api/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, language }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    if (!data.audio_base64) return null;
    const audio = new Audio(`data:audio/mp3;base64,${data.audio_base64}`);
    audio.play();
    return audio;
  } catch {
    return null;
  }
}

function waitForAudioEnd(audio: HTMLAudioElement | null): Promise<void> {
  if (!audio) return Promise.resolve();
  return new Promise((resolve) => {
    audio.onended = () => resolve();
    audio.onerror = () => resolve();
  });
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */
export default function TalkPage() {
  const [language, setLanguageRaw] = useState("hi");
  useEffect(() => {
    const saved = localStorage.getItem("kisanmind_lang");
    if (saved && saved !== "hi") setLanguageRaw(saved);
  }, []);
  const setLanguage = (lang: string) => {
    setLanguageRaw(lang);
    localStorage.setItem("kisanmind_lang", lang);
  };

  const [callState, setCallState] = useState<CallState>("pre-call");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [showLangPicker, setShowLangPicker] = useState(false);
  const [statusText, setStatusText] = useState("");

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);
  const callActiveRef = useRef(false);
  const sessionIdRef = useRef("");
  const silenceCountRef = useRef(0);
  const advisoryDeliveredRef = useRef(false);
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
      setMessages((prev) => prev.map((m) => ({ ...m, text: m.text_en })));
      return;
    }
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
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [language]);

  const addMessage = useCallback((type: "farmer" | "kisanmind", text: string, kind?: "conversation" | "advisory" | "status", textEn?: string) => {
    setMessages((prev) => [...prev, { type, text, text_en: textEn || text, timestamp: new Date(), kind }]);
  }, []);

  /* ---- Mic helpers ---- */
  const startMic = useCallback(async (): Promise<void> => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamRef.current = stream;
    const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "audio/mp4";
    const recorder = new MediaRecorder(stream, { mimeType });
    chunksRef.current = [];
    recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data); };
    mediaRecorderRef.current = recorder;
    recorder.start(250);
  }, []);

  const stopMic = useCallback((): Promise<Blob> => {
    return new Promise((resolve) => {
      const recorder = mediaRecorderRef.current;
      if (!recorder || recorder.state === "inactive") { resolve(new Blob()); return; }
      recorder.onstop = () => resolve(new Blob(chunksRef.current, { type: recorder.mimeType }));
      recorder.stop();
    });
  }, []);

  const releaseMic = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  /* ---- Voice activity detection + recording ---- */
  const SILENCE_TIMEOUT = 4;
  const MAX_RECORDING = 30;

  const listenOnce = useCallback(async (): Promise<string> => {
    if (!callActiveRef.current) return "";
    setCallState("listening");
    setStatusText("");

    await startMic();

    const stream = streamRef.current;
    let isSpeaking = false;
    let silenceStart = 0;
    let hasSpokeAtAll = false;
    let analyser: AnalyserNode | null = null;

    if (stream) {
      try {
        const audioCtx = new AudioContext();
        const source = audioCtx.createMediaStreamSource(stream);
        analyser = audioCtx.createAnalyser();
        analyser.fftSize = 512;
        analyser.smoothingTimeConstant = 0.4;
        source.connect(analyser);
      } catch { /* fallback to fixed timer */ }
    }

    const getAudioLevel = (): number => {
      if (!analyser) return 0;
      const data = new Uint8Array(analyser.frequencyBinCount);
      analyser.getByteFrequencyData(data);
      let sum = 0;
      for (let i = 0; i < data.length; i++) sum += data[i];
      return sum / data.length;
    };

    const result = await new Promise<"timeout" | "silence" | "cancelled">((resolve) => {
      const startTime = Date.now();
      const interval = setInterval(() => {
        if (!callActiveRef.current) { clearInterval(interval); resolve("cancelled"); return; }
        const elapsed = (Date.now() - startTime) / 1000;
        if (elapsed >= MAX_RECORDING) { clearInterval(interval); resolve("timeout"); return; }

        const level = getAudioLevel();
        const speaking = level > 30;

        if (speaking) {
          isSpeaking = true;
          hasSpokeAtAll = true;
          silenceStart = 0;
        } else if (isSpeaking && !speaking) {
          isSpeaking = false;
          silenceStart = Date.now();
        }

        if (hasSpokeAtAll && !isSpeaking && silenceStart > 0) {
          const silenceSec = (Date.now() - silenceStart) / 1000;
          if (silenceSec >= SILENCE_TIMEOUT) {
            clearInterval(interval);
            resolve("silence");
          }
        }

        if (!hasSpokeAtAll && elapsed > 8) {
          clearInterval(interval);
          resolve("timeout");
        }
      }, 200);
    });

    if (result === "cancelled") { releaseMic(); return ""; }

    const blob = await stopMic();
    releaseMic();
    if (blob.size === 0 || !hasSpokeAtAll) return "";

    // STT
    setCallState("processing");
    setStatusText("");
    try {
      const fd = new FormData();
      fd.append("audio", blob, "recording.webm");
      fd.append("language", language);
      const res = await fetch(`${API_BASE}/api/stt`, { method: "POST", body: fd });
      const d = await res.json();
      return d.transcript || "";
    } catch { return ""; }
  }, [language, startMic, stopMic, releaseMic]);

  /* ---- Multi-turn conversation loop ---- */
  const conversationLoop = useCallback(async (): Promise<void> => {
    // First turn: send a greeting trigger to Gemini
    setCallState("processing");
    try {
      const greetResp = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionIdRef.current,
          message: "Hello, I need farming advice.",
          language,
          latitude: geo.latitude || 0,
          longitude: geo.longitude || 0,
        }),
      });
      const greetData = await greetResp.json();
      sessionIdRef.current = greetData.session_id || sessionIdRef.current;

      // Speak greeting
      setCallState("speaking");
      addMessage("kisanmind", greetData.response, "conversation", greetData.response_en || greetData.response);
      const greetAudio = await playTTS(greetData.response, language);
      await waitForAudioEnd(greetAudio);
    } catch {
      addMessage("kisanmind", "Connection issue. Please try again.", "status", "Connection issue. Please try again.");
      callActiveRef.current = false;
      setCallState("ended");
      return;
    }

    // Conversation turns
    while (callActiveRef.current) {
      const transcript = await listenOnce();

      if (!transcript.trim()) {
        silenceCountRef.current++;
        if (silenceCountRef.current >= 3) {
          callActiveRef.current = false;
          setCallState("ended");
          return;
        }
        // Ask Gemini what to say when farmer is silent
        try {
          const silenceResp = await fetch(`${API_BASE}/api/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              session_id: sessionIdRef.current,
              message: "(farmer was silent, could not hear anything)",
              language,
              latitude: geo.latitude || 0,
              longitude: geo.longitude || 0,
            }),
          });
          const silenceData = await silenceResp.json();
          setCallState("speaking");
          addMessage("kisanmind", silenceData.response, "conversation", silenceData.response_en || silenceData.response);
          const retryAudio = await playTTS(silenceData.response, language);
          await waitForAudioEnd(retryAudio);
        } catch {}
        continue;
      }

      silenceCountRef.current = 0;
      addMessage("farmer", transcript, "conversation", transcript);

      // Send to Gemini conversation — show trivia while waiting
      setCallState("processing");
      setStatusText("");

      // Show trivia only on first data fetch (not follow-ups)
      let triviaDone = false;
      if (!advisoryDeliveredRef.current) {
        const TRIVIA = [
          "Please wait... fetching live satellite data and mandi prices for you.",
          "Did you know? Selling at the right mandi can earn Rs 200-500 more per quintal.",
          "We use European Sentinel-2 satellite to check your crop health from space.",
          "Weather-informed farming reduces crop loss by up to 30%.",
        ];
        (async () => {
          for (const fact of TRIVIA) {
            if (triviaDone || !callActiveRef.current) break;
            addMessage("kisanmind", fact, "status", fact);
            await new Promise(r => setTimeout(r, 3000));
          }
        })();
      }

      try {
        const chatResp = await fetch(`${API_BASE}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: sessionIdRef.current,
            message: transcript,
            language,
            latitude: geo.latitude || 0,
            longitude: geo.longitude || 0,
          }),
        });
        triviaDone = true;
        const chatData = await chatResp.json();

        // Speak Gemini's response
        setCallState("speaking");
        const kind = chatData.has_advisory ? "advisory" : "conversation";
        if (chatData.has_advisory) advisoryDeliveredRef.current = true;
        addMessage("kisanmind", chatData.response, kind, chatData.response_en || chatData.response);
        const respAudio = await playTTS(chatData.response, language);
        currentAudioRef.current = respAudio;
        await waitForAudioEnd(respAudio);

        // If Gemini detected goodbye, end the call
        if (chatData.call_complete) {
          callActiveRef.current = false;
          setCallState("ended");
          return;
        }
        // Otherwise keep listening — farmer may ask more
      } catch {
        triviaDone = true;
        addMessage("kisanmind", "Technical issue. Please try again.", "status", "Technical issue. Please try again.");
      }
    }
  }, [language, geo.latitude, geo.longitude, listenOnce, addMessage]);

  /* ---- Start the call ---- */
  const startCall = useCallback(async () => {
    callActiveRef.current = true;
    silenceCountRef.current = 0;
    sessionIdRef.current = "";
    advisoryDeliveredRef.current = false;
    setMessages([]);
    setCallState("connecting");
    setStatusText("");

    await conversationLoop();
  }, [conversationLoop]);

  /* ---- End the call ---- */
  const endCall = useCallback(() => {
    callActiveRef.current = false;
    currentAudioRef.current?.pause();
    currentAudioRef.current = null;
    mediaRecorderRef.current?.stop();
    releaseMic();
    setCallState("ended");
    setStatusText("");
  }, [releaseMic]);

  /* ---- UI ---- */
  const isInCall = !["pre-call", "ended"].includes(callState);
  const currentLang = LANGUAGES.find((l) => l.code === language) || LANGUAGES[0];

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-white text-gray-900">
      {/* GOI Tricolor bar */}
      <div className="flex h-1.5">
        <div className="flex-1 bg-[#FF9933]" />
        <div className="flex-1 bg-white" />
        <div className="flex-1 bg-[#138808]" />
      </div>

      {/* Header — GOI style */}
      <div className="flex items-center justify-between px-4 py-3 bg-[#1a3a5c] text-white">
        <div className="flex items-center gap-2">
          <span className="text-xl">🌾</span>
          <div>
            <div className="text-sm font-bold leading-tight">KisanMind</div>
            <div className="text-[10px] text-white/60">AI Krishi Salahkaar Seva</div>
          </div>
        </div>

        {!isInCall && (
          <button
            onClick={() => setShowLangPicker(!showLangPicker)}
            className="flex items-center gap-1.5 rounded bg-white/10 px-3 py-1.5 text-xs font-medium hover:bg-white/20 border border-white/20"
          >
            {currentLang.label}
          </button>
        )}

        {isInCall && (
          <div className="flex items-center gap-2 text-xs">
            <span className="h-2 w-2 rounded-full bg-red-400 animate-pulse" />
            <span>{currentLang.label}</span>
            {callState === "listening" && <Mic size={12} className="text-green-300 animate-pulse" />}
          </div>
        )}
      </div>

      {/* Language picker */}
      {showLangPicker && !isInCall && (
        <div className="absolute top-16 left-0 right-0 z-50 bg-white border-b border-gray-200 px-4 py-4 shadow-lg">
          <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-2 max-w-2xl mx-auto">
            {LANGUAGES.map((lang) => (
              <button
                key={lang.code}
                onClick={() => { setLanguage(lang.code); setShowLangPicker(false); }}
                className={`rounded px-3 py-2.5 text-sm font-medium border ${
                  language === lang.code
                    ? "bg-[#138808] text-white border-[#138808]"
                    : "bg-gray-50 text-gray-700 border-gray-200 hover:bg-gray-100"
                }`}
              >
                {lang.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3 bg-gray-50">
        {/* Pre-call: GOI style landing */}
        {callState === "pre-call" && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="text-5xl mb-4">🌾</div>
            <h1 className="text-2xl font-bold text-[#1a3a5c]">KisanMind</h1>
            <p className="text-sm text-gray-500 mt-1">AI Krishi Salahkaar Seva</p>
            <p className="text-xs text-gray-400 mt-4 max-w-xs">Satellite + Mandi + Mausam data se aapki fasal ki salah</p>
            <div className="mt-8">
              <button
                onClick={startCall}
                className="flex items-center gap-3 px-8 py-4 rounded-lg bg-[#138808] text-white text-lg font-bold shadow-lg hover:bg-[#0f6d06] active:scale-95 transition-transform"
              >
                <Phone size={24} />
                Call KisanMind
              </button>
            </div>
            <p className="text-[10px] text-gray-400 mt-6">Aatmanirbhar Bharat | 22 Bhashayen | Satellite Data</p>
          </div>
        )}

        {/* Messages */}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.type === "farmer" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] rounded-lg px-4 py-3 leading-relaxed ${
              msg.type === "farmer"
                ? "bg-[#1a3a5c] text-white text-sm"
                : msg.kind === "advisory"
                ? "bg-white border-l-4 border-[#138808] text-gray-900 text-sm shadow-sm"
                : msg.kind === "status"
                ? "bg-gray-100 text-gray-500 text-xs italic border border-gray-200"
                : "bg-white text-gray-800 text-sm shadow-sm border border-gray-100"
            }`}>
              <div className={`text-[10px] mb-1 ${msg.type === "farmer" ? "text-white/50" : "text-gray-400"}`}>
                {msg.type === "farmer" ? "You" : "KisanMind"} · {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </div>
              {msg.text}
            </div>
          </div>
        ))}

        {/* Processing indicator */}
        {(callState === "processing" || callState === "connecting") && (
          <div className="flex justify-start">
            <div className="bg-white border border-gray-200 rounded-lg px-4 py-3 shadow-sm">
              <div className="flex gap-1.5">
                <span className="h-2 w-2 rounded-full bg-[#138808] animate-bounce" />
                <span className="h-2 w-2 rounded-full bg-[#FF9933] animate-bounce [animation-delay:150ms]" />
                <span className="h-2 w-2 rounded-full bg-[#1a3a5c] animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          </div>
        )}

        {/* Summary sheet after call ends */}
        {callState === "ended" && messages.length > 0 && (() => {
          const advisoryMsgs = messages.filter(m => m.kind === "advisory");
          const farmerMsgs = messages.filter(m => m.type === "farmer");
          if (advisoryMsgs.length === 0) return null;
          return (
            <div className="mx-auto max-w-md mt-4 rounded-lg bg-white border-2 border-[#138808] p-4 space-y-3 shadow-md">
              <div className="flex items-center justify-center gap-2">
                <div className="h-0.5 flex-1 bg-[#FF9933]" />
                <h3 className="text-xs font-bold text-[#1a3a5c] uppercase tracking-wider px-2">Call Summary</h3>
                <div className="h-0.5 flex-1 bg-[#138808]" />
              </div>
              {farmerMsgs.length > 0 && (
                <div className="text-xs text-gray-500">
                  <span className="font-medium text-gray-700">You said: </span>
                  {farmerMsgs.map(m => m.text).join(" | ")}
                </div>
              )}
              <div className="text-sm text-gray-800 leading-relaxed">
                {advisoryMsgs[advisoryMsgs.length - 1].text}
              </div>
              <div className="text-[10px] text-gray-400 text-center border-t border-gray-100 pt-2">
                KisanMind · {new Date().toLocaleDateString()} · Helpline: 1800-180-1551
              </div>
            </div>
          );
        })()}

        <div ref={chatEndRef} />
      </div>

      {/* Call controls — bottom bar */}
      {(isInCall || callState === "ended") && (
        <div className="flex flex-col items-center gap-2 px-4 py-4 bg-white border-t border-gray-200">
          {isInCall && (
            <>
              <button
                onClick={endCall}
                className="flex items-center gap-2 px-6 py-3 rounded-lg bg-red-600 text-white font-medium hover:bg-red-700 active:scale-95 transition-transform"
              >
                <PhoneOff size={18} />
                End Call
              </button>
              {callState === "listening" && (
                <div className="flex items-center gap-1.5 text-xs text-gray-500">
                  <Mic size={12} className="text-[#138808] animate-pulse" /> Listening...
                </div>
              )}
              {callState === "speaking" && (
                <div className="flex items-center gap-1.5 text-xs text-gray-500">
                  <Volume2 size={12} className="text-[#FF9933] animate-pulse" /> Speaking...
                </div>
              )}
            </>
          )}
          {callState === "ended" && (
            <button
              onClick={() => { setCallState("pre-call"); setMessages([]); }}
              className="flex items-center gap-2 px-6 py-3 rounded-lg bg-[#138808] text-white font-medium hover:bg-[#0f6d06] active:scale-95 transition-transform"
            >
              <Phone size={18} />
              New Call
            </button>
          )}
        </div>
      )}

      {/* Footer — GOI style */}
      <div className="flex h-1.5">
        <div className="flex-1 bg-[#FF9933]" />
        <div className="flex-1 bg-white" />
        <div className="flex-1 bg-[#138808]" />
      </div>
    </div>
  );
}
