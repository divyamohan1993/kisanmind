# ET AI Hackathon 2026: strategic intelligence briefing

**The single most important finding: Domain-specific AI agents for Indian agriculture and healthcare (Problem 5) and voice-first AI news for Bharat (Problem 8) are the two highest-impact, most defensible hackathon choices** — and they play directly to this team's strengths in multilingual voice AI, rural India deployment, and Bhashini/Sarvam AI integration. Enterprise workflow automation (Problem 2) and knowledge management (Problem 1) are rapidly commoditizing and should be avoided. The Indian personal finance AI space (Problem 9) offers a strong fallback with genuine regulatory moats, but faces higher competition from funded incumbents.

Why this matters: Of 2,000+ teams competing for 20 finalist spots, most will gravitate toward generic enterprise AI or chatbot wrappers — exactly the categories foundation models are commoditizing fastest. The teams that win will demonstrate something GPT-5 cannot do out of the box: voice-first interaction in Bhojpuri with real domain context, compliance guardrails tuned to Indian regulations, and distribution strategies for the next 800 million users. This report synthesizes March 2026 signals across all 10 research dimensions to inform that winning strategy.

---

## The agentic AI market has exploded, but most deployments aren't truly agentic

The global agentic AI market reached **$7–7.6 billion in 2025** and is projected to hit **$52.6 billion by 2030**, with enterprise generative AI spending tripling to $37 billion in 2025 alone. Yet beneath the headline numbers, a critical reality check emerges: only **16% of enterprise deployments qualify as "true agents"** — systems where an LLM plans, executes, and adapts autonomously. Most production systems remain fixed-sequence workflows or simple routing around a single model call.

The major AI companies have made dramatic moves. OpenAI's **GPT-5.4** (released March 5, 2026) is the first model with native computer-use capabilities, scoring 75% on the OSWorld benchmark — surpassing the 72.4% human baseline — with a million-token context window. Anthropic, now valued at **$380 billion** after a $30 billion Series G, launched **Claude Cowork** as a persistent workplace platform and released **Computer Use** as a Mac research preview on March 23, 2026. Anthropic now captures **40% of enterprise LLM spend**, up from 12% two years ago, while OpenAI dropped from ~50% to ~25%. Google's **Project Mariner** achieves 83.5% on browser automation benchmarks, and Microsoft's **Agent Framework** merges AutoGen and Semantic Kernel into a unified SDK supporting both the A2A protocol and MCP.

The commoditization picture is now stark. Basic RAG pipelines, simple chatbots, single-model API wrappers, and low-code agent builders are all table stakes — IBM's chief AI architect declared "we're at a commodity point; the model itself is not the main differentiator." What remains differentiated: **domain-specific compliance** in regulated industries, multi-agent orchestration and governance (cited by 65% of leaders as the top barrier), proprietary data exposed as agent-callable APIs, and voice AI agents in non-English languages. Agentic AI startups raised **$6.03 billion in 2025** alone, with software development as the highest-funded vertical, but Gartner warns that **40% of agentic AI projects will be cancelled by 2027** due to escalating costs and unclear ROI.

---

## India's AI market is structurally unique, and the gaps are enormous

India's technology landscape in early 2026 reveals a paradox: extraordinary digital infrastructure alongside massive service gaps. UPI processed **21 billion transactions in January 2026 alone**. There are **21.6 crore (216 million) demat accounts**, up 8x from 2016. Yet mutual fund penetration sits at just **4% of the population** versus 37% in the US, and there are fewer than **973 SEBI-registered Investment Advisors** for over 12 crore unique investors — a ratio of roughly one advisor per 123,000 investors.

In fintech, the infrastructure is world-class but the AI intelligence layer is thin. Zerodha, India's pioneer discount broker, is widely criticized as "stuck in 2015" with no meaningful AI features. Groww leads active client share at 27% and growing, but offers only basic research tools. Angel One's ARQ Prime robo-advisory engine stands as the most advanced AI offering among brokers. **ET Markets** — directly relevant to this hackathon — is primarily an information platform offering live data, stock screeners, and recommendations, but does not offer order execution, portfolio rebalancing, or personalized AI advisory. The critical gaps include: no AI-powered tax-loss harvesting tool in India, absent portfolio rebalancing automation, limited multilingual support, and no integrated cross-asset tax optimization.

