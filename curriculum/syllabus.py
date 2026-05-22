"""
AI² — Career Roadmap syllabus data (v2.0).

5-week compressed curriculum at 8-10 hrs/day intensity.
Agri-Saathi is the one real build project (Weeks 3–4).
AI² multi-agent system is a design/analysis exercise only (Day 18–19).

Task keys: "w{week_num}-d{day_idx}-{scope}-{task_idx}"
  scope = "all" | "aipm" | "evals" | "context"
"""

# compatibility-only: fixed week bounds for old sessions/static fallback.
# New modular curriculum features should use course/module/topic sequence_order
# plus learner enrollment/progress state.
MAX_WEEKS = 5

# ── Role definitions ───────────────────────────────────────────────────────────

# compatibility-only: static track metadata for fallback/seed export.
# New modular curriculum features should use modular course/enrollment state.
ROLE_TRACKS = {
    "aipm":    {"label": "AI Product Manager",  "icon": "📦", "color": "#4FC3F7"},
    "evals":   {"label": "AI Evals Specialist", "icon": "🔬", "color": "#FF8A65"},
    "context": {"label": "Context Engineer",    "icon": "🧩", "color": "#AED581"},
}

# ── 5-Week Roadmap ─────────────────────────────────────────────────────────────

# compatibility-only: static roadmap for old sessions/static fallback and seed
# export. Do not use WEEKS for new modular curriculum features; use
# course/module/topic sequence_order plus learner enrollment/progress state.
WEEKS = [
    {
        "num": 1,
        "title": "AI Foundations & Core Fluency",
        "subtitle": "Build the knowledge base all three roles share",
        "color": "#E85D26",
        "week_hours": "50 hrs — 10 hrs/day × 5 days",
        "theme": "Understand AI systems deeply enough to make product decisions, design evaluations, and architect context pipelines.",
        "days": [
            {
                "day_label": "Day 1–2",
                "day_idx": 0,
                "title": "AI/ML Foundations",
                "hours": "16 hrs",
                "all_tracks": [
                    "AI vs ML vs DL — draw the Venn diagram, explain each to a 5-year-old and a CTO",
                    "How models learn: training, loss functions, gradient descent (intuition, not math)",
                    "Overfitting, underfitting, regularization — why they matter for product decisions",
                    "Supervised vs unsupervised vs reinforcement learning — when to use each",
                    "Neural network anatomy: layers, weights, activation functions (visual intuition)",
                ],
                "tracks": {
                    "aipm": ["Write a 1-page explainer: 'AI/ML for stakeholders' — translate technical concepts into business language"],
                    "evals": ["Create a cheat sheet: 'What can go wrong at each stage of model training' — overfitting, data leakage, label noise"],
                    "context": ["Map: 'Where does context enter the ML pipeline?' — training data, prompt, retrieval, system instructions"],
                },
                "artifact": "AI Foundations Cheat Sheet (1-page visual reference per role)",
                "resources": [
                    "3Blue1Brown Neural Networks series",
                    "fast.ai Practical Deep Learning Ch.1",
                    "Andrej Karpathy — Neural Networks: Zero to Hero",
                ],
            },
            {
                "day_label": "Day 3–4",
                "day_idx": 1,
                "title": "LLMs, Transformers & Token Economics",
                "hours": "16 hrs",
                "all_tracks": [
                    "Transformer architecture: attention mechanism, self-attention, multi-head attention",
                    "Tokenization: BPE, token budgets, why token count ≠ word count",
                    "Embeddings: what they are, how they encode meaning, why they enable similarity search",
                    "LLM inference: temperature, top-p, frequency penalty — how each affects output",
                    "Model landscape: GPT-4o vs Claude vs Gemini vs Llama — capabilities, costs, trade-offs",
                    "Hallucinations: why they happen, taxonomy of failure modes, mitigation strategies",
                ],
                "tracks": {
                    "aipm": ["Write a model selection decision framework: 'When to use which LLM' with cost/quality/latency matrix"],
                    "evals": ["Build a hallucination taxonomy: 5 types with detection strategies for each"],
                    "context": ["Create a token budget calculator: allocate tokens across system prompt, RAG context, chat history, output"],
                },
                "artifact": "LLM Decision Matrix + Hallucination Taxonomy + Token Budget Template",
                "resources": [
                    "The Illustrated Transformer (jalammar.github.io)",
                    "Anthropic Claude model cards",
                    "OpenAI tokenizer",
                ],
            },
            {
                "day_label": "Day 5",
                "day_idx": 2,
                "title": "Track-Specific Foundations",
                "hours": "10 hrs",
                "all_tracks": [],
                "tracks": {
                    "aipm": [
                        "PRD structure for AI products (differs from traditional PRDs)",
                        "RICE/MoSCoW for AI feature prioritization",
                        "North Star metrics for AI products (accuracy ≠ success)",
                        "Stakeholder communication: translating AI uncertainty to business confidence",
                        "Write a mini-PRD for an AI feature you'd add to a product you use daily",
                    ],
                    "evals": [
                        "Evaluation metrics: accuracy, precision, recall, F1, BLEU, ROUGE",
                        "Train/val/test splits for LLM evaluation",
                        "Offline vs online evaluation — what each catches",
                        "Human vs automated evaluation: cost, speed, quality trade-offs",
                        "Read OpenAI's eval guidance + Anthropic's eval best practices",
                    ],
                    "context": [
                        "Read Anthropic's Context Engineering guide (the definitive reference)",
                        "Context vs prompt: why the distinction matters",
                        "RAG fundamentals: chunking, embedding, retrieval, re-ranking",
                        "Context assembly pipeline: what goes in, in what order, and why",
                        "Map the CE landscape: RAG, function calling, system prompts, few-shot, memory",
                    ],
                },
                "artifact": "Mini-PRD + Eval Metrics Cheat Sheet + Context Engineering Landscape Map",
                "resources": [
                    "Anthropic Context Engineering guide",
                    "OpenAI Evals docs",
                    "Lenny's Newsletter PRD templates",
                    "Eugene Yan's eval posts",
                ],
            },
        ],
    },
    {
        "num": 2,
        "title": "APIs, Prompting & Applied Techniques",
        "subtitle": "Get hands-on with the tools each role uses daily",
        "color": "#7C3AED",
        "week_hours": "50 hrs — 10 hrs/day × 5 days",
        "theme": "Move from understanding to doing. Build your prompt library, your first eval harness, and your first context pipeline.",
        "days": [
            {
                "day_label": "Day 6–7",
                "day_idx": 0,
                "title": "APIs + Prompt → Context Engineering",
                "hours": "16 hrs",
                "all_tracks": [
                    "API fundamentals: REST, authentication, rate limits, error handling",
                    "Claude/OpenAI API hands-on: 5 calls (chat, JSON mode, streaming, function calling, vision)",
                    "Prompt engineering progression: zero-shot → few-shot → CoT → system prompts → structured outputs",
                    "Advanced prompting: meta-prompting, prompt chaining, self-consistency, decomposition",
                    "Build a 20-prompt library: classification, extraction, generation, analysis, evaluation",
                ],
                "tracks": {
                    "aipm": ["Write a stakeholder memo: 'API cost analysis for our AI feature' — model costs, latency, reliability trade-offs"],
                    "evals": ["Design 10 eval test cases for your prompt library — input, expected output, rubric, edge case per test"],
                    "context": ["Build a context assembly spec: system prompt template + dynamic context injection + output schema"],
                },
                "artifact": "20-Prompt Library + API Cost Memo + 10 Eval Test Cases + Context Assembly Spec",
                "resources": [
                    "Anthropic Prompt Engineering guide",
                    "OpenAI Cookbook",
                    "promptingguide.ai",
                    "Brex Prompt Engineering guide",
                ],
            },
            {
                "day_label": "Day 8–9",
                "day_idx": 1,
                "title": "Evaluation Deep Dive + Agent Architecture",
                "hours": "16 hrs",
                "all_tracks": [
                    "LLM-as-Judge: using one model to evaluate another — prompt design, calibration, bias",
                    "Eval frameworks: RAGAS, DeepEval, Phoenix — when to use which",
                    "Agent architecture: single-agent vs multi-agent, orchestrator patterns, tool use",
                    "Agent protocols: MCP (Model Context Protocol), A2A, tool calling standards",
                    "7 agentic design patterns: ReAct, Plan-and-Execute, Reflection, Multi-Agent Debate, etc.",
                ],
                "tracks": {
                    "aipm": ["Write a 1-pager: 'Should we build an agent or a pipeline?' — decision framework for PMs"],
                    "evals": ["Build eval harness v0: 10 test cases + LLM-as-Judge scoring + pass/fail report"],
                    "context": ["Design agent context flow: how context moves between orchestrator and specialists, what compresses vs passes through"],
                },
                "artifact": "Agent Decision Framework + Eval Harness v0 + Agent Context Flow Diagram",
                "resources": [
                    "RAGAS docs",
                    "DeepEval docs",
                    "Anthropic — Building Effective Agents",
                    "LangGraph docs",
                ],
            },
            {
                "day_label": "Day 10",
                "day_idx": 2,
                "title": "RAG Architecture & Context Pipelines",
                "hours": "10 hrs",
                "all_tracks": [
                    "RAG end-to-end: ingestion → chunking → embedding → vector DB → retrieval → re-ranking → generation",
                    "Chunking strategies: fixed-size, semantic, recursive, document-aware",
                    "Vector databases: pgvector vs Pinecone vs Chroma vs Weaviate — trade-offs",
                    "Retrieval quality: precision@k, recall@k, MRR — how to measure if your RAG is working",
                    "Context window management: what happens when retrieved context exceeds token limits",
                ],
                "tracks": {
                    "aipm": ["Write a RAG build-vs-buy analysis: when to build custom RAG vs use off-the-shelf"],
                    "evals": ["Design a RAG eval suite: 15 test queries with ground truth, relevance scoring, retrieval quality metrics"],
                    "context": ["Build a context pipeline spec: ingestion → chunking → embedding → retrieval → assembly → generation with optimization notes per stage"],
                },
                "artifact": "RAG Build-vs-Buy Analysis + RAG Eval Suite + Context Pipeline Spec",
                "resources": [
                    "LlamaIndex docs",
                    "LangChain RAG tutorials",
                    "Pinecone learning center",
                    "pgvector GitHub",
                ],
            },
        ],
    },
    {
        "num": 3,
        "title": "Advanced Skills & Agri-Saathi Build Part 1",
        "subtitle": "Role-specific depth + full data pipeline build (Days 11–15)",
        "color": "#16A34A",
        "week_hours": "50 hrs — 10 hrs/day × 5 days",
        "theme": "Days 11–15 are dual-purpose: build the Agri-Saathi data pipeline while developing advanced role-specific skills through the project lens.",
        "days": [
            {
                "day_label": "Day 11",
                "day_idx": 0,
                "title": "Project Setup + Data Source Mapping",
                "hours": "10 hrs",
                "agrisaathi_day": 1,
                "all_tracks": [
                    "Set up project repo: agri-saathi/ with clean folder structure (downloaders/, processors/, storage/, api/, scheduler/, tests/)",
                    "Create requirements.txt: fastapi, uvicorn, apscheduler, sqlalchemy, pgvector, chromadb, httpx, pandas, geopandas, rasterio, anthropic, openai",
                    "Write config.py: all API keys, DB URLs, schedule intervals loaded from .env",
                    "Design the DataSource abstract base class: every downloader inherits from it (download, validate, normalize, store)",
                    "Map all data sources: URL/API, auth method, rate limits, update frequency, data format, license, coverage",
                    "Create sources_registry.json: single source of truth for all data sources",
                ],
                "tracks": {
                    "aipm": [
                        "AI product lifecycle deep dive: ideation → data strategy → model selection → eval → deployment → monitoring",
                        "Write the Data Strategy 1-pager: which sources, why, what farmer decisions they enable, data quality trade-offs",
                        "Case study: Agri-Saathi as a product — user personas, North Star metric, success criteria",
                    ],
                    "evals": [
                        "Design data quality eval schema: freshness score, completeness, accuracy signal, coverage score per source",
                    ],
                    "context": [
                        "Advanced RAG: hybrid search (keyword + semantic), re-ranking models, multi-hop retrieval",
                        "Design the context schema: how each data type gets formatted for RAG injection (tabular → narrative, NDVI → human-readable)",
                    ],
                },
                "artifact": "Project skeleton + sources_registry.json + DataSource base class + Data Strategy 1-pager",
            },
            {
                "day_label": "Day 12",
                "day_idx": 1,
                "title": "Weather + Market Price Downloaders",
                "hours": "10 hrs",
                "agrisaathi_day": 2,
                "all_tracks": [
                    "Build WeatherDownloader: Open-Meteo + IMD — current, 7-day forecast, historical data per district",
                    "Parameters: temperature, rainfall, humidity, wind, UV index, evapotranspiration",
                    "Build MarketPriceDownloader: Agmarknet + commodity API — daily mandi prices per crop per market",
                    "Normalize price data: quintal → kg, handle missing values, 7-day rolling average",
                    "Store both: raw JSON to file store, cleaned data to PostgreSQL with timestamp + source metadata",
                    "Write unit tests with mock HTTP responses (pytest + respx)",
                    "Add retry logic: 3 retries with exponential backoff, log each failure",
                ],
                "tracks": {
                    "aipm": ["Write farmer user story: 'As a farmer, I want to know if tomorrow's price for wheat will be higher so I can decide when to sell'"],
                    "evals": ["Build freshness eval: check if downloaded data is within expected update window — alert if stale"],
                    "context": ["Write context formatter for weather + price data: converts raw numbers to farmer-friendly narratives"],
                },
                "artifact": "WeatherDownloader + MarketPriceDownloader (tested, with retry) + Context formatters",
            },
            {
                "day_label": "Day 13",
                "day_idx": 2,
                "title": "Crop/Soil + Satellite Downloaders",
                "hours": "10 hrs",
                "agrisaathi_day": 3,
                "all_tracks": [
                    "Build CropSoilDownloader: ICAR crop database + FAO soil maps + state agriculture portal scrapers",
                    "Data: crop calendar by region, soil type by district, recommended crops, fertilizer recommendations",
                    "Build SatelliteDownloader: NASA MODIS NDVI + Sentinel-2 via ESA Copernicus + ISRO Bhuvan",
                    "Process satellite data: NDVI calculation, soil moisture estimation, crop stress detection",
                    "Handle raster data: rasterio for GeoTIFF processing, extract per-district statistics, WGS84 standardization",
                    "Build first multi-source join: satellite NDVI + weather + soil type per district",
                ],
                "tracks": {
                    "aipm": ["Prioritize features: which satellite signals most directly answer farmer questions? Build impact-effort matrix"],
                    "evals": ["Design satellite data quality check: cloud cover filter (>30% reject), NDVI range validation, anomaly detection"],
                    "context": ["Write NDVI interpreter: converts NDVI values to human-readable crop health assessment with recommended actions"],
                },
                "artifact": "CropSoilDownloader + SatelliteDownloader + Multi-source district join + NDVI interpreter",
            },
            {
                "day_label": "Day 14",
                "day_idx": 3,
                "title": "Additional Sources + Scheduler + Storage",
                "hours": "10 hrs",
                "agrisaathi_day": 4,
                "all_tracks": [
                    "Build remaining source downloader stubs: AgriNews, GovernmentAdvisory, FertilizerPrice, SeedDatabase, WaterLevel, CreditScheme, PestAlert, ExportPrice, InputCost",
                    "For each stub: define source URL/API, schema, update frequency, storage target",
                    "Set up APScheduler: cron jobs per source (weather=hourly, prices=daily 6am, satellite=weekly, advisories=daily)",
                    "Build scheduler manager: start/stop/status per job, health endpoint with last run + next run",
                    "Set up PostgreSQL schema: raw_downloads, processed_data, ingestion_log, source_health tables",
                    "Set up Chroma vector store: collections per data type, embedding model, upsert logic",
                    "Build unified store() interface: every downloader calls store(source, data, metadata) → routes to right destination",
                ],
                "tracks": {
                    "aipm": ["Write the data pipeline PRD section: SLA targets per source, monitoring requirements, failure handling policy"],
                    "evals": ["Build pipeline health eval: automated check — all sources within SLA, no failing jobs, storage within capacity"],
                    "context": ["Design the multi-source context assembler: given a farmer query, which sources to pull, in what order, with what priority"],
                },
                "artifact": "Full scheduler + PostgreSQL schema + Chroma setup + Unified store() interface + Source stubs",
            },
            {
                "day_label": "Day 15",
                "day_idx": 4,
                "title": "RAG Backend + FastAPI Server",
                "hours": "10 hrs",
                "agrisaathi_day": 5,
                "all_tracks": [
                    "Build RAG retrieval engine: embed query → search Chroma → filter by source + district + date recency → re-rank",
                    "Multi-source retrieval: combine weather + price + satellite + advisory into single context window",
                    "Context assembly: order by relevance + recency, apply 4000-token budget, add source citations",
                    "Build FastAPI server with 6 endpoints: GET /health, GET /data/{source}/{district}, POST /search, POST /chat, POST /refresh/{source}, POST /metrics",
                    "Add 'I don't know' behavior: if retrieved context confidence < threshold, return graceful fallback",
                    "Test end-to-end: farmer question → retrieval → Claude response → cited sources",
                ],
                "tracks": {
                    "aipm": ["Write the API design doc: endpoint contracts, error codes, rate limits, auth strategy — shareable with eng team"],
                    "evals": ["Build chat eval suite: 20 farmer questions with expected answers, run LLM-as-Judge scoring"],
                    "context": ["Run context ablation test: remove each source one at a time, document quality impact per source"],
                },
                "artifact": "RAG engine + FastAPI server (6 endpoints) + Chat eval suite + Context ablation results",
            },
        ],
    },
    {
        "num": 4,
        "title": "Agri-Saathi Polish + Integration & Systems Thinking",
        "subtitle": "Complete the project, then practice cross-functional thinking",
        "color": "#2563EB",
        "week_hours": "50 hrs — 10 hrs/day × 5 days",
        "theme": "Days 16–17 complete Agri-Saathi. Days 18–20 zoom out to integration thinking, AI product teardowns, and mock interviews.",
        "days": [
            {
                "day_label": "Day 16",
                "day_idx": 0,
                "title": "Agri-Saathi: E2E Testing + Architecture Diagram",
                "hours": "8 hrs",
                "agrisaathi_day": 6,
                "all_tracks": [
                    "Run full end-to-end test: trigger all downloaders → verify storage → run RAG queries → verify responses",
                    "Test failure modes: source down, scheduler retry, API graceful degradation",
                    "Draw complete architecture diagram (draw.io / Excalidraw): all data sources → ingestion → processing → storage → serving → user",
                    "Annotate diagram: update frequencies, token budgets, retry logic, eval checkpoints",
                    "Write README.md: project overview, architecture, local setup, how to add a new data source",
                    "Write Context Pipeline Spec: formal document describing context assembly logic, source priorities, token budget",
                ],
                "tracks": {
                    "aipm": ["Write PRD v1: complete product requirements — user personas, feature list, success metrics, launch criteria"],
                    "evals": ["Run full eval suite, write Eval Report v1: per-source data quality, per-question chat quality, failure modes"],
                    "context": ["Finalize Context Pipeline Spec with ablation findings: which sources matter most, optimal token allocation, compression strategy"],
                },
                "artifact": "Architecture diagram + README + PRD v1 + Eval Report v1 + Context Pipeline Spec",
            },
            {
                "day_label": "Day 17",
                "day_idx": 1,
                "title": "Agri-Saathi: Portfolio Packaging + Demo Prep",
                "hours": "6 hrs",
                "agrisaathi_day": 7,
                "all_tracks": [
                    "Polish GitHub repo: clean code, docstrings, type hints throughout, clear commit history",
                    "Write 3 resume bullets for Agri-Saathi (quantified: # sources, # endpoints, eval scores, data freshness SLA)",
                    "Prepare demo script: 5 farmer questions showcasing different data sources working together",
                    "Write the case study: problem → approach → architecture decisions → trade-offs → results → what you'd do next",
                    "Create Notion portfolio page: project summary, architecture diagram, key artifacts, code links",
                ],
                "tracks": {
                    "aipm": ["Prepare PM interview story: 'Tell me about an AI product you built' — context, decision, trade-off, outcome, metric"],
                    "evals": ["Prepare Evals interview story: 'How do you evaluate an AI system?' — use Agri-Saathi eval framework as the concrete example"],
                    "context": ["Prepare CE interview story: 'Design a context pipeline for a real-world AI application' — use Agri-Saathi architecture as reference"],
                },
                "artifact": "Polished GitHub repo + Case study + Demo script + 3 role-specific interview stories",
            },
            {
                "day_label": "Day 18–19",
                "day_idx": 2,
                "title": "Multi-Agent System Design (Cross-Role Integration)",
                "hours": "16 hrs",
                "all_tracks": [
                    "Design a multi-agent system from scratch — use AI² itself as the design exercise",
                    "Architecture: Orchestrator (Sonnet — routing) → one of 3 specialists (Learning Coach, Practice Arena, Idea Generator)",
                    "Draw full system diagram with data flows, eval checkpoints, context pipeline annotations",
                    "Identify 5 failure modes and mitigation strategies from each role's perspective",
                    "Study: how context moves between orchestrator and specialists, what compresses vs passes through",
                    "Study: shared learner state design — what each agent needs vs what can be lazy-loaded",
                    "Study: routing intelligence — how the orchestrator classifies intent and selects the right agent",
                ],
                "tracks": {
                    "aipm": ["Own the PRD: user stories, success metrics, launch criteria, risk assessment for the multi-agent system"],
                    "evals": ["Own the eval framework: per-agent evals, end-to-end evals, regression tests, adversarial scenarios"],
                    "context": ["Own the context architecture: orchestrator context, agent-specific context, shared state, handoff compression"],
                },
                "artifact": "Multi-Agent System Design Doc (PRD + Eval Framework + Context Architecture + System Diagram)",
            },
            {
                "day_label": "Day 20",
                "day_idx": 3,
                "title": "AI Product Teardowns + Mock Interviews Round 1",
                "hours": "10 hrs",
                "all_tracks": [
                    "Teardown ChatGPT: PM decisions, quality evals, 100K+ token context management",
                    "Teardown Perplexity AI: product differentiation, search+RAG accuracy evals, real-time web context assembly",
                    "Teardown GitHub Copilot: productivity measurement, bad code suggestion evals, repo-wide context pipeline",
                    "Teardown Claude Artifacts: creative tools product decision, creative output evals, multi-modal context",
                    "Teardown Notion AI: integration PM decisions, open-ended writing evals, workspace-wide context",
                ],
                "tracks": {
                    "aipm": ["Practice 5 AIPM interview questions: product sense, execution, technical, metrics, behavioral. Record yourself."],
                    "evals": ["Practice 5 Evals questions: eval design, debugging, adversarial testing, trade-offs. Mock scenario: quality dropped after a prompt change."],
                    "context": ["Practice 5 CE questions: pipeline design, cost optimization, context debugging, architecture. Mock: RAG returns irrelevant results for 30% of queries."],
                },
                "artifact": "5 AI Product Teardowns + Self-recorded Mock Answers (5 per track) + Self-Assessment Notes",
            },
        ],
    },
    {
        "num": 5,
        "title": "Portfolio, Interview Mastery & Career Launch",
        "subtitle": "Package everything. Perform.",
        "color": "#B45309",
        "week_hours": "50 hrs — 10 hrs/day × 5 days",
        "theme": "You've learned the concepts and built the artifacts. Package them into a portfolio that gets you hired, and drill interview performance until it's second nature.",
        "days": [
            {
                "day_label": "Day 21–22",
                "day_idx": 0,
                "title": "Portfolio Assembly",
                "hours": "16 hrs",
                "all_tracks": [
                    "Build Notion portfolio page showcasing all artifacts organized by role",
                    "Update LinkedIn summary reflecting all three skill areas",
                    "Update resume with AI-specific bullets for each track",
                ],
                "tracks": {
                    "aipm": [
                        "Polish AI Product Case Study into a publishable piece",
                        "Compile PRD + metrics tree + model selection framework",
                        "Write 3 resume bullets with quantified outcomes",
                        "Create 'Product Thinking' doc: your framework for AI product decisions",
                    ],
                    "evals": [
                        "Polish Eval Harness into a documented, runnable project",
                        "Write short white paper: 'Evaluating LLM Quality: A Practical Framework'",
                        "Compile eval taxonomy + adversarial testing methodology",
                        "Create 'Quality Philosophy' doc: how you think about AI evaluation",
                    ],
                    "context": [
                        "Polish Context Pipeline Spec into a technical architecture document",
                        "Write technical blog post: 'Context Engineering: Beyond Prompt Engineering'",
                        "Compile RAG optimization report + context ablation study",
                        "Create 'System Thinking' doc: how you approach context architecture decisions",
                    ],
                },
                "artifact": "Complete Portfolio: Notion Page + Resume + LinkedIn + Role-Specific Writing Samples",
            },
            {
                "day_label": "Day 23–24",
                "day_idx": 1,
                "title": "Interview Deep Practice",
                "hours": "16 hrs",
                "all_tracks": [
                    "Cross-functional scenario: quality dropped 8% after a context change — answer from each role",
                    "STAR story: navigating ambiguity with probabilistic AI outputs",
                    "STAR story: managing a failed model or evaluation that surprised everyone",
                    "STAR story: making an ethical decision about AI deployment",
                    "STAR story: cross-functional conflict between PM, ML engineer, and designer",
                    "STAR story: data-driven decision that contradicted stakeholder intuition",
                    "STAR story: shipping under uncertainty with incomplete eval data",
                    "STAR story: stakeholder pushback on AI quality or limitations",
                ],
                "tracks": {
                    "aipm": ["3 full mock rounds (product sense, execution, technical). Record + review for clarity, structure, AI-specific depth."],
                    "evals": ["3 full mock rounds (eval design, debugging, methodology). Write your own scoring rubric for each answer."],
                    "context": ["3 full mock rounds (system design, optimization, debugging). Whiteboard the pipeline on paper before explaining."],
                },
                "artifact": "Interview Ready Kit: 15+ practiced answers (recorded) + 7 STAR stories + Question Bank",
            },
            {
                "day_label": "Day 25",
                "day_idx": 2,
                "title": "Final Review + Career Launch",
                "hours": "10 hrs",
                "all_tracks": [
                    "Full knowledge audit: can you explain every topic from all 5 weeks in 2 minutes?",
                    "Identify 3 weak spots and do targeted deep-dives on each",
                    "Final portfolio review: does every artifact demonstrate real understanding?",
                    "Prepare 'tell me about yourself' story tailored for each role (AIPM, Evals, CE)",
                    "Application strategy: identify 20 target companies, customize resume for top 5",
                    "Set up job alerts, update LinkedIn status, reach out to 5 people in target roles",
                ],
                "tracks": {
                    "aipm": ["Finalize AIPM 'tell me about yourself' + research top 5 AIPM target companies + draft outreach messages"],
                    "evals": ["Finalize Evals 'tell me about yourself' + research top 5 evals target companies + draft outreach messages"],
                    "context": ["Finalize CE 'tell me about yourself' + research top 5 CE target companies + draft outreach messages"],
                },
                "artifact": "Target Company List (20) + Customized Resumes (5) + Final Knowledge Audit + Outreach Drafts",
            },
        ],
    },
]

