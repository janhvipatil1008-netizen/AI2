"""
AI² — Market-Aligned Curriculum Catalog (v3, role-applied + shared-core)
=======================================================================

Drop-in replacement for `curriculum/curriculum_catalog.py`. Returns the SAME
dataclasses the app uses (`curriculum.modular_seed_export`), so it flows straight
through `scripts/seed_modular_curriculum.py`:

    from curriculum.curriculum_catalog import build_full_curriculum_export
    export = build_full_curriculum_export()   # -> ModularCurriculumSeedExport

WHAT CHANGED FROM v2 (all driven by curriculum review):
-------------------------------------------------------
1. AI FOUNDATIONS FIRST. Course 1 is the shared trunk. Specializations carry a
   *recommended* prerequisite (not a hard lock): metadata["recommended_prerequisite"]
   = "ai-foundations" and metadata["allow_direct_start"] = True.

2. SHARED CORE + BRANCH on all four multi-track courses. Each course has a
   shared-core module set (track_key="core") taken by every track, then
   role-specific modules (track_key=<role>). Tracks are listed in course
   metadata["tracks"]. This now includes AI Product & Business, which gains a
   "Product & Business Core" it previously lacked.

3. ROLE-APPLIED TOPIC TITLES. Foundation repeats in specializations are renamed
   to how that role *uses* the concept (e.g. "How LLMs actually behave" ->
   "Applying LLM behavior to product decisions"). Rule: Foundations teaches the
   concept; specialization teaches the role's application of it.

4. LEARNING OUTCOMES. Every course carries metadata["outcomes"] (3-5 measurable
   "be able to..." statements); every track carries metadata["track_outcomes"].

5. SKILL-LEVEL PREREQUISITES. Technical tracks carry
   metadata["recommended_background"] (e.g. Basic Python, Git, SQL). Lighter
   tracks state what is NOT required.

6. STANDARDIZED STAGES. Only the four canonical stages are used
   (foundation/application/integration/mastery), which map to
   Beginner/Intermediate/Advanced via STAGE_TO_DIFFICULTY. Ad-hoc labels removed.

7. FULL ACTIVITY SET PER TOPIC. Every topic emits Learn/Practice/Quiz/Portfolio/
   Interview/Reflection. Learn+Practice+Quiz are always required; Portfolio and
   Interview are required only on milestone / role-critical topics (flagged via
   the topic's `milestone` and `interview` args); Reflection is always optional.

8. STRONGER CAPSTONES. Thin capstones (Builder, QA, Growth) are specified to the
   same depth as the Aria PRD, with explicit deliverables and success criteria.

9. MARKETING CLAIMS REMOVED. Superlative and hype phrasing (claims about a role
   being the fastest growing, an SEO replacement, an industry-standard mandate,
   etc.) replaced with factual, verifiable descriptions.

10. STABLE IDENTIFIERS. Every module/topic carries course_key, track_key,
    module_key, topic_key, sequence_order.

Four Claude-ready prompts (learn/quiz/portfolio/interview) live on each topic's
metadata["prompts"], mirroring the TopicCard prompt fields. No DB/env/network.
"""

from __future__ import annotations

import re

from curriculum.modular_seed_export import (
    ModularActivitySeed,
    ModularCourseSeed,
    ModularCurriculumSeedExport,
    ModularModuleSeed,
    ModularSkillSeed,
    ModularTopicSeed,
)

# Canonical stage -> difficulty. Only these four stages may be used anywhere.
STAGE_TO_DIFFICULTY = {
    "foundation":  "beginner",
    "application": "intermediate",
    "integration": "advanced",
    "mastery":     "advanced",
}

# Canonical code-path labels surfaced in topic metadata["code_path"].
CODE_PATHS = {"no_code", "code_optional", "code_required"}


def slugify_key(value: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "-", value.lower().strip()).strip("-")
    return key or "untitled"


# ----------------------------------------------------------------------------
# Activities. Full set on every topic. Learn/Practice/Quiz always required.
# Portfolio + Interview required only when the topic opts in (milestone /
# role-critical). Reflection always optional.
# ----------------------------------------------------------------------------
def _activities(*, portfolio_required: bool, interview_required: bool) -> list[ModularActivitySeed]:
    spec = [
        ("lesson",     "lesson",             "Read & Learn",   1, True),
        ("practice",   "practice_task",      "Practice Task",  2, True),
        ("quiz",       "quiz",               "Quiz",           3, True),
        ("portfolio",  "portfolio_task",     "Portfolio Task", 4, portfolio_required),
        ("interview",  "interview_practice", "Interview Prep", 5, interview_required),
        ("reflection", "reflection",         "Reflection",     6, False),
    ]
    return [
        ModularActivitySeed(activity_key=k, activity_type=t, title=title,
                            sequence_order=seq, is_required=req)
        for k, t, title, seq, req in spec
    ]


def _prompts(title: str, summary: str, role_label: str, stage: str) -> dict:
    level_hint = {
        "foundation":  "Assume the learner is new to this. Build intuition first.",
        "application": "The learner knows the basics; focus on applying them in practice.",
        "integration": "Push the learner to combine multiple concepts in a realistic build.",
        "mastery":     "Focus on trade-offs, judgment, failure modes, and senior-level decisions.",
    }[stage]
    return {
        "learn": (
            f"You are an expert {role_label} mentor teaching \"{title}\". {summary} "
            f"{level_hint} Teach it clearly with a current, real-world example using "
            f"present-day tools and practice, then a short 'why this matters for a "
            f"{role_label} today' note. Be concrete and practical."
        ),
        "quiz": (
            f"Create a 5-question quiz on \"{title}\" for an aspiring {role_label}. "
            f"{level_hint} Reflect current industry practice. For each question give "
            f"options where useful, the correct answer, and a one-line explanation."
        ),
        "portfolio": (
            f"Design a portfolio task for \"{title}\" for a {role_label}. {level_hint} "
            f"It must produce a tangible artifact an employer would value. State the "
            f"goal, the deliverable, the tools to use, and clear success criteria."
        ),
        "interview": (
            f"Generate interview practice for \"{title}\" targeting {role_label} roles. "
            f"{level_hint} Provide 3 questions (conceptual, applied, scenario), what a "
            f"strong answer covers, and a concise model answer for each."
        ),
    }


def _topic(course_key, track_key, module_key, seq, title, summary, stage, role_label,
           code_path, skills=None, milestone=False, interview=False, shared=False,
           cross=False, refresh=False):
    """Build a ModularTopicSeed with stable IDs and full metadata.

    code_path: one of CODE_PATHS.
    milestone: topic produces a required Portfolio artifact.
    interview: topic includes required Interview Prep (role-critical).
    shared:    topic is a Meridian shared-scenario capstone deliverable.
    cross:     cross-functional topic (reads/links another role's work).
    refresh:   tool/standard-specific; flagged for scheduled refresh.
    """
    assert stage in STAGE_TO_DIFFICULTY, f"bad stage {stage!r}"
    assert code_path in CODE_PATHS, f"bad code_path {code_path!r}"
    topic_key = slugify_key(f"{module_key}-{title}")
    skill_seeds = [
        ModularSkillSeed(skill_key=k, title=t, category="ai",
                         level=STAGE_TO_DIFFICULTY[stage])
        for k, t in (skills or [])
    ]
    meta = {
        "stage": stage,
        "track": track_key,
        "code_path": code_path,
        "prompts": _prompts(title, summary, role_label, stage),
    }
    if milestone:
        meta["milestone"] = True
    if shared:
        meta["meridian_capstone"] = True
    if cross:
        meta["cross_functional"] = True
    if refresh:
        meta["refresh"] = "scheduled"
    return ModularTopicSeed(
        course_key=course_key, module_key=module_key, topic_key=topic_key,
        title=title, description=summary,
        difficulty_level=STAGE_TO_DIFFICULTY[stage], sequence_order=seq,
        skills=skill_seeds,
        activities=_activities(portfolio_required=milestone, interview_required=interview),
        metadata=meta,
    )