Indian agritech is growing from **$9 billion to $28 billion by 2030**, with AI as the fastest sub-segment scaling from $900 million to $5.6 billion. The government's **AgriStack** has registered 70+ million farmers, and the 2026 Budget launched **Bharat VISTAAR** — an intelligence layer delivering AI-driven multilingual advice via voice calls and basic phones. DeHaat serves 1.8 million farmers across 12 states, CropIn has digitized 7 million+ farmers globally, and Wadhwani AI's agricultural programs operate in 10+ states. Yet the biggest unmet needs persist: **69% of Indian farmers hold less than one hectare**, digital literacy remains low, and most solutions operate only in a few languages out of India's 22 scheduled languages.

Healthcare AI in India is valued at $1.26 billion and projected to reach **$18.55 billion by 2035**. The Ayushman Bharat Digital Mission has created **74 crore (740 million) ABHA health IDs** with 49+ crore health records linked. India's government launched **SAHI** (Strategy for AI in Healthcare) and the **BODH** platform at the India AI Impact Summit 2026. AI diagnostics leaders like Qure.ai (medical imaging) and MadhuNetrAI (diabetic retinopathy screening of 7,100+ patients) are achieving real clinical impact. However, AI adoption remains concentrated in Tier 1 cities, and the country has only **64 doctors per 100,000 people**.

India's regulatory approach remains "light-touch" — there is **no standalone AI law**. The India AI Governance Guidelines released in November 2025 propose seven core principles but are not legally binding. SEBI's AI Accountability Framework requires advisers to take full legal responsibility for AI-generated advice and disclose AI usage. The Digital Personal Data Protection Act 2023 shapes data handling. For hackathon purposes, this regulatory environment favors demonstrating compliance guardrails as a feature rather than a constraint.

---

## Hackathon winners share a clear pattern: multi-agent, voice-enabled, story-driven

Analysis of major 2025-2026 hackathon winners reveals remarkably consistent patterns. The Microsoft AI Agents Hackathon (18,000 registrants, 570 submissions) was won by **RiskWise**, a multi-agent supply chain risk analysis system. Google's ADK Hackathon (10,400 participants) was won by **SalesShortcut**, a multi-agent SDR system. Meta's LlamaCon hackathon was won by **OrgLens**, using knowledge graphs from Jira and GitHub. Google's Gen AI Exchange in India drew 270,000 developers and focused on production-ready agentic systems with real industry partners.

Five attributes consistently differentiate the top 1%:

- **Multi-agent architecture with visible collaboration**: Winners deploy 2–5 specialized agents with clear roles and show the orchestration in their demos. GameForge AI, RiskWise, and SalesShortcut all used this pattern. CrewAI and LangGraph are the dominant frameworks.
- **Multimodal interaction, especially voice**: Projects with voice + text + visual interaction consistently outperform text-only solutions. The ElevenLabs x a16z hackathon specifically awarded voice-to-voice reasoning agents.
- **Measurable, relatable impact framing**: Klaviyo's grand prize winner pivoted their framing from "noisy neighbor in data pipelines" to "getting paged at 3AM" — universal resonance. Quantified impact ("40% faster hospital discharge") beats generic claims ("improved efficiency").
- **Trust and explainability trails**: Judges increasingly want to see WHY the AI decided something, not just THAT it did. Citation chains, confidence scores, and human-in-the-loop design are expected.
- **Polished, working demos over slides**: Devpost judges report that "a slick homepage with no code behind it is a red flag." Live data integration and real-time visualization score highest.

