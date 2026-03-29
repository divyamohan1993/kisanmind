"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Mic, Phone, PhoneOff, Sun, CloudRain, Cloud, Leaf, Volume2, TrendingUp, MapPin, Thermometer, CheckCircle, Droplets } from "lucide-react";
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

/* ---- UI Translations: all interface text in selected language ---- */
const UI: Record<string, Record<string, string>> = {
  hi: { callBtn: "किसानमाइंड को कॉल करें", tagline: "150M+ भारतीय किसान | 22 भाषाएं | असली सैटेलाइट + मंडी डेटा", listening: "सुन रहे हैं...", processing: "प्रोसेसिंग...", speaking: "बोल रहे हैं...", continueOrWait: "बोलें या रुकें...", endCall: "कॉल खत्म करें", callEnded: "कॉल समाप्त", newCall: "नई कॉल करें", connecting: "जोड़ रहे हैं...", advisor: "आपका खेती सलाहकार तैयार है", tapStart: "हरे बटन पर टैप करें", callSummary: "कॉल सारांश", bestMandi: "सबसे अच्छी मंडी", weather: "5 दिन का मौसम", dashboard: "डैशबोर्ड", fetchingData: "असली डेटा ला रहे हैं...", adviceReady: "आपकी सलाह तैयार है..." },
  en: { callBtn: "Call KisanMind", tagline: "150M+ Indian Farmers | 22 Languages | Real Satellite + Mandi Data", listening: "Listening...", processing: "Processing...", speaking: "Speaking...", continueOrWait: "Continue or wait...", endCall: "End call", callEnded: "Call ended", newCall: "New Call", connecting: "Connecting...", advisor: "Your farming advisor is ready", tapStart: "Tap the green button", callSummary: "Call Summary", bestMandi: "Best Mandi", weather: "5-Day Weather", dashboard: "Dashboard", fetchingData: "Getting real data...", adviceReady: "Here's your advice..." },
  ta: { callBtn: "கிசான்மைண்ட் அழைக்கவும்", tagline: "150M+ விவசாயிகள் | 22 மொழிகள்", listening: "கேட்கிறேன்...", processing: "செயலாக்கம்...", speaking: "பேசுகிறேன்...", continueOrWait: "தொடருங்கள்...", endCall: "அழைப்பு முடிக்க", callEnded: "அழைப்பு முடிந்தது", newCall: "புதிய அழைப்பு", connecting: "இணைக்கிறது...", advisor: "ஆலோசகர் தயார்", tapStart: "பச்சை பட்டனை தட்டுங்கள்", callSummary: "அழைப்பு சுருக்கம்", bestMandi: "சிறந்த மண்டி", weather: "5 நாள் வானிலை", dashboard: "டாஷ்போர்ட்", fetchingData: "உண்மை தரவு...", adviceReady: "ஆலோசனை..." },
  te: { callBtn: "కిసాన్‌మైండ్ కాల్ చేయండి", tagline: "150M+ రైతులు | 22 భాషలు", listening: "వింటున్నాను...", processing: "ప్రాసెసింగ్...", speaking: "చెప్తున్నాను...", continueOrWait: "కొనసాగించు...", endCall: "కాల్ ముగించు", callEnded: "కాల్ ముగిసింది", newCall: "కొత్త కాల్", connecting: "కనెక్ట్...", advisor: "సలహాదారు సిద్ధం", tapStart: "ఆకుపచ్చ బటన్ నొక్కండి", callSummary: "కాల్ సారాంశం", bestMandi: "ఉత్తమ మండి", weather: "5 రోజుల వాతావరణం", dashboard: "డాష్‌బోర్డ్", fetchingData: "డేటా...", adviceReady: "సలహా..." },
  bn: { callBtn: "কিষাণমাইন্ড কল করুন", tagline: "150M+ কৃষক | 22 ভাষা", listening: "শুনছি...", processing: "প্রসেসিং...", speaking: "বলছি...", continueOrWait: "বলুন বা অপেক্ষা করুন...", endCall: "কল শেষ", callEnded: "কল শেষ হয়েছে", newCall: "নতুন কল", connecting: "সংযোগ...", advisor: "আপনার কৃষি পরামর্শদাতা প্রস্তুত", tapStart: "সবুজ বোতাম টিপুন", callSummary: "কল সারাংশ", bestMandi: "সেরা মান্ডি", weather: "5 দিনের আবহাওয়া", dashboard: "ড্যাশবোর্ড", fetchingData: "ডেটা আনা হচ্ছে...", adviceReady: "পরামর্শ..." },
  mr: { callBtn: "किसानमाइंड ला कॉल करा", tagline: "150M+ शेतकरी | 22 भाषा", listening: "ऐकतोय...", processing: "प्रोसेसिंग...", speaking: "बोलतोय...", continueOrWait: "बोला किंवा थांबा...", endCall: "कॉल बंद", callEnded: "कॉल संपली", newCall: "नवीन कॉल", connecting: "जोडतोय...", advisor: "शेती सल्लागार तयार", tapStart: "हिरवे बटण दाबा", callSummary: "कॉल सारांश", bestMandi: "सर्वोत्तम मंडी", weather: "5 दिवस हवामान", dashboard: "डॅशबोर्ड", fetchingData: "डेटा...", adviceReady: "सल्ला..." },
  pa: { callBtn: "ਕਿਸਾਨਮਾਈਂਡ ਨੂੰ ਕਾਲ ਕਰੋ", tagline: "150M+ ਕਿਸਾਨ | 22 ਭਾਸ਼ਾਵਾਂ", listening: "ਸੁਣ ਰਹੇ ਹਾਂ...", processing: "ਪ੍ਰੋਸੈਸਿੰਗ...", speaking: "ਬੋਲ ਰਹੇ ਹਾਂ...", continueOrWait: "ਬੋਲੋ ਜਾਂ ਰੁਕੋ...", endCall: "ਕਾਲ ਖਤਮ", callEnded: "ਕਾਲ ਖਤਮ ਹੋ ਗਈ", newCall: "ਨਵੀਂ ਕਾਲ", connecting: "ਜੋੜ ਰਹੇ ਹਾਂ...", advisor: "ਸਲਾਹਕਾਰ ਤਿਆਰ ਹੈ", tapStart: "ਹਰਾ ਬਟਨ ਦਬਾਓ", callSummary: "ਕਾਲ ਸਾਰ", bestMandi: "ਸਭ ਤੋਂ ਵਧੀਆ ਮੰਡੀ", weather: "5 ਦਿਨ ਮੌਸਮ", dashboard: "ਡੈਸ਼ਬੋਰਡ", fetchingData: "ਡੇਟਾ...", adviceReady: "ਸਲਾਹ..." },
  gu: { callBtn: "કિસાનમાઈન્ડ ને કૉલ કરો", tagline: "150M+ ખેડૂતો | 22 ભાષાઓ", listening: "સાંભળી રહ્યા છીએ...", processing: "પ્રોસેસિંગ...", speaking: "બોલી રહ્યા છીએ...", continueOrWait: "બોલો અથવા રાહ જુઓ...", endCall: "કૉલ પૂરો", callEnded: "કૉલ પૂરો થયો", newCall: "નવો કૉલ", connecting: "જોડાઈ રહ્યા છીએ...", advisor: "સલાહકાર તૈયાર", tapStart: "લીલું બટન દબાવો", callSummary: "કૉલ સારાંશ", bestMandi: "શ્રેષ્ઠ મંડી", weather: "5 દિવસ હવામાન", dashboard: "ડૅશબોર્ડ", fetchingData: "ડેટા...", adviceReady: "સલાહ..." },
  kn: { callBtn: "ಕಿಸಾನ್‌ಮೈಂಡ್ ಕರೆ ಮಾಡಿ", tagline: "150M+ ರೈತರು | 22 ಭಾಷೆಗಳು", listening: "ಕೇಳುತ್ತಿದ್ದೇನೆ...", processing: "ಪ್ರಕ್ರಿಯೆ...", speaking: "ಹೇಳುತ್ತಿದ್ದೇನೆ...", continueOrWait: "ಮುಂದುವರಿಸಿ...", endCall: "ಕರೆ ಮುಗಿಸಿ", callEnded: "ಕರೆ ಮುಗಿಯಿತು", newCall: "ಹೊಸ ಕರೆ", connecting: "ಸಂಪರ್ಕಿಸುತ್ತಿದ್ದೇವೆ...", advisor: "ಸಲಹೆಗಾರ ಸಿದ್ಧ", tapStart: "ಹಸಿರು ಬಟನ್ ಒತ್ತಿ", callSummary: "ಕರೆ ಸಾರಾಂಶ", bestMandi: "ಅತ್ಯುತ್ತಮ ಮಂಡಿ", weather: "5 ದಿನ ಹವಾಮಾನ", dashboard: "ಡ್ಯಾಶ್‌ಬೋರ್ಡ್", fetchingData: "ಡೇಟಾ...", adviceReady: "ಸಲಹೆ..." },
  ml: { callBtn: "കിസാൻമൈൻഡ് വിളിക്കുക", tagline: "150M+ കർഷകർ | 22 ഭാഷകൾ", listening: "കേൾക്കുന്നു...", processing: "പ്രോസസ്സിംഗ്...", speaking: "സംസാരിക്കുന്നു...", continueOrWait: "തുടരുക...", endCall: "കോൾ അവസാനിപ്പിക്കുക", callEnded: "കോൾ കഴിഞ്ഞു", newCall: "പുതിയ കോൾ", connecting: "കണക്ട്...", advisor: "ഉപദേഷ്ടാവ് തയ്യാർ", tapStart: "പച്ച ബട്ടൺ അമർത്തുക", callSummary: "കോൾ സംഗ്രഹം", bestMandi: "മികച്ച മണ്ടി", weather: "5 ദിന കാലാവസ്ഥ", dashboard: "ഡാഷ്‌ബോർഡ്", fetchingData: "ഡാറ്റ...", adviceReady: "ഉപദേശം..." },
};

