"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Phone, PhoneOff, Mic, Volume2 } from "lucide-react";
import useGeolocation from "./useGeolocation";

const LANGUAGES = [
  { code: "hi", label: "हिन्दी" }, { code: "en", label: "English" },
  { code: "ta", label: "தமிழ்" }, { code: "te", label: "తెలుగు" },
  { code: "bn", label: "বাংলা" }, { code: "mr", label: "मराठी" },
  { code: "gu", label: "ગુજરાતી" }, { code: "kn", label: "ಕನ್ನಡ" },
  { code: "ml", label: "മലയാളം" }, { code: "pa", label: "ਪੰਜਾਬੀ" },
];

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface ChatMessage { type: "farmer" | "kisanmind"; text: string; text_en: string; timestamp: Date; kind?: "conversation" | "advisory" | "status"; }
type CallState = "pre-call" | "connecting" | "listening" | "processing" | "speaking" | "ended";

function stripMarkdown(t: string): string {
  return t.replace(/\*\*(.+?)\*\*/g, '$1').replace(/\*(.+?)\*/g, '$1').replace(/#{1,6}\s*/g, '').replace(/`(.+?)`/g, '$1').replace(/CALL_COMPLETE:\s*/g, '').trim();
}

async function playTTS(text: string, language: string): Promise<HTMLAudioElement | null> {
  try {
    const res = await fetch(`${API_BASE}/api/tts`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, language }) });
    if (!res.ok) return null;
    const data = await res.json();
    if (!data.audio_base64) return null;
    const audio = new Audio(`data:audio/mp3;base64,${data.audio_base64}`);
    audio.play();
    return audio;
  } catch { return null; }
}

function waitForAudioEnd(audio: HTMLAudioElement | null): Promise<void> {
  if (!audio) return Promise.resolve();
  return new Promise((resolve) => { audio.onended = () => resolve(); audio.onerror = () => resolve(); });
}