The ET GenAI Hackathon 2026, organized by the Economic Times with Unstop and Avataar.ai, attracted **55,000+ participants**. It runs in three phases: online assessment, prototype development, and a live jury presentation. The prize pool is ₹10 lakh, with job and incubation offers for the winner. Themes span media, finance, healthcare, sustainability, smart cities, education, and open innovation. Judges include Unstop CEO Ankit Aggarwal and Avataar.ai CEO Sravanth Aluru. The evaluation criteria weight innovation, technical implementation, practical impact, UX, and pitch quality equally at 20% each.

---

## Domain-specific AI agents offer the deepest moats and highest India relevance

Across the four domain verticals in Problem 5, the maturity and opportunity landscape varies significantly. **Healthcare medical coding** is at Growth maturity, with companies like Fathom Health, CodaMetrix (200+ hospitals), and India-origin AGS Health deploying production systems. The FDA has authorized **1,250+ AI-enabled medical devices**, and coding errors cost US healthcare over $125 billion annually. In India, the NHCX (National Health Claims Exchange) enables AI-powered claims automation with built-in consent frameworks.

**Agricultural advisory AI** sits at Emerging-to-Growth maturity but represents the highest India-specific opportunity. Wadhwani AI is developing **Garuda**, a purpose-built language model for Indian agriculture, and its programs have cut pesticide costs by 25% and boosted farmer incomes by 20%. Odisha's voice-based agricultural advisory demonstrated benefit-cost ratios of **$12–$19 per dollar invested**. The regulatory complexity is low compared to healthcare, but the moat comes from farmer network effects, local data, and vernacular language models — exactly this team's strengths.

**Financial close automation** is a Growth-stage market dominated by BlackLine (4,300+ customers) and FloQast, with AI-native disruptors like Nominal and ChatFin emerging. India's GST compliance ecosystem — with e-invoicing, Invoice Management Systems, and GSTN APIs — is arguably the most AI-ready tax infrastructure globally. **Supply chain AI** is projected to reach $58.55 billion by 2031, with 62% of organizations experimenting with agentic AI in supply chains, but this domain favors incumbents like SAP and Oracle with deep ERP integrations.

The common thread across all four domains: compliance guardrails are the moat. Essential guardrail architecture includes input validation, runtime business rule enforcement, output content moderation, human-in-the-loop for high-stakes decisions, and tamper-evident audit trails. Frameworks like NVIDIA NeMo Guardrails and standards like ISO/IEC 42001 are becoming baseline requirements. For a hackathon, demonstrating a clean guardrail architecture around a domain agent signals both technical sophistication and commercial viability.

---

## Indian retail investing is booming but the AI intelligence layer barely exists

India's retail investing explosion is creating a massive gap between infrastructure and intelligence. **Monthly SIP inflows hit a record ₹31,002 crore in December 2025**, with annual SIP inflows reaching ₹3.34 lakh crore. The mutual fund industry AUM crossed ₹82 lakh crore. Yet 75% of new demat accounts belong to adults under 30 who lack financial literacy, and **91% of retail F&O traders lose money** per SEBI data.

The personal finance AI gap in India is structural. With fewer than 1,000 registered investment advisors for 216 million demat account holders, the advisory-to-investor ratio is among the worst globally. SEBI's regulatory framework creates both barriers and opportunities: registration is mandatory, net worth requirements are steep (₹50 lakh for corporate IAs), and physical agreement requirements impede digital-first models. However, the Account Aggregator framework is enabling robo-advisers to collect comprehensive financial data, and SEBI's sandbox approach is trending favorable.

Existing tools barely scratch the surface. Fintoo offers SEBI-registered AI financial planning. INDmoney provides unified dashboards. CheQ's Wisor handles AI credit card management. But none deliver truly intelligent, voice-first, multilingual financial guidance. The opportunity: **68% of users now use AI/LLMs for at least one financial activity**, users with AI budgeting tools save 15–20% more, and companies cracking "Bharat distribution" — vernacular, low-ticket, assisted journeys — are expected to build the next decade's giants.

---

## Enterprise workflow automation is commoditizing fastest among all nine problems