def _module(course_key, track_key, key, title, seq, desc, minutes=240):
    return ModularModuleSeed(
        course_key=course_key, module_key=key, title=title, description=desc,
        sequence_order=seq, estimated_minutes=minutes, status="active",
        metadata={"track": track_key},
    )


_MODULES: list[ModularModuleSeed] = []
_TOPICS: list[ModularTopicSeed] = []


def _add(module, topics):
    _MODULES.append(module)
    _TOPICS.extend(topics)


# ============================================================================
# COURSE DEFINITIONS
# ============================================================================
_COURSES = [
    ModularCourseSeed(
        course_key="ai-foundations", title="AI Foundations",
        description="The shared trunk for every AI role: how modern AI works, how to "
                    "work with it (prompting, context, RAG, agents, MCP), responsible "
                    "AI, and choosing your specialization. Start here.",
        target_audience="Everyone starting in AI, any role",
        level="beginner", status="active", sequence_order=1,
        metadata={
            "is_prerequisite": True,
            "start_here": True,
            "serves_roles": ["all"],
            "outcomes": [
                "Explain how LLMs work and where they fail, in plain language",
                "Write effective prompts and structure context to reduce hallucination",
                "Describe how RAG, agents, tool use, and MCP fit together",
                "Judge whether an AI output is good using a basic evaluation mindset",
                "Identify the main AI role families and choose a path to pursue",
            ],
        },
    ),
    ModularCourseSeed(
        course_key="ai-product-business", title="AI Product & Business",
        description="Lead AI products and drive AI adoption. A shared Product & Business "
                    "core, then branch into AI Product Manager (discovery, PRDs, launch) "
                    "or AI Business Analyst (process, requirements, ROI, change).",
        target_audience="Aspiring AI Product Managers and AI Business Analysts",
        level="beginner", status="active", sequence_order=2,
        metadata={
            "serves_roles": ["ai_product_manager", "ai_business_analyst"],
            "tracks": ["core", "product-manager", "business-analyst"],
            "recommended_prerequisite": "ai-foundations",
            "allow_direct_start": True,
            "outcomes": [
                "Assess and size an AI opportunity against business value and feasibility",
                "Define AI quality metrics and business metrics for a feature",
                "Reason about probabilistic systems, governance, and risk",
                "Produce a role-specific deliverable (PRD or transformation case) for a real scenario",
            ],
        },
    ),
    ModularCourseSeed(
        course_key="ai-engineering-building", title="AI Engineering & Building",
        description="Build and ship production AI systems. A shared systems core, then "
                    "branch into AI Engineer (production depth: MLOps, scale, reliability) "
                    "or AI Builder (ship working products fast).",
        target_audience="Aspiring AI Engineers and AI Builders",
        level="intermediate", status="active", sequence_order=3,
        metadata={
            "serves_roles": ["ai_engineer", "ai_builder"],
            "tracks": ["core", "engineer", "builder"],
            "recommended_prerequisite": "ai-foundations",
            "allow_direct_start": True,
            "outcomes": [
                "Build a retrieval-grounded AI application with tool use",
                "Decide between prompting, RAG, and fine-tuning for a given task",
                "Deploy an AI service and instrument it for reliability and cost",
                "Ship a documented, demoable AI product for a portfolio",
            ],
        },
    ),
    ModularCourseSeed(
        course_key="ai-evaluation-quality", title="AI Evaluation & Quality",
        description="The three-layer AI testing stack: offline evals on golden datasets, "
                    "runtime guardrails, and production observability. A shared evaluation "
                    "foundation, then branch into AI Evals Specialist or QA-to-AI Quality.",
        target_audience="Aspiring AI Evaluation specialists and QA testers moving into AI",
        level="intermediate", status="active", sequence_order=4,
        metadata={
            "serves_roles": ["ai_evals_specialist", "qa_to_ai_quality"],
            "tracks": ["core", "evals-specialist", "qa-transition"],
            "recommended_prerequisite": "ai-foundations",
            "allow_direct_start": True,
            "outcomes": [
                "Explain why non-determinism breaks pass/fail QA and what replaces it",
                "Build an evaluation suite with a golden dataset and an LLM-as-judge rubric",
                "Red-team an AI system for prompt injection and jailbreaks",
                "Map evaluation work to OWASP, NIST AI RMF, and EU AI Act requirements",
            ],
        },
    ),
    ModularCourseSeed(
        course_key="ai-data-analytics", title="AI Data & Analytics",
        description="The data layer for AI: RAG-ready data, vector databases and "
                    "embeddings, governance, plus analytics and experimentation on "
                    "non-deterministic systems. Shared data foundations, then branch into "
                    "AI Data Analyst or AI Data Engineer.",
        target_audience="Aspiring AI Data Analysts and AI Data Engineers",
        level="intermediate", status="active", sequence_order=5,
        metadata={
            "serves_roles": ["ai_data_analyst", "ai_data_engineer"],
            "tracks": ["core", "data-analyst", "data-engineer"],
            "recommended_prerequisite": "ai-foundations",
            "allow_direct_start": True,
            "outcomes": [
                "Prepare retrieval-ready data with quality and governance controls",
                "Work with embeddings and vector databases for AI retrieval",
                "Analyze AI behavior and connect performance to business outcomes",
                "Deliver a role-specific data artifact (analysis or pipeline) for a real scenario",
            ],
        },
    ),
    ModularCourseSeed(
        course_key="ai-experience-growth", title="AI Experience & Growth",
        description="The human-facing side of AI. A shared experience core, then branch "
                    "into AI UX/Design (agent UX, trust, multimodal), AI Marketing/Growth "
                    "(GEO/AEO, agentic campaigns), or AI Collaborator Essentials.",
        target_audience="Aspiring AI Designers, AI Marketers, and AI-adjacent team members",
        level="beginner", status="active", sequence_order=6,
        metadata={
            "serves_roles": ["ai_design_ux", "ai_marketing_growth", "ai_collaborator"],
            "tracks": ["core", "ux-design", "marketing-growth", "collaborator"],
            "recommended_prerequisite": "ai-foundations",
            "allow_direct_start": True,
            "outcomes": [
                "Design or communicate AI experiences that handle uncertainty well",
                "Distinguish generative from agentic AI and its impact on your function",
                "Produce a role-specific artifact (UX, growth strategy, or improvement proposal)",
                "Collaborate effectively with AI product, engineering, and evaluation teams",
            ],
        },
    ),
]


# Per-track metadata helper (outcomes, prerequisites, background, code path).
TRACK_META = {
    # course_key -> track_key -> dict
    "ai-product-business": {
        "core": {
            "title": "Product & Business Core",
            "recommended_prerequisite": "ai-foundations", "allow_direct_start": True,
            "code_path": "no_code",
            "track_outcomes": [
                "Assess an AI opportunity for business value and feasibility",
                "Explain probabilistic-system basics to non-technical stakeholders",
                "Define AI quality and business metrics with eval awareness",
                "Map governance, risk, stakeholders, and workflows for an AI initiative",
            ],
        },
        "product-manager": {
            "title": "AI Product Manager",
            "recommended_prerequisite": "ai-foundations", "allow_direct_start": True,
            "recommended_background": "No coding required.",
            "code_path": "no_code",
            "track_outcomes": [
                "Identify suitable AI opportunities and frame the business case",
                "Write an AI PRD with eval criteria, guardrails, and uncertainty handling",
                "Compare build, buy, and API options with a cost model",
                "Design human-in-the-loop agentic product workflows",
                "Create a launch and monitoring plan for an AI feature",
            ],
        },
        "business-analyst": {
            "title": "AI Business Analyst",
            "recommended_prerequisite": "ai-foundations", "allow_direct_start": True,
            "recommended_background": "No coding required.",
            "code_path": "no_code",
            "track_outcomes": [
                "Map a business process and score its automation potential",
                "Elicit and write requirements and acceptance criteria for probabilistic systems",
                "Perform gap analysis between current and AI-augmented workflows",
                "Build an ROI model for an AI initiative",
                "Plan change management and adoption for an AI rollout",
            ],
        },
    },
    "ai-engineering-building": {
        "core": {
            "title": "AI Systems Core",
            "recommended_prerequisite": "ai-foundations", "allow_direct_start": True,
            "recommended_background": "Basic Python, basic APIs, Git fundamentals.",
            "code_path": "code_required",
            "track_outcomes": [
                "Describe the layers of a production AI application",
                "Call LLM APIs with streaming, structured output, retries, and cost control",
                "Build a RAG pipeline from scratch and an agent with tool use",
                "Expose tools and data to an AI client via an MCP server",
            ],
        },
        "engineer": {
            "title": "AI Engineer",
            "recommended_prerequisite": "ai-foundations", "allow_direct_start": True,
            "recommended_background": "Basic Python, basic APIs, Git fundamentals. "
                                      "Module 0 covers the toolkit if you are rusty.",
            "code_path": "code_required",
            "track_outcomes": [
                "Fine-tune a model with LoRA and judge when not to",
                "Operate AI systems with Docker, CI/CD, and versioning",
                "Optimize latency and cost at production scale",
                "Deploy a reliable, secured AI service to the cloud",
            ],
        },
        "builder": {
            "title": "AI Builder",
            "recommended_prerequisite": "ai-foundations", "allow_direct_start": True,
            "recommended_background": "No advanced coding required. "
                                      "Basic API and JSON familiarity recommended.",
            "code_path": "code_optional",
            "track_outcomes": [
                "Assemble a working AI prototype with an AI framework",
                "Ground a product in a knowledge source and add a tool call",
                "Ship an AI feature end-to-end with a UI and feedback capture",
            ],
        },
    },
    "ai-evaluation-quality": {
        "core": {
            "title": "Evaluation Foundations",
            "recommended_prerequisite": "ai-foundations", "allow_direct_start": True,
            "code_path": "no_code",
            "track_outcomes": [
                "Explain why testing AI differs from deterministic QA",
                "Choose appropriate metrics and scoring methods",
                "Describe the offline / runtime / observability testing stack",
            ],
        },
        "evals-specialist": {
            "title": "AI Evals Specialist",
            "recommended_prerequisite": "ai-foundations", "allow_direct_start": True,
            "recommended_background": "Basic scripting helpful; platform routes available.",
            "code_path": "code_optional",
            "track_outcomes": [
                "Build and maintain a golden dataset",
                "Design an LLM-as-judge rubric and avoid its pitfalls",
                "Evaluate multi-step agent traces, not just final outputs",
                "Stand up a CI/CD eval harness that blocks regressions",
            ],
        },
        "qa-transition": {
            "title": "QA-to-AI Quality",
            "recommended_prerequisite": "ai-foundations", "allow_direct_start": True,
            "recommended_background": "Traditional QA experience helpful. "
                                      "No coding required to start; platform-first.",
            "code_path": "no_code",
            "track_outcomes": [
                "Translate QA instincts into AI quality practice",
                "Build a first eval suite using platform tools",
                "Run basic red-teaming (prompt injection, jailbreaks)",
            ],
        },
    },
    "ai-data-analytics": {
        "core": {
            "title": "AI Data Foundations",
            "recommended_prerequisite": "ai-foundations", "allow_direct_start": True,
            "recommended_background": "Basic SQL helpful but not mandatory.",
            "code_path": "code_optional",
            "track_outcomes": [
                "Apply data quality and governance controls for AI inputs",
                "Use embeddings and vector databases for retrieval",
                "Curate and label datasets that feed retrieval and evals",
            ],
        },
        "data-analyst": {
            "title": "AI Data Analyst",
            "recommended_prerequisite": "ai-foundations", "allow_direct_start": True,
            "recommended_background": "Basic SQL helpful but not mandatory.",
            "code_path": "code_optional",
            "track_outcomes": [
                "Instrument an AI product for prompts, traces, feedback, and cost",
                "Cluster and analyze AI failure modes at scale",
                "Run valid A/B tests on probabilistic features",
                "Connect AI performance to business impact",
            ],
        },
        "data-engineer": {
            "title": "AI Data Engineer",
            "recommended_prerequisite": "ai-foundations", "allow_direct_start": True,
            "recommended_background": "Basic Python and SQL, Git fundamentals.",
            "code_path": "code_required",
            "track_outcomes": [
                "Build ETL/ELT pipelines and modular SQL (dbt) data products",
                "Stand up vector infrastructure and retrieval at scale",
                "Engineer features and retrieval inputs for models",
                "Operate the data flywheel feeding evals and fine-tunes",
            ],
        },
    },
    "ai-experience-growth": {
        "core": {
            "title": "Human + AI Experience Core",
            "recommended_prerequisite": "ai-foundations", "allow_direct_start": True,
            "code_path": "no_code",
            "track_outcomes": [
                "Design and message for AI uncertainty",
                "Distinguish generative from agentic AI for non-engineers",
                "Use AI tools while keeping human judgment",
            ],
        },
        "ux-design": {
            "title": "AI UX / Design",
            "recommended_prerequisite": "ai-foundations", "allow_direct_start": True,
            "recommended_background": "No coding required.",
            "code_path": "no_code",
            "track_outcomes": [
                "Design agent UX with transparency and step-level control",
                "Design conversational and multimodal interactions with graceful recovery",
                "Map edge cases and build trust through transparency",
            ],
        },
        "marketing-growth": {
            "title": "AI Marketing / Growth",
            "recommended_prerequisite": "ai-foundations", "allow_direct_start": True,
            "recommended_background": "No coding required.",
            "code_path": "no_code",
            "track_outcomes": [
                "Optimize content to be cited inside AI answer engines (GEO/AEO)",
                "Run agentic campaigns and produce on-brand AI content at scale",
                "Measure citation, AI-referral conversion, and adoption loops",
            ],
        },
        "collaborator": {
            "title": "AI Collaborator Essentials",
            "recommended_prerequisite": "ai-foundations", "allow_direct_start": True,
            "recommended_background": "No coding required. An entry track, not a full pathway.",
            "code_path": "no_code",
            "track_outcomes": [
                "Apply working AI literacy to your own function",
                "Distinguish generative from agentic AI in practice",
                "Contribute meaningfully to PRDs, eval reports, and dashboards",
            ],
        },
    },
}


# Attach per-track metadata to each course so it seeds with the course.
for _course in _COURSES:
    if _course.course_key in TRACK_META:
        _course.metadata["track_meta"] = TRACK_META[_course.course_key]


# ============================================================================
# COURSE 1 — AI FOUNDATIONS  (no tracks; the shared trunk)
# ============================================================================
C, TK, RL = "ai-foundations", "core", "AI practitioner"

_add(_module(C, TK, "f-how-ai-works", "How Modern AI Works", 1,
             "Conceptual foundation: models, LLMs, and their behavior."), [
    _topic(C, TK, "f-how-ai-works", 1, "AI, ML & Deep Learning — the map",
           "How the field fits together and where LLMs sit.", "foundation", RL,
           "no_code", [("ai-fundamentals", "AI Fundamentals")]),
    _topic(C, TK, "f-how-ai-works", 2, "How models learn",
           "Training, loss, generalization — intuition over math.", "foundation", RL,
           "no_code", [("ml-intuition", "ML Intuition")]),
    _topic(C, TK, "f-how-ai-works", 3, "LLMs, transformers & attention",
           "Why LLMs behave as they do; context windows and limits.", "application", RL,
           "no_code", [("llms", "LLM Fundamentals")]),
    _topic(C, TK, "f-how-ai-works", 4, "Tokens, embeddings & inference cost",
           "Tokenization, embeddings, temperature, and the economics of inference.",
           "application", RL, "no_code",
           [("tokens", "Token Economics"), ("embeddings", "Embeddings")]),
])
_add(_module(C, TK, "f-working-with-ai", "Working With AI", 2,
             "The practical core every modern AI role needs."), [
    _topic(C, TK, "f-working-with-ai", 1, "Prompting & context engineering",
           "Clear instructions, examples, and persistent context that cut "
           "hallucination and add consistency.", "foundation", RL, "no_code",
           [("prompting", "Prompting"), ("context", "Context Engineering")],
           milestone=True),
    _topic(C, TK, "f-working-with-ai", 2, "RAG & grounding basics",
           "How retrieval grounds answers in real data; the components of a RAG system.",
           "application", RL, "no_code", [("rag", "RAG & Retrieval")]),
    _topic(C, TK, "f-working-with-ai", 3, "Agents, tool use & MCP",
           "How AI moves from answering to doing: agents, tool calling, and the Model "
           "Context Protocol used across major AI platforms.", "application", RL,
           "no_code", [("agents", "Agents & Tool Use"), ("mcp", "Model Context Protocol")],
           refresh=True),
    _topic(C, TK, "f-working-with-ai", 4, "Evaluating AI output",
           "How to judge whether an AI answer is actually good — the eval mindset.",
           "application", RL, "no_code", [("evaluation", "Evaluation Basics")]),
])
_add(_module(C, TK, "f-responsible-ai", "Responsible AI & Your Path", 3,
             "Safety, governance, lifecycle, and career direction."), [
    _topic(C, TK, "f-responsible-ai", 1, "AI safety, ethics & bias",
           "Harm, bias, privacy, and responsible-use fundamentals.", "foundation", RL,
           "no_code", [("ai-safety", "AI Safety")]),
    _topic(C, TK, "f-responsible-ai", 2, "AI governance & regulation",
           "What OWASP LLM Top 10, NIST AI RMF, and the EU AI Act mean in practice.",
           "application", RL, "no_code", [("governance", "AI Governance")]),
    _topic(C, TK, "f-responsible-ai", 3, "The AI product lifecycle",
           "From idea to shipped, monitored AI feature — and who owns each stage.",
           "application", RL, "no_code", [("lifecycle", "AI Product Lifecycle")]),
    _topic(C, TK, "f-responsible-ai", 4, "Choosing your AI career path",
           "A tour of the role families and how to pick and build toward one.",
           "foundation", RL, "no_code", [("career", "AI Career Paths")], cross=True),
])


# ============================================================================
# COURSE 2 — AI PRODUCT & BUSINESS  (shared core + PM + BA)
# ============================================================================
C = "ai-product-business"

# ---- Shared core ----
TK, RL = "core", "AI product professional"
_add(_module(C, TK, "pb-core", "Product & Business Core (shared)", 1,
             "The shared foundation for product and business-analyst tracks.", 300), [
    _topic(C, TK, "pb-core", 1, "Assessing AI opportunities",
           "Spotting where AI creates value, where it shouldn't be used, and how to "
           "frame the opportunity for a business audience.", "foundation", RL, "no_code",
           [("opportunity", "AI Opportunity Assessment")], milestone=True),
    _topic(C, TK, "pb-core", 2, "Working with probabilistic systems",
           "What it means to build on systems that are sometimes wrong, and how that "
           "changes planning, expectations, and acceptance.", "foundation", RL, "no_code",
           [("probabilistic", "Probabilistic Systems")]),
    _topic(C, TK, "pb-core", 3, "Business value & feasibility",
           "Weighing impact against effort, data readiness, and cost to judge whether an "
           "AI idea is worth pursuing.", "application", RL, "no_code",
           [("feasibility", "Value & Feasibility")]),
    _topic(C, TK, "pb-core", 4, "AI metrics & eval awareness",
           "Defining quality and business metrics, and why 'accuracy' alone rarely "
           "captures whether an AI feature is working.", "application", RL, "no_code",
           [("metrics", "AI Metrics"), ("eval-awareness", "Eval Awareness")]),
    _topic(C, TK, "pb-core", 5, "Governance & risk for AI initiatives",
           "Bias, transparency, compliance, and the risk questions every AI initiative "
           "must answer before launch.", "application", RL, "no_code",
           [("governance", "AI Governance & Risk")]),
    _topic(C, TK, "pb-core", 6, "Workflow & stakeholder mapping",
           "Mapping who is affected by an AI system and how it reshapes the workflow "
           "around them.", "application", RL, "no_code",
           [("stakeholders", "Stakeholder Mapping")], cross=True),
])

# ---- AI Product Manager track ----
TK, RL = "product-manager", "AI product manager"
_add(_module(C, TK, "pm-discovery", "Product Discovery & Strategy", 2,
             "Turning opportunities into a validated AI product direction.", 300), [
    _topic(C, TK, "pm-discovery", 1, "Applying LLM behavior to product decisions",
           "Using what you know about model capabilities and limits to set scope, "
           "expectations, and roadmap bets.", "application", RL, "no_code",
           [("llm-product", "LLM Product Judgment")]),
    _topic(C, TK, "pm-discovery", 2, "Rapid AI prototyping for product managers",
           "Using prompting and no/low-code tools to prototype and pressure-test an idea "
           "before engineering invests.", "application", RL, "code_optional",
           [("pm-prototyping", "PM Prototyping")], milestone=True),
    _topic(C, TK, "pm-discovery", 3, "Build vs buy vs API & cost modeling",
           "Comparing model and vendor options and modeling the real cost of AI "
           "ownership.", "application", RL, "no_code",
           [("build-buy", "Build vs Buy"), ("ai-cost", "AI Cost Modeling")], refresh=True),
])
_add(_module(C, TK, "pm-shipping", "Specifying & Shipping", 3,
             "PRDs engineering can build and evals teams can test.", 300), [
    _topic(C, TK, "pm-shipping", 1, "Writing AI PRDs",
           "PRDs that specify eval criteria, guardrails, uncertainty handling, and "
           "fallback UX.", "application", RL, "no_code", [("prd", "AI PRDs")],
           milestone=True, interview=True),
    _topic(C, TK, "pm-shipping", 2, "Designing agentic products",
           "Human-in-the-loop checkpoints, failure modes, trust calibration, and "
           "progressive delegation for autonomous products.", "integration", RL,
           "no_code", [("agent-product", "Agentic Product Design")], interview=True),
    _topic(C, TK, "pm-shipping", 3, "Prioritization for AI products",
           "Adapting prioritization to AI risk and cost; translating model uncertainty "
           "into business confidence.", "integration", RL, "no_code",
           [("prioritization", "AI Prioritization")]),
    _topic(C, TK, "pm-shipping", 4, "Launch, monitoring & roadmap",
           "Reading an eval report and a dashboard, planning launch and monitoring, and "
           "deciding what to do when the model drifts.", "integration", RL, "no_code",
           [("launch", "AI Launch & Monitoring")], cross=True),
])
_add(_module(C, TK, "pm-capstone", "Capstone & Career", 4,
             "The Meridian PM capstone and interview preparation.", 300), [
    _topic(C, TK, "pm-capstone", 1, "Capstone — the Aria product pack",
           "For Meridian's Aria support agent, deliver: an opportunity memo; a full PRD "
           "with eval criteria, guardrails, and fallback UX; a build-vs-buy cost model; "
           "and a launch and monitoring plan. Success criteria: an engineer could build "
           "from the PRD and an evals specialist could test against it.", "mastery", RL,
           "no_code", [("capstone-pm", "PM Capstone")], milestone=True, shared=True),
    _topic(C, TK, "pm-capstone", 2, "AI PM interview preparation",
           "Case frameworks, portfolio storytelling, and technical-credibility drills.",
           "mastery", RL, "no_code", [("pm-interview", "PM Interview Prep")],
           interview=True),
])