# ── All artifacts (flat list for portfolio view) ───────────────────────────────

ALL_ARTIFACTS = [
    {"week": 1, "day": "1–2",   "name": "AI Foundations Cheat Sheet (1-page visual reference per role)"},
    {"week": 1, "day": "3–4",   "name": "LLM Decision Matrix + Hallucination Taxonomy + Token Budget Template"},
    {"week": 1, "day": "5",     "name": "Mini-PRD + Eval Metrics Cheat Sheet + Context Engineering Landscape Map"},
    {"week": 2, "day": "6–7",   "name": "20-Prompt Library + API Cost Memo + 10 Eval Test Cases + Context Assembly Spec"},
    {"week": 2, "day": "8–9",   "name": "Agent Decision Framework + Eval Harness v0 + Agent Context Flow Diagram"},
    {"week": 2, "day": "10",    "name": "RAG Build-vs-Buy Analysis + RAG Eval Suite + Context Pipeline Spec"},
    {"week": 3, "day": "11",    "name": "Project skeleton + sources_registry.json + DataSource base class + Data Strategy 1-pager"},
    {"week": 3, "day": "12",    "name": "WeatherDownloader + MarketPriceDownloader (tested, with retry) + Context formatters"},
    {"week": 3, "day": "13",    "name": "CropSoilDownloader + SatelliteDownloader + Multi-source district join + NDVI interpreter"},
    {"week": 3, "day": "14",    "name": "Full scheduler + PostgreSQL schema + Chroma setup + Unified store() + Source stubs"},
    {"week": 3, "day": "15",    "name": "RAG engine + FastAPI server (6 endpoints) + Chat eval suite + Context ablation results"},
    {"week": 4, "day": "16",    "name": "Architecture diagram + README + PRD v1 + Eval Report v1 + Context Pipeline Spec"},
    {"week": 4, "day": "17",    "name": "Polished GitHub repo + Case study + Demo script + 3 role-specific interview stories"},
    {"week": 4, "day": "18–19", "name": "Multi-Agent System Design Doc (PRD + Eval Framework + Context Architecture + System Diagram)"},
    {"week": 4, "day": "20",    "name": "5 AI Product Teardowns + Self-recorded Mock Answers (5 per track) + Self-Assessment Notes"},
    {"week": 5, "day": "21–22", "name": "Complete Portfolio: Notion Page + Resume + LinkedIn + Role-Specific Writing Samples"},
    {"week": 5, "day": "23–24", "name": "Interview Ready Kit: 15+ practiced answers (recorded) + 7 STAR stories + Question Bank"},
    {"week": 5, "day": "25",    "name": "Target Company List (20) + Customized Resumes (5) + Final Knowledge Audit + Outreach Drafts"},
]