Salesforce's Agentforce has reached an **$800 million annual run rate** growing 169% year-over-year. ServiceNow's Now Assist AI surpassed **$600 million in annual contract value**. Microsoft's Copilot Studio is now included free with all Microsoft 365 Copilot licenses. These platform giants are making horizontal workflow automation table stakes.

The "SaaSpocalypse" narrative — triggered by Anthropic's Claude Cowork launch — sent both Salesforce and ServiceNow to 52-week stock lows in February 2026 on fears that agentic AI will cannibalize traditional per-seat SaaS licensing. Build-versus-buy has flipped: approximately 75% of AI use cases now run on vendor products versus internal builds. Derek Ashmore of Asperitas captured the consensus: "The smart move is to treat low-level agent orchestration as a temporary advantage, not a permanent asset. Don't overinvest in bespoke planners and routers that your cloud provider will give you in a year."

What remains defensible in workflows: regulated industry compliance (healthcare HIPAA, financial SOX), legacy system integration (agents navigating mainframe screens), and agent governance/security — which 65% of leaders cite as their top barrier. Generic enterprise workflow automation is the wrong hackathon bet.

---

## AI news personalization is a real opportunity, but only with deep differentiation

The AI news landscape reveals a clear lesson from Artifact's January 2024 shutdown: a standalone AI news app cannot compete against built-in platforms like Apple News and Google News without extraordinary differentiation. Artifact had only 100,000 downloads and no revenue model despite building excellent AI summarization. Reuters Institute forecasts that **only 6% of users currently access news through AI interfaces** versus 24% for general information-seeking — the gap represents the opportunity.

In India, Inshorts (pivoting away from news toward influencer content), Dailyhunt (100M+ downloads, 14 languages but more entertainment than intelligence), and Google News India dominate. The massive white space: **no app combines voice-first access, deep AI personalization, multilingual vernacular intelligence, a trust/verification layer, and audio briefings for low-literacy users**. Economic Times itself is primarily a text-based business information platform without significant consumer-facing AI news features.

A truly differentiated AI news experience would deliver personalized 5-minute audio briefings in regional languages, integrate actionable context (mandi prices for farmers, scheme updates for citizens), display trust signals through multi-source triangulation, and learn not just topic preferences but format, depth, and literacy level. This is precisely what foundation models alone cannot solve — it requires India-specific language models, voice infrastructure, and contextual knowledge.

---

## Future-proofing: which problems survive the next generation of foundation models

Ranking all nine ET Hackathon problem domains on a composite of commoditization risk, moat depth, India-specific defensibility, five-year relevance, and hackathon demonstrability yields a clear hierarchy:

| Rank | Problem domain | Score | Key moat |
|------|---------------|-------|----------|
| 1 | Domain-specific AI agents (Prob. 5) | **9/10** | Regulatory compliance + domain data + India DPI |
| 2 | AI-native news experiences (Prob. 8) | **8/10** | Voice-first multilingual + ET brand alignment |
| 3 | AI Money Mentor (Prob. 9) | **7/10** | SEBI compliance + India tax complexity |
| 4 | AI-powered CX — voice (Prob. 3) | **6/10** | Sub-300ms multilingual voice is structurally hard |
| 5 | AI for Indian investors (Prob. 6) | **6/10** | India market data + SEBI regulatory knowledge |
| 6 | Enterprise workflow (Prob. 2) | **4/10** | Commoditizing rapidly; platform giants dominating |
| 7 | AI recruitment (Prob. 7) | **4/10** | Crowded; LinkedIn AI dominates |
| 8 | Knowledge management (Prob. 1) | **3/10** | RAG is commodity; Notion/Confluence shipping AI |
| 9 | Document processing (Prob. 4) | **3/10** | Foundation models solving this natively |

The pattern is unmistakable: **problems requiring India-specific regulatory knowledge, vernacular language processing, and domain expertise resist commoditization far longer** than horizontal enterprise tools. GPT-5 won't solve voice-first Bhojpuri agricultural advisory with mandi price context, but it will trivially replace most enterprise chatbots and document processors.

