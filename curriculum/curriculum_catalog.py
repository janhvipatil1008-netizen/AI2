"""Market-aligned six-course curriculum catalog v2.

Pure data only. This module does not read environment variables, open database
connections, import route/service code, or mutate the legacy syllabus.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


CATALOG_VERSION = "v2"


@dataclass(frozen=True)
class CatalogActivity:
    activity_key: str
    activity_type: str
    title: str
    sequence_order: int
    is_required: bool = True


@dataclass(frozen=True)
class CatalogTopic:
    topic_key: str
    title: str
    description: str
    sequence_order: int
    activities: tuple[CatalogActivity, ...]
    metadata: dict


@dataclass(frozen=True)
class CatalogModule:
    module_key: str
    title: str
    description: str
    sequence_order: int
    topics: tuple[CatalogTopic, ...]
    metadata: dict


@dataclass(frozen=True)
class CatalogCourse:
    course_key: str
    title: str
    description: str
    target_audience: str
    level: str
    sequence_order: int
    card_label: str
    path_type: str
    modules: tuple[CatalogModule, ...]
    metadata: dict


@dataclass(frozen=True)
class CurriculumCatalogExport:
    catalog_version: str
    courses: tuple[CatalogCourse, ...]


def _activities() -> tuple[CatalogActivity, ...]:
    return (
        CatalogActivity("learn", "lesson", "Learn", 1),
        CatalogActivity("quiz", "quiz", "Quiz", 2),
        CatalogActivity("portfolio", "portfolio_task", "Portfolio Task", 3),
        CatalogActivity("interview", "interview_practice", "Interview Practice", 4),
        CatalogActivity("reflection", "reflection", "Reflection", 5, False),
    )


def _prompts(title: str, course_title: str) -> dict:
    base = f"{title} in the {course_title} course"
    return {
        "learn": f"Teach me {base} with definitions, examples, pitfalls, and a short checklist.",
        "quiz": f"Quiz me on {base} with mixed conceptual and scenario questions.",
        "portfolio": f"Give me a practical portfolio task for {base}, including deliverables and acceptance criteria.",
        "interview": f"Give me interview questions and model answer outlines for {base}.",
    }


def _topic(
    key: str,
    title: str,
    description: str,
    order: int,
    course_title: str,
    concepts: tuple[str, ...],
) -> CatalogTopic:
    return CatalogTopic(
        topic_key=key,
        title=title,
        description=description,
        sequence_order=order,
        activities=_activities(),
        metadata={
            "prompts": _prompts(title, course_title),
            "market_concepts": list(concepts),
        },
    )


COURSES: tuple[CatalogCourse, ...] = (
    CatalogCourse(
        course_key="ai-foundations",
        title="AI Foundations",
        description="Shared prerequisite for understanding modern AI systems, LLMs, retrieval, safety, and market vocabulary.",
        target_audience="All learners entering AI2",
        level="beginner",
        sequence_order=1,
        card_label="Start here",
        path_type="foundation",
        metadata={
            "is_prerequisite": True,
            "is_specialization_path": False,
            "recommended_badge": "Start here",
            "prerequisite_for": [
                "ai-engineering-building",
                "ai-evaluation-quality",
                "ai-product-strategy",
                "ai-data-analytics",
                "ai-experience-growth",
            ],
        },
        modules=(
            CatalogModule(
                module_key="foundations-01-ai-systems",
                title="Modern AI Systems",
                description="Core fluency in LLMs, agents, model behavior, and AI product constraints.",
                sequence_order=1,
                metadata={"focus": "shared-foundation"},
                topics=(
                    _topic(
                        "llms-and-agent-basics",
                        "LLMs, Agents, and AI System Basics",
                        "How large language models, agent loops, tools, memory, and orchestration fit together in current AI products.",
                        1,
                        "AI Foundations",
                        ("LLMs", "Agents", "Tools", "Memory"),
                    ),
                    _topic(
                        "prompting-rag-vector-databases",
                        "Prompting, RAG, and Vector Databases",
                        "How prompts, retrieval augmented generation, embeddings, and vector databases ground AI outputs.",
                        2,
                        "AI Foundations",
                        ("Prompting", "RAG", "Embeddings", "Vector Databases"),
                    ),
                ),
            ),
            CatalogModule(
                module_key="foundations-02-quality-market",
                title="Quality, Safety, and Market Context",
                description="The baseline vocabulary for evaluation, guardrails, AI search, and deployment decisions.",
                sequence_order=2,
                metadata={"focus": "shared-quality"},
                topics=(
                    _topic(
                        "evals-guardrails-failure-modes",
                        "Evals, Guardrails, and Failure Modes",
                        "Core evaluation patterns, hallucination risks, safety guardrails, and practical quality gates.",
                        1,
                        "AI Foundations",
                        ("Evals", "Guardrails", "Hallucinations", "Quality Gates"),
                    ),
                    _topic(
                        "geo-aeo-ai-discovery",
                        "GEO and AEO for AI Discovery",
                        "How generative engine optimization and answer engine optimization change content, product, and growth strategy.",
                        2,
                        "AI Foundations",
                        ("GEO", "AEO", "AI Search", "Discovery"),
                    ),
                ),
            ),
        ),
    ),
    CatalogCourse(
        course_key="ai-engineering-building",
        title="AI Engineering & Building",
        description="Build production AI applications with agents, MCP, RAG, tools, observability, and deployment discipline.",
        target_audience="Builders, software engineers, and technical founders",
        level="intermediate",
        sequence_order=2,
        card_label="Specialization paths",
        path_type="specialization",
        metadata={"is_prerequisite": False, "is_specialization_path": True, "requires": ["ai-foundations"]},
        modules=(
            CatalogModule(
                module_key="engineering-01-agentic-apps",
                title="Agentic Application Architecture",
                description="Design and implement agent workflows, tool calling, and multi-step AI applications.",
                sequence_order=1,
                metadata={"focus": "agent-systems"},
                topics=(
                    _topic(
                        "agent-patterns-orchestration",
                        "Agent Patterns and Orchestration",
                        "ReAct, planner-executor, reflection, routing, and multi-agent orchestration for reliable AI systems.",
                        1,
                        "AI Engineering & Building",
                        ("Agents", "Orchestration", "Tools"),
                    ),
                    _topic(
                        "mcp-tool-servers",
                        "MCP Tool Servers and Integrations",
                        "Use Model Context Protocol patterns to connect models to files, APIs, tools, and enterprise systems.",
                        2,
                        "AI Engineering & Building",
                        ("MCP", "Tool Calling", "Integrations"),
                    ),
                ),
            ),
            CatalogModule(
                module_key="engineering-02-retrieval-production",
                title="Retrieval and Production Readiness",
                description="Ship RAG-backed AI features with vector databases, observability, tests, and cost controls.",
                sequence_order=2,
                metadata={"focus": "production-rag"},
                topics=(
                    _topic(
                        "production-rag-vector-search",
                        "Production RAG and Vector Search",
                        "Chunking, embeddings, retrieval quality, vector databases, reranking, and context assembly.",
                        1,
                        "AI Engineering & Building",
                        ("RAG", "Vector Databases", "Reranking"),
                    ),
                    _topic(
                        "ai-app-observability-cost",
                        "AI App Observability and Cost Control",
                        "Trace prompts, latency, token spend, cache behavior, and model quality in production AI apps.",
                        2,
                        "AI Engineering & Building",
                        ("Observability", "Cost", "Telemetry"),
                    ),
                ),
            ),
        ),
    ),
    CatalogCourse(
        course_key="ai-evaluation-quality",
        title="AI Evaluation & Quality",
        description="Measure, test, and improve AI systems with evals, guardrails, red teaming, and release gates.",
        target_audience="AI quality engineers, evaluators, QA leads, and platform teams",
        level="intermediate",
        sequence_order=3,
        card_label="Specialization paths",
        path_type="specialization",
        metadata={"is_prerequisite": False, "is_specialization_path": True, "requires": ["ai-foundations"]},
        modules=(
            CatalogModule(
                module_key="quality-01-eval-systems",
                title="Evaluation Systems",
                description="Create eval suites that measure task success, risk, regressions, and user value.",
                sequence_order=1,
                metadata={"focus": "evals"},
                topics=(
                    _topic(
                        "evals-design-golden-sets",
                        "Evals Design and Golden Sets",
                        "Build datasets, rubrics, assertions, pass rates, and regression checks for LLM applications.",
                        1,
                        "AI Evaluation & Quality",
                        ("Evals", "Golden Sets", "Rubrics"),
                    ),
                    _topic(
                        "llm-as-judge-calibration",
                        "LLM-as-Judge Calibration",
                        "Design judge prompts, calibrate scoring, detect bias, and compare automated review with human review.",
                        2,
                        "AI Evaluation & Quality",
                        ("LLM-as-Judge", "Calibration", "Bias"),
                    ),
                ),
            ),
            CatalogModule(
                module_key="quality-02-safety-release",
                title="Safety and Release Quality",
                description="Use guardrails, adversarial testing, and monitoring to keep AI behavior within policy and product bounds.",
                sequence_order=2,
                metadata={"focus": "safety"},
                topics=(
                    _topic(
                        "guardrails-policy-tests",
                        "Guardrails and Policy Tests",
                        "Define safety policies, refusal behavior, structured validation, and automated guardrail tests.",
                        1,
                        "AI Evaluation & Quality",
                        ("Guardrails", "Policy", "Validation"),
                    ),
                    _topic(
                        "red-teaming-release-gates",
                        "Red Teaming and Release Gates",
                        "Find risky behavior before launch and define go/no-go criteria for AI releases.",
                        2,
                        "AI Evaluation & Quality",
                        ("Red Teaming", "Release Gates", "Risk"),
                    ),
                ),
            ),
        ),
    ),
    CatalogCourse(
        course_key="ai-product-strategy",
        title="AI Product & Strategy",
        description="Define AI product bets, roadmaps, metrics, pricing, trust, and platform strategy.",
        target_audience="Product managers, founders, operators, and strategy teams",
        level="intermediate",
        sequence_order=4,
        card_label="Specialization paths",
        path_type="specialization",
        metadata={"is_prerequisite": False, "is_specialization_path": True, "requires": ["ai-foundations"]},
        modules=(
            CatalogModule(
                module_key="product-01-ai-product-craft",
                title="AI Product Craft",
                description="Translate AI capability into product value, requirements, metrics, and roadmaps.",
                sequence_order=1,
                metadata={"focus": "product-craft"},
                topics=(
                    _topic(
                        "ai-prds-and-agent-roadmaps",
                        "AI PRDs and Agent Roadmaps",
                        "Write product requirements for AI features, agents, evals, risk, and iteration loops.",
                        1,
                        "AI Product & Strategy",
                        ("AI PRD", "Agents", "Roadmaps"),
                    ),
                    _topic(
                        "ai-metrics-roi-pricing",
                        "AI Metrics, ROI, and Pricing",
                        "Define success metrics beyond accuracy, including latency, cost, adoption, retention, and willingness to pay.",
                        2,
                        "AI Product & Strategy",
                        ("Metrics", "ROI", "Pricing"),
                    ),
                ),
            ),
            CatalogModule(
                module_key="product-02-platform-strategy",
                title="Platform and Market Strategy",
                description="Plan buy/build decisions, trust, distribution, and competitive positioning for AI products.",
                sequence_order=2,
                metadata={"focus": "strategy"},
                topics=(
                    _topic(
                        "build-buy-model-selection",
                        "Build, Buy, and Model Selection",
                        "Choose models, vendors, data strategy, and architecture based on product constraints.",
                        1,
                        "AI Product & Strategy",
                        ("Model Selection", "Build vs Buy", "Vendors"),
                    ),
                    _topic(
                        "trust-launch-ai-products",
                        "Trust and Launch Strategy for AI Products",
                        "Create launch plans that communicate uncertainty, safety, quality, and user trust.",
                        2,
                        "AI Product & Strategy",
                        ("Trust", "Launch", "Safety"),
                    ),
                ),
            ),
        ),
    ),
    CatalogCourse(
        course_key="ai-data-analytics",
        title="AI Data & Analytics",
        description="Use data, analytics, retrieval, and measurement systems to power and improve AI experiences.",
        target_audience="Data analysts, analytics engineers, data scientists, and growth analysts",
        level="intermediate",
        sequence_order=5,
        card_label="Specialization paths",
        path_type="specialization",
        metadata={"is_prerequisite": False, "is_specialization_path": True, "requires": ["ai-foundations"]},
        modules=(
            CatalogModule(
                module_key="data-01-ai-data-products",
                title="AI Data Products",
                description="Prepare datasets, knowledge sources, and analytical layers for AI applications.",
                sequence_order=1,
                metadata={"focus": "data-products"},
                topics=(
                    _topic(
                        "analytics-for-ai-features",
                        "Analytics for AI Features",
                        "Instrument AI usage, user journeys, quality feedback, and business outcomes.",
                        1,
                        "AI Data & Analytics",
                        ("Analytics", "Instrumentation", "Feedback"),
                    ),
                    _topic(
                        "data-pipelines-for-rag",
                        "Data Pipelines for RAG",
                        "Design ingestion, cleaning, chunking, embedding, freshness, and vector database update pipelines.",
                        2,
                        "AI Data & Analytics",
                        ("RAG", "Vector Databases", "Data Pipelines"),
                    ),
                ),
            ),
            CatalogModule(
                module_key="data-02-measurement-decisioning",
                title="Measurement and Decisioning",
                description="Turn AI telemetry into experiments, quality dashboards, and decision systems.",
                sequence_order=2,
                metadata={"focus": "measurement"},
                topics=(
                    _topic(
                        "eval-analytics-dashboards",
                        "Eval Analytics Dashboards",
                        "Build dashboards for eval scores, guardrail triggers, user feedback, cost, and drift.",
                        1,
                        "AI Data & Analytics",
                        ("Evals", "Guardrails", "Dashboards"),
                    ),
                    _topic(
                        "experimentation-for-ai-products",
                        "Experimentation for AI Products",
                        "Run A/B tests, prompt experiments, cohort analysis, and model comparisons for AI features.",
                        2,
                        "AI Data & Analytics",
                        ("Experimentation", "Prompt Tests", "Cohorts"),
                    ),
                ),
            ),
        ),
    ),
    CatalogCourse(
        course_key="ai-experience-growth",
        title="AI Experience & Growth",
        description="Design AI-native user experiences, trust loops, onboarding, content discovery, and growth systems.",
        target_audience="Designers, growth teams, marketers, founders, and customer-facing AI teams",
        level="intermediate",
        sequence_order=6,
        card_label="Specialization paths",
        path_type="specialization",
        metadata={"is_prerequisite": False, "is_specialization_path": True, "requires": ["ai-foundations"]},
        modules=(
            CatalogModule(
                module_key="growth-01-ai-experience-design",
                title="AI Experience Design",
                description="Design useful AI interactions, onboarding, trust cues, controls, and human handoff.",
                sequence_order=1,
                metadata={"focus": "experience"},
                topics=(
                    _topic(
                        "ai-ux-conversation-patterns",
                        "AI UX and Conversation Patterns",
                        "Design chat, copilots, agent handoff, memory controls, transparency, and recovery states.",
                        1,
                        "AI Experience & Growth",
                        ("AI UX", "Agents", "Trust"),
                    ),
                    _topic(
                        "onboarding-activation-ai-products",
                        "Onboarding and Activation for AI Products",
                        "Help users understand AI capabilities, limits, value moments, and repeatable workflows.",
                        2,
                        "AI Experience & Growth",
                        ("Onboarding", "Activation", "Retention"),
                    ),
                ),
            ),
            CatalogModule(
                module_key="growth-02-ai-distribution",
                title="AI Distribution and Growth",
                description="Use AI search, content systems, communities, and lifecycle messaging to grow products.",
                sequence_order=2,
                metadata={"focus": "growth"},
                topics=(
                    _topic(
                        "geo-aeo-content-systems",
                        "GEO, AEO, and AI Content Systems",
                        "Design content that performs in generative engines, answer engines, and AI-assisted search.",
                        1,
                        "AI Experience & Growth",
                        ("GEO", "AEO", "AI Search"),
                    ),
                    _topic(
                        "support-success-ai-agents",
                        "Support and Success AI Agents",
                        "Design customer-facing agents, escalation paths, knowledge bases, and quality monitoring.",
                        2,
                        "AI Experience & Growth",
                        ("Agents", "Knowledge Base", "Quality Monitoring"),
                    ),
                ),
            ),
        ),
    ),
)


def build_full_curriculum_export() -> CurriculumCatalogExport:
    """Return the full market-aligned curriculum catalog export."""
    return CurriculumCatalogExport(catalog_version=CATALOG_VERSION, courses=COURSES)


def curriculum_export_to_dict(export: CurriculumCatalogExport | None = None) -> dict:
    """Return a JSON-serializable dict for tests and future seed adapters."""
    export = export or build_full_curriculum_export()
    return asdict(export)


def summary() -> dict:
    """Return a compact count and course summary for sanity checks."""
    export = build_full_curriculum_export()
    courses = list(export.courses)
    modules = [module for course in courses for module in course.modules]
    topics = [topic for module in modules for topic in module.topics]
    return {
        "catalog_version": export.catalog_version,
        "course_count": len(courses),
        "module_count": len(modules),
        "topic_count": len(topics),
        "courses": [
            {
                "course_key": course.course_key,
                "title": course.title,
                "card_label": course.card_label,
                "path_type": course.path_type,
                "module_count": len(course.modules),
                "topic_count": sum(len(module.topics) for module in course.modules),
            }
            for course in courses
        ],
    }


__all__ = [
    "CATALOG_VERSION",
    "CatalogActivity",
    "CatalogCourse",
    "CatalogModule",
    "CatalogTopic",
    "CurriculumCatalogExport",
    "build_full_curriculum_export",
    "curriculum_export_to_dict",
    "summary",
]