# ── Skill trees per role ───────────────────────────────────────────────────────

ROLE_SKILLS = {
    "aipm": [
        {"category": "AI Literacy",       "skills": ["ML/DL fundamentals", "LLM architecture (conceptual)", "Tokenization & context windows", "Hallucination taxonomy", "Model landscape & selection"]},
        {"category": "PM Core",           "skills": ["PRD writing for AI products", "RICE/MoSCoW prioritization", "North Star & funnel metrics", "A/B test design", "Stakeholder communication"]},
        {"category": "AI Product Craft",  "skills": ["API cost analysis", "Agent vs pipeline decisions", "RAG build-vs-buy analysis", "Data strategy for AI products", "Multi-agent system PRDs", "Product teardown methodology"]},
        {"category": "Portfolio",         "skills": ["Case study writing", "Demo scripting", "Interview story framing (STAR)", "Resume bullets with quantified outcomes", "Notion portfolio"]},
    ],
    "evals": [
        {"category": "Eval Fundamentals", "skills": ["Accuracy, precision, recall, F1, BLEU, ROUGE", "Train/val/test methodology", "Offline vs online evaluation", "Human vs automated evaluation"]},
        {"category": "LLM Evaluation",    "skills": ["LLM-as-Judge pipelines", "Rubric design & calibration", "Hallucination taxonomy & detection", "Adversarial testing", "Bias detection (position, verbosity)"]},
        {"category": "Eval Engineering",  "skills": ["Eval harness v0 → production", "Golden set creation", "Regression testing for LLMs", "Multi-dimensional scoring (RAGAS)", "Data quality evaluation", "Pipeline health monitoring"]},
        {"category": "RAG Evaluation",    "skills": ["Retrieval metrics (P@k, MRR)", "Freshness scoring", "Context ablation study design", "Chat quality evaluation (LLM-as-Judge)"]},
    ],
    "context": [
        {"category": "Context Foundations", "skills": ["Context window mechanics", "Attention patterns & limits", "Token budget optimization", "System prompt architecture", "Context vs prompt distinction"]},
        {"category": "Retrieval & RAG",     "skills": ["Chunking strategies (semantic, fixed, hybrid)", "Embedding model selection", "Vector DB ops (Chroma, pgvector)", "Retrieval tuning (top-k, re-ranking)", "Hybrid search (vector + keyword)"]},
        {"category": "Data Pipeline",       "skills": ["Multi-source data ingestion", "Downloader architecture", "Scheduler design (APScheduler)", "Context formatters (tabular → narrative)", "Storage routing (PostgreSQL + Chroma)"]},
        {"category": "Agent Context",       "skills": ["Context assembly pipelines", "Context compression / summarization", "Context handoff between agents", "Token-efficient tool returns", "Context ablation testing"]},
    ],
}