The team's strengths — voice-first AI for rural India, multilingual NLP (Hindi, Bhojpuri), civic tech experience, and Bhashini/Sarvam AI/AI4Bharat integration — align perfectly with the top-ranked domains. The team-to-domain fit score is 10/10 for Problem 5 (agriculture/healthcare agents) and 8/10 for Problem 8 (AI-native news), versus just 2–3/10 for the commodity categories.

---

## The optimal tech stack for a 48-hour AI agent hackathon

For rapid prototyping of multi-agent AI systems with Indian language support, the recommended stack layers are:

**Agent orchestration**: **CrewAI** for fastest multi-agent prototyping (role/goal/task abstraction lets you build 2–4 agent teams in hours) or **LangGraph** for complex stateful workflows with visual debugging. Both are free and open-source.

**LLM backbone**: Start with **Google Gemini Flash** (generous free tier, multimodal, fast) for general reasoning. Use **Groq** for ultra-fast inference during live demos. Add **Sarvam AI's Sarvam-30B** (open-source, 32K context, optimized for Indian languages) for vernacular processing.

**Indian language stack**: **Sarvam AI** provides the most complete Indian voice pipeline — Saaras V3 speech-to-text, text-to-speech, and Sarvam Vision for Indic OCR. **AI4Bharat's IndicTrans3** handles state-of-the-art translation across 22 languages. **Bhashini** (350+ optimized models, 15M+ daily inferences) provides government-grade language services. For Bhojpuri specifically, AI4Bharat's IndicVoices dataset covering 400+ districts is the most comprehensive resource.

**UI/demo layer**: **Streamlit** offers the best balance of speed and polish for multi-page AI apps with charts and chat. **Gradio** is fastest for ML model demos (5 minutes to working demo). **Next.js + v0.dev** produces the most impressive visual results but requires 1–2 hours. For maximum judge impact, combine Streamlit for the main app with embedded voice interaction via Sarvam AI.

**RAG infrastructure**: **ChromaDB** (zero-setup, in-memory) for local prototyping. **Pinecone** free tier for managed vector search. **LlamaIndex** for document processing pipelines. OpenAI's text-embedding-3-small or Sentence Transformers for embeddings.

**Optimal 48-hour timeline**: Hours 0–3 for architecture and problem definition. Hours 3–18 for core agent logic and RAG pipeline. Hours 18–30 for UI development and demo data. Hours 30–42 for integration testing, polish, and demo video. Hours 42–48 for pitch practice, GitHub cleanup, and final submission.

---

## Conclusion: the winning formula for the top 20

The convergence of evidence across all research dimensions points to a clear strategic recommendation. The hackathon's evaluation criteria weight innovation, technical implementation, practical impact, UX, and pitch quality equally — which means a project must excel across all five dimensions rather than over-indexing on any single one.

**The highest-probability winning strategy** is to build a voice-first, multilingual AI agent in either agricultural advisory (Problem 5) or AI-native news (Problem 8) that demonstrates: a multi-agent architecture with 3–4 specialized agents collaborating visibly, real-time voice interaction in Hindi and at least one additional Indian language via Sarvam AI/Bhashini, a compliance guardrail framework appropriate to the domain, and a story-driven pitch that opens with a relatable human problem (a farmer in Bihar trying to decide when to sell, or a semi-literate worker in Varanasi wanting to understand the day's news) and closes with quantified impact.

Three insights that emerged from this research deserve emphasis. First, the "SaaSpocalypse" narrative hitting enterprise AI stocks means judges and industry leaders are hypersensitive to whether AI projects create genuine new value versus wrapping existing capabilities — domain specificity and India-first design signal authentic innovation. Second, India's digital public infrastructure (AgriStack, ABDM, Bhashini, Account Aggregator) creates globally unique opportunities that no other country can replicate — building on this infrastructure is both a technical moat and a compelling narrative. Third, the single most memorable element in any hackathon demo is a working voice interaction in a language the judges don't expect — Bhojpuri voice AI solving a real problem will linger in memory long after the hundredth generic dashboard is forgotten.