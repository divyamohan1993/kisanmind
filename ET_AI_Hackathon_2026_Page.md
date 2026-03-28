# ET GenAI Hackathon 2026 — Phase II: Build Marathon

**By The Economic Times**
**Hiring Partner:** Avataar.ai | **Hackathon Partner:** Unstop

---

## The Funnel

**54,000 registrations → Phase I shortlist → Phase II prototype → Top 20 finalists → 3 winners**

| Milestone | Date | Status |
|-----------|------|--------|
| Registrations Open | 26 Dec 2025 | ~~Closed~~ |
| Phase I — MCQ + Idea Submission | — | ~~Completed~~ |
| Shortlisting & Problem Statement Release | 16 Mar 2026 | ~~Done~~ |
| **Phase II — Prototype Submission** | **29 Mar 2026** | **NOW — Deadline in 1 day** |
| Phase III — Top 20 Presentations (Grand Finale) | TBA | **Our target** |
| Winners Announced (Top 3) | TBA | Upcoming |

**Goal: Crack the Top 20.** Phase II submissions are scored to select 20 finalists from all shortlisted teams. Only those 20 present at the Grand Finale. Everything below is oriented toward maximizing our score.

---

## Our Problem Statement: #5 — Domain-Specialized AI Agents with Compliance Guardrails

Build a domain-specific AI agent for healthcare, finance, supply chain, or **agriculture** that executes domain workflows, handles edge cases properly, and stays within regulatory and policy guardrails at all times.

**Our build:** KisanMind — an AI-powered agricultural advisory agent using multi-modal inputs (satellite imagery, weather, mandi prices, voice in Hindi) to deliver actionable guidance to farmers, even in low-connectivity environments.

**Problem Statement Evaluation Focus:** Domain expertise depth, compliance and guardrail enforcement, edge-case handling, full task completion, and auditability of every agent decision.

---

## Phase II Submission Requirements

All submissions via the **Unstop platform** only. All links must be **public and accessible**. Deadline: **29 March 2026**.

| # | Deliverable | What Makes It Top-20 Quality | Status |
|---|-------------|------------------------------|--------|
| 1 | **System Architecture Diagram (PDF/PNG)** | 1–2 page visual showing all 5 agent roles (VaaniSetu, FasalNetra, MandiMitra, MausamGuru, SalahBot), inter-agent communication, tool integrations (Earth Engine, AgMarkNet, OpenWeatherMap, Gemini), error-handling logic, data flow from voice input to advisory output | |
| 2 | **Functional Prototype** | Working demo — voice call triggers agent pipeline, returns advisory. All 5 agents functional. Edge cases handled gracefully (cloudy satellite, API failures, unrecognized speech). Low-connectivity tiers working | |
| 3 | **Public GitHub Repository** | Clean structure, meaningful commits showing build process, well-commented code, proper README with setup instructions | |
| 4 | **2–3 Minute Demo Video** | End-to-end walkthrough: farmer calls → STT → agents reason → satellite + mandi + weather → TTS response. Show agent completing full workflow start to finish. Show edge-case handling | |
| 5 | **README / Documentation** | Setup instructions, tech stack, solution approach, how to run the prototype, API keys needed, architecture overview | |

---

## Phase II Evaluation Parameters

These are the **actual Phase II scoring criteria** used to select the Top 20 finalists:

| Parameter | What Judges Score | How KisanMind Scores High |
|-----------|-------------------|--------------------------|
| **Code Quality & Architecture** | Clean code, modular design, proper separation of concerns, scalable architecture | 5 specialized agents with clear boundaries, Cloud Functions per agent, Firestore for state, Pub/Sub for inter-agent messaging, proper error handling at every boundary, meaningful commit history |
| **Creativity of Solution** | Novel approach, unique Gen-AI application, innovative thinking | Multi-agent orchestration with satellite NDVI + mandi price fusion + weather forecasting — no other team likely combines Earth Engine + voice-first + agriculture. 5-tier connectivity degradation (smartphone → 2G voice → SMS → missed call → proactive push) |
| **Working Demo** | Functional prototype, end-to-end workflow completion, reliability | Live voice call in Hindi → STT → 5 agents execute in parallel → satellite analysis + best mandi + weather advisory → TTS response in 30 seconds. Graceful degradation when APIs fail. First-time onboarding flow |
| **Documentation Clarity** | Clear README, architecture explained, easy to understand and reproduce | Architecture doc with agent roles, data flow diagrams, API integration details, edge-case handling table, setup instructions, tech stack rationale |
| **Real Business Impact** | Quantified impact, addressable market, believable math | 150M+ Indian farmers, ₹34,000/year income increase per farmer (30% gain), specific math: Solan→Shimla tomato arbitrage saves ₹12,000/harvest, weather-timed picking prevents ₹10,000 spoilage. ET revenue alignment: 150M new users for ET platform |

---

## General Judging Criteria (from Hackathon Page)

These are the overall hackathon evaluation criteria (20% each) — Phase II parameters above are the immediate filter for Top 20 selection:

| Criterion (20%) | What Judges Look For | How KisanMind Addresses It |
|-----------------|---------------------|---------------------------|
| **Innovation & Creativity** | Fresh perspective, unique Gen-AI approach | Multi-agent architecture, satellite NDVI + mandi price fusion, 5-tier connectivity degradation — combines Earth Engine + voice-first + agriculture |
| **Technical Implementation** | Code quality, Gen-AI use, scalability, soundness | Gemini 2.5 orchestration, Vertex AI Agent Builder, Cloud STT/TTS for Hindi voice, Earth Engine API for NDVI, real AgMarkNet + OpenWeatherMap integrations, Firestore for state |
| **Practical Impact** | Real-world problem, significant potential impact | 150M+ Indian farmers, 30% income increase (₹34,000/year per farmer), post-harvest loss reduction, mandi price arbitrage — backed with specific math |
| **User Experience** | Ease of use, interface, accessibility | Voice-first on any ₹500 feature phone via 2G — zero smartphone/internet/literacy requirement. Web dashboard for demo. Hindi interaction. SMS fallback. 60-second onboarding |
| **Pitch Quality** | Presentation clarity, demo quality, value proposition | 3-min demo: live voice call → satellite analysis → mandi recommendation → all 5 agents visible. Clear impact numbers. "One farmer's story" narrative |

---

## Rules That Matter for Phase II

- All code, documents, and assets must be **original and created during the hackathon**
- Pre-built projects or unauthorized third-party material → **immediate disqualification**
- Open-source tools, libraries, and models are **permitted**
- Late submissions **will not be accepted**
- All files and links (GitHub, demo videos, documents) must be **public and accessible**
- Submissions exclusively through the **Unstop platform**

---

## Prizes — ₹10 Lakh Prize Pool

| Place | Cash Prize | Bonus |
|-------|-----------|-------|
| **1st** | ₹5,00,000 | + Incubation / Job Offer |
| **2nd** | ₹3,00,000 | + Mentorship |
| **3rd** | ₹2,00,000 | + Mentorship |

All participants get: ET certification, industry mentorship, networking with experts & founders, career opportunities.

---

*Source: [economictimes.indiatimes.com/et-ai-hackathon](https://economictimes.indiatimes.com/et-ai-hackathon)*