# ---- AI Business Analyst track ----
TK, RL = "business-analyst", "AI business analyst"
_add(_module(C, TK, "ba-requirements", "Process & Requirements", 2,
             "Finding and specifying AI work that creates value.", 300), [
    _topic(C, TK, "ba-requirements", 1, "Assessing AI feasibility as a business analyst",
           "Judging what is reliable, what is probabilistic, and what it costs — the "
           "analyst's calibrated read on an AI proposal.", "application", RL, "no_code",
           [("ba-feasibility", "AI Feasibility for BAs")]),
    _topic(C, TK, "ba-requirements", 2, "Process mapping & automation potential",
           "Mapping a current process and scoring where AI augmentation pays off.",
           "application", RL, "no_code", [("process-mapping", "Process Mapping")],
           milestone=True),
    _topic(C, TK, "ba-requirements", 3, "Requirements elicitation & gap analysis",
           "Drawing out real needs and finding the gap between current and AI-augmented "
           "workflows.", "application", RL, "no_code",
           [("elicitation", "Requirements Elicitation")]),
    _topic(C, TK, "ba-requirements", 4, "Acceptance criteria for probabilistic systems",
           "Writing acceptance criteria when output varies — the hardest and most "
           "valuable requirement-writing skill in AI.", "integration", RL, "no_code",
           [("acceptance", "AI Acceptance Criteria")], interview=True),
])
_add(_module(C, TK, "ba-impact", "ROI, Governance & Adoption", 3,
             "Getting AI deployed, used, and measured.", 300), [
    _topic(C, TK, "ba-impact", 1, "ROI & cost modeling",
           "Token economics, vendor comparison, and total cost of AI ownership for a "
           "business case.", "integration", RL, "no_code",
           [("roi", "AI ROI Modeling")], milestone=True),
    _topic(C, TK, "ba-impact", 2, "Risk & governance for BAs",
           "Policy frameworks, approval workflows, and the analyst's role in compliance.",
           "integration", RL, "no_code", [("ba-governance", "AI Governance for BAs")]),
    _topic(C, TK, "ba-impact", 3, "Change management & adoption",
           "Driving adoption, handling resistance, training plans, and AI champion "
           "networks.", "integration", RL, "no_code",
           [("change-mgmt", "Change Management")], cross=True),
])
_add(_module(C, TK, "ba-capstone", "Capstone & Career", 4,
             "The Meridian BA capstone and interview preparation.", 300), [
    _topic(C, TK, "ba-capstone", 1, "Capstone — Meridian AI transformation case",
           "For Meridian, deliver: a process analysis of the support department; an "
           "automation roadmap with Aria at the center; an ROI model that uses the data "
           "track's instrumentation figures; a governance plan; and a change-management "
           "strategy. Success criteria: leadership could decide go/no-go from it.",
           "mastery", RL, "no_code", [("capstone-ba", "BA Capstone")],
           milestone=True, shared=True, cross=True),
    _topic(C, TK, "ba-capstone", 2, "AI BA interview preparation",
           "Case frameworks for AI ops and BA roles, portfolio framing, and stakeholder "
           "simulation drills.", "mastery", RL, "no_code",
           [("ba-interview", "BA Interview Prep")], interview=True),
])


# ============================================================================
# COURSE 3 — AI ENGINEERING & BUILDING  (shared core + Engineer + Builder)
# ============================================================================
C = "ai-engineering-building"

# ---- Shared core ----
TK, RL = "core", "AI builder"
_add(_module(C, TK, "eb-core", "AI Systems Core (shared)", 1,
             "The shared build foundation for engineers and builders.", 360), [
    _topic(C, TK, "eb-core", 1, "Anatomy of a production AI app",
           "The layers of a real AI system: UI, orchestration, model, retrieval, data — "
           "and where each kind of failure lives.", "foundation", RL, "no_code",
           [("ai-systems", "AI Systems")]),
    _topic(C, TK, "eb-core", 2, "Working with LLM APIs",
           "Calls, streaming, structured output, retries, timeouts, and cost control.",
           "application", RL, "code_required", [("llm-apis", "LLM APIs")], refresh=True),
    _topic(C, TK, "eb-core", 3, "Build a RAG pipeline from scratch",
           "Chunking, embeddings, vector store, retrieval, reranking — without a "
           "framework first, so you understand what frameworks abstract.", "application",
           RL, "code_required",
           [("rag", "RAG & Retrieval"), ("vector-db", "Vector Databases")],
           milestone=True),
    _topic(C, TK, "eb-core", 4, "Agents & tool use (the ReAct loop)",
           "Give a model tools; implement plan-act-observe; debug where agents break: "
           "loops, wrong tools, hallucinated calls.", "integration", RL, "code_required",
           [("agents", "Agents & Tool Use")], interview=True),
    _topic(C, TK, "eb-core", 5, "Building MCP servers",
           "Expose tools and data to any AI client via the Model Context Protocol.",
           "integration", RL, "code_required", [("mcp", "Model Context Protocol")],
           milestone=True, refresh=True),
])

