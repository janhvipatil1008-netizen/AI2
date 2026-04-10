"""
AI² — The Career Roadmap syllabus data.

Single source of truth for the 13-week curriculum.
All phases, tracks, tasks, and role assignments live here.

Task keys follow the pattern "<phase_id>-<track_idx>-<task_idx>"
and are stored in the learner's profile under "syllabus_progress".
"""

# ── Role definitions ───────────────────────────────────────────────────────────

ROLE_TRACKS = {
    "aipm":    {"label": "AI Product Manager",  "icon": "📦", "color": "#4FC3F7"},
    "evals":   {"label": "AI Evals Specialist", "icon": "🔬", "color": "#FF8A65"},
    "context": {"label": "Context Engineer",    "icon": "🧩", "color": "#AED581"},
}

# ── 6-Phase Roadmap ────────────────────────────────────────────────────────────

PHASES = [
    {
        "id": "foundation",
        "phase": "Phase 1",
        "title": "AI Foundations & PM Core",
        "weeks": "Weeks 1–2",
        "icon": "🧠",
        "description": "Build unshakeable AI literacy + sharpen PM fundamentals",
        "artifact": "AI PM Handbook + Eval Metrics Cheat Sheet + Context Engineering Map",
        "tracks": [
            {
                "name": "AI Fundamentals",
                "roles": ["aipm", "evals", "context"],
                "tasks": [
                    {"text": "Write 1-page explainers: AI vs ML vs DL, supervised vs unsupervised",        "roles": ["aipm", "evals", "context"]},
                    {"text": "Understand overfitting/underfitting — what PMs do about it",                  "roles": ["aipm"]},
                    {"text": "Build a toy classifier (Google Teachable Machine / no-code AutoML)",          "roles": ["aipm", "evals"]},
                    {"text": "Study loss functions, gradient descent (conceptual, not math-heavy)",         "roles": ["aipm", "evals"]},
                    {"text": "Create 'AI PM Handbook' doc with sections matching your skill checklist",     "roles": ["aipm"]},
                ],
            },
            {
                "name": "LLMs & Transformers",
                "roles": ["aipm", "evals", "context"],
                "tasks": [
                    {"text": "Read 'The Illustrated Transformer' → write 10-bullet summary",                         "roles": ["aipm", "evals", "context"]},
                    {"text": "1-page cheat sheet: tokens, context windows, embeddings, attention",                   "roles": ["aipm", "evals", "context"]},
                    {"text": "Understand hallucinations — causes, mitigation strategies for products",               "roles": ["aipm", "evals", "context"]},
                    {"text": "Study attention mechanics: U-shaped curves, 'lost-in-the-middle' phenomenon",          "roles": ["context"]},
                    {"text": "Map token budget math: how context window size affects cost, latency, and quality",    "roles": ["context"]},
                ],
            },
            {
                "name": "PM Fundamentals Refresh",
                "roles": ["aipm"],
                "tasks": [
                    {"text": "Review RICE & MoSCoW prioritization — practice scoring 10 backlog items",  "roles": ["aipm"]},
                    {"text": "Define North Star metrics, funnel metrics, cohort analysis concepts",      "roles": ["aipm"]},
                    {"text": "Write a mini PRD for any product feature you use daily",                   "roles": ["aipm"]},
                ],
            },
            {
                "name": "Evaluation Foundations",
                "roles": ["evals"],
                "tasks": [
                    {"text": "Study core metrics: accuracy, precision, recall, F1, BLEU, ROUGE",                "roles": ["evals"]},
                    {"text": "Understand train/val/test splits — why they matter, common mistakes",             "roles": ["evals"]},
                    {"text": "Learn difference: offline eval vs online A/B testing vs human eval",              "roles": ["evals"]},
                    {"text": "Read OpenAI's eval guidance (3-step workflow)",                                   "roles": ["evals"]},
                ],
            },
            {
                "name": "Context Engineering Foundations",
                "roles": ["context"],
                "tasks": [
                    {"text": "Read Anthropic's 'Effective Context Engineering for AI Agents' guide",                        "roles": ["context"]},
                    {"text": "Understand context vs prompt: system prompts, tool defs, message history, retrieved docs",   "roles": ["context"]},
                    {"text": "Study RAG basics: why retrieval grounds AI, chunking strategies, embedding models",           "roles": ["context"]},
                    {"text": "Map the context engineering landscape: rules, skills, memory, tools, retrieval",              "roles": ["context"]},
                ],
            },
        ],
    },
    {
        "id": "prompts-apis",
        "phase": "Phase 2",
        "title": "APIs, Prompts & Core Techniques",
        "weeks": "Weeks 3–4",
        "icon": "⚡",
        "description": "Master API calls, prompt/context craft, and eval thinking",
        "artifact": "Prompt Library + Eval Harness v0 + Context Assembly Spec + Agent Patterns Sheet",
        "tracks": [
            {
                "name": "APIs & Tooling",
                "roles": ["aipm", "evals", "context"],
                "tasks": [
                    {"text": "Install Postman → send first REST request to any public API",                             "roles": ["aipm"]},
                    {"text": "Create OpenAI developer account → complete API quickstart",                               "roles": ["aipm", "evals", "context"]},
                    {"text": "Make 3 API calls: plain chat, structured JSON output, cost-aware (capped tokens)",        "roles": ["aipm", "evals", "context"]},
                    {"text": "Write stakeholder-ready note: temperature, tokens, latency, cost tradeoffs",              "roles": ["aipm"]},
                ],
            },
            {
                "name": "Prompt Engineering → Context Engineering",
                "roles": ["aipm", "context"],
                "tasks": [
                    {"text": "Build prompt library (20+ prompts): extraction, classification, summarization, safety",                   "roles": ["aipm", "context"]},
                    {"text": "Study prompt frameworks: chain-of-thought, few-shot, system/user roles",                                  "roles": ["aipm", "context"]},
                    {"text": "Learn structured outputs (JSON mode, function calling)",                                                  "roles": ["aipm", "context"]},
                    {"text": "Advance to context engineering: dynamic system prompts, persona prompting, least-to-most",               "roles": ["context"]},
                    {"text": "Build a 'context assembly pipeline': user metadata + task context + retrieved docs + tool schemas",      "roles": ["context"]},
                    {"text": "Experiment: same task with minimal vs rich context — document quality delta",                             "roles": ["context"]},
                ],
            },
            {
                "name": "Eval Methodologies Deep Dive",
                "roles": ["evals"],
                "tasks": [
                    {"text": "Study LLM-as-a-Judge: direct scoring, pairwise comparison, rubric generation",           "roles": ["evals"]},
                    {"text": "Learn eval frameworks: RAGAS, DeepEval, Phoenix/TruLens, OpenAI Evals",                  "roles": ["evals"]},
                    {"text": "Build 10 'unit-test-like' eval cases for prompts (pass/fail with rubrics)",              "roles": ["evals"]},
                    {"text": "Understand bias in evals: position bias, verbosity bias, self-enhancement bias",          "roles": ["evals"]},
                    {"text": "Create a simple automated eval harness (script that runs questions + scores outputs)",    "roles": ["evals"]},
                    {"text": "Study human-in-the-loop evaluation design: when to use humans vs LLM judges",            "roles": ["evals"]},
                ],
            },
            {
                "name": "Agents & Protocols",
                "roles": ["aipm", "context"],
                "tasks": [
                    {"text": "Understand Agents vs LLMs — tool use, orchestration, planning patterns",                                      "roles": ["aipm", "context"]},
                    {"text": "Study MCP (Model Context Protocol) and A2A — the new interoperability standards",                             "roles": ["aipm", "context"]},
                    {"text": "Map the 7 agentic design patterns: ReAct, Reflection, Tool Use, Planning, Multi-Agent, Sequential, Human-in-Loop", "roles": ["aipm", "context"]},
                    {"text": "Study tool design principles: self-contained, token-efficient returns, clear schemas",                         "roles": ["context"]},
                ],
            },
        ],
    },
    {
        "id": "agrisaathi",
        "phase": "Phase 3",
        "title": "Agri-Saathi MVP Build",
        "weeks": "Weeks 5–7",
        "icon": "🌾",
        "description": "Flagship project — RAG + citations + weather tool + safety rails + evals",
        "artifact": "Working Agri-Saathi MVP + Architecture Diagram + Context Pipeline Spec + PRD v1",
        "tracks": [
            {
                "name": "Week 5: PRD + Knowledge Base + UI",
                "roles": ["aipm", "context"],
                "tasks": [
                    {"text": "Define target user (small farmers / agri retailers / extension workers)",             "roles": ["aipm"]},
                    {"text": "Conduct 8 user conversations (informal farmer/retailer interviews)",                  "roles": ["aipm"]},
                    {"text": "Write Agri-Saathi PRD v1: persona, JTBD, MVP features, non-goals, risks",            "roles": ["aipm"]},
                    {"text": "Create 'Top 20 FAQs farmers ask' list (seed for eval set)",                          "roles": ["aipm", "evals"]},
                    {"text": "Build knowledge pack: 15-30 pages trusted sources for 1 crop",                       "roles": ["aipm", "context"]},
                    {"text": "Create sources.csv: source name, type, date, trust level",                           "roles": ["aipm", "context"]},
                    {"text": "Define 'What Agri-Saathi will NOT answer' safety list",                              "roles": ["aipm", "evals"]},
                    {"text": "Build prototype UI (Lovable): onboarding, chat screen, citations drawer",            "roles": ["aipm"]},
                    {"text": "Define UX contract (API shape: answer, citations, confidence, follow-up)",           "roles": ["aipm"]},
                ],
            },
            {
                "name": "Week 6: RAG Backend + Context Pipeline",
                "roles": ["aipm", "context"],
                "tasks": [
                    {"text": "Implement: doc ingestion → chunking → embeddings → vector store (Chroma)",                       "roles": ["aipm", "context"]},
                    {"text": "Experiment with chunking strategies: size, overlap, semantic vs fixed",                           "roles": ["context"]},
                    {"text": "Design the context assembly: system prompt + user profile + retrieved chunks + tool outputs",     "roles": ["context"]},
                    {"text": "Implement context compression: summarize long retrievals, trim irrelevant chunks",                "roles": ["context"]},
                    {"text": "Build /chat endpoint: embed query → retrieve top-k → LLM with context → citations",             "roles": ["aipm", "context"]},
                    {"text": "Add 'I don't know' behavior when retrieval confidence is low",                                    "roles": ["aipm", "context"]},
                    {"text": "Create 1-page architecture diagram (boxes + arrows)",                                             "roles": ["aipm"]},
                ],
            },
            {
                "name": "Week 7: Weather Tool + Weekly Plan (Agent Feature)",
                "roles": ["aipm", "context"],
                "tasks": [
                    {"text": "Add get_weather() tool — design token-efficient response format",                                 "roles": ["context"]},
                    {"text": "Build 'Weekly Crop Plan' agentic workflow: weather call → RAG → 7-day plan",                    "roles": ["aipm", "context"]},
                    {"text": "Implement dynamic context switching: different tool/retrieval configs per query type",            "roles": ["context"]},
                    {"text": "Add guardrails: no precise pesticide dosing without citation",                                    "roles": ["aipm"]},
                    {"text": "Build Weekly Plan screen in UI",                                                                  "roles": ["aipm"]},
                    {"text": "Write 1-page 'tool calling / workflow' spec",                                                    "roles": ["aipm"]},
                ],
            },
        ],
    },
    {
        "id": "evals-deep",
        "phase": "Phase 4",
        "title": "Evaluation & Metrics Mastery",
        "weeks": "Week 8",
        "icon": "📊",
        "description": "The phase that separates prompt hobbyists from real AIPMs & Eval specialists",
        "artifact": "Eval Report + LLM Judge Pipeline + Context Ablation Study + Metrics Tree",
        "tracks": [
            {
                "name": "Golden Set & Offline Evals",
                "roles": ["aipm", "evals"],
                "tasks": [
                    {"text": "Create golden_set.csv: 60 questions with expected answers, must-cite sources, failure tags",  "roles": ["aipm", "evals"]},
                    {"text": "Define scoring rubric (0/1/2): groundedness, helpfulness, safety, localization",              "roles": ["aipm", "evals"]},
                    {"text": "Run Agri-Saathi against full golden set",                                                     "roles": ["aipm", "evals"]},
                    {"text": "Produce Eval Report v1: baseline scores, top 10 failures, 3 concrete fixes",                 "roles": ["aipm", "evals"]},
                    {"text": "Show before/after: 'Groundedness improved from X → Y after change Z'",                       "roles": ["aipm", "evals"]},
                ],
            },
            {
                "name": "Advanced Eval Techniques",
                "roles": ["evals"],
                "tasks": [
                    {"text": "Build LLM-as-Judge pipeline: design rubrics, test for judge consistency/bias",                "roles": ["evals"]},
                    {"text": "Create adversarial test set: prompt injection, jailbreak attempts, edge cases",               "roles": ["evals"]},
                    {"text": "Implement multi-dimensional scoring: faithfulness, relevance, coherence, safety (RAGAS-style)", "roles": ["evals"]},
                    {"text": "Design regression testing: automated checks that catch quality drops on code changes",         "roles": ["evals"]},
                    {"text": "Build eval dashboard: visualize scores over time, failure mode distribution",                 "roles": ["evals"]},
                    {"text": "Study synthetic data generation for scaling eval sets with LLMs",                             "roles": ["evals"]},
                    {"text": "Write Eval Methodology doc: when to use human eval vs LLM judge vs heuristic",               "roles": ["evals"]},
                ],
            },
            {
                "name": "Context Quality Evaluation",
                "roles": ["context", "evals"],
                "tasks": [
                    {"text": "Measure retrieval quality: precision@k, recall@k, MRR for your RAG pipeline",                "roles": ["context", "evals"]},
                    {"text": "A/B test context configurations: minimal vs rich context, different chunk sizes",             "roles": ["context"]},
                    {"text": "Measure context efficiency: quality-per-token (output quality / input tokens used)",         "roles": ["context"]},
                    {"text": "Build context ablation tests: systematically remove context components, measure impact",     "roles": ["context"]},
                    {"text": "Document context failure modes: too much, wrong, stale, missing context",                    "roles": ["context"]},
                ],
            },
            {
                "name": "Metrics, Logging & Experiments",
                "roles": ["aipm"],
                "tasks": [
                    {"text": "Define North Star + 3 supporting metrics for Agri-Saathi",                                           "roles": ["aipm"]},
                    {"text": "Add lightweight logging: question category, retrieval score, response rating, failure tag",           "roles": ["aipm"]},
                    {"text": "Write A/B test plan: hypothesis, primary metric, guardrails, sample size, rollback",                 "roles": ["aipm"]},
                    {"text": "Master AI-specific metrics: precision, recall, F1, latency, cost-per-session",                       "roles": ["aipm"]},
                ],
            },
        ],
    },
    {
        "id": "ai2-agent",
        "phase": "Phase 5",
        "title": "AI² — Multi-Agent Learning System",
        "weeks": "Weeks 9–11",
        "icon": "🤖",
        "description": "5-agent orchestration system for AI learners — build one agent at a time",
        "artifact": "5-Agent Learning System + Orchestrator + Per-Agent Evals + Context Handoff Spec + PRD #2 + Demo",
        "tracks": [
            {
                "name": "System Design & PRD",
                "roles": ["aipm", "evals", "context"],
                "tasks": [
                    {"text": "Write PRD #2: AI Learning Multi-Agent System — target users, JTBD, architecture overview",            "roles": ["aipm"]},
                    {"text": "Define orchestrator routing logic: how central orchestrator routes to 5 specialized agents",          "roles": ["aipm", "context"]},
                    {"text": "Design inter-agent handoff protocol: how agents pass context to each other",                          "roles": ["context"]},
                    {"text": "Design the eval framework: per-agent eval dimensions + end-to-end orchestration eval",               "roles": ["evals"]},
                    {"text": "Map context flow diagram: what learner state/history each agent needs at inference time",             "roles": ["context"]},
                    {"text": "Define modular agent interface contract: inputs, outputs, handoff schema for each agent",             "roles": ["aipm", "context"]},
                ],
            },
            {
                "name": "Step 1: AI Coding Agent",
                "roles": ["aipm", "evals", "context"],
                "tasks": [
                    {"text": "Build AI Coding Agent: teaches AI-related coding, adapts to learner's current skill level",          "roles": ["aipm", "context"]},
                    {"text": "Design adaptive context: learner profile injected into system prompt",                               "roles": ["context"]},
                    {"text": "Implement skill-level detection: beginner/intermediate/advanced routing",                            "roles": ["context"]},
                    {"text": "Create 20-question eval set: does it teach correctly at each level?",                                "roles": ["evals"]},
                    {"text": "Test & confirm: agent works standalone before proceeding to Step 2",                                 "roles": ["evals"]},
                ],
            },
            {
                "name": "Step 2: Learning Management Agent",
                "roles": ["aipm", "evals", "context"],
                "tasks": [
                    {"text": "Build Learning Mgmt Agent: docs, progress tracking, to-do lists, topic selection",                  "roles": ["aipm", "context"]},
                    {"text": "Implement learner state management: tracks what's learned, what's next, completion %",              "roles": ["context"]},
                    {"text": "Add resource aggregation: pulls learning materials from multiple sources",                           "roles": ["context"]},
                    {"text": "Build handoff to Research Agent: when learner wants to go deeper",                                   "roles": ["context"]},
                    {"text": "Create 15-question eval set: does it track progress? Does handoff preserve context?",               "roles": ["evals"]},
                    {"text": "Test & confirm: agent works standalone + handoff to Research works",                                 "roles": ["evals"]},
                ],
            },
            {
                "name": "Step 3: Research & Learning Agent",
                "roles": ["aipm", "evals", "context"],
                "tasks": [
                    {"text": "Build Research Agent: explores topics via web search, Wikipedia, Claude, ChatGPT",                  "roles": ["aipm", "context"]},
                    {"text": "Design multi-source context assembly: merge results into coherent context",                         "roles": ["context"]},
                    {"text": "Implement handoff reception: receives topic + learner level from Learning Mgmt Agent",              "roles": ["context"]},
                    {"text": "Add source citation and trust-level tagging for retrieved information",                              "roles": ["context"]},
                    {"text": "Create 15-question eval set: accuracy, source quality, adaptation to learner level",               "roles": ["evals"]},
                    {"text": "Test & confirm: standalone + receives handoffs correctly from Learning Mgmt",                       "roles": ["evals"]},
                ],
            },
            {
                "name": "Step 4: Practice Agent",
                "roles": ["aipm", "evals", "context"],
                "tasks": [
                    {"text": "Build Practice Agent: quizzes, coding challenges, mock interview simulations",                      "roles": ["aipm", "context"]},
                    {"text": "Design assessment context: pull learner history + completed topics for relevant challenges",        "roles": ["context"]},
                    {"text": "Implement difficulty adaptation: adjust based on learner's performance history",                    "roles": ["context"]},
                    {"text": "Add mock interview mode: AI PM product sense, execution, and technical deep-dive simulations",     "roles": ["aipm"]},
                    {"text": "Create 20-question eval set: question quality, difficulty calibration, feedback accuracy",         "roles": ["evals"]},
                    {"text": "Test & confirm: standalone practice flows work before proceeding",                                  "roles": ["evals"]},
                ],
            },
            {
                "name": "Step 5: Idea Generation Agent",
                "roles": ["aipm", "evals", "context"],
                "tasks": [
                    {"text": "Build Idea Gen Agent: brainstorming, real-world project discovery, guided solution exploration",   "roles": ["aipm", "context"]},
                    {"text": "Design creative context: inject learner's skills, interests, and completed projects",              "roles": ["context"]},
                    {"text": "Add project feasibility assessment: scope, complexity, portfolio value for target roles",          "roles": ["aipm"]},
                    {"text": "Create 10-question eval set: idea quality, relevance to learner's level, actionability",          "roles": ["evals"]},
                    {"text": "Test & confirm: standalone brainstorming works before orchestration assembly",                     "roles": ["evals"]},
                ],
            },
            {
                "name": "Orchestration Layer Assembly",
                "roles": ["aipm", "evals", "context"],
                "tasks": [
                    {"text": "Build central orchestrator: routes learner requests to the correct specialized agent",             "roles": ["aipm", "context"]},
                    {"text": "Implement shared learner state: orchestrator maintains and passes profile across all agents",      "roles": ["context"]},
                    {"text": "Design context handoff compression: summarize agent outputs before passing (token efficiency)",    "roles": ["context"]},
                    {"text": "Add routing intelligence: classify intent → select agent → inject context → return response",     "roles": ["context"]},
                    {"text": "Build end-to-end eval: 30-question set testing cross-agent workflows",                             "roles": ["evals"]},
                    {"text": "Test orchestration failure modes: wrong routing, context loss, circular handoffs",                 "roles": ["evals"]},
                    {"text": "Produce Eval Report v2: per-agent scores + orchestration scores",                                  "roles": ["evals"]},
                    {"text": "Build demo UI showing agent switching, learner dashboard, progress tracking",                      "roles": ["aipm"]},
                ],
            },
        ],
    },
    {
        "id": "portfolio",
        "phase": "Phase 6",
        "title": "Portfolio Packaging & Interview Prep",
        "weeks": "Weeks 12–13",
        "icon": "🎯",
        "description": "Make your work discoverable and role-specific for recruiters",
        "artifact": "Complete Package: 2 Projects + Role-Specific Artifacts + Demo Videos + Case Studies",
        "tracks": [
            {
                "name": "Polish & Harden",
                "roles": ["aipm", "evals", "context"],
                "tasks": [
                    {"text": "Add reliability features to Agri-Saathi: follow-up questions, escalation CTA",    "roles": ["aipm"]},
                    {"text": "Final eval run → summarize deltas vs Week 8 baseline",                            "roles": ["aipm", "evals"]},
                    {"text": "Final context quality audit → document improvements over iterations",              "roles": ["context"]},
                    {"text": "Create 1-page Launch Checklist: privacy, limitations, monitoring, rollback",      "roles": ["aipm"]},
                ],
            },
            {
                "name": "Role-Specific Portfolio Artifacts",
                "roles": ["aipm", "evals", "context"],
                "tasks": [
                    {"text": "AIPM: Case study (problem→users→solution→architecture→evals→results→roadmap)",       "roles": ["aipm"]},
                    {"text": "AIPM: 2 PRDs + metrics tree + experiment plan + RICE prioritization exercise",        "roles": ["aipm"]},
                    {"text": "EVALS: Eval methodology white paper (human/LLM-judge/heuristic)",                    "roles": ["evals"]},
                    {"text": "EVALS: Published eval framework with golden sets, rubrics, dashboards, regression",  "roles": ["evals"]},
                    {"text": "EVALS: Adversarial testing report + safety audit findings",                          "roles": ["evals"]},
                    {"text": "CONTEXT: Context architecture spec with diagrams showing info flow at inference",     "roles": ["context"]},
                    {"text": "CONTEXT: Context ablation study showing quality-per-token optimization",             "roles": ["context"]},
                    {"text": "CONTEXT: RAG optimization report: chunking experiments, retrieval benchmarks",       "roles": ["context"]},
                ],
            },
            {
                "name": "Demo Videos & Resume",
                "roles": ["aipm", "evals", "context"],
                "tasks": [
                    {"text": "Record Agri-Saathi demo (2-3 min): chat + citations + weekly plan + evals",              "roles": ["aipm", "evals", "context"]},
                    {"text": "Record AI² demo (2-3 min): 5-agent system, orchestrator routing, learner dashboard",     "roles": ["aipm", "evals", "context"]},
                    {"text": "Create portfolio page (Notion) with role-specific sections",                             "roles": ["aipm", "evals", "context"]},
                    {"text": "Update resume with 3 role-specific bullets tied to quantified outcomes",                 "roles": ["aipm", "evals", "context"]},
                    {"text": "Update LinkedIn with project entries",                                                    "roles": ["aipm", "evals", "context"]},
                ],
            },
            {
                "name": "Interview Prep",
                "roles": ["aipm", "evals", "context"],
                "tasks": [
                    {"text": "AIPM: 3 product sense + 2 execution/metrics + 1 technical deep dive mocks",                          "roles": ["aipm"]},
                    {"text": "AIPM: Prep for 'How would you prioritize which agent to build next?'",                               "roles": ["aipm"]},
                    {"text": "EVALS: Prep for 'How would you evaluate X?' questions across 5 product types",                       "roles": ["evals"]},
                    {"text": "EVALS: Prep for 'This model is hallucinating — walk me through your debugging process'",             "roles": ["evals"]},
                    {"text": "EVALS: Prep for 'How do you eval a multi-agent system vs a single agent?'",                         "roles": ["evals"]},
                    {"text": "CONTEXT: Prep for 'Design the context pipeline for X agent' system design questions",                "roles": ["context"]},
                    {"text": "CONTEXT: Prep for 'How would you optimize context to reduce cost by 40%?'",                         "roles": ["context"]},
                    {"text": "CONTEXT: Prep for 'How do you handle context handoffs between agents without losing state?'",        "roles": ["context"]},
                    {"text": "ALL: Prepare 'why this role' narrative with concrete project evidence from both projects",            "roles": ["aipm", "evals", "context"]},
                ],
            },
        ],
    },
]

