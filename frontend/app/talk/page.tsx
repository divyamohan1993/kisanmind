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
/** Strip markdown formatting from Gemini responses */
function stripMarkdown(text: string): string {
  return text
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\*(.+?)\*/g, '$1')
    .replace(/#{1,6}\s*/g, '')
    .replace(/`(.+?)`/g, '$1')
    .replace(/CALL_COMPLETE:\s*/g, '')
    .trim();
}

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
  const [liveText, setLiveText] = useState("");  // Real-time speech display

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

  /* ---- Listen using Chrome Web Speech API — live transcription ---- */
  const listenOnce = useCallback(async (): Promise<string> => {
    if (!callActiveRef.current) return "";
    setCallState("listening");
    setLiveText("");

    // Map language codes to BCP47 for Web Speech API
    const speechLang: Record<string, string> = {
      hi: "hi-IN", en: "en-IN", ta: "ta-IN", te: "te-IN", bn: "bn-IN",
      mr: "mr-IN", gu: "gu-IN", kn: "kn-IN", ml: "ml-IN", pa: "pa-IN",
      or: "or-IN", as: "as-IN",
    };

    return new Promise((resolve) => {
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (!SpeechRecognition) {
        // Fallback to backend STT if Web Speech API not available
        resolve("");
        return;
      }

      const recognition = new SpeechRecognition();
      recognition.lang = speechLang[language] || "hi-IN";
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;

      let finalTranscript = "";
      let timeout: ReturnType<typeof setTimeout>;

      recognition.onresult = (event: any) => {
        let interim = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          if (event.results[i].isFinal) {
            finalTranscript += event.results[i][0].transcript + " ";
          } else {
            interim += event.results[i][0].transcript;
          }
        }
        // Show live text as farmer speaks
        setLiveText(finalTranscript + interim);

        // Reset silence timeout on each result
        clearTimeout(timeout);
        timeout = setTimeout(() => {
          recognition.stop();
        }, 3000); // 3 sec silence after speech
      };

      recognition.onerror = () => {
        clearTimeout(timeout);
        resolve(finalTranscript.trim());
      };

      recognition.onend = () => {
        clearTimeout(timeout);
        setLiveText("");
        resolve(finalTranscript.trim());
      };

      // Auto-stop after 30 seconds max
      const maxTimeout = setTimeout(() => {
        recognition.stop();
      }, 30000);

      // Stop if call ends
      const checkInterval = setInterval(() => {
        if (!callActiveRef.current) {
          clearInterval(checkInterval);
          clearTimeout(maxTimeout);
          recognition.stop();
        }
      }, 500);

      recognition.onend = () => {
        clearTimeout(timeout);
        clearTimeout(maxTimeout);
        clearInterval(checkInterval);
        setLiveText("");
        resolve(finalTranscript.trim());
      };

      recognition.start();

      // If no speech at all after 8 seconds, stop
      timeout = setTimeout(() => {
        recognition.stop();
      }, 8000);
    });
  }, [language]);

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

      // Speak dynamic trivia while data is being fetched
      let triviaDone = false;
      if (!advisoryDeliveredRef.current) {
        (async () => {
          // Fetch dynamic trivia based on what farmer said
          let facts = [
            "Your call is important. Fetching satellite data and mandi prices for you.",
          ];
          try {
            const triviaResp = await fetch(`${API_BASE}/api/trivia`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ crop: transcript, location: "", language }),
            });
            const triviaData = await triviaResp.json();
            if (triviaData.trivia?.length) facts = triviaData.trivia;
          } catch { /* use default */ }

          for (const fact of facts) {
            if (triviaDone || !callActiveRef.current) break;
            setCallState("speaking");
            addMessage("kisanmind", fact, "status", fact);
            const triviaAudio = await playTTS(fact, language);
            await waitForAudioEnd(triviaAudio);
            if (triviaDone) break;
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

        // Strip markdown and speak
        setCallState("speaking");
        const cleanResponse = stripMarkdown(chatData.response);
        const cleanResponseEn = stripMarkdown(chatData.response_en || chatData.response);
        const kind = chatData.has_advisory ? "advisory" : "conversation";
        if (chatData.has_advisory) advisoryDeliveredRef.current = true;
        addMessage("kisanmind", cleanResponse, kind, cleanResponseEn);

        // Play beep before advisory
        if (chatData.has_advisory) {
          try {
            const beepRes = await fetch(`${API_BASE}/api/beep`);
            if (beepRes.ok) {
              const beepData = await beepRes.json();
              const beep = new Audio(`data:audio/wav;base64,${beepData.audio_base64}`);
              await beep.play();
              await waitForAudioEnd(beep);
            }
          } catch { /* beep is non-critical */ }
        }

        const respAudio = await playTTS(cleanResponse, language);
        currentAudioRef.current = respAudio;
        await waitForAudioEnd(respAudio);

        // Auto-end: if advisory delivered OR goodbye detected, end the call
        if (chatData.call_complete || chatData.has_advisory) {
          callActiveRef.current = false;
          setCallState("ended");
          return;
        }
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
    setCallState("ended");
    setStatusText("");
    setLiveText("");
  }, []);

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
                <div className="flex flex-col items-center gap-1">
                  <div className="flex items-center gap-1.5 text-xs text-gray-500">
                    <Mic size={12} className="text-[#138808] animate-pulse" /> Listening...
                  </div>
                  {liveText && (
                    <div className="text-xs text-[#1a3a5c] font-medium max-w-[80vw] text-center truncate">
                      {liveText}
                    </div>
                  )}
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