# ---- AI Engineer track ----
TK, RL = "engineer", "AI engineer"
_add(_module(C, TK, "eng-toolkit", "Builder's Toolkit (optional)", 2,
             "Skippable primer for those rusty on AI-specific tooling.", 180), [
    _topic(C, TK, "eng-toolkit", 1, "Python for AI work",
           "Environments, packages, and async basics — the minimum to be unblocked.",
           "foundation", RL, "code_required", [("python-ai", "Python for AI")]),
    _topic(C, TK, "eng-toolkit", 2, "Git, APIs & the terminal",
           "The professional toolchain you'll use every day.", "foundation", RL,
           "code_required", [("toolchain", "Dev Toolchain")]),
])
_add(_module(C, TK, "eng-buildlast", "Build to Last", 3,
             "Fine-tuning, MLOps, scale, and performance.", 360), [
    _topic(C, TK, "eng-buildlast", 1, "Fine-tuning with LoRA — and when not to",
           "Run a real fine-tune; build the judgment for fine-tune vs RAG vs prompting.",
           "integration", RL, "code_required", [("fine-tuning", "LLM Fine-Tuning")]),
    _topic(C, TK, "eng-buildlast", 2, "MLOps for AI systems",
           "Docker, Kubernetes, CI/CD, versioning, and deployment pipelines for AI.",
           "integration", RL, "code_required", [("mlops", "MLOps")], interview=True),
    _topic(C, TK, "eng-buildlast", 3, "Scaling, performance & cost",
           "Caching, batching, concurrency, KV-caching, and cost at production scale.",
           "integration", RL, "code_required", [("scaling", "Scaling AI")]),
])
_add(_module(C, TK, "eng-prod", "Production, Security & Capstone", 4,
             "Reliability, security, cloud deploy, and the Aria build.", 360), [
    _topic(C, TK, "eng-prod", 1, "Production reliability",
           "Monitoring, fallbacks, graceful degradation, and incident response.",
           "integration", RL, "code_required", [("reliability", "Production Reliability")]),
    _topic(C, TK, "eng-prod", 2, "Securing AI systems",
           "Prompt-injection defense, OWASP LLM Top 10, and data boundaries.",
           "integration", RL, "code_required", [("ai-security", "AI Security")]),
    _topic(C, TK, "eng-prod", 3, "Cloud deploy & reading a PRD as an engineer",
           "Deploy on AWS/GCP/Azure, and turn eval criteria and guardrail requirements "
           "into architecture.", "integration", RL, "code_required",
           [("cloud", "Cloud Deployment")], cross=True, refresh=True),
    _topic(C, TK, "eng-prod", 4, "Capstone — build Aria end-to-end",
           "Build Meridian's Aria: RAG over the knowledge base, order-lookup tools via "
           "MCP, deployed to cloud, instrumented, with guardrails — meeting the eval "
           "criteria from the Product track's PRD. Deliverables: running service, "
           "deployment link, architecture note, and a demo.", "mastery", RL,
           "code_required", [("capstone-eng", "Engineer Capstone")],
           milestone=True, interview=True, shared=True),
])

# ---- AI Builder track ----
TK, RL = "builder", "AI builder"
_add(_module(C, TK, "build-shipfast", "Ship Fast", 2,
             "Get working AI products in front of users quickly.", 300), [
    _topic(C, TK, "build-shipfast", 1, "Prototyping with AI frameworks",
           "LangChain/LlamaIndex and rapid-build tools to assemble a working prototype.",
           "application", RL, "code_optional", [("frameworks", "AI Frameworks")],
           refresh=True),
    _topic(C, TK, "build-shipfast", 2, "Grounding & structured output for builders",
           "Add a knowledge source and reliable structured output to a product without "
           "building infrastructure from scratch.", "application", RL, "code_optional",
           [("builder-grounding", "Builder Grounding")], milestone=True),
    _topic(C, TK, "build-shipfast", 3, "Ship an AI feature end-to-end",
           "From prompt to deployed feature with a real UI and a feedback hook.",
           "integration", RL, "code_optional", [("shipping", "Shipping AI")],
           interview=True),
])
_add(_module(C, TK, "build-capstone", "Capstone & Career", 3,
             "A complete, deployed AI workflow and interview preparation.", 300), [
    _topic(C, TK, "build-capstone", 1, "Capstone — a deployed AI workflow",
           "Build and deploy a functional AI workflow with: one grounded knowledge "
           "source; one tool call; structured output; user-feedback capture; a basic "
           "evaluation dataset; a deployment link; an architecture note; and a product "
           "demo. (You may use the Meridian scenario as your brief.) Success criteria: a "
           "stranger can use it from the link and see it respond grounded and on-task.",
           "mastery", RL, "code_optional", [("capstone-build", "Builder Capstone")],
           milestone=True, shared=True),
    _topic(C, TK, "build-capstone", 2, "AI builder interview preparation",
           "Portfolio framing and practical build interviews.", "mastery", RL,
           "no_code", [("builder-interview", "Builder Interview Prep")], interview=True),
])


# ============================================================================
# COURSE 4 — AI EVALUATION & QUALITY  (shared core + Evals + QA transition)
# ============================================================================
C = "ai-evaluation-quality"

# ---- Shared core ----
TK, RL = "core", "AI evaluation specialist"
_add(_module(C, TK, "ev-core", "Evaluation Foundations (shared)", 1,
             "Why AI testing is its own discipline.", 240), [
    _topic(C, TK, "ev-core", 1, "Why testing AI is different",
           "Non-determinism breaks pass/fail QA; the eval-driven approach instead.",
           "foundation", RL, "no_code", [("eval-foundations", "Evaluation Foundations")]),
    _topic(C, TK, "ev-core", 2, "Core metrics & scoring",
           "Faithfulness, relevance, accuracy; binary verdicts vs scored scales; code "
           "evals vs semantic evals.", "application", RL, "no_code",
           [("metrics", "Eval Metrics")], milestone=True),
    _topic(C, TK, "ev-core", 3, "The three-layer testing stack",
           "How offline evals, runtime guardrails, and production observability fit into "
           "one feedback loop.", "application", RL, "no_code",
           [("eval-stack", "Eval Stack")]),
])

# ---- AI Evals Specialist track ----
TK, RL = "evals-specialist", "AI evaluation specialist"
_add(_module(C, TK, "evs-building", "Building Evaluation Systems", 2,
             "Datasets, judges, harnesses, and trace depth.", 300), [
    _topic(C, TK, "evs-building", 1, "Golden datasets",
           "Curating and maintaining a held-out evaluation set that evolves with the "
           "product.", "application", RL, "code_optional",
           [("golden-set", "Golden Datasets")], milestone=True),
    _topic(C, TK, "evs-building", 2, "LLM-as-judge",
           "Using models to evaluate models — formats, rubrics, and pitfalls (bias, "
           "position effects, drift).", "integration", RL, "code_optional",
           [("llm-judge", "LLM-as-Judge")], interview=True),
    _topic(C, TK, "evs-building", 3, "Span, trace & session evaluation",
           "Evaluating agentic multi-step pipelines, not just final outputs.",
           "integration", RL, "code_optional", [("trace-eval", "Trace Evaluation")],
           refresh=True),
    _topic(C, TK, "evs-building", 4, "Building a CI/CD eval harness",
           "A repeatable pipeline that scores the system on every change and blocks "
           "regressions.", "integration", RL, "code_optional",
           [("eval-harness", "Eval Harness")], milestone=True, refresh=True),
])
_add(_module(C, TK, "evs-advanced", "Security, Compliance & Capstone", 3,
             "Red-teaming, guardrails, drift, standards, and the Aria report.", 300), [
    _topic(C, TK, "evs-advanced", 1, "Red-teaming & adversarial testing",
           "Finding vulnerabilities and attack vectors (prompt injection, jailbreaks) "
           "before users and attackers do.", "integration", RL, "code_optional",
           [("red-team", "Red-Teaming")], interview=True),
    _topic(C, TK, "evs-advanced", 2, "Runtime guardrails",
           "Live input/output controls that catch issues in production.", "integration",
           RL, "code_optional", [("guardrails", "Guardrails")]),
    _topic(C, TK, "evs-advanced", 3, "Production observability & drift",
           "Live quality and faithfulness monitoring, regression on drift, and alerting.",
           "mastery", RL, "code_optional", [("eval-observability", "Eval Observability")]),
    _topic(C, TK, "evs-advanced", 4, "Compliance + Capstone: the Aria evaluation report",
           "Map evaluation to OWASP LLM Top 10, NIST AI RMF, and EU AI Act, then deliver "
           "a full report on Meridian's Aria: golden-dataset results, judge scores, "
           "red-team findings with severity ratings, guardrail recommendations, and a "
           "compliance gap analysis. Success criteria: a PM could make a go/no-go call "
           "from it.", "mastery", RL, "code_optional",
           [("compliance", "AI Compliance"), ("capstone-evals", "Evals Capstone")],
           milestone=True, shared=True),
])