function t(lang: string, key: string): string {
  return UI[lang]?.[key] || UI["hi"]?.[key] || UI["en"]?.[key] || key;
}

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
  kind?: "greeting" | "filler" | "advisory" | "goodbye";
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
  latitude?: number;
  longitude?: number;
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
  // Persist language in localStorage so it survives refresh
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
    setStatusText(t(language, "listening"));
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
        const speaking = level > 30; // raised threshold — ignores fans, traffic, wind noise

        if (speaking) {
          isSpeaking = true;
          hasSpokeAtAll = true;
          silenceStart = 0;
          setCountdown(null);
          setStatusText(t(language, "listening"));
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
            setStatusText(t(language, "continueOrWait"));
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
    setStatusText(t(language, "processing"));
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
        addMessage("kisanmind", byeText, "goodbye");
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
      addMessage("kisanmind", retryText, "greeting");
      const retryAudio = await playTTS(retryText, language);
      await waitForAudioEnd(retryAudio);
      if (callActiveRef.current) await processOneTurn();
      return;
    }

    silenceCountRef.current = 0;
    addMessage("farmer", transcript);

    // Start advisory fetch in background
    setCallState("speaking");
    let advisoryDone = false;
    let advisoryResult: Record<string, unknown> | null = null;

    const advisoryPromise = fetch(`${API_BASE}/api/advisory`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        latitude: geo.latitude, longitude: geo.longitude,
        crop: "auto", language, intent: transcript,
      }),
    }).then(r => r.json()).then(d => { advisoryResult = d; advisoryDone = true; return d; }).catch(() => { advisoryDone = true; return null; });

    // Keep farmer engaged with rotating facts until advisory returns
    const FACTS = [
      "आपकी कॉल प्रोसेस हो रही है। मैं अभी सरकारी मंडी भाव ला रहा हूँ।",
      "क्या आप जानते हैं? सही मंडी में बेचने से हर क्विंटल पर 200 से 500 रुपये ज्यादा मिल सकते हैं।",
      "आपके इलाके का सैटेलाइट डेटा भी देख रहा हूँ। इससे फसल की सेहत पता चलती है।",
      "मौसम की जानकारी से फसल खराब होने का खतरा 30 प्रतिशत तक कम हो जाता है।",
      "भारत में 15 करोड़ से ज्यादा किसान परिवार हैं। किसानमाइंड सबकी मदद करना चाहता है।",
      "बस कुछ सेकंड और। आपके लिए सबसे अच्छी मंडी ढूंढ रहा हूँ।",
    ];
    const FACTS_EN = [
      "Processing your call. Fetching live government mandi prices right now.",
      "Did you know? Selling at the right mandi can earn ₹200-500 more per quintal.",
      "Also checking satellite data for your area to assess crop health.",
      "Weather-informed farming reduces crop loss risk by up to 30%.",
      "India has over 150 million farming families. KisanMind aims to help them all.",
      "Almost done. Finding the most profitable mandi for you.",
    ];
    const facts = language === "en" ? FACTS_EN : FACTS;

    let factIdx = 0;
    while (!advisoryDone && callActiveRef.current && factIdx < facts.length) {
      const factText = facts[factIdx];
      addMessage("kisanmind", factText, "filler");
      const factAudio = await playTTS(factText, language);
      await waitForAudioEnd(factAudio);
      factIdx++;
      // Small pause between facts
      if (!advisoryDone) await new Promise(r => setTimeout(r, 500));
    }

    // If advisory still not done after all facts, wait silently
    if (!advisoryDone) {
      await advisoryPromise;
    }

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
        latitude: geo.latitude || undefined,
        longitude: geo.longitude || undefined,
      });
    } else {
      advisoryText = language === "en"
        ? "Sorry, could not fetch advisory right now. Please try again later."
        : "माफ कीजिए, अभी सलाह नहीं मिल पाई। थोड़ी देर बाद फिर कोशिश करें।";
    }

    // Play a chime to signal "now listen to the real advice"
    try {
      const beepRes = await fetch(`${API_BASE}/api/beep`);
      if (beepRes.ok) {
        const beepData = await beepRes.json();
        const beep = new Audio(`data:audio/wav;base64,${beepData.audio_base64}`);
        await beep.play();
        await waitForAudioEnd(beep);
      }
    } catch { /* beep is non-critical */ }

    // Speak advisory
    setStatusText(t(language, "adviceReady"));
    addMessage("kisanmind", advisoryText, "advisory");
    const advAudio = await playTTS(advisoryText, language);
    currentAudioRef.current = advAudio;
    await waitForAudioEnd(advAudio);

    if (!callActiveRef.current) return;

    // End the call with goodbye
    const goodbyeText = language === "en"
      ? "That's my advice for today. Call again anytime you need help. Goodbye and good farming!"
      : "आज के लिए मेरी सलाह यही है। जब भी ज़रूरत हो दोबारा कॉल करें। नमस्ते और अच्छी खेती करें!";
    addMessage("kisanmind", goodbyeText, "goodbye");
    const goodbyeAudio = await playTTS(goodbyeText, language);
    await waitForAudioEnd(goodbyeAudio);

    // End call, show summary
    callActiveRef.current = false;
    setCallState("ended");
    setStatusText("");
  }, [language, geo.latitude, geo.longitude, listenOnce]);

  const addMessage = (type: "farmer" | "kisanmind", text: string, kind?: "greeting" | "filler" | "advisory" | "goodbye") => {
    setMessages((prev) => [...prev, { type, text, timestamp: new Date(), kind }]);
  };

  /* ---- Start the call ---- */
  const startCall = useCallback(async () => {
    callActiveRef.current = true;
    silenceCountRef.current = 0;
    setMessages([]);
    setSummary(null);

    // Greeting — adapt based on whether GPS is available
    setCallState("greeting");
    setStatusText(t(language, "connecting"));
    const hasGps = !!(geo.latitude && geo.longitude);
    const greetText = getGreeting(language, hasGps);
    addMessage("kisanmind", greetText, "greeting");

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
    setStatusText(t(language, "callEnded"));
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
          {t(language, "dashboard")}
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
            <p className="text-lg">{t(language, "advisor")}</p>
            <p className="text-sm mt-2 text-white/40">{t(language, "tapStart")}</p>
          </div>
        )}

        {/* Messages */}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.type === "farmer" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] rounded-2xl px-4 py-3 leading-relaxed ${
              msg.type === "farmer"
                ? "bg-blue-600/20 border border-blue-500/20 text-white/90 text-sm"
                : msg.kind === "filler"
                ? "bg-white/5 border border-white/10 text-white/60 text-xs italic"
                : msg.kind === "advisory"
                ? "bg-emerald-600/15 border-l-4 border-emerald-400 text-white text-base font-medium"
                : "bg-emerald-600/10 border border-emerald-500/20 text-white/90 text-sm"
            }`}>
              <div className="text-[10px] text-white/30 mb-1">
                {msg.type === "farmer" ? "You" : "KisanMind"} · {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </div>
              {msg.kind === "filler" && <span className="not-italic">💡 </span>}
              {msg.kind === "advisory" && <span>🌾 </span>}
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

        {/* Call summary — visual, icon-heavy for illiterate farmers */}
        {callState === "ended" && summary && (
          <div className="mx-auto max-w-md space-y-4 mt-4">
            <h3 className="text-center text-lg font-bold text-white/80">
              {t(language, "callSummary")}
            </h3>

            {/* Location — big icon + name */}
            {summary.location && (
              <div className="flex items-center gap-4 rounded-xl bg-white/5 border border-white/10 p-4">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-sky/20">
                  <MapPin size={24} className="text-sky" />
                </div>
                <div className="text-lg font-bold">{summary.location}</div>
              </div>
            )}

            {/* Google Maps satellite view of farmer's location */}
            {summary.latitude && summary.longitude && (
              <a href={`https://www.google.com/maps/@${summary.latitude},${summary.longitude},14z`}
                 target="_blank" rel="noopener noreferrer"
                 className="block rounded-xl overflow-hidden border border-white/10">
                <img
                  src={`https://maps.googleapis.com/maps/api/staticmap?center=${summary.latitude},${summary.longitude}&zoom=13&size=400x200&maptype=hybrid&markers=color:green%7C${summary.latitude},${summary.longitude}&key=AIzaSyDNzMMqAqTJJh9LYxcIM-xb1Qjb6eMIjyI`}
                  alt="Your location"
                  className="w-full h-[150px] object-cover"
                />
              </a>
            )}

            {/* Best mandi — BIG price visual */}
            {summary.bestMandi && (
              <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/20 p-5 text-center">
                <div className="flex justify-center mb-2">
                  <div className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500/20">
                    <TrendingUp size={28} className="text-emerald-400" />
                  </div>
                </div>
                <div className="text-sm text-emerald-400/70">{t(language, "bestMandi")}</div>
                <div className="text-2xl font-bold mt-1">{summary.bestMandi}</div>
                {summary.bestPrice && (
                  <div className="text-4xl font-black text-emerald-400 mt-1">₹{summary.bestPrice.toLocaleString()}</div>
                )}
                {summary.distanceKm && (
                  <div className="text-sm text-white/40 mt-1">{summary.distanceKm} km</div>
                )}
                {summary.localMandi && summary.localPrice && summary.bestPrice && summary.bestPrice > summary.localPrice && (
                  <div className="mt-3 pt-3 border-t border-emerald-500/20 text-lg font-bold text-emerald-400">
                    +₹{(summary.bestPrice - summary.localPrice).toLocaleString()}
                    <span className="text-sm font-normal text-white/40 ml-1">/ qtl</span>
                  </div>
                )}
              </div>
            )}

            {/* Weather — visual cards */}
            {summary.weatherDays && summary.weatherDays.length > 0 && (
              <div className="rounded-xl bg-sky/5 border border-sky/20 p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Thermometer size={20} className="text-sky" />
                  <span className="text-sm font-bold text-sky/80">{t(language, "weather")}</span>
                </div>
                <div className="flex gap-2 overflow-x-auto pb-1">
                  {summary.weatherDays.slice(0, 5).map((d, i) => (
                    <div key={i} className={`flex-shrink-0 text-center rounded-xl px-3 py-3 min-w-[75px] ${d.precipitation_mm > 2 ? "bg-sky/10 border border-sky/20" : "bg-white/5"}`}>
                      <div className="text-[10px] text-white/40">{d.date?.split("-").slice(1).join("/")}</div>
                      {d.precipitation_mm > 2 ? <CloudRain size={24} className="mx-auto my-1 text-sky" /> : <Sun size={24} className="mx-auto my-1 text-amber-400" />}
                      <div className="text-sm font-bold">{d.max_temp_c}°</div>
                      {d.precipitation_mm > 0 && <div className="text-xs text-sky font-medium">{d.precipitation_mm}mm</div>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Advisory key points — visual icons for illiterate farmers */}
            {summary.advisory && (
              <div className="rounded-xl bg-white/5 border border-white/10 p-4 space-y-3">
                <div className="text-sm font-bold text-white/60 mb-2">
                  {language === "en" ? "Key Advice" : language === "hi" ? "मुख्य सलाह" : t(language, "adviceReady")}
                </div>
                {summary.advisory.split(/[।.!\n]+/).filter(s => s.trim().length > 15).slice(0, 5).map((point, i) => {
                  const lower = point.toLowerCase();
                  const isWarning = lower.includes("बारिश") || lower.includes("rain") || lower.includes("barish") || lower.includes("khatr");
                  const isSell = lower.includes("मंडी") || lower.includes("mandi") || lower.includes("बेच") || lower.includes("sell") || lower.includes("₹");
                  const isHealth = lower.includes("satellite") || lower.includes("सैटेलाइट") || lower.includes("fasal") || lower.includes("फसल") || lower.includes("sehat") || lower.includes("सेहत");
                  return (
                    <div key={i} className={`flex items-start gap-3 rounded-lg p-3 ${isWarning ? "bg-amber-500/10 border border-amber-500/20" : isSell ? "bg-emerald-500/10 border border-emerald-500/20" : isHealth ? "bg-sky/10 border border-sky/20" : "bg-white/5"}`}>
                      <div className="shrink-0 mt-0.5">
                        {isWarning ? <CloudRain size={20} className="text-amber-400" /> : isSell ? <TrendingUp size={20} className="text-emerald-400" /> : isHealth ? <Leaf size={20} className="text-sky" /> : <CheckCircle size={20} className="text-white/40" />}
                      </div>
                      <div className="text-sm text-white/80 leading-relaxed">{point.trim()}</div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Play advisory again */}
            <button
              onClick={() => { if (summary.advisory) playTTS(summary.advisory, language); }}
              className="w-full flex items-center justify-center gap-2 rounded-xl bg-white/5 border border-white/10 py-3 text-sm text-white/60 hover:bg-white/10"
            >
              <Volume2 size={16} /> {language === "en" ? "Play again" : language === "hi" ? "फिर से सुनें" : t(language, "speaking")}
            </button>

            {/* New call button */}
            <button
              onClick={() => { setCallState("pre-call"); setSummary(null); setMessages([]); }}
              className="w-full rounded-xl bg-healthy/20 border border-healthy/30 py-4 text-lg font-bold text-healthy hover:bg-healthy/30 transition"
            >
              {t(language, "newCall")}
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
              className="relative flex items-center justify-center h-[170px] w-[170px] rounded-full bg-healthy/80 shadow-[0_0_60px_rgba(34,197,94,0.3)] hover:shadow-[0_0_80px_rgba(34,197,94,0.5)] active:scale-95 transition-all phone-glow"
            >
              <span className="absolute inset-0 rounded-full bg-healthy/30 animate-ping [animation-duration:2s]" />
              <span className="absolute inset-[-12px] rounded-full border-2 border-healthy/20 animate-ping [animation-duration:2.5s]" />
              <Phone size={56} className="relative z-10 text-white" />
            </button>
            <p className="mt-4 text-lg font-medium text-white/70">
              {t(language, "callBtn")}
            </p>
            <p className="mt-2 text-xs text-white/30 tracking-wide text-center max-w-[280px]">
              {t(language, "tagline")}
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
              {t(language, "endCall")}
            </p>
          </>
        )}
      </div>
    </div>
  );
}
