"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Mic, Phone, PhoneOff, Sun, CloudRain, Cloud, Leaf, Volume2, TrendingUp, MapPin, Thermometer } from "lucide-react";
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

// Greetings — GPS handles location automatically, only ask for crop
function getGreeting(lang: string, hasGps: boolean): string {
  if (hasGps) {
    const g: Record<string, string> = {
      hi: "नमस्ते किसान भाई! मैं किसानमाइंड हूँ, आपका खेती सलाहकार। आपकी लोकेशन मिल गई है। बस बताइए, आप कौनसी फसल उगा रहे हैं?",
      en: "Welcome farmer! I am KisanMind, your agriculture advisor. I have your location. Just tell me which crop you are growing.",
      ta: "வணக்கம் விவசாயி! நான் கிசான்மைண்ட். உங்கள் இருப்பிடம் கிடைத்துவிட்டது. நீங்கள் எந்தப் பயிரை பயிரிடுகிறீர்கள் என்று மட்டும் சொல்லுங்கள்.",
      te: "నమస్కారం రైతు! నేను కిసాన్‌మైండ్. మీ లొకేషన్ దొరికింది. మీరు ఏ పంట పండిస్తున్నారో చెప్పండి.",
      bn: "নমস্কার কৃষক ভাই! আমি কিষাণমাইন্ড। আপনার লোকেশন পেয়ে গেছি। শুধু বলুন, কোন ফসল চাষ করছেন?",
      mr: "नमस्कार शेतकरी बंधू! मी किसानमाइंड. तुमची लोकेशन मिळाली. फक्त सांगा, कोणतं पीक घेत आहात?",
      pa: "ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਕਿਸਾਨ ਵੀਰ! ਮੈਂ ਕਿਸਾਨਮਾਈਂਡ ਹਾਂ। ਤੁਹਾਡੀ ਲੋਕੇਸ਼ਨ ਮਿਲ ਗਈ ਹੈ। ਬੱਸ ਦੱਸੋ, ਕਿਹੜੀ ਫਸਲ ਉਗਾ ਰਹੇ ਹੋ?",
      gu: "નમસ્તે ખેડૂત ભાઈ! હું કિસાનમાઈન્ડ છું. તમારું લોકેશન મળી ગયું. બસ કહો, કઈ ફસલ ઉગાડો છો?",
      kn: "ನಮಸ್ಕಾರ ರೈತ ಬಂಧು! ನಾನು ಕಿಸಾನ್‌ಮೈಂಡ್. ನಿಮ್ಮ ಲೊಕೇಶನ್ ಸಿಕ್ಕಿದೆ. ಯಾವ ಬೆಳೆ ಬೆಳೆಯುತ್ತಿದ್ದೀರಿ ಅಷ್ಟೇ ಹೇಳಿ.",
      ml: "നമസ്കാരം കർഷക സഹോദരാ! ഞാൻ കിസാൻമൈൻഡ്. നിങ്ങളുടെ ലൊക്കേഷൻ കിട്ടി. ഏത് വിള കൃഷി ചെയ്യുന്നു എന്ന് മാത്രം പറയൂ.",
    };
    return g[lang] || g["hi"];
  }
  // No GPS — ask for both crop and location
  const g: Record<string, string> = {
    hi: "नमस्ते किसान भाई! मैं किसानमाइंड हूँ। आपकी लोकेशन नहीं मिल पाई। कृपया बताइए, आप कहाँ हैं और कौनसी फसल उगा रहे हैं?",
    en: "Welcome farmer! I am KisanMind. I could not detect your location. Please tell me where you are and which crop you are growing.",
  };
  return g[lang] || g["hi"];
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */
interface ChatMessage {
  type: "farmer" | "kisanmind";
  text: string;
  timestamp: Date;
}

interface CallSummary {
  location?: string;
  crop?: string;
  bestMandi?: string;
  bestPrice?: number;
  localMandi?: string;
  localPrice?: number;
  distanceKm?: number;
  weatherDays?: Array<{ date: string; max_temp_c: number; min_temp_c: number; precipitation_mm: number }>;
  advisory?: string;
}

type CallState = "pre-call" | "greeting" | "listening" | "processing" | "speaking" | "ended";

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
  const [language, setLanguage] = useState("hi");
  const [callState, setCallState] = useState<CallState>("pre-call");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [summary, setSummary] = useState<CallSummary | null>(null);
  const [showLangPicker, setShowLangPicker] = useState(false);
  const [statusText, setStatusText] = useState("");
  const [countdown, setCountdown] = useState<number | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);
  const callActiveRef = useRef(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const geo = useGeolocation();

  // Auto-scroll
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, summary]);

  /* ---- Mic helpers ---- */
  const startMic = useCallback(async (): Promise<void> => {
    try {
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
    } catch {
      console.error("Mic access denied");
    }
  }, []);

  const stopMic = useCallback((): Promise<Blob> => {
    return new Promise((resolve) => {
      const recorder = mediaRecorderRef.current;
      if (!recorder || recorder.state === "inactive") { resolve(new Blob()); return; }
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType });
        resolve(blob);
      };
      recorder.stop();
    });
  }, []);

  const releaseMic = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const silenceCountRef = useRef(0);

  /* ---- Smart voice-activity-aware recording ---- */
  // Records continuously. When farmer pauses, starts a silence countdown.
  // If farmer speaks again, resets countdown. Only stops after sustained silence.

  const SILENCE_TIMEOUT = 4; // seconds of silence before processing
  const MAX_RECORDING = 30;  // hard max recording time

  const listenOnce = useCallback(async (): Promise<string> => {
    if (!callActiveRef.current) return "";
    setCallState("listening");
    setStatusText(language === "en" ? "Speak..." : "बोलिए...");
    setCountdown(null);

    await startMic();

    // Set up audio level monitoring via AnalyserNode
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
      } catch { /* analyser not available — fall back to fixed timer */ }
    }

    const getAudioLevel = (): number => {
      if (!analyser) return 0;
      const data = new Uint8Array(analyser.frequencyBinCount);
      analyser.getByteFrequencyData(data);
      let sum = 0;
      for (let i = 0; i < data.length; i++) sum += data[i];
      return sum / data.length;
    };

    // Poll audio level every 200ms
    const result = await new Promise<"timeout" | "silence" | "cancelled">((resolve) => {
      const startTime = Date.now();
      const interval = setInterval(() => {
        if (!callActiveRef.current) { clearInterval(interval); resolve("cancelled"); return; }

        const elapsed = (Date.now() - startTime) / 1000;
        if (elapsed >= MAX_RECORDING) { clearInterval(interval); resolve("timeout"); return; }

        const level = getAudioLevel();
        const speaking = level > 12; // threshold for speech vs silence

        if (speaking) {
          isSpeaking = true;
          hasSpokeAtAll = true;
          silenceStart = 0;
          setCountdown(null);
          setStatusText(language === "en" ? "Listening..." : "सुन रहे हैं...");
        } else if (isSpeaking && !speaking) {
          // Just went silent after speaking
          isSpeaking = false;
          silenceStart = Date.now();
        }

        // If farmer spoke and then went silent, start countdown
        if (hasSpokeAtAll && !isSpeaking && silenceStart > 0) {
          const silenceSec = (Date.now() - silenceStart) / 1000;
          const remaining = Math.ceil(SILENCE_TIMEOUT - silenceSec);
          if (remaining > 0) {
            setCountdown(remaining);
            setStatusText(language === "en" ? "Continue or wait..." : "बोलें या रुकें...");
          } else {
            clearInterval(interval);
            resolve("silence");
          }
        }

        // If no speech at all after 8 seconds, give up
        if (!hasSpokeAtAll && elapsed > 8) {
          clearInterval(interval);
          resolve("timeout");
        }
      }, 200);
    });

    setCountdown(null);

    if (result === "cancelled") { releaseMic(); return ""; }

    const blob = await stopMic();
    releaseMic();
    if (blob.size === 0 || !hasSpokeAtAll) return "";

    // STT
    setCallState("processing");
    setStatusText(language === "en" ? "Processing..." : "प्रोसेसिंग...");
    try {
      const fd = new FormData();
      fd.append("audio", blob, "recording.webm");
      fd.append("language", language);
      const res = await fetch(`${API_BASE}/api/stt`, { method: "POST", body: fd });
      const d = await res.json();
      return d.transcript || "";
    } catch { return ""; }
  }, [language, startMic, stopMic, releaseMic]);

  /* ---- The full call flow ---- */
  const processOneTurn = useCallback(async (): Promise<void> => {
    if (!callActiveRef.current) return;

    // Listen for farmer's crop
    const transcript = await listenOnce();

    if (!transcript.trim()) {
      silenceCountRef.current++;
      if (silenceCountRef.current >= 2) {
        // End call after 2 silences
        const byeText = language === "en"
          ? "I could not hear you. Please call again when you are ready. Goodbye!"
          : "आपकी आवाज़ नहीं आ रही। जब चाहें दोबारा कॉल करें। नमस्ते!";
        setCallState("speaking");
        addMessage("kisanmind", byeText);
        const byeAudio = await playTTS(byeText, language);
        await waitForAudioEnd(byeAudio);
        callActiveRef.current = false;
        setCallState("ended");
        return;
      }
      // One retry
      const retryText = language === "en"
        ? "I didn't catch that. Please tell me which crop you are growing."
        : "सुनाई नहीं दिया। बताइए आप कौनसी फसल उगा रहे हैं?";
      setCallState("speaking");
      addMessage("kisanmind", retryText);
      const retryAudio = await playTTS(retryText, language);
      await waitForAudioEnd(retryAudio);
      if (callActiveRef.current) await processOneTurn();
      return;
    }

    silenceCountRef.current = 0;
    addMessage("farmer", transcript);

    // Engagement fact WHILE fetching
    const FACTS: Record<string, string[]> = {
      hi: [
        "बहुत अच्छा! मैं अभी आपके इलाके की मंडी भाव, मौसम और सैटेलाइट से फसल की सेहत देख रहा हूँ। बस कुछ सेकंड लगेंगे।",
        "ठीक है! आपके लिए असली डेटा जोड़ रहा हूँ। सही मंडी चुनने से हर क्विंटल पर 200 से 500 रुपये ज्यादा मिल सकते हैं। यही मैं ढूंढ रहा हूँ।",
      ],
      en: [
        "Great! I'm now checking real mandi prices, weather, and satellite crop health for your area. Just a few seconds.",
        "Got it! Pulling real data for you. Choosing the right mandi can earn ₹200-500 extra per quintal.",
      ],
    };
    const facts = FACTS[language] || FACTS["hi"];
    const engagementText = facts[Math.floor(Math.random() * facts.length)];

    setCallState("speaking");
    addMessage("kisanmind", engagementText);

    // Start advisory + engagement audio in parallel
    const advisoryPromise = fetch(`${API_BASE}/api/advisory`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        latitude: geo.latitude, longitude: geo.longitude,
        crop: "auto", language, intent: transcript,
      }),
    }).then(r => r.json()).catch(() => null);

    const engagementAudio = await playTTS(engagementText, language);
    const [advisoryResult] = await Promise.all([
      advisoryPromise,
      waitForAudioEnd(engagementAudio),
    ]);

    if (!callActiveRef.current) return;

    // Process advisory
    let advisoryText = "";
    if (advisoryResult && !advisoryResult.detail && !advisoryResult.error) {
      advisoryText = advisoryResult.advisory || "";
      const bm = advisoryResult.best_mandi || {};
      const lm = advisoryResult.local_mandi || {};
      const loc = advisoryResult.location || {};
      setSummary({
        location: loc.location_name ? `${loc.location_name}, ${loc.state}` : undefined,
        crop: advisoryResult.crop,
        bestMandi: bm.market,
        bestPrice: bm.modal_price,
        localMandi: lm.market,
        localPrice: lm.modal_price,
        distanceKm: bm.distance_km,
        weatherDays: advisoryResult.weather?.daily_forecast,
        advisory: advisoryText,
      });
    } else {
      advisoryText = language === "en"
        ? "Sorry, could not fetch advisory right now. Please try again later."
        : "माफ कीजिए, अभी सलाह नहीं मिल पाई। थोड़ी देर बाद फिर कोशिश करें।";
    }

    // Speak advisory
    setStatusText(language === "en" ? "Here's your advice..." : "आपकी सलाह तैयार है...");
    addMessage("kisanmind", advisoryText);
    const advAudio = await playTTS(advisoryText, language);
    currentAudioRef.current = advAudio;
    await waitForAudioEnd(advAudio);

    if (!callActiveRef.current) return;

    // End the call with goodbye
    const goodbyeText = language === "en"
      ? "That's my advice for today. Call again anytime you need help. Goodbye and good farming!"
      : "आज के लिए मेरी सलाह यही है। जब भी ज़रूरत हो दोबारा कॉल करें। नमस्ते और अच्छी खेती करें!";
    addMessage("kisanmind", goodbyeText);
    const goodbyeAudio = await playTTS(goodbyeText, language);
    await waitForAudioEnd(goodbyeAudio);

    // End call, show summary
    callActiveRef.current = false;
    setCallState("ended");
    setStatusText("");
  }, [language, geo.latitude, geo.longitude, listenOnce]);

  const addMessage = (type: "farmer" | "kisanmind", text: string) => {
    setMessages((prev) => [...prev, { type, text, timestamp: new Date() }]);
  };

  /* ---- Start the call ---- */
  const startCall = useCallback(async () => {
    callActiveRef.current = true;
    silenceCountRef.current = 0;
    setMessages([]);
    setSummary(null);

    // Greeting — adapt based on whether GPS is available
    setCallState("greeting");
    setStatusText(language === "en" ? "Connecting..." : "जोड़ रहे हैं...");
    const hasGps = !!(geo.latitude && geo.longitude);
    const greetText = getGreeting(language, hasGps);
    addMessage("kisanmind", greetText);

    const greetAudio = await playTTS(greetText, language);
    await waitForAudioEnd(greetAudio);

    // Start conversation loop
    if (callActiveRef.current) {
      await processOneTurn();
    }
  }, [language, processOneTurn]);

  /* ---- End the call ---- */
  const endCall = useCallback(() => {
    callActiveRef.current = false;
    // Stop any playing audio
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current = null;
    }
    // Stop mic
    mediaRecorderRef.current?.stop();
    releaseMic();
    setCountdown(null);
    setCallState("ended");
    setStatusText(language === "en" ? "Call ended" : "कॉल समाप्त");
  }, [language, releaseMic]);

  /* ---- UI state ---- */
  const isInCall = callState !== "pre-call" && callState !== "ended";
  const currentLang = LANGUAGES.find((l) => l.code === language) || LANGUAGES[0];

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-[#0a0f14] text-white">
      {/* Top bar */}
      <div className="flex items-center justify-between px-4 py-3 bg-[#0d1117]/90 border-b border-white/5">
        <Link href="/" className="flex items-center gap-2">
          <span className="text-xl">🌾</span>
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

      {/* Chat + summary area */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {/* Pre-call: empty state */}
        {callState === "pre-call" && (
          <div className="flex flex-col items-center justify-center h-full text-center opacity-50">
            <Leaf size={48} className="mb-4" />
            <p className="text-lg">{language === "en" ? "Your farming advisor is ready" : "आपका खेती सलाहकार तैयार है"}</p>
            <p className="text-sm mt-2 text-white/40">{language === "en" ? "Tap the green button to start" : "हरे बटन पर टैप करें"}</p>
          </div>
        )}

        {/* Messages */}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.type === "farmer" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
              msg.type === "farmer"
                ? "bg-blue-600/20 border border-blue-500/20 text-white/90"
                : "bg-emerald-600/10 border border-emerald-500/20 text-white/90"
            }`}>
              <div className="text-[10px] text-white/30 mb-1">
                {msg.type === "farmer" ? "You" : "KisanMind"} · {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </div>
              {msg.text}
            </div>
          </div>
        ))}

        {/* Processing indicator */}
        {(callState === "processing" || callState === "greeting") && (
          <div className="flex justify-start">
            <div className="bg-emerald-600/10 border border-emerald-500/20 rounded-2xl px-4 py-3">
              <div className="flex gap-1.5">
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-bounce" />
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-bounce [animation-delay:150ms]" />
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          </div>
        )}

        {/* Call summary — shown after call ends */}
        {callState === "ended" && summary && (
          <div className="mx-auto max-w-md space-y-4 mt-4">
            <h3 className="text-center text-lg font-bold text-white/80">
              {language === "en" ? "Call Summary" : "कॉल सारांश"}
            </h3>

            {/* Location + crop */}
            {(summary.location || summary.crop) && (
              <div className="flex items-center gap-3 rounded-xl bg-white/5 border border-white/10 p-4">
                <MapPin size={24} className="text-sky shrink-0" />
                <div>
                  {summary.location && <div className="font-medium">{summary.location}</div>}
                  {summary.crop && <div className="text-sm text-white/50">{language === "en" ? "Crop" : "फसल"}: {summary.crop}</div>}
                </div>
              </div>
            )}

            {/* Best mandi */}
            {summary.bestMandi && (
              <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/20 p-4">
                <div className="flex items-center gap-3">
                  <TrendingUp size={24} className="text-emerald-400 shrink-0" />
                  <div className="flex-1">
                    <div className="text-xs text-emerald-400/70 uppercase tracking-wider">
                      {language === "en" ? "Best Mandi" : "सबसे अच्छी मंडी"}
                    </div>
                    <div className="text-xl font-bold">{summary.bestMandi}</div>
                    {summary.bestPrice && (
                      <div className="text-2xl font-bold text-emerald-400">₹{summary.bestPrice.toLocaleString()}/qtl</div>
                    )}
                    {summary.distanceKm && (
                      <div className="text-xs text-white/40 mt-1">{summary.distanceKm} km away</div>
                    )}
                  </div>
                </div>
                {summary.localMandi && summary.localPrice && summary.bestPrice && (
                  <div className="mt-3 pt-3 border-t border-white/10 text-sm text-white/60">
                    {language === "en" ? "vs" : "बनाम"} {summary.localMandi}: ₹{summary.localPrice.toLocaleString()}/qtl
                    {summary.bestPrice > summary.localPrice && (
                      <span className="text-emerald-400 font-medium ml-2">
                        +₹{(summary.bestPrice - summary.localPrice).toLocaleString()}/qtl
                      </span>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Weather */}
            {summary.weatherDays && summary.weatherDays.length > 0 && (
              <div className="rounded-xl bg-sky/5 border border-sky/20 p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Thermometer size={20} className="text-sky" />
                  <span className="text-xs text-sky/70 uppercase tracking-wider">
                    {language === "en" ? "5-Day Weather" : "5 दिन का मौसम"}
                  </span>
                </div>
                <div className="flex gap-2 overflow-x-auto pb-1">
                  {summary.weatherDays.slice(0, 5).map((d, i) => (
                    <div key={i} className="flex-shrink-0 text-center bg-white/5 rounded-lg px-3 py-2 min-w-[70px]">
                      <div className="text-[10px] text-white/40">{d.date?.split("-").slice(1).join("/")}</div>
                      {d.precipitation_mm > 0 ? <CloudRain size={18} className="mx-auto my-1 text-sky" /> : <Sun size={18} className="mx-auto my-1 text-amber-400" />}
                      <div className="text-xs font-medium">{d.max_temp_c}°</div>
                      <div className="text-[10px] text-white/40">{d.min_temp_c}°</div>
                      {d.precipitation_mm > 0 && <div className="text-[10px] text-sky">{d.precipitation_mm}mm</div>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* New call button */}
            <button
              onClick={() => { setCallState("pre-call"); setSummary(null); setMessages([]); }}
              className="w-full rounded-xl bg-healthy/20 border border-healthy/30 py-4 text-lg font-bold text-healthy hover:bg-healthy/30 transition"
            >
              {language === "en" ? "New Call" : "नई कॉल करें"}
            </button>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Bottom: Call button */}
      <div className="flex flex-col items-center pb-8 pt-4 bg-gradient-to-t from-[#0a0f14] via-[#0a0f14] to-transparent">
        {callState === "pre-call" ? (
          /* START CALL — big green phone button */
          <>
            <button
              onClick={startCall}
              className="relative flex items-center justify-center h-[170px] w-[170px] rounded-full bg-healthy/80 shadow-[0_0_60px_rgba(34,197,94,0.3)] hover:shadow-[0_0_80px_rgba(34,197,94,0.5)] active:scale-95 transition-all"
            >
              <span className="absolute inset-0 rounded-full bg-healthy/30 animate-ping [animation-duration:2s]" />
              <span className="absolute inset-[-12px] rounded-full border-2 border-healthy/20 animate-ping [animation-duration:2.5s]" />
              <Phone size={56} className="relative z-10 text-white" />
            </button>
            <p className="mt-4 text-lg font-medium text-white/70">
              {language === "en" ? "Tap to call KisanMind" : "किसानमाइंड को कॉल करें"}
            </p>
          </>
        ) : callState === "ended" ? null : (
          /* IN CALL — red end call button + status */
          <>
            {/* Listening indicator with countdown */}
            {callState === "listening" && (
              <div className="mb-3 flex flex-col items-center gap-2">
                {countdown !== null && (
                  <div className="text-6xl font-black text-healthy tabular-nums animate-pulse">
                    {countdown}
                  </div>
                )}
                <div className="flex items-center gap-1">
                  {[...Array(5)].map((_, i) => (
                    <div key={i} className="w-1 bg-healthy rounded-full animate-pulse" style={{
                      height: `${12 + Math.random() * 20}px`,
                      animationDelay: `${i * 100}ms`,
                      animationDuration: "0.5s",
                    }} />
                  ))}
                </div>
              </div>
            )}

            <p className="mb-3 text-sm text-white/50">{statusText}</p>

            <button
              onClick={endCall}
              className="flex items-center justify-center h-[80px] w-[80px] rounded-full bg-red-600 shadow-[0_0_30px_rgba(239,68,68,0.3)] hover:bg-red-500 active:scale-95 transition-all"
            >
              <PhoneOff size={32} className="text-white" />
            </button>
            <p className="mt-2 text-xs text-white/40">
              {language === "en" ? "End call" : "कॉल खत्म करें"}
            </p>
          </>
        )}
      </div>
    </div>
  );
}