# ── Helper functions ───────────────────────────────────────────────────────────

def get_task_key(week_num: int, day_idx: int, scope: str, task_idx: int) -> str:
    """Return the canonical key for a task in syllabus_progress."""
    return f"w{week_num}-d{day_idx}-{scope}-{task_idx}"


def get_week_by_num(week_num: int) -> dict | None:
    """Return a week dict by its number, or None."""
    return next((w for w in WEEKS if w["num"] == week_num), None)


def get_progress(syllabus_progress: dict, selected_roles: list[str]) -> dict:
    """
    Compute overall + per-week completion counts for the selected roles.

    Returns:
        {
            "total": int, "done": int, "in_progress": int, "pct": int,
            "by_week": {week_num: {"total": int, "done": int, "pct": int}}
        }
    """
    total = done = in_prog = 0
    by_week: dict[int, dict] = {}

    for week in WEEKS:
        wn = week["num"]
        w_total = w_done = 0

        for day in week["days"]:
            for ti in range(len(day["all_tracks"])):
                key = get_task_key(wn, day["day_idx"], "all", ti)
                status = syllabus_progress.get(key, "todo")
                w_total += 1
                total += 1
                if status == "done":
                    w_done += 1
                    done += 1
                elif status == "in_progress":
                    in_prog += 1

            for role in selected_roles:
                tasks = day["tracks"].get(role, [])
                task_list = tasks if isinstance(tasks, list) else [tasks]
                for ti in range(len(task_list)):
                    key = get_task_key(wn, day["day_idx"], role, ti)
                    status = syllabus_progress.get(key, "todo")
                    w_total += 1
                    total += 1
                    if status == "done":
                        w_done += 1
                        done += 1
                    elif status == "in_progress":
                        in_prog += 1

        by_week[wn] = {
            "total": w_total,
            "done":  w_done,
            "pct":   round(w_done / w_total * 100) if w_total > 0 else 0,
        }

    return {
        "total":       total,
        "done":        done,
        "in_progress": in_prog,
        "pct":         round(done / total * 100) if total > 0 else 0,
        "by_week":     by_week,
    }