# ── Skill trees per role ───────────────────────────────────────────────────────

ROLE_SKILLS = {
    "aipm": [
        {"category": "PM Core", "skills": ["PRD writing & JTBD", "RICE/MoSCoW prioritization", "North Star & funnel metrics", "A/B test design", "Cohort analysis"]},
        {"category": "AI Literacy", "skills": ["ML/DL fundamentals", "LLM architecture (conceptual)", "RAG + vector DBs", "Agents & tool use", "MCP & A2A protocols"]},
        {"category": "AI Product Craft", "skills": ["Model lifecycle mgmt", "AI-specific metrics (P/R/F1)", "Risk mgmt (bias, drift, injection)", "Cost/latency optimization", "Responsible AI practices", "Multi-agent system design", "Modular agent interfaces"]},
        {"category": "Tools", "skills": ["Lovable / v0 (rapid UI)", "Postman / API tools", "Notion for PRDs", "Loom for demos", "Basic Python / JSON"]},
    ],
    "evals": [
        {"category": "Eval Fundamentals", "skills": ["Precision, recall, F1, BLEU, ROUGE", "Train/val/test methodology", "Offline vs online evaluation", "Statistical significance basics", "Human eval design"]},
        {"category": "LLM Evaluation", "skills": ["LLM-as-Judge pipelines", "Rubric design & calibration", "Judge bias detection & mitigation", "Adversarial testing", "Prompt injection detection"]},
        {"category": "Eval Engineering", "skills": ["Golden set creation & maintenance", "Automated eval harnesses", "Regression testing for LLMs", "Multi-dimensional scoring (RAGAS)", "Synthetic data for eval scaling", "Multi-agent orchestration evals", "Routing correctness scoring"]},
        {"category": "RAG Evaluation", "skills": ["Retrieval metrics (P@k, MRR)", "Faithfulness scoring", "Citation accuracy measurement", "Context relevance scoring", "End-to-end RAG benchmarking"]},
        {"category": "Tools", "skills": ["RAGAS / DeepEval / Phoenix", "OpenAI Evals framework", "Label Studio / Prodigy", "Custom scoring scripts (Python)", "Eval dashboards & visualization"]},
    ],
    "context": [
        {"category": "Context Foundations", "skills": ["Context window mechanics", "Attention patterns & limits", "Token budget optimization", "System prompt architecture", "Few-shot example design"]},
        {"category": "Retrieval & RAG", "skills": ["Chunking strategies (semantic, fixed, hybrid)", "Embedding model selection", "Vector DB ops (Chroma, Pinecone)", "Retrieval tuning (top-k, threshold)", "Hybrid search (vector + keyword)"]},
        {"category": "Dynamic Context", "skills": ["Context assembly pipelines", "Context compression / summarization", "Dynamic tool selection at runtime", "User state & memory management", "Context routing per query type"]},
        {"category": "Agent Context", "skills": ["MCP tool schema design", "Token-efficient tool returns", "Multi-turn state management", "Context ablation testing", "Quality-per-token optimization", "Inter-agent context handoffs", "Multi-agent shared state mgmt"]},
        {"category": "Tools", "skills": ["LangChain / LlamaIndex", "Chroma / Pinecone / Weaviate", "Claude / OpenAI APIs", "Claude Code / Cursor (context rules)", "Custom context pipelines (Python)"]},
    ],
}