# ---- QA-to-AI Quality track ----
TK, RL = "qa-transition", "AI quality specialist"
_add(_module(C, TK, "qa-bridge", "From QA to AI Quality", 2,
             "Your existing instincts, updated for non-deterministic systems.", 240), [
    _topic(C, TK, "qa-bridge", 1, "Why your QA instincts help and mislead you",
           "Non-determinism breaks pass/fail testing — what carries over and what "
           "doesn't.", "foundation", RL, "no_code", [("qa-instincts", "QA Instincts")]),
    _topic(C, TK, "qa-bridge", 2, "Quality dimensions for AI",
           "Faithfulness, relevance, safety, and tone — the dimensions a tester now "
           "scores against.", "application", RL, "no_code",
           [("quality-dims", "Quality Dimensions")], milestone=True),
    _topic(C, TK, "qa-bridge", 3, "Building a first eval suite (platform-first)",
           "Curating test cases and edge cases using platform tools before any code.",
           "application", RL, "no_code", [("first-eval", "First Eval Suite")]),
])
_add(_module(C, TK, "qa-capstone", "Red-teaming & Capstone", 3,
             "Basic red-teaming and the Aria evaluation.", 240), [
    _topic(C, TK, "qa-capstone", 1, "Red-teaming basics",
           "Prompt injection and jailbreaks — the QA tester's natural next skill.",
           "application", RL, "no_code", [("qa-redteam", "Red-Teaming Basics")],
           interview=True),
    _topic(C, TK, "qa-capstone", 2, "Capstone — evaluate Aria (platform-first)",
           "Deliver a practical evaluation of Meridian's Aria using platform tools: a "
           "test-case set with edge cases; pass/score results across quality dimensions; "
           "a short red-team finding list; and a recommendations note. Success criteria: "
           "reproducible by another tester from your write-up.", "mastery", RL,
           "no_code", [("capstone-qa", "QA Capstone")], milestone=True, shared=True),
    _topic(C, TK, "qa-capstone", 3, "QA-to-AI transition interview preparation",
           "Framing your QA experience as an asset for AI quality roles.", "mastery", RL,
           "no_code", [("qa-interview", "QA Interview Prep")], interview=True),
])


# ============================================================================
# COURSE 5 — AI DATA & ANALYTICS  (shared core + Analyst + Data Engineer)
# ============================================================================
C = "ai-data-analytics"

# ---- Shared core ----
TK, RL = "core", "AI data professional"
_add(_module(C, TK, "da-core", "AI Data Foundations (shared)", 1,
             "RAG-ready data, the backbone of grounded AI.", 300), [
    _topic(C, TK, "da-core", 1, "Data quality & governance for AI",
           "Cleaning, lineage, consent, and access control — bad data in, hallucination "
           "out.", "foundation", RL, "no_code", [("data-quality", "Data Quality")]),
    _topic(C, TK, "da-core", 2, "Embeddings & vector databases",
           "pgvector, Pinecone, Weaviate; chunking and retrieval-ready structures for "
           "RAG and semantic search.", "application", RL, "code_optional",
           [("embeddings", "Embeddings"), ("vector-db", "Vector Databases")],
           milestone=True, refresh=True),
    _topic(C, TK, "da-core", 3, "Annotation, labeling & dataset curation",
           "Producing the labeled data that retrieval and evaluation depend on.",
           "application", RL, "no_code", [("annotation", "Data Annotation")]),
])

# ---- AI Data Analyst track ----
TK, RL = "data-analyst", "AI data analyst"
_add(_module(C, TK, "dan-analytics", "Analytics on AI Systems", 2,
             "Measuring how AI behaves and performs.", 300), [
    _topic(C, TK, "dan-analytics", 1, "Instrumenting AI products",
           "What to log — prompts, traces, feedback, cost — and how, to learn from real "
           "AI usage.", "application", RL, "code_optional",
           [("instrumentation", "Instrumentation")], milestone=True),
    _topic(C, TK, "dan-analytics", 2, "Behavior & failure analysis",
           "Finding patterns and failure clusters in AI output at scale.", "integration",
           RL, "code_optional", [("behavior-analysis", "Behavior Analysis")],
           interview=True),
    _topic(C, TK, "dan-analytics", 3, "Measuring AI business impact",
           "Connecting AI performance to business outcomes, not just model metrics.",
           "integration", RL, "no_code", [("impact", "Impact Measurement")]),
])
_add(_module(C, TK, "dan-capstone", "Experimentation & Capstone", 3,
             "Rigorous experiments and the Aria analysis.", 300), [
    _topic(C, TK, "dan-capstone", 1, "A/B testing AI features",
           "Valid experiment design when outputs are probabilistic.", "integration", RL,
           "code_optional", [("ab-testing", "A/B Testing")], interview=True),
    _topic(C, TK, "dan-capstone", 2, "Capstone — instrument & analyze Aria",
           "For Meridian's Aria, deliver: a logging design; a labeled evaluation dataset "
           "built from production traces; a failure-cluster analysis; and an executive "
           "impact dashboard. Success criteria: the BA track can plug your figures into "
           "an ROI model.", "mastery", RL, "code_optional",
           [("capstone-data-analyst", "Data Analyst Capstone")],
           milestone=True, shared=True, cross=True),
    _topic(C, TK, "dan-capstone", 3, "AI data analyst interview preparation",
           "Portfolio framing and analytics interview drills for AI data roles.",
           "mastery", RL, "no_code", [("dan-interview", "Data Analyst Interview Prep")],
           interview=True),
])

# ---- AI Data Engineer track ----
TK, RL = "data-engineer", "AI data engineer"
_add(_module(C, TK, "den-pipelines", "Pipelines & Infrastructure", 2,
             "Building the data layer for grounded AI.", 360), [
    _topic(C, TK, "den-pipelines", 1, "Pipelines & modeling (SQL, dbt)",
           "ETL/ELT and modular SQL that turn raw data into trusted data products.",
           "application", RL, "code_required",
           [("pipelines", "Data Pipelines"), ("dbt", "dbt & SQL")], milestone=True,
           refresh=True),
    _topic(C, TK, "den-pipelines", 2, "Feature engineering for AI",
           "Turning raw data into features and retrieval inputs models can use.",
           "application", RL, "code_required", [("feature-eng", "Feature Engineering")]),
    _topic(C, TK, "den-pipelines", 3, "Vector infrastructure at scale",
           "Operating embeddings and vector stores as production retrieval "
           "infrastructure.", "integration", RL, "code_required",
           [("vector-infra", "Vector Infrastructure")], interview=True),
])
_add(_module(C, TK, "den-capstone", "The Flywheel & Capstone", 3,
             "Feedback loops and the Aria data layer.", 360), [
    _topic(C, TK, "den-capstone", 1, "The data flywheel",
           "Feeding production insights back into datasets, evals, and fine-tunes.",
           "integration", RL, "code_required", [("flywheel", "Data Flywheel")]),
    _topic(C, TK, "den-capstone", 2, "Capstone — Aria's data layer",
           "Build the ingestion-to-retrieval pipeline behind Meridian's Aria, plus the "
           "logging schema that feeds the analyst's dashboard. Deliverables: a runnable "
           "pipeline, a schema doc, and a short reliability/cost note. Success criteria: "
           "the engineer track's Aria build could retrieve from it.", "mastery", RL,
           "code_required", [("capstone-data-eng", "Data Engineer Capstone")],
           milestone=True, shared=True, cross=True),
    _topic(C, TK, "den-capstone", 3, "AI data engineer interview preparation",
           "System design and pipeline interview drills for AI data engineering roles.",
           "mastery", RL, "no_code", [("den-interview", "Data Engineer Interview Prep")],
           interview=True),
])