def get_current_week(syllabus_progress: dict, selected_roles: list[str]) -> int:
    """Return the week number the learner should be working on (first incomplete week)."""
    progress = get_progress(syllabus_progress, selected_roles)
    for week in WEEKS:
        wn = week["num"]
        w = progress["by_week"].get(wn, {})
        if w.get("pct", 0) < 100 or w.get("total", 0) == 0:
            return wn
    return MAX_WEEKS


def get_all_tasks_for_roles(
    selected_roles: list[str],
    syllabus_progress: dict | None = None,
) -> list[dict]:
    """
    Return every task relevant to the given roles, in syllabus order.
    Each item: key, week_num, week_title, day_label, day_title, scope, text, status, roles, label
    """
    if syllabus_progress is None:
        syllabus_progress = {}
    results = []

    for week in WEEKS:
        for day in week["days"]:
            for ti, task_text in enumerate(day["all_tracks"]):
                key = get_task_key(week["num"], day["day_idx"], "all", ti)
                short = task_text if len(task_text) <= 72 else task_text[:69] + "…"
                results.append({
                    "key":        key,
                    "week_num":   week["num"],
                    "week_title": week["title"],
                    "day_label":  day["day_label"],
                    "day_title":  day["title"],
                    "scope":      "all",
                    "text":       task_text,
                    "status":     syllabus_progress.get(key, "todo"),
                    "roles":      list(ROLE_TRACKS.keys()),
                    "label":      f"Week {week['num']} › {day['title']} › {short}",
                })

            for role in selected_roles:
                tasks = day["tracks"].get(role, [])
                task_list = tasks if isinstance(tasks, list) else [tasks]
                for ti, task_text in enumerate(task_list):
                    key = get_task_key(week["num"], day["day_idx"], role, ti)
                    short = task_text if len(task_text) <= 72 else task_text[:69] + "…"
                    results.append({
                        "key":        key,
                        "week_num":   week["num"],
                        "week_title": week["title"],
                        "day_label":  day["day_label"],
                        "day_title":  day["title"],
                        "scope":      role,
                        "text":       task_text,
                        "status":     syllabus_progress.get(key, "todo"),
                        "roles":      [role],
                        "label":      f"Week {week['num']} › {day['title']} › {short}",
                    })

    return results