# ── Core helper functions ──────────────────────────────────────────────────────

def get_task_key(phase_id: str, track_idx: int, task_idx: int) -> str:
    """Return the canonical key for a task in syllabus_progress."""
    return f"{phase_id}-{track_idx}-{task_idx}"


def get_phase_by_id(phase_id: str) -> dict | None:
    """Return a phase dict by its id, or None."""
    return next((p for p in PHASES if p["id"] == phase_id), None)


def get_progress(syllabus_progress: dict, selected_roles: list[str]) -> dict:
    """
    Compute overall + per-phase completion counts for the selected roles.

    Returns:
        {
            "total": int, "done": int, "in_progress": int, "pct": int,
            "by_phase": {phase_id: {"total": int, "done": int, "pct": int}}
        }
    """
    total = done = in_prog = 0
    by_phase: dict[str, dict] = {}

    for phase in PHASES:
        ph_total = ph_done = 0
        for ti, track in enumerate(phase["tracks"]):
            if not any(r in selected_roles for r in track["roles"]):
                continue
            for taski, task in enumerate(track["tasks"]):
                if not any(r in selected_roles for r in task["roles"]):
                    continue
                key = get_task_key(phase["id"], ti, taski)
                status = syllabus_progress.get(key, "todo")
                ph_total += 1
                total += 1
                if status == "done":
                    ph_done += 1
                    done += 1
                elif status == "in_progress":
                    in_prog += 1
        by_phase[phase["id"]] = {
            "total": ph_total,
            "done":  ph_done,
            "pct":   round(ph_done / ph_total * 100) if ph_total > 0 else 0,
        }

    return {
        "total":       total,
        "done":        done,
        "in_progress": in_prog,
        "pct":         round(done / total * 100) if total > 0 else 0,
        "by_phase":    by_phase,
    }