# ============================================================================
# COURSE 6 — AI EXPERIENCE & GROWTH  (shared core + UX + Growth + Collaborator)
# ============================================================================
C = "ai-experience-growth"

# ---- Shared core ----
TK, RL = "core", "AI experience specialist"
_add(_module(C, TK, "xg-core", "Human + AI Experience Core (shared)", 1,
             "Foundations for design, growth, and collaborator tracks.", 240), [
    _topic(C, TK, "xg-core", 1, "Designing for AI uncertainty",
           "UX and messaging patterns for systems that are sometimes wrong.",
           "foundation", RL, "no_code", [("ai-ux", "AI UX")], milestone=True),
    _topic(C, TK, "xg-core", 2, "Generative vs agentic AI for non-engineers",
           "The practical difference between AI that suggests and AI that acts — and why "
           "it changes what you build.", "foundation", RL, "no_code",
           [("agentic-literacy", "Agentic Literacy")]),
    _topic(C, TK, "xg-core", 3, "AI-assisted workflows & tools",
           "Using AI tools to work faster while keeping human judgment.", "application",
           RL, "no_code", [("ai-tools", "AI Tooling")], refresh=True),
])

# ---- AI UX / Design track ----
TK, RL = "ux-design", "AI UX designer"
_add(_module(C, TK, "ux-agent", "Agent UX", 2,
             "Designing trustworthy human-facing AI.", 300), [
    _topic(C, TK, "ux-agent", 1, "Agent UX: transparency & control",
           "Status communication, override controls at every step, confidence "
           "signaling, and progressive delegation.", "application", RL, "no_code",
           [("agent-ux", "Agent UX")], milestone=True),
    _topic(C, TK, "ux-agent", 2, "Conversational & multimodal interfaces",
           "Designing chat, voice, and multimodal AI interactions with graceful "
           "recovery.", "integration", RL, "no_code", [("conv-ux", "Conversational UX")],
           interview=True),
])
_add(_module(C, TK, "ux-capstone", "Trust & Capstone", 3,
             "Edge-case mapping and the Aria UX.", 300), [
    _topic(C, TK, "ux-capstone", 1, "Capstone — Aria's experience design",
           "Design the UX for Meridian's Aria: an agentic product flow with full "
           "control and recovery patterns, plus an edge-case map. Deliverables: key "
           "screens/flows, a trust-and-transparency rationale, and an error/recovery "
           "spec. Success criteria: a PM could write a UX section of a PRD from it.",
           "mastery", RL, "no_code", [("capstone-ux", "UX Capstone")],
           milestone=True, shared=True),
    _topic(C, TK, "ux-capstone", 2, "AI UX designer interview preparation",
           "Portfolio framing and design interview drills for AI UX roles.", "mastery",
           RL, "no_code", [("ux-interview", "UX Interview Prep")], interview=True),
])

# ---- AI Marketing / Growth track ----
TK, RL = "marketing-growth", "AI growth marketer"
_add(_module(C, TK, "gr-geo", "GEO & AI Marketing", 2,
             "Winning visibility in AI-driven search.", 300), [
    _topic(C, TK, "gr-geo", 1, "GEO & AEO: getting cited by AI",
           "Generative/Answer Engine Optimization — being cited inside AI answer engines "
           "such as ChatGPT, Perplexity, and Google AI Overviews.", "application", RL,
           "no_code", [("geo", "Generative Engine Optimization")], milestone=True,
           refresh=True),
    _topic(C, TK, "gr-geo", 2, "Agentic campaigns & AI content at scale",
           "Autonomous agents that plan and optimize campaigns; AI content with brand "
           "voice and authority signals.", "integration", RL, "no_code",
           [("agentic-marketing", "Agentic Marketing")], interview=True),
])
_add(_module(C, TK, "gr-capstone", "Measurement & Capstone", 3,
             "AI-era growth metrics and the strategy capstone.", 300), [
    _topic(C, TK, "gr-capstone", 1, "Measuring AI-era growth",
           "New metrics for citation, AI-referral conversion, and adoption loops.",
           "integration", RL, "no_code", [("ai-growth", "AI Growth Measurement")]),
    _topic(C, TK, "gr-capstone", 2, "Capstone — GEO + growth strategy",
           "Deliver a GEO and growth strategy for Meridian (or a real product): a "
           "citation-and-visibility audit; a content/authority plan; an agentic-campaign "
           "outline; and a measurement plan with citation and AI-referral metrics. "
           "Success criteria: an operator could execute the first 30 days from it.",
           "mastery", RL, "no_code", [("capstone-growth", "Growth Capstone")],
           milestone=True, shared=True),
    _topic(C, TK, "gr-capstone", 3, "AI growth marketer interview preparation",
           "Portfolio framing and growth interview drills for AI-era marketing roles.",
           "mastery", RL, "no_code", [("gr-interview", "Growth Interview Prep")],
           interview=True),
])

# ---- AI Collaborator Essentials (folded into course core) ----
TK, RL = "core", "AI experience specialist"
_add(_module(C, TK, "co-essentials", "AI Collaborator Essentials", 2,
             "For everyone else on an AI product team. An entry track.", 240), [
    _topic(C, TK, "co-essentials", 1, "Working with AI teams",
           "The artifacts — PRD, eval report, dashboard — and how to have a real voice "
           "in them, not just sign off.", "application", RL, "no_code",
           [("ai-collab", "AI Collaboration")], cross=True),
    _topic(C, TK, "co-essentials", 2, "AI in your function",
           "Applying AI to operations, support, or leadership work at your role's depth.",
           "application", RL, "no_code", [("ai-in-function", "AI in Your Function")],
           refresh=True),
    _topic(C, TK, "co-essentials", 3, "Capstone — AI improvement proposal",
           "A one-page proposal to improve AI in your own function, grounded in the "
           "Meridian scenario: the opportunity, the business case, the risks, and the "
           "cross-team asks. Success criteria: a manager could act on it.", "integration",
           RL, "no_code", [("capstone-collab", "Collaborator Capstone")],
           milestone=True, shared=True),
])


# ============================================================================
# EXPORT
# ============================================================================
def build_full_curriculum_export() -> ModularCurriculumSeedExport:
    """Complete role-applied, shared-core curriculum. Drop-in for
    scripts/seed_modular_curriculum.py."""
    return ModularCurriculumSeedExport(
        courses=list(_COURSES), modules=list(_MODULES), topics=list(_TOPICS),
    )


def summary() -> dict:
    by_course: dict[str, int] = {}
    tracks_by_course: dict[str, set] = {}
    for t in _TOPICS:
        by_course[t.course_key] = by_course.get(t.course_key, 0) + 1
        tracks_by_course.setdefault(t.course_key, set()).add(t.metadata.get("track"))
    return {
        "courses": len(_COURSES),
        "modules": len(_MODULES),
        "topics": len(_TOPICS),
        "topics_per_course": by_course,
        "tracks_per_course": {k: sorted(v) for k, v in tracks_by_course.items()},
    }


if __name__ == "__main__":
    import json
    print(json.dumps(summary(), indent=2))
