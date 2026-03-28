"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Mic, MicOff, Send, Languages } from "lucide-react";

interface VoiceInputProps {
  onSubmit: (text: string, language: string) => void;
  isLoading?: boolean;
}

const LANGUAGES = [
  { code: "hi-IN", label: "हिंदी", name: "Hindi" },
  { code: "en-IN", label: "English", name: "English" },
  { code: "ta-IN", label: "தமிழ்", name: "Tamil" },
  { code: "te-IN", label: "తెలుగు", name: "Telugu" },
  { code: "bn-IN", label: "বাংলা", name: "Bengali" },
];

export default function VoiceInput({ onSubmit, isLoading }: VoiceInputProps) {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [textInput, setTextInput] = useState("");
  const [language, setLanguage] = useState("hi-IN");
  const [speechSupported, setSpeechSupported] = useState(true);
  const recognitionRef = useRef<ReturnType<typeof createRecognition> | null>(null);

  useEffect(() => {
    const w = window as Window & { webkitSpeechRecognition?: unknown; SpeechRecognition?: unknown };
    if (!w.webkitSpeechRecognition && !w.SpeechRecognition) {
      setSpeechSupported(false);
    }
  }, []);

  function createRecognition() {
    const w = window as Window & { webkitSpeechRecognition?: new () => SpeechRecognition; SpeechRecognition?: new () => SpeechRecognition };
    const SR = w.webkitSpeechRecognition || w.SpeechRecognition;
    if (!SR) return null;
    const recognition = new SR();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = language;
    return recognition;
  }

  const startListening = useCallback(() => {
    const recognition = createRecognition();
    if (!recognition) return;

    recognitionRef.current = recognition;
    setTranscript("");

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interim = "";
      let final = "";
      for (let i = 0; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          final += event.results[i][0].transcript;
        } else {
          interim += event.results[i][0].transcript;
        }
      }
      setTranscript(final || interim);
    };

    recognition.onerror = () => {
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognition.start();
    setIsListening(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [language]);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    setIsListening(false);
  }, []);

  const handleSubmit = () => {
    const text = transcript || textInput;
    if (text.trim()) {
      onSubmit(text.trim(), language);
      setTranscript("");
      setTextInput("");
    }
  };

  const currentLang = LANGUAGES.find((l) => l.code === language) || LANGUAGES[0];

  return (
    <div className="glass-card p-4 sm:p-6">
      {/* Language selector */}
      <div className="mb-4 flex items-center gap-2">
        <Languages size={14} className="text-white/40" />
        <div className="flex flex-wrap gap-1.5">
          {LANGUAGES.map((lang) => (
            <button
              key={lang.code}
              onClick={() => setLanguage(lang.code)}
              className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-all ${
                language === lang.code
                  ? "bg-healthy/20 text-healthy border border-healthy/30"
                  : "bg-white/5 text-white/50 border border-transparent hover:bg-white/10 hover:text-white/70"
              }`}
            >
              {lang.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-col items-center gap-4 sm:flex-row">
        {/* Mic button */}
        {speechSupported && (
          <button
            onClick={isListening ? stopListening : startListening}
            className={`relative flex h-16 w-16 shrink-0 items-center justify-center rounded-full transition-all ${
              isListening
                ? "bg-stressed text-white pulse-ring"
                : "bg-healthy/20 text-healthy hover:bg-healthy/30"
            }`}
          >
            {isListening ? <MicOff size={24} /> : <Mic size={24} />}
          </button>
        )}

        {/* Input area */}
        <div className="flex flex-1 flex-col gap-2 w-full">
          {isListening && (
            <div className="rounded-lg bg-healthy/5 border border-healthy/20 px-3 py-2">
              <div className="text-[10px] uppercase tracking-wider text-healthy/60 mb-1">
                Listening in {currentLang.name}...
              </div>
              <div className="text-sm text-white/80 min-h-[20px]">
                {transcript || (
                  <span className="text-white/30 italic">Speak now...</span>
                )}
              </div>
            </div>
          )}

          <div className="flex gap-2">
            <input
              type="text"
              value={transcript || textInput}
              onChange={(e) => {
                setTextInput(e.target.value);
                setTranscript("");
              }}
              placeholder={
                speechSupported
                  ? "Type or use voice: e.g., 'मेरे टमाटर का NDVI क्या है?'"
                  : "Type your question: e.g., 'Tomato advisory for Solan'"
              }
              className="flex-1 rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white placeholder-white/30 outline-none transition-colors focus:border-healthy/40 focus:bg-white/[0.07]"
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
            />
            <button
              onClick={handleSubmit}
              disabled={isLoading || (!transcript && !textInput)}
              className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-healthy text-kisan-dark transition-all hover:bg-healthy/90 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-kisan-dark border-t-transparent" />
              ) : (
                <Send size={18} />
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