def get_next_tasks(
    syllabus_progress: dict,
    selected_roles: list[str],
    n: int = 5,
) -> list[dict]:
    """Return the next n incomplete tasks for the learner's selected roles."""
    results = []
    for week in WEEKS:
        if len(results) >= n:
            break
        for day in week["days"]:
            if len(results) >= n:
                break
            for ti, task_text in enumerate(day["all_tracks"]):
                key = get_task_key(week["num"], day["day_idx"], "all", ti)
                if syllabus_progress.get(key, "todo") != "done":
                    results.append({
                        "key":        key,
                        "week_num":   week["num"],
                        "week_title": week["title"],
                        "day_label":  day["day_label"],
                        "day_title":  day["title"],
                        "scope":      "all",
                        "text":       task_text,
                        "status":     syllabus_progress.get(key, "todo"),
                        "roles":      list(ROLE_TRACKS.keys()),
                    })
                if len(results) >= n:
                    break

            for role in selected_roles:
                if len(results) >= n:
                    break
                tasks = day["tracks"].get(role, [])
                task_list = tasks if isinstance(tasks, list) else [tasks]
                for ti, task_text in enumerate(task_list):
                    key = get_task_key(week["num"], day["day_idx"], role, ti)
                    if syllabus_progress.get(key, "todo") != "done":
                        results.append({
                            "key":        key,
                            "week_num":   week["num"],
                            "week_title": week["title"],
                            "day_label":  day["day_label"],
                            "day_title":  day["title"],
                            "scope":      role,
                            "text":       task_text,
                            "status":     syllabus_progress.get(key, "todo"),
                            "roles":      [role],
                        })
                    if len(results) >= n:
                        break
    return results


def get_full_track_summary(role_key: str) -> str:
    """
    Return a multi-line text summary of the entire curriculum for a given role.
    Used as the stable, cacheable portion of every sub-agent's system prompt.
    """
    role_info = ROLE_TRACKS.get(role_key, {"label": role_key})
    lines = [
        f"CURRICULUM: {role_info['label']} — 5-Week AI Career Roadmap (v2.0)",
        "=" * 60,
    ]

    for week in WEEKS:
        lines.append(f"\nWeek {week['num']}: {week['title']} ({week['week_hours']})")
        lines.append(f"  {week['theme']}")

        for day in week["days"]:
            lines.append(f"\n  [{day['day_label']}] {day['title']} ({day['hours']})")
            for task in day["all_tracks"]:
                lines.append(f"    • {task}")
            role_tasks = day["tracks"].get(role_key, [])
            task_list = role_tasks if isinstance(role_tasks, list) else [role_tasks]
            for task in task_list:
                if task:
                    lines.append(f"    → [{role_key.upper()}] {task}")
            if day.get("artifact"):
                lines.append(f"    Artifact: {day['artifact']}")

    skills = ROLE_SKILLS.get(role_key, [])
    if skills:
        lines.append("\n" + "=" * 60)
        lines.append("SKILL TREE")
        for cat in skills:
            lines.append(f"\n  {cat['category']}:")
            for skill in cat["skills"]:
                lines.append(f"    • {skill}")

    return "\n".join(lines)


def format_week_context(role_key: str, week: int) -> str:
    """
    Return a focused context block for the learner's current week.
    week is 1–5 in the new curriculum.
    """
    week_data = get_week_by_num(week) or WEEKS[-1]
    lines = [
        f"Current: Week {week_data['num']} — {week_data['title']}",
        f"Focus: {week_data['theme']}",
        f"Intensity: {week_data['week_hours']}",
        "",
        "Day-by-day breakdown:",
    ]

    for day in week_data["days"]:
        lines.append(f"\n  {day['day_label']}: {day['title']} ({day['hours']})")
        for task in day["all_tracks"][:3]:
            lines.append(f"    • {task}")
        role_tasks = day["tracks"].get(role_key, [])
        task_list = role_tasks if isinstance(role_tasks, list) else [role_tasks]
        for task in task_list:
            if task:
                lines.append(f"    → [{role_key.upper()}] {task}")
        if day.get("artifact"):
            lines.append(f"    Artifact: {day['artifact']}")

    return "\n".join(lines)


def get_week(role_key: str, week: int) -> dict:
    """
    Return a dict describing the week for the given role.
    week is 1–5 in the new curriculum; values outside that range clamp to week 5.
    Maintained for backward compatibility with agents and app.py.
    """
    week_data = get_week_by_num(week) or WEEKS[-1]
    tasks = []
    for day in week_data["days"]:
        tasks.extend(day["all_tracks"])
        role_tasks = day["tracks"].get(role_key, [])
        task_list = role_tasks if isinstance(role_tasks, list) else [role_tasks]
        tasks.extend(t for t in task_list if t)

    return {
        "title":      week_data["title"],
        "week_num":   week_data["num"],
        "week_hours": week_data["week_hours"],
        "theme":      week_data["theme"],
        "subtitle":   week_data["subtitle"],
        "tasks":      tasks,
    }


# ── Backward compatibility shims ──────────────────────────────────────────────

def get_current_phase_id(syllabus_progress: dict, selected_roles: list[str]) -> str:
    """Backward compat: returns 'week-{n}' for the current active week."""
    return f"week-{get_current_week(syllabus_progress, selected_roles)}"


def get_phase_by_id(phase_id: str) -> dict | None:
    """Backward compat: accepts 'week-{n}' or bare int string, returns week dict."""
    try:
        num = int(str(phase_id).replace("week-", ""))
        return get_week_by_num(num)
    except (ValueError, TypeError):
        return None


_WEEK_TO_PHASE = {wn: f"week-{wn}" for wn in range(1, MAX_WEEKS + 1)}
PHASES = WEEKS  # import alias — /syllabus route now iterates WEEKS directly
