"use client";

import { useState, useEffect, useCallback } from "react";

const SLIDES = [
  // 1. TITLE
  {
    bg: "bg-gradient-to-br from-[#0f1f3d] to-[#1a365d]",
    content: (
      <div className="text-center text-white">
        <p className="text-sm uppercase tracking-[0.2em] text-green-400 mb-6">ET AI Hackathon 2026 · Problem #5</p>
        <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight mb-4">🌾 KisanMind</h1>
        <p className="text-xl md:text-2xl font-light text-white/90 max-w-2xl mx-auto">
          One phone call. Four satellites. Personalized farming advice in 22 languages.
        </p>
        <div className="flex justify-center gap-8 mt-10 flex-wrap">
          {[["150M", "Farmers"], ["9", "Data Sources"], ["4", "Satellites"], ["112", "Crops"], ["22", "Languages"]].map(([n, l]) => (
            <div key={l} className="text-center">
              <div className="text-3xl font-bold text-green-400">{n}</div>
              <div className="text-xs uppercase tracking-widest text-white/70">{l}</div>
            </div>
          ))}
        </div>
        <p className="mt-10 text-sm text-white/70">Divya Mohan · Kumkum Thakur</p>
      </div>
    ),
  },

  // 2. PROBLEM
  {
    bg: "bg-white",
    content: (
      <div className="max-w-3xl mx-auto">
        <p className="text-sm uppercase tracking-[0.15em] text-red-500 font-bold mb-2">The Problem</p>
        <h2 className="text-3xl md:text-5xl font-extrabold text-[#1a365d] tracking-tight mb-8">
          ₹45 lakh crore in decisions.<br />Made blind.
        </h2>
        <div className="space-y-4">
          {[
            ["Can't see what satellites see", "Crop health data from 4 satellite constellations exists — but zero reaches the farmer"],
            ["Sell at nearest mandi, not the best", "No comparison of net profit after transport, commission, and spoilage across mandis"],
            ['"Rain expected" is useless', "Doesn't say whether to irrigate, harvest, or spray for their specific crop at their growth stage"],
            ["60% of farmers excluded", "Advisory services only in English/Hindi — 22 scheduled languages, 10 with TTS voices, all ignored"],
          ].map(([title, desc]) => (
            <div key={title} className="flex gap-4 items-start">
              <span className="text-red-500 text-xl font-bold mt-0.5">✗</span>
              <div>
                <p className="font-bold text-[#1a365d] text-lg">{title}</p>
                <p className="text-gray-800 text-sm">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    ),
  },

  // 3. VALUE PROPOSITION
  {
    bg: "bg-gradient-to-br from-[#0f1f3d] to-[#1a365d]",
    content: (
      <div className="text-center text-white max-w-3xl mx-auto">
        <p className="text-sm uppercase tracking-[0.15em] text-green-400 font-bold mb-2">Value Proposition</p>
        <h2 className="text-3xl md:text-5xl font-extrabold tracking-tight mb-6">
          Satellite intelligence,<br />delivered by voice.
        </h2>
        <p className="text-lg text-white/90 mb-10 max-w-xl mx-auto">
          A farmer calls. Says their crop. Gets personalized advice from 4 satellites, 112 commodity prices, and 5-day weather — in their language. Under 30 seconds.
        </p>
        <div className="grid grid-cols-3 gap-6 text-left">
          {[
            ["🛰️", "4 Satellites", "Sentinel-2 NDVI · SAR moisture · MODIS heat · SMAP root-zone"],
            ["📊", "112 Crops", "Live AgMarkNet prices · Net profit after transport · 90-day history"],
            ["🌤️", "Smart Weather", "5-day forecast + GDD growth stage · Date-specific DO/DON'T actions"],
          ].map(([icon, title, desc]) => (
            <div key={title} className="bg-white/5 rounded-xl p-5 border border-white/10">
              <div className="text-2xl mb-2">{icon}</div>
              <p className="font-bold text-white text-sm mb-1">{title}</p>
              <p className="text-white/70 text-xs leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </div>
    ),
  },

  // 4. UNDERLYING MAGIC
  {
    bg: "bg-white",
    content: (
      <div className="max-w-3xl mx-auto">
        <p className="text-sm uppercase tracking-[0.15em] text-[#138808] font-bold mb-2">The Magic</p>
        <h2 className="text-3xl md:text-5xl font-extrabold text-[#1a365d] tracking-tight mb-8">
          Cross-validation.<br />Not just data relay.
        </h2>
        <p className="text-gray-800 mb-6">We don't just show satellite data. We compare it across sources to catch contradictions before the farmer gets wrong advice.</p>
        <div className="space-y-3">
          {[
            ["NDVI declining + rain adequate", "Sentinel-2 vs Weather", "→ Pest/disease, NOT drought. Refer KVK."],
            ["NDVI declining + SAR confirms dry", "Sentinel-2 vs SAR", "→ High-confidence: irrigate now."],
            ["Surface wet, roots dry", "SMAP layers", "→ Deep irrigation. Rain didn't reach roots."],
            ["Heat stress + flowering stage", "MODIS vs GDD", "→ Protect crop. Shade + morning water."],
            ["Rain coming + harvest ready", "Weather vs Growth", "→ Harvest before rain. Today."],
            ["Price above 90-day average", "AgMarkNet history", "→ Sell now. May correct down."],
          ].map(([signal, src, action]) => (
            <div key={signal} className="flex items-center gap-3 bg-gray-50 rounded-lg p-3 border border-gray-100">
              <div className="flex-1">
                <p className="font-semibold text-[#1a365d] text-sm">{signal}</p>
                <p className="text-gray-800 text-xs">{src}</p>
              </div>
              <p className="font-bold text-[#138808] text-sm text-right">{action}</p>
            </div>
          ))}
        </div>
      </div>
    ),
  },

  // 5. BUSINESS MODEL — with explicit assumptions and back-of-envelope math
  {
    bg: "bg-gradient-to-br from-[#0f1f3d] to-[#1a365d]",
    content: (
      <div className="text-white max-w-3xl mx-auto">
        <p className="text-sm uppercase tracking-[0.15em] text-green-400 font-bold mb-1">Impact · Back-of-Envelope Math</p>
        <h2 className="text-2xl md:text-3xl font-extrabold tracking-tight mb-3">
          +26% income per farmer. Here's the math.
        </h2>

        <p className="text-white/70 text-xs mb-4 leading-relaxed">
          <span className="text-green-400 font-bold">Assumptions:</span> 2ha farm · 30q/season · 2 seasons/yr · Tomato/wheat · Income ₹1.1L/yr · Local mandi 15km · Best mandi 60km · Transport ₹3.5/km/q · Commission 4%
        </p>

        <div className="grid grid-cols-2 gap-2 mb-4">
          {[
            ["Revenue recovered", "Mandi arbitrage", "₹2,400/q best vs ₹1,800 local. Net Δ₹330/q × 30q × 2", "+₹19,800"],
            ["Cost reduced", "Spoilage prevention", "Weather-timed harvest avoids 5% loss. 30q × ₹1,800 × 5% × 2", "+₹5,400"],
            ["Cost reduced", "Irrigation savings", "SAR+SMAP prevents 2 unneeded irrigations. ₹800 × 2 × 2", "+₹3,200"],
            ["Time saved", "One call vs 3 trips", "4hr saved/query × 6 queries × ₹100", "+₹600"],
          ].map(([lever, label, math, value]) => (
            <div key={label} className="bg-white/5 rounded-lg p-2.5 border border-white/10">
              <div className="flex justify-between items-start">
                <div className="flex-1 min-w-0">
                  <span className="text-[0.6rem] uppercase tracking-wider text-green-400 font-bold">{lever}</span>
                  <p className="font-semibold text-white text-xs">{label}</p>
                  <p className="text-white/70 text-[0.65rem] mt-0.5 leading-snug">{math}</p>
                </div>
                <span className="text-green-400 font-bold text-sm whitespace-nowrap ml-2">{value}</span>
              </div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-3 gap-2 text-center">
          <div className="bg-green-500/10 border border-green-500/20 rounded-xl p-3">
            <p className="text-green-400 text-[0.65rem] font-semibold">Per Farmer</p>
            <p className="text-xl font-extrabold text-white">₹29,000</p>
            <p className="text-white/60 text-[0.65rem]">/year (+26%)</p>
          </div>
          <div className="bg-green-500/10 border border-green-500/20 rounded-xl p-3">
            <p className="text-green-400 text-[0.65rem] font-semibold">Year 1 · 100K</p>
            <p className="text-xl font-extrabold text-white">₹2.9B</p>
            <p className="text-white/60 text-[0.65rem]">value created</p>
          </div>
          <div className="bg-green-500/10 border border-green-500/20 rounded-xl p-3">
            <p className="text-green-400 text-[0.65rem] font-semibold">150M farmers</p>
            <p className="text-xl font-extrabold text-white">₹4.4T</p>
            <p className="text-white/60 text-[0.65rem]">TAM ceiling</p>
          </div>
        </div>
      </div>
    ),
  },

  // 6. HOW IT WORKS (DEMO)
  {
    bg: "bg-white",
    content: (
      <div className="max-w-3xl mx-auto">
        <p className="text-sm uppercase tracking-[0.15em] text-[#138808] font-bold mb-2">How It Works</p>
        <h2 className="text-3xl md:text-5xl font-extrabold text-[#1a365d] tracking-tight mb-8">
          30 seconds.<br />Farm to advisory.
        </h2>
        <div className="space-y-0">
          {[
            ["1", "Farmer speaks", "Says crop name in any of 22 languages. GPS auto-detects location.", "bg-[#1a365d]"],
            ["2", "Gemini extracts intent", "Multi-turn conversation. Gathers crop, problems, sowing date naturally.", "bg-[#6366f1]"],
            ["3", "9 APIs fire in parallel", "4 satellites + mandi prices + weather + distances + KVK — all at once.", "bg-[#FF9933]"],
            ["4", "Cross-validate", "Compare satellite vs weather vs prices. Catch contradictions.", "bg-[#ef4444]"],
            ["5", "Gemini synthesizes", "All data into conversational advice. Fact-checked. Confidence-gated.", "bg-[#138808]"],
            ["6", "Voice response", "TTS in farmer's language. Call summary after. SMS with key points.", "bg-[#1a365d]"],
          ].map(([num, title, desc, color]) => (
            <div key={num} className="flex gap-4 items-start py-3 border-b border-gray-100 last:border-0">
              <div className={`${color} text-white w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold shrink-0`}>{num}</div>
              <div>
                <p className="font-bold text-[#1a365d]">{title}</p>
                <p className="text-gray-700 text-sm">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    ),
  },

  // 7. TECH STACK
  {
    bg: "bg-gradient-to-br from-[#0f1f3d] to-[#1a365d]",
    content: (
      <div className="text-white max-w-3xl mx-auto">
        <p className="text-sm uppercase tracking-[0.15em] text-green-400 font-bold mb-2">Technology</p>
        <h2 className="text-3xl md:text-5xl font-extrabold tracking-tight mb-8">
          What's under the hood.
        </h2>
        <div className="grid grid-cols-2 gap-4 text-sm">
          {[
            ["AI", "Gemini 3 Flash · 5-model fallback · Vertex AI · Gemini Live WebSocket"],
            ["Satellites", "Sentinel-2 (10m) · Sentinel-1 SAR · MODIS Terra (1km) · NASA SMAP (9km)"],
            ["Backend", "FastAPI · Python 3.11+ · Fully async · O(1) satellite cache"],
            ["Frontend", "Next.js 16 · React 19 · Tailwind CSS 4 · WCAG 2.2 AAA"],
            ["Voice", "Cloud STT V2 · Cloud TTS Wavenet · Cloud Translation · 22 languages"],
            ["Data", "AgMarkNet 112 crops · Open-Meteo · Google Maps · Twilio Voice+SMS"],
            ["Cache", "L0: Satellite grid O(1) · L1: Memory 0.13s · L2: GCS ~200ms"],
            ["Quality", "140-test E2E suite · Fact-check · Confidence scoring · Session cleanup"],
          ].map(([label, tech]) => (
            <div key={label} className="bg-white/5 rounded-lg p-4 border border-white/10">
              <p className="font-bold text-green-400 text-xs uppercase tracking-wider mb-1">{label}</p>
              <p className="text-white/90 text-xs leading-relaxed">{tech}</p>
            </div>
          ))}
        </div>
      </div>
    ),
  },

  // 8. RESILIENCE
  {
    bg: "bg-white",
    content: (
      <div className="max-w-3xl mx-auto">
        <p className="text-sm uppercase tracking-[0.15em] text-[#138808] font-bold mb-2">Resilience</p>
        <h2 className="text-3xl md:text-5xl font-extrabold text-[#1a365d] tracking-tight mb-8">
          Built to never fail<br />a farmer mid-call.
        </h2>
        <div className="grid grid-cols-2 gap-4">
          {[
            ["5-Model Fallback", "Gemini 3 Flash → 2.5 → 2.0 → Lite → 1.5 + Vertex AI. If one is overloaded, next takes over."],
            ["3-Tier Cache", "Pre-computed satellite grid (O(1)) + in-memory (0.13s) + Cloud Storage (~200ms). Cache hit = instant."],
            ["Graceful Degradation", "If SAR fails, MODIS + SMAP + Sentinel-2 still work. Advisory adapts to available data."],
            ["Confidence Gating", "LOW data: omitted. MEDIUM: hedged. HIGH: stated as advice. Farmer never gets uncertain data presented as fact."],
            ["Cross-Validation", "Catches when satellites disagree with weather. Prevents wrong irrigation/pest advice."],
            ["Fact-Check", "Gemini verifies advisory against raw source data. Catches hallucinated prices, distances, dates."],
          ].map(([title, desc]) => (
            <div key={title} className="bg-gray-50 rounded-xl p-4 border border-gray-100">
              <p className="font-bold text-[#1a365d] text-sm mb-1">{title}</p>
              <p className="text-gray-700 text-xs leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </div>
    ),
  },

  // 9. COMPETITIVE ADVANTAGE
  {
    bg: "bg-gradient-to-br from-[#0f1f3d] to-[#1a365d]",
    content: (
      <div className="text-white max-w-3xl mx-auto">
        <p className="text-sm uppercase tracking-[0.15em] text-green-400 font-bold mb-2">Why Us</p>
        <h2 className="text-3xl md:text-5xl font-extrabold tracking-tight mb-8">
          What others don't do.
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/10">
                <th className="text-left py-3 px-3 text-white/70 text-xs uppercase tracking-wider">Feature</th>
                <th className="text-center py-3 px-3 text-green-400 text-xs uppercase tracking-wider">KisanMind</th>
                <th className="text-center py-3 px-3 text-white/60 text-xs uppercase tracking-wider">Others</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["Satellite sources", "4 (S2, SAR, MODIS, SMAP)", "0–1"],
                ["Cross-validation", "Multi-source conflict detection", "None"],
                ["Price intelligence", "Net profit + 90-day history", "Raw prices"],
                ["Languages", "22 scheduled Indian", "1–2"],
                ["Interface", "Voice-first (phone call)", "App only"],
                ["Cache", "3-tier O(1)", "None"],
                ["Accessibility", "WCAG 2.2 AAA", "—"],
                ["Data transparency", "Confidence + age + source", "Black box"],
              ].map(([feat, us, them]) => (
                <tr key={feat} className="border-b border-white/5">
                  <td className="py-2.5 px-3 text-white/80">{feat}</td>
                  <td className="py-2.5 px-3 text-center font-semibold text-green-400">{us}</td>
                  <td className="py-2.5 px-3 text-center text-white/60">{them}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    ),
  },

  // 10. CALL TO ACTION
  {
    bg: "bg-gradient-to-br from-[#0f1f3d] to-[#1a365d]",
    content: (
      <div className="text-center text-white max-w-2xl mx-auto">
        <h2 className="text-4xl md:text-6xl font-extrabold tracking-tight mb-6">
          Try it now.
        </h2>
        <p className="text-lg text-white/80 mb-10">
          Live at kisanmind.dmj.one. Call and speak in Hindi. See satellite data turn into farming advice in 30 seconds.
        </p>
        <div className="flex justify-center gap-4 flex-wrap">
          <a href="https://kisanmind.dmj.one" target="_blank" rel="noopener"
            className="inline-flex items-center gap-2 px-8 py-4 rounded-xl bg-[#138808] text-white text-lg font-bold hover:bg-[#0f6d06] transition-colors">
            Open Live App
          </a>
          <a href="https://github.com/divyamohan1993/kisanmind" target="_blank" rel="noopener"
            className="inline-flex items-center gap-2 px-8 py-4 rounded-xl border-2 border-white/30 text-white text-lg font-bold hover:bg-white/5 transition-colors">
            GitHub
          </a>
        </div>
        <div className="mt-12 pt-8 border-t border-white/10">
          <p className="text-white/60 text-sm">
            🌾 KisanMind · ET AI Hackathon 2026 · Problem #5: Domain-Specialized AI Agents
          </p>
          <p className="text-white/60 text-xs mt-2">
            100% real data · 4 satellites · 112 crops · 22 languages · Zero hallucination
          </p>
          <p className="text-white/60 text-xs mt-1">Divya Mohan · Kumkum Thakur</p>
        </div>
      </div>
    ),
  },
];

export default function PitchPage() {
  const [slide, setSlide] = useState(0);
  const total = SLIDES.length;

  const next = useCallback(() => setSlide(s => Math.min(s + 1, total - 1)), [total]);
  const prev = useCallback(() => setSlide(s => Math.max(s - 1, 0)), []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" || e.key === " " || e.key === "Enter") { e.preventDefault(); next(); }
      if (e.key === "ArrowLeft" || e.key === "Backspace") { e.preventDefault(); prev(); }
      if (e.key === "Home") { e.preventDefault(); setSlide(0); }
      if (e.key === "End") { e.preventDefault(); setSlide(total - 1); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [next, prev, total]);

  // Touch/swipe support
  useEffect(() => {
    let startX = 0;
    const touchStart = (e: TouchEvent) => { startX = e.touches[0].clientX; };
    const touchEnd = (e: TouchEvent) => {
      const dx = e.changedTouches[0].clientX - startX;
      if (Math.abs(dx) > 50) { dx < 0 ? next() : prev(); }
    };
    window.addEventListener("touchstart", touchStart);
    window.addEventListener("touchend", touchEnd);
    return () => { window.removeEventListener("touchstart", touchStart); window.removeEventListener("touchend", touchEnd); };
  }, [next, prev]);

  const current = SLIDES[slide];

  return (
    <div className={`min-h-screen flex flex-col ${current.bg} transition-colors duration-500`}>
      {/* Progress bar */}
      <div className="fixed top-0 left-0 right-0 h-1 z-50 bg-black/10">
        <div className="h-full bg-[#138808] transition-all duration-300" role="progressbar" aria-valuenow={slide + 1} aria-valuemin={1} aria-valuemax={total} aria-label="Pitch progress" style={{ width: `${((slide + 1) / total) * 100}%` }} />
      </div>

      {/* Slide content */}
      <div className="flex-1 flex items-center justify-center px-6 py-12 md:px-12" onClick={next} role="main" aria-label={`Slide ${slide + 1} of ${total}`}>
        <div className="w-full max-w-4xl">
          {current.content}
        </div>
      </div>

      {/* Navigation */}
      <nav className="fixed bottom-0 left-0 right-0 flex items-center justify-between px-6 py-4 z-50" aria-label="Slide navigation">
        <button onClick={(e) => { e.stopPropagation(); prev(); }} disabled={slide === 0}
          className="w-11 h-11 rounded-full bg-black/10 hover:bg-black/20 text-white/90 disabled:opacity-20 flex items-center justify-center text-lg transition-colors"
          aria-label="Previous slide">
          ←
        </button>
        <span className={`text-xs font-mono ${current.bg.includes("white") ? "text-gray-800" : "text-white/60"}`} aria-live="polite">
          {slide + 1} / {total}
        </span>
        <button onClick={(e) => { e.stopPropagation(); next(); }} disabled={slide === total - 1}
          className="w-11 h-11 rounded-full bg-black/10 hover:bg-black/20 text-white/90 disabled:opacity-20 flex items-center justify-center text-lg transition-colors"
          aria-label="Next slide">
          →
        </button>
      </nav>
    </div>
  );
}