export default function TalkPage() {
  const [language, setLanguage] = useState("hi");
  useEffect(() => { const s = localStorage.getItem("kisanmind_lang"); if (s) setLanguage(s); }, []);
  const setLang = (l: string) => { setLanguage(l); localStorage.setItem("kisanmind_lang", l); };

  // Use refs for values needed in long-running async loops
  const languageRef = useRef(language);
  useEffect(() => { languageRef.current = language; }, [language]);

  const [callState, setCallState] = useState<CallState>("pre-call");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [liveText, setLiveText] = useState("");
  const [showLang, setShowLang] = useState(false);
  const [locationInput, setLocationInput] = useState("");
  const [askingLocation, setAskingLocation] = useState(false);

  const currentAudioRef = useRef<HTMLAudioElement | null>(null);
  const callActiveRef = useRef(false);
  const sessionIdRef = useRef("");
  const silenceCountRef = useRef(0);
  const advisoryDeliveredRef = useRef(false);
  const [callSummary, setCallSummary] = useState("");
  const [geminiError, setGeminiError] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const geo = useGeolocation();
  const geoRef = useRef(geo);
  useEffect(() => { geoRef.current = geo; }, [geo]);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  // Re-translate messages on language change
  useEffect(() => {
    if (messages.length === 0) return;
    if (language === "en") { setMessages(prev => prev.map(m => ({ ...m, text: m.text_en }))); return; }
    fetch(`${API_BASE}/api/translate`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ texts: messages.map(m => m.text_en), target_language: language }) })
      .then(r => r.json()).then(d => { if (d.translated?.length === messages.length) setMessages(prev => prev.map((m, i) => ({ ...m, text: d.translated[i] }))); }).catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [language]);

  const addMsg = useCallback((type: "farmer" | "kisanmind", text: string, kind?: "conversation" | "advisory" | "status", textEn?: string) => {
    setMessages(prev => [...prev, { type, text, text_en: textEn || text, timestamp: new Date(), kind }]);
  }, []);

  // Listen using Chrome Web Speech API
  const listenOnce = useCallback(async (): Promise<string> => {
    if (!callActiveRef.current) return "";
    setCallState("listening"); setLiveText("");
    const langMap: Record<string, string> = { hi: "hi-IN", en: "en-IN", ta: "ta-IN", te: "te-IN", bn: "bn-IN", mr: "mr-IN", gu: "gu-IN", kn: "kn-IN", ml: "ml-IN", pa: "pa-IN" };
    return new Promise((resolve) => {
      const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (!SR) { resolve(""); return; }
      const rec = new SR();
      const lang = languageRef.current;
      rec.lang = langMap[lang] || "hi-IN"; rec.continuous = false; rec.interimResults = true;
      let final = ""; let to: ReturnType<typeof setTimeout>;
      rec.onresult = (e: any) => {
        let interim = "";
        for (let i = e.resultIndex; i < e.results.length; i++) { if (e.results[i].isFinal) final += e.results[i][0].transcript + " "; else interim += e.results[i][0].transcript; }
        setLiveText(final + interim);
        clearTimeout(to); to = setTimeout(() => rec.stop(), 3000);
      };
      rec.onerror = () => { clearTimeout(to); resolve(final.trim()); };
      rec.onend = () => { clearTimeout(to); setLiveText(""); resolve(final.trim()); };
      rec.start();
      to = setTimeout(() => rec.stop(), 8000);
      const ci = setInterval(() => { if (!callActiveRef.current) { clearInterval(ci); rec.stop(); } }, 500);
      rec.onend = () => { clearTimeout(to); clearInterval(ci); setLiveText(""); resolve(final.trim()); };
    });
  }, []);

  // Multi-turn conversation — uses refs for always-current language & geo
  const conversationLoop = useCallback(async () => {
    const lang = () => languageRef.current;
    const lat = () => geoRef.current.latitude || 0;
    const lon = () => geoRef.current.longitude || 0;

    setCallState("processing");
    try {
      const g = await fetch(`${API_BASE}/api/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: sessionIdRef.current, message: "Hello, I need farming advice.", language: lang(), latitude: lat(), longitude: lon() }) });
      const gd = await g.json(); sessionIdRef.current = gd.session_id || sessionIdRef.current;
      setCallState("speaking"); addMsg("kisanmind", stripMarkdown(gd.response), "conversation", stripMarkdown(gd.response_en || gd.response));
      const ga = await playTTS(gd.response, lang()); await waitForAudioEnd(ga);
    } catch { addMsg("kisanmind", "Connection issue.", "status", "Connection issue."); callActiveRef.current = false; setCallState("ended"); return; }

    while (callActiveRef.current) {
      const transcript = await listenOnce();
      if (!transcript.trim()) { silenceCountRef.current++; if (silenceCountRef.current >= 3) { callActiveRef.current = false; setCallState("ended"); return; } continue; }
      silenceCountRef.current = 0;
      addMsg("farmer", transcript, "conversation", transcript);
      setCallState("processing");

      try {
        const cr = await fetch(`${API_BASE}/api/chat`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: sessionIdRef.current, message: transcript, language: lang(), latitude: lat(), longitude: lon() }) });
        const cd = await cr.json();
        setCallState("speaking");
        const clean = stripMarkdown(cd.response); const cleanEn = stripMarkdown(cd.response_en || cd.response);
        if (clean.includes("Technical issue") || clean.includes("Gemini AI may be overloaded")) setGeminiError(true);
        const kind = cd.has_advisory ? "advisory" : "conversation";
        if (cd.has_advisory) advisoryDeliveredRef.current = true;
        addMsg("kisanmind", clean, kind, cleanEn);
        if (cd.has_advisory) { try { const b = await fetch(`${API_BASE}/api/beep`); if (b.ok) { const bd = await b.json(); const beep = new Audio(`data:audio/wav;base64,${bd.audio_base64}`); await beep.play(); await waitForAudioEnd(beep); } } catch {} }
        const ra = await playTTS(clean, lang()); currentAudioRef.current = ra; await waitForAudioEnd(ra);
        if (cd.call_complete) { callActiveRef.current = false; setCallState("ended"); return; }
      } catch { setGeminiError(true); addMsg("kisanmind", "Technical issue. Gemini AI may be overloaded — please try again in a moment.", "status", "Technical issue. Gemini AI may be overloaded — please try again in a moment."); }
    }
  }, [listenOnce, addMsg]);

  // Resolve location from text input via backend geocoding
  const resolveLocationByName = useCallback(async (name: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/geocode-name`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ location_name: name }) });
      if (res.ok) {
        const data = await res.json();
        if (data.latitude && data.longitude) {
          geoRef.current = { ...geoRef.current, latitude: data.latitude, longitude: data.longitude, accuracy: 1000, loading: false, error: null };
        }
      }
    } catch {}
  }, []);

  const startCall = useCallback(async () => {
    // Re-request GPS for freshest location
    geoRef.current.refresh();
    setCallState("connecting");

    // Wait up to 5 seconds for GPS
    for (let i = 0; i < 10; i++) {
      await new Promise(r => setTimeout(r, 500));
      if (geoRef.current.latitude && geoRef.current.longitude) break;
    }

    // If still no GPS, ask user for location
    if (!geoRef.current.latitude || !geoRef.current.longitude) {
      setAskingLocation(true);
      setCallState("pre-call");
      return;
    }

    callActiveRef.current = true; silenceCountRef.current = 0; sessionIdRef.current = ""; advisoryDeliveredRef.current = false;
    setMessages([]);
    await conversationLoop();
  }, [conversationLoop]);

  const startCallWithLocation = useCallback(async () => {
    if (!locationInput.trim()) return;
    setAskingLocation(false);
    setCallState("connecting");
    await resolveLocationByName(locationInput.trim());
    callActiveRef.current = true; silenceCountRef.current = 0; sessionIdRef.current = ""; advisoryDeliveredRef.current = false;
    setMessages([]);
    await conversationLoop();
  }, [conversationLoop, locationInput, resolveLocationByName]);

  const endCall = useCallback(() => {
    callActiveRef.current = false; currentAudioRef.current?.pause(); currentAudioRef.current = null;
    setCallState("ended"); setLiveText("");
  }, []);

  // Generate summary when call ends
  useEffect(() => {
    if (callState !== "ended" || messages.length === 0) return;
    const advisories = messages.filter(m => m.kind === "advisory");
    if (advisories.length === 0) { setCallSummary(""); return; }
    const fullText = advisories.map(m => m.text_en).join("\n");
    setCallSummary("...");
    fetch(`${API_BASE}/api/summarize`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: fullText, language: languageRef.current }) })
      .then(r => r.json()).then(d => setCallSummary(d.summary || "")).catch(() => setCallSummary(""));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [callState]);

  const isInCall = !["pre-call", "ended"].includes(callState);
  const advisoryMsgs = messages.filter(m => m.kind === "advisory");
  const farmerMsgs = messages.filter(m => m.type === "farmer");

  return (
    <div className="min-h-screen bg-[#fafafa] text-gray-900" style={{ fontFamily: "'Inter', sans-serif" }}>
      {/* Skip navigation link — WCAG 2.2 AAA */}
      <a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:bg-white focus:px-4 focus:py-2 focus:text-[#1a365d] focus:rounded focus:shadow-lg focus:text-sm focus:font-medium">
        Skip to main content
      </a>

      {/* Tricolor strip */}
      <div className="flex h-1.5" role="presentation"><div className="flex-1 bg-[#FF9933]" /><div className="flex-1 bg-white" /><div className="flex-1 bg-[#138808]" /></div>

      {/* Header */}
      <header className="bg-[#1a365d] text-white py-6 relative" role="banner">
        <div className="max-w-4xl mx-auto px-4 text-center">
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">🌾 KisanMind</h1>
          <p className="text-sm mt-1">AI Krishi Salahkaar Seva | आत्मनिर्भर भारत</p>
        </div>
        <div className="absolute bottom-0 left-0 right-0 h-1.5" style={{ background: "linear-gradient(90deg, #FF9933 33%, #fff 33%, #fff 66%, #138808 66%)" }} />
      </header>

      {/* Gemini overload banner */}
      {geminiError && (
        <div className="bg-red-600 text-white text-center py-3 px-4 text-sm font-medium">
          Gemini AI is currently overloaded. Please try again after some time. We do not know when Gemini will be back.
        </div>
      )}

      <main id="main-content" className="max-w-4xl mx-auto px-4 py-6" role="main">
        {/* Pre-call: Project info + Call button */}
        {callState === "pre-call" && !advisoryMsgs.length && (
          <>
            {/* Call CTA */}
            <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6 mb-6 text-center">
              <p className="text-gray-800 text-sm mb-4">Satellite + Mandi + Mausam = Smart Farming Decisions</p>

              {/* Language selector */}
              <div className="flex flex-wrap justify-center gap-2 mb-6" role="group" aria-label="Language selection">
                {LANGUAGES.map(l => (
                  <button key={l.code} onClick={() => setLang(l.code)}
                    aria-label={`Select ${l.label}`}
                    aria-current={language === l.code ? "true" : undefined}
                    className={`px-3 py-1.5 min-h-[44px] min-w-[44px] rounded text-sm border ${language === l.code ? "bg-[#138808] text-white border-[#138808]" : "bg-white text-gray-800 border-gray-200 hover:bg-gray-50"}`}>
                    {l.label}
                  </button>
                ))}
              </div>

              {askingLocation ? (
                <div className="space-y-3">
                  <label htmlFor="location-input" className="text-sm text-gray-800 block">GPS unavailable. Enter your village/town:</label>
                  <input id="location-input" type="text" value={locationInput} onChange={e => setLocationInput(e.target.value)}
                    onKeyDown={e => e.key === "Enter" && startCallWithLocation()}
                    placeholder="e.g. Solan, Himachal Pradesh"
                    aria-label="Enter your village or town name"
                    className="w-full max-w-xs mx-auto block px-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#138808]" autoFocus />
                  <button onClick={startCallWithLocation}
                    aria-label="Start Call"
                    className="inline-flex items-center gap-3 px-10 py-4 rounded-lg bg-[#138808] text-white text-lg font-bold shadow-lg hover:bg-[#0f6d06] active:scale-95 transition-transform">
                    <Phone size={24} /> Start Call
                  </button>
                </div>
              ) : (
                <>
                  <button onClick={startCall}
                    aria-label="Call KisanMind"
                    className="inline-flex items-center gap-3 px-10 py-4 rounded-lg bg-[#138808] text-white text-lg font-bold shadow-lg hover:bg-[#0f6d06] active:scale-95 transition-transform">
                    <Phone size={24} /> Call KisanMind
                  </button>
                  <p className="text-xs text-gray-700 mt-3">Tap to speak with your AI farming advisor in your language</p>
                  <p className="text-xs text-gray-700 mt-1">Advice generation fetches live satellite + mandi + weather data — may take up to 1 minute. You will hear a beep when ready.</p>
                </>
              )}
            </div>

            {/* Data sources — visible on desktop */}
            <div className="hidden md:grid grid-cols-3 gap-4 mb-6">
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <h2 className="font-semibold text-[#1a365d] text-sm mb-2">🛰 Satellite Data</h2>
                <ul className="text-xs text-gray-700 space-y-1">
                  <li>Sentinel-2 — Crop health (NDVI)</li>
                  <li>Sentinel-1 SAR — Soil moisture</li>
                  <li>MODIS Terra — Surface temperature</li>
                  <li>NASA SMAP — Root zone moisture</li>
                </ul>
              </div>
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <h2 className="font-semibold text-[#1a365d] text-sm mb-2">📊 Mandi Prices</h2>
                <ul className="text-xs text-gray-700 space-y-1">
                  <li>AgMarkNet — Govt. of India live data</li>
                  <li>106 crops cached daily</li>
                  <li>Net profit after transport + commission</li>
                  <li>Best mandi recommendation</li>
                </ul>
              </div>
              <div className="bg-white rounded-lg border border-gray-200 p-4">
                <h2 className="font-semibold text-[#1a365d] text-sm mb-2">🌤 Weather</h2>
                <ul className="text-xs text-gray-700 space-y-1">
                  <li>Open-Meteo — 5 day forecast</li>
                  <li>Rain alerts with dates</li>
                  <li>Temperature & humidity</li>
                  <li>Crop-specific action items</li>
                </ul>
              </div>
            </div>

            {/* Project info card */}
            <div className="bg-white rounded-lg border border-gray-200 p-4 text-xs text-gray-700">
              <p><strong>KisanMind</strong> uses AI + real satellite data to give personalized farming advice to 150M+ Indian farmers in 22 languages. Voice-first, designed for farmers in the field.</p>
              <p className="mt-2">Data: ESA Sentinel-2, Sentinel-1 SAR, NASA SMAP, MODIS Terra, AgMarkNet, Open-Meteo | AI: Google Gemini | 22 Indian languages | KVK referral network</p>
            </div>
          </>
        )}

        {/* In-call: Chat interface */}
        {isInCall && (
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
            {/* Call header */}
            <div className="bg-[#1a365d] text-white px-4 py-2 flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm">
                <span className="h-2 w-2 rounded-full bg-red-400 animate-pulse" />
                <span>KisanMind</span>
                {callState === "listening" && <Mic size={12} className="text-green-300 animate-pulse" />}
              </div>
              <button onClick={() => setShowLang(!showLang)} aria-label="Change language" className="text-xs text-white hover:underline">
                {LANGUAGES.find(l => l.code === language)?.label}
              </button>
            </div>

            {showLang && (
              <div className="bg-gray-50 px-4 py-2 flex flex-wrap gap-2 border-b" role="group" aria-label="Language selection">
                {LANGUAGES.map(l => (
                  <button key={l.code} onClick={() => { setLang(l.code); setShowLang(false); }}
                    aria-label={`Select ${l.label}`}
                    aria-current={language === l.code ? "true" : undefined}
                    className={`px-2 py-1 min-h-[44px] min-w-[44px] rounded text-xs ${language === l.code ? "bg-[#138808] text-white" : "bg-white text-gray-800 border border-gray-200"}`}>
                    {l.label}
                  </button>
                ))}
              </div>
            )}

            {/* Messages */}
            <div className="p-4 space-y-3 max-h-[60vh] overflow-y-auto bg-gray-50" role="log" aria-live="polite" aria-label="Conversation messages" lang={language}>
              {messages.filter(m => m.kind !== "status" || !advisoryDeliveredRef.current).map((msg, i) => (
                <div key={i} className={`flex ${msg.type === "farmer" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[85%] rounded-lg px-3 py-2 text-sm leading-relaxed ${
                    msg.type === "farmer" ? "bg-[#1a365d] text-white"
                    : msg.kind === "advisory" ? "bg-white border-l-4 border-[#138808] shadow-sm text-gray-900"
                    : msg.kind === "status" ? "bg-gray-100 text-gray-700 text-xs italic"
                    : "bg-white text-gray-800 shadow-sm border border-gray-100"
                  }`}>
                    {msg.text}
                  </div>
                </div>
              ))}

              {(callState === "processing" || callState === "connecting") && (
                <div className="flex justify-start" role="status" aria-live="assertive" aria-busy="true" aria-label={messages.filter(m => m.type === "farmer").length >= 2 ? "Generating advice — may take up to 1 minute" : "Processing"}>
                  <div className="bg-white border border-gray-200 rounded-lg px-4 py-3 shadow-sm">
                    <div className="flex gap-1.5">
                      <span className="h-2 w-2 rounded-full bg-[#138808] animate-bounce" />
                      <span className="h-2 w-2 rounded-full bg-[#FF9933] animate-bounce [animation-delay:150ms]" />
                      <span className="h-2 w-2 rounded-full bg-[#1a365d] animate-bounce [animation-delay:300ms]" />
                    </div>
                    {messages.filter(m => m.type === "farmer").length >= 2 && !advisoryDeliveredRef.current && (
                      <div className="mt-2 bg-[#FFF7ED] border border-[#FF9933]/30 rounded p-2">
                        <p className="text-xs font-semibold text-[#1a365d]">🛰️ Generating your advisory...</p>
                        <p className="text-xs text-gray-700 mt-0.5">Fetching live data from 4 satellites + mandi prices + weather. This may take up to 1 minute.</p>
                        <p className="text-xs text-gray-700 mt-0.5">You will hear a <strong>beep</strong> when your advice is ready.</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Call controls */}
            <div className="px-4 py-3 bg-white border-t border-gray-100 flex flex-col items-center gap-2">
              <button onClick={endCall} aria-label="End Call" className="flex items-center gap-2 px-5 py-2 min-h-[44px] rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700">
                <PhoneOff size={16} /> End Call
              </button>
              {callState === "listening" && liveText && (
                <p className="text-xs text-[#1a365d] font-medium text-center max-w-[80%] truncate">{liveText}</p>
              )}
              {callState === "listening" && <p role="status" aria-live="assertive" className="text-xs text-gray-700 flex items-center gap-1"><Mic size={10} className="text-[#138808]" /> Listening...</p>}
              {callState === "speaking" && <p role="status" aria-live="assertive" className="text-xs text-gray-700 flex items-center gap-1"><Volume2 size={10} className="text-[#FF9933]" /> Speaking...</p>}
            </div>
          </div>
        )}

        {/* Call ended with advisory — show summary-only screen */}
        {callState === "ended" && advisoryMsgs.length > 0 && (
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
            <div className="flex items-center gap-2 mb-4">
              <div className="h-0.5 flex-1 bg-[#FF9933]" />
              <h2 className="text-sm font-bold text-[#1a365d] uppercase tracking-wider">Call Summary</h2>
              <div className="h-0.5 flex-1 bg-[#138808]" />
            </div>

            {farmerMsgs.length > 0 && (
              <div className="mb-4 p-3 bg-gray-50 rounded-lg">
                <p className="text-xs font-semibold text-gray-800 mb-1">Your Questions:</p>
                <p className="text-sm text-gray-700">{farmerMsgs.map(m => m.text).join(" | ")}</p>
              </div>
            )}

            <div className="text-sm text-gray-900 leading-relaxed mb-4 whitespace-pre-line">
              {callSummary === "..." ? (
                <div className="flex items-center gap-2 text-gray-700" role="status" aria-live="polite">
                  <span className="h-2 w-2 rounded-full bg-[#138808] animate-bounce" />
                  <span>Generating summary...</span>
                </div>
              ) : callSummary || advisoryMsgs[advisoryMsgs.length - 1].text}
            </div>

            <div className="border-t border-gray-100 pt-4 mt-4">
              <p className="text-xs text-gray-700 text-center mb-4">
                KisanMind · {new Date().toLocaleDateString()} · KVK Helpline: 1800-180-1551
              </p>
              <div className="text-center">
                <button onClick={() => { setCallState("pre-call"); setMessages([]); setCallSummary(""); }}
                  aria-label="Start a new call"
                  className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-[#138808] text-white text-sm font-medium hover:bg-[#0f6d06] min-h-[44px]">
                  <Phone size={16} /> New Call
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Call ended without advisory — show messages only */}
        {callState === "ended" && messages.length > 0 && advisoryMsgs.length === 0 && (
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
            {/* Show messages only - no summary */}
            <div className="p-4 space-y-3 max-h-[60vh] overflow-y-auto bg-gray-50" role="log">
              {messages.map((msg, i) => (
                <div key={i} className={`flex ${msg.type === "farmer" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[85%] rounded-lg px-3 py-2 text-sm leading-relaxed ${
                    msg.type === "farmer" ? "bg-[#1a365d] text-white" : "bg-white text-gray-900 shadow-sm border border-gray-100"
                  }`}>
                    {msg.text}
                  </div>
                </div>
              ))}
            </div>
            <div className="px-4 py-3 bg-white border-t border-gray-100 text-center">
              <button onClick={() => { setCallState("pre-call"); setMessages([]); }}
                aria-label="Start a new call"
                className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-[#138808] text-white text-sm font-medium hover:bg-[#0f6d06] min-h-[44px]">
                <Phone size={16} /> New Call
              </button>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="text-center py-4 text-xs text-gray-700 border-t border-gray-100 mt-8" role="contentinfo">
        <p>KisanMind · AI Krishi Salahkaar Seva · ET GenAI Hackathon 2026</p>
        <p className="mt-1 text-xs">Data: ESA Sentinel-2, Sentinel-1, NASA SMAP, MODIS, AgMarkNet, Open-Meteo</p>
      </footer>

      <div className="flex h-1.5" role="presentation"><div className="flex-1 bg-[#FF9933]" /><div className="flex-1 bg-white" /><div className="flex-1 bg-[#138808]" /></div>
    </div>
  );
}