def get_current_phase_id(syllabus_progress: dict, selected_roles: list[str]) -> str:
    """
    Return the id of the phase the learner should be working on right now.
    Logic: the first phase that isn't 100% complete.
    Falls back to the last phase if all are done.
    """
    progress = get_progress(syllabus_progress, selected_roles)
    for phase in PHASES:
        ph = progress["by_phase"].get(phase["id"], {})
        if ph.get("pct", 0) < 100 or ph.get("total", 0) == 0:
            return phase["id"]
    return PHASES[-1]["id"]


def get_all_tasks_for_roles(
    selected_roles: list[str],
    syllabus_progress: dict | None = None,
) -> list[dict]:
    """
    Return every task relevant to the given roles, in syllabus order.
    Optionally annotates each task with its completion status.

    Each returned item has:
        key, phase_num, phase_title, track_name, text, status, roles, label

    The 'label' field is pre-formatted for st.selectbox:
        "Phase 1 › AI Fundamentals › Write 1-page explainers: AI vs ML…"
    Long task text is truncated to 72 characters.
    """
    if syllabus_progress is None:
        syllabus_progress = {}
    results = []
    for phase in PHASES:
        for ti, track in enumerate(phase["tracks"]):
            if not any(r in selected_roles for r in track["roles"]):
                continue
            for taski, task in enumerate(track["tasks"]):
                if not any(r in selected_roles for r in task["roles"]):
                    continue
                key = get_task_key(phase["id"], ti, taski)
                status = syllabus_progress.get(key, "todo")
                text = task["text"]
                short_text = text if len(text) <= 72 else text[:69] + "…"
                label = f"{phase['phase']} › {track['name']} › {short_text}"
                results.append({
                    "key":         key,
                    "phase_num":   phase["phase"],
                    "phase_title": phase["title"],
                    "track_name":  track["name"],
                    "text":        text,
                    "status":      status,
                    "roles":       task["roles"],
                    "label":       label,
                })
    return results


def get_next_tasks(
    syllabus_progress: dict,
    selected_roles: list[str],
    n: int = 5,
) -> list[dict]:
    """
    Return the next n incomplete tasks for the learner's selected roles,
    in syllabus order, with phase/track context attached.

    Each returned item:
        {
            "key": str,
            "phase_id": str, "phase_title": str,
            "track_name": str,
            "text": str,
            "status": "todo" | "in_progress",
            "roles": [str],
        }
    """
    results = []
    for phase in PHASES:
        if len(results) >= n:
            break
        for ti, track in enumerate(phase["tracks"]):
            if not any(r in selected_roles for r in track["roles"]):
                continue
            for taski, task in enumerate(track["tasks"]):
                if not any(r in selected_roles for r in task["roles"]):
                    continue
                key = get_task_key(phase["id"], ti, taski)
                status = syllabus_progress.get(key, "todo")
                if status != "done":
                    results.append({
                        "key":         key,
                        "phase_id":    phase["id"],
                        "phase_title": phase["title"],
                        "track_name":  track["name"],
                        "text":        task["text"],
                        "status":      status,
                        "roles":       task["roles"],
                    })
                if len(results) >= n:
                    break
    return results


# ── Compatibility shims for sub-agent prompts ──────────────────────────────────
# The Learning Coach, Practice Arena, and Idea Generator agents call these
# functions to build their cached system prompts. They map the phase-based
# structure above into the flat-text format those agents expect.

# Week → phase mapping (weeks are approximate; phases are the real unit)
_WEEK_TO_PHASE = {
    1: "foundation",  2: "foundation",
    3: "prompts-apis", 4: "prompts-apis",
    5: "agrisaathi",  6: "agrisaathi",  7: "agrisaathi",
    8: "evals-deep",
    9: "ai2-agent",  10: "ai2-agent",  11: "ai2-agent",
    12: "portfolio",  13: "portfolio",
}


def get_full_track_summary(role_key: str) -> str:
    """
    Return a multi-line text summary of the entire curriculum for a given role.
    Used as the stable, cacheable portion of every sub-agent's system prompt.
    """
    role_info = ROLE_TRACKS.get(role_key, {"label": role_key})
    lines = [
        f"CURRICULUM: {role_info['label']} — 13-Week AI Career Roadmap",
        "=" * 60,
    ]

    for phase in PHASES:
        # Only include tracks/tasks relevant to this role
        relevant_tracks = [
            t for t in phase["tracks"]
            if any(r == role_key for r in t["roles"])
        ]
        if not relevant_tracks:
            continue

        lines.append(f"\n{phase['phase']}: {phase['title']} ({phase['weeks']})")
        lines.append(f"  {phase['description']}")
        lines.append(f"  Artifact: {phase['artifact']}")

        for track in relevant_tracks:
            lines.append(f"\n  [{track['name']}]")
            for task in track["tasks"]:
                if role_key in task["roles"]:
                    lines.append(f"    • {task['text']}")

    # Append skill tree
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
    Maps the week number to the appropriate phase and lists relevant tasks.
    """
    phase_id = _WEEK_TO_PHASE.get(week, _WEEK_TO_PHASE[13])
    phase = get_phase_by_id(phase_id)
    if phase is None:
        return f"Week {week} — no phase data found."

    lines = [
        f"Current: {phase['phase']} — {phase['title']} ({phase['weeks']})",
        f"Focus: {phase['description']}",
        f"Target artifact: {phase['artifact']}",
        "",
        "Relevant tasks for your role:",
    ]

    for track in phase["tracks"]:
        relevant = [t for t in track["tasks"] if role_key in t["roles"]]
        if relevant:
            lines.append(f"\n  {track['name']}")
            for task in relevant:
                lines.append(f"    • {task['text']}")

    return "\n".join(lines)


def get_week(role_key: str, week: int) -> dict:
    """
    Return a dict describing the phase that corresponds to the given week.
    Included for backwards compatibility with any code that expects a week dict.
    """
    phase_id = _WEEK_TO_PHASE.get(week, _WEEK_TO_PHASE[13])
    phase = get_phase_by_id(phase_id) or {}
    return {
        "title":      phase.get("title", f"Week {week}"),
        "phase_id":   phase_id,
        "phase":      phase.get("phase", ""),
        "weeks":      phase.get("weeks", ""),
        "description": phase.get("description", ""),
        "artifact":   phase.get("artifact", ""),
        "tasks": [
            task["text"]
            for track in phase.get("tracks", [])
            for task in track.get("tasks", [])
            if role_key in task.get("roles", [])
        ],
    }
