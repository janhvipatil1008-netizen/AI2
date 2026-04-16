"""
AI² Platform — Learning Coach Sub-Agent
A conversational AI mentor with full awareness of the learner's journey, progress,
and goals. Explains concepts, recommends research papers and resources, and guides
the learner through the curriculum with a clear eye on where they've been and
where they're going.
"""

import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

import anthropic
from context.session import SessionContext
from curriculum.syllabus import (
    get_full_track_summary,
    format_week_context,
    get_next_tasks,
    get_phase_by_id,
    _WEEK_TO_PHASE,
)
from config import AGENT_MODEL, AGENT_MAX_TOKENS

# ── Tool definition ────────────────────────────────────────────────────────────
# This is the contract between Claude and our code.
# "description" = what Claude reads to decide WHEN to call it.
# "input_schema" = what Claude must fill in (and what _fetch_arxiv_papers receives).
_PAPER_SEARCH_TOOL = {
    "name": "paper_search",
    "description": (
        "Search arXiv for research papers on a topic. "
        "Use when the learner asks for papers, citations, reading lists, "
        "or wants to go deeper on any concept."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search terms, e.g. 'retrieval augmented generation LLM'",
            },
            "max_results": {
                "type": "integer",
                "description": "Papers to return (1–5)",
                "default": 3,
            },
        },
        "required": ["query"],
    },
}

# ── Curated paper / resource database ─────────────────────────────────────────
# Keyed by phase_id. Each entry has:
#   title   – short title used for dedup (papers_seen)
#   cite    – author(s), year
#   why     – one-sentence reason this paper matters for this phase
#   topics  – list of keywords so Claude can match papers to the learner's question

PHASE_PAPERS: dict[str, list[dict]] = {
    "foundation": [
        {
            "title": "Attention Is All You Need",
            "cite": "Vaswani et al., 2017",
            "why": "The original transformer paper — understanding this makes every LLM concept click.",
            "topics": ["transformer", "attention", "architecture", "llm", "self-attention"],
        },
        {
            "title": "The Illustrated Transformer (blog)",
            "cite": "Jay Alammar, 2018",
            "why": "Best visual explanation of transformers; bridges the gap between the paper and intuition.",
            "topics": ["transformer", "attention", "visual", "beginner", "intuition"],
        },
        {
            "title": "Scaling Laws for Neural Language Models",
            "cite": "Kaplan et al. (OpenAI), 2020",
            "why": "Explains WHY bigger models work — essential context for product and eval decisions.",
            "topics": ["scaling", "model size", "compute", "training", "performance"],
        },
        {
            "title": "Language Models are Few-Shot Learners (GPT-3)",
            "cite": "Brown et al. (OpenAI), 2020",
            "why": "Introduces in-context learning and few-shot prompting as a paradigm shift.",
            "topics": ["few-shot", "in-context learning", "prompting", "gpt-3", "emergent"],
        },
        {
            "title": "Constitutional AI: Harmlessness from AI Feedback",
            "cite": "Bai et al. (Anthropic), 2022",
            "why": "Explains how Claude is trained to be helpful and safe — key for eval foundations.",
            "topics": ["rlhf", "safety", "alignment", "constitutional ai", "anthropic", "claude"],
        },
        {
            "title": "Lost in the Middle: How Language Models Use Long Contexts",
            "cite": "Liu et al., 2023",
            "why": "Reveals the U-shaped attention pattern — critical for context engineering.",
            "topics": ["context window", "long context", "attention", "retrieval", "context engineering"],
        },
    ],
    "prompts-apis": [
        {
            "title": "Chain-of-Thought Prompting Elicits Reasoning in LLMs",
            "cite": "Wei et al. (Google), 2022",
            "why": "The paper that made step-by-step reasoning a standard prompting technique.",
            "topics": ["chain of thought", "reasoning", "prompting", "cot", "few-shot"],
        },
        {
            "title": "ReAct: Synergizing Reasoning and Acting in LLMs",
            "cite": "Yao et al., 2022",
            "why": "Foundational agentic pattern — reasoning + tool use in a loop.",
            "topics": ["react", "agents", "tool use", "reasoning", "acting", "agentic"],
        },
        {
            "title": "Least-to-Most Prompting Enables Complex Reasoning",
            "cite": "Zhou et al. (Google), 2022",
            "why": "Decompose hard problems into sub-problems — powerful for context engineers.",
            "topics": ["prompting", "decomposition", "context engineering", "reasoning", "least-to-most"],
        },
        {
            "title": "Large Language Models Are Human-Level Prompt Engineers",
            "cite": "Zhou et al., 2023 (APE)",
            "why": "Automatic prompt optimisation — relevant to building scalable prompt libraries.",
            "topics": ["prompt engineering", "automation", "optimisation", "prompt library"],
        },
        {
            "title": "Toolformer: Language Models Can Teach Themselves to Use Tools",
            "cite": "Schick et al. (Meta), 2023",
            "why": "Core theory behind function calling and API-aware models.",
            "topics": ["tool use", "function calling", "api", "agents", "plugins"],
        },
        {
            "title": "The Claude Prompt Engineering Guide (Anthropic docs)",
            "cite": "Anthropic, 2024",
            "why": "Practical, battle-tested techniques directly from the team that builds Claude.",
            "topics": ["prompting", "claude", "system prompt", "xml", "context engineering"],
        },
    ],
    "agrisaathi": [
        {
            "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
            "cite": "Lewis et al. (Meta), 2020",
            "why": "The original RAG paper — the architecture underlying Agri-Saathi's knowledge layer.",
            "topics": ["rag", "retrieval", "knowledge", "grounding", "vector", "citations"],
        },
        {
            "title": "Dense Passage Retrieval for Open-Domain Question Answering",
            "cite": "Karpukhin et al. (Meta), 2020",
            "why": "How dense embeddings beat keyword search for retrieving relevant passages.",
            "topics": ["retrieval", "embeddings", "dense retrieval", "vector search", "dpr"],
        },
        {
            "title": "Improving Language Models by Retrieving from Trillions of Tokens",
            "cite": "Borgeaud et al. (DeepMind), 2022 (RETRO)",
            "why": "Shows retrieval-augmented training at scale — context for architecture choices.",
            "topics": ["rag", "retrieval", "scale", "architecture", "training"],
        },
        {
            "title": "REALM: Retrieval-Augmented Language Model Pre-Training",
            "cite": "Guu et al. (Google), 2020",
            "why": "Embeds retrieval into pre-training — useful context for understanding RAG variants.",
            "topics": ["rag", "pretraining", "retrieval", "knowledge"],
        },
        {
            "title": "Chunking Strategies for LLM Applications (Pinecone blog)",
            "cite": "Pinecone, 2023",
            "why": "Practical guide to chunking — directly applicable to the Agri-Saathi build.",
            "topics": ["chunking", "rag", "vector store", "context pipeline", "retrieval"],
        },
        {
            "title": "Gorilla: Large Language Model Connected with Massive APIs",
            "cite": "Patil et al., 2023",
            "why": "Shows how LLMs can reliably call real-world APIs — relevant to the weather tool feature.",
            "topics": ["tool use", "api", "agents", "function calling", "weather tool"],
        },
    ],
    "evals-deep": [
        {
            "title": "Holistic Evaluation of Language Models (HELM)",
            "cite": "Liang et al. (Stanford), 2022",
            "why": "The gold standard multi-dimensional eval framework — essential reading for Evals Specialists.",
            "topics": ["evaluation", "benchmark", "metrics", "holistic", "helm", "multi-dimensional"],
        },
        {
            "title": "TruthfulQA: Measuring How Models Mimic Human Falsehoods",
            "cite": "Lin et al., 2021",
            "why": "Reveals that bigger models can be MORE untruthful — challenges naive eval thinking.",
            "topics": ["hallucination", "truthfulness", "evaluation", "benchmark", "safety"],
        },
        {
            "title": "RAGAS: Automated Evaluation of RAG Pipelines",
            "cite": "Es et al., 2023",
            "why": "The eval framework you'll use for Agri-Saathi — faithfulness, relevance, groundedness.",
            "topics": ["ragas", "rag evaluation", "faithfulness", "relevance", "groundedness", "eval harness"],
        },
        {
            "title": "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena",
            "cite": "Zheng et al. (UC Berkeley), 2023",
            "why": "Validates LLM-as-a-Judge as a scalable approach; also covers judge bias.",
            "topics": ["llm judge", "evaluation", "pairwise", "bias", "mt-bench", "chatbot arena"],
        },
        {
            "title": "Can LLMs Replace Human Annotators?",
            "cite": "Gilardi et al., 2023",
            "why": "Empirical analysis of when LLM annotators beat crowdworkers — informs eval design.",
            "topics": ["human eval", "annotation", "llm judge", "crowdsourcing", "quality"],
        },
        {
            "title": "DeepEval: The Open-Source LLM Evaluation Framework (docs)",
            "cite": "Confident AI, 2024",
            "why": "Production eval tooling — directly usable to build your eval harness.",
            "topics": ["deepeval", "eval harness", "automated eval", "regression testing", "tooling"],
        },
        {
            "title": "Adversarial NLI: A New Benchmark for NLU",
            "cite": "Nie et al., 2019",
            "why": "How adversarial test design reveals model blind spots — informs red-teaming.",
            "topics": ["adversarial", "red team", "robustness", "eval", "prompt injection"],
        },
    ],
    "ai2-agent": [
        {
            "title": "Reflexion: Language Agents with Verbal Reinforcement Learning",
            "cite": "Shinn et al., 2023",
            "why": "Agents that improve by reflecting on their own failures — directly relevant to AI² architecture.",
            "topics": ["agents", "reflection", "self-improvement", "reinforcement", "multi-agent"],
        },
        {
            "title": "Voyager: An Open-Ended Embodied Agent with LLMs",
            "cite": "Wang et al. (NVIDIA), 2023",
            "why": "Shows how agents build persistent skill libraries — inspiration for the Learning Mgmt Agent.",
            "topics": ["agents", "skill library", "persistence", "continual learning", "memory"],
        },
        {
            "title": "AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation",
            "cite": "Wu et al. (Microsoft), 2023",
            "why": "The leading multi-agent conversation framework — directly applicable to AI² orchestration.",
            "topics": ["multi-agent", "orchestration", "conversation", "autogen", "agent framework"],
        },
        {
            "title": "Communicative Agents for Software Development (ChatDev)",
            "cite": "Qian et al., 2023",
            "why": "Multi-agent pipelines with role specialisation — mirrors your 5-agent architecture.",
            "topics": ["multi-agent", "role specialisation", "orchestration", "pipeline", "handoff"],
        },
        {
            "title": "MemGPT: Towards LLMs as Operating Systems",
            "cite": "Packer et al. (UC Berkeley), 2023",
            "why": "Solves long-term memory across sessions — key problem for the Learning Mgmt Agent.",
            "topics": ["memory", "context management", "long-term", "state", "persistence", "agent"],
        },
        {
            "title": "The Model Context Protocol (MCP) Specification",
            "cite": "Anthropic, 2024",
            "why": "The open standard for tool and context interoperability between agents — essential for context engineers.",
            "topics": ["mcp", "context protocol", "tool use", "interoperability", "a2a", "agent"],
        },
        {
            "title": "Large Language Model based Multi-Agent Systems: A Survey",
            "cite": "Guo et al., 2024",
            "why": "Comprehensive survey of multi-agent patterns, routing strategies, and handoff protocols.",
            "topics": ["multi-agent", "survey", "patterns", "routing", "orchestration", "handoff"],
        },
    ],
    "portfolio": [
        {
            "title": "Sparks of Artificial General Intelligence",
            "cite": "Bubeck et al. (Microsoft), 2023",
            "why": "The most-cited paper on emergent LLM capabilities — excellent for interview prep discussions.",
            "topics": ["agi", "capabilities", "emergent", "gpt-4", "reasoning", "interview"],
        },
        {
            "title": "Generative Agents: Interactive Simulacra of Human Behavior",
            "cite": "Park et al. (Stanford), 2023",
            "why": "Landmark agent architecture with memory, planning, and reflection — strong portfolio reference.",
            "topics": ["agents", "memory", "planning", "simulation", "portfolio", "architecture"],
        },
        {
            "title": "How to Build Your Machine Learning Portfolio (blog)",
            "cite": "Chip Huyen, 2023",
            "why": "Practical, no-BS advice on what hiring managers actually look for in AI portfolios.",
            "topics": ["portfolio", "career", "hiring", "projects", "showcase"],
        },
        {
            "title": "AI Product Management: What It Really Takes (a16z blog)",
            "cite": "Andreessen Horowitz, 2023",
            "why": "Industry-level expectations for AI PMs — great interview prep context.",
            "topics": ["ai pm", "product management", "career", "interview", "industry"],
        },
        {
            "title": "A Survey of Large Language Model Alignment Methods",
            "cite": "Wang et al., 2023",
            "why": "Covers RLHF, RLAIF, Constitutional AI — shows depth of understanding in interviews.",
            "topics": ["alignment", "rlhf", "safety", "constitutional ai", "interview", "depth"],
        },
    ],
}


# ── Live arXiv paper fetch ─────────────────────────────────────────────────────

def _fetch_arxiv_papers(query: str, max_results: int = 3) -> list[dict]:
    """
    Fetch papers from arXiv's free Atom API.

    HOW IT WORKS:
      1. Build the URL with urllib.parse.urlencode — safely encodes spaces/special chars
      2. urllib.request.urlopen fetches the HTTP response (timeout=8s prevents hanging)
      3. arXiv returns Atom XML — xml.etree.ElementTree parses it
      4. Each <entry> is one paper; we extract title, authors, year, abstract, URL
      5. Return a list of dicts Claude will read as tool_result

    The Atom namespace prefix "atom:" is required because arXiv uses
    xmlns="http://www.w3.org/2005/Atom" in the XML root.
    """
    base = "https://export.arxiv.org/api/query"
    params = urllib.parse.urlencode({
        "search_query": f"all:{query}",
        "max_results": max_results,
        "sortBy": "relevance",
    })
    with urllib.request.urlopen(f"{base}?{params}", timeout=8) as resp:
        xml_data = resp.read()

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(xml_data)
    papers = []
    for entry in root.findall("atom:entry", ns):
        title   = entry.find("atom:title", ns).text.strip().replace("\n", " ")
        authors = ", ".join(
            a.find("atom:name", ns).text
            for a in entry.findall("atom:author", ns)[:3]
        )
        summary = entry.find("atom:summary", ns).text.strip()[:300]
        url     = entry.find("atom:id", ns).text.strip()
        year    = entry.find("atom:published", ns).text[:4]
        papers.append({
            "title": title, "authors": authors,
            "year": year, "summary": summary, "url": url,
        })
    return papers


# ── System prompt ──────────────────────────────────────────────────────────────

_SYSTEM_PROMPT_TEMPLATE = """\
You are the Learning Coach for AI² — a personalized AI mentor guiding a learner through
a 13-week career transformation program. You have complete awareness of the learner's
journey: where they started, what they've covered, what they're working on right now,
and where they're headed.

═══════════════════════════════════════════════════════
MENTOR IDENTITY & APPROACH
═══════════════════════════════════════════════════════
You are a warm, intellectually rigorous mentor — not a generic chatbot.
Every response you give should feel like it came from someone who:
  • Knows this learner's specific track and goals
  • Has read their progress and knows exactly what they've already covered
  • Can connect any new concept to something they've seen before
  • Can see 3 steps ahead and is gently steering them toward mastery

TEACHING PHILOSOPHY
  • Start with the 30,000-foot view, then zoom into specifics
  • Use concrete, real-world analogies before abstract definitions
  • Connect every new concept to what the learner is building (Agri-Saathi, AI²)
  • Ask one clarifying question when depth or goal is ambiguous
  • Celebrate progress; normalize confusion as part of learning
  • Never just answer — help the learner build a mental model they own

COMMUNICATION STYLE
  • Warm, direct, intellectually honest
  • Use structured formatting (headers, bullets) for multi-part answers
  • Keep explanations concise unless the learner asks to go deeper
  • Flag areas of active debate in the field as such

═══════════════════════════════════════════════════════
RESEARCH PAPER & RESOURCE RECOMMENDATIONS
═══════════════════════════════════════════════════════
You have a curated library of papers and resources for each phase of the curriculum.
Use this library actively — don't just answer questions, enrich them with sources.

HOW TO RECOMMEND PAPERS
  1. Weave recommendations naturally into your teaching — not as an appendix
  2. Only recommend a paper when it genuinely deepens the concept being discussed
  3. Give a one-sentence "why this matters for you right now" specific to the learner's context
  4. Prefer papers the learner hasn't seen yet (tracked in PAPERS ALREADY SEEN below)
  5. Limit to 1-2 papers per response unless explicitly asked for a reading list
  6. Format each recommendation as:

     📄 **[Paper Title]** — Author(s), Year
     _Why now:_ One sentence connecting this paper to what the learner is building or learning.

WHEN TO RECOMMEND PAPERS
  • When explaining a concept that has a landmark paper behind it
  • When the learner asks "how does X work" at any depth
  • When they're about to build something (recommend the paper BEFORE they build)
  • When they ask for reading lists or resources
  • When they seem stuck — a well-chosen paper can unlock a mental model

═══════════════════════════════════════════════════════
FULL CURRICULUM FOR CONTEXT
(Use this to connect today's question to the arc of the learner's journey)
═══════════════════════════════════════════════════════

{full_syllabus}
"""


def _build_system_prompt(session: SessionContext) -> list[dict]:
    """
    Returns a system prompt block with prompt caching enabled.
    The full syllabus + paper library is the stable cache anchor.
    """
    full_syllabus = get_full_track_summary(session.track.value)
    static_text = _SYSTEM_PROMPT_TEMPLATE.format(full_syllabus=full_syllabus)

    return [
        {
            "type": "text",
            "text": static_text,
            # Cache the full syllabus — it never changes within a track session.
            "cache_control": {"type": "ephemeral"},
        }
    ]


def _get_papers_for_phase(phase_id: str, role_key: str) -> list[dict]:
    """Return curated papers for the learner's current phase."""
    return PHASE_PAPERS.get(phase_id, [])


def _build_learner_context(session: SessionContext, depth: str) -> str:
    """
    Build a rich, dynamic context block injected into every Learning Coach call.
    This is what makes the coach feel like it knows the learner personally.
    """
    role_key = session.track.value
    phase_id = _WEEK_TO_PHASE.get(session.current_week, "portfolio")
    phase = get_phase_by_id(phase_id)

    # Next 3 tasks to give the coach forward-awareness
    next_tasks = get_next_tasks(
        syllabus_progress=session.syllabus_progress,
        selected_roles=[role_key],
        n=3,
    )
    next_task_lines = "\n".join(
        f"  • [{t['status'].upper()}] {t['text']}" for t in next_tasks
    ) or "  (all tasks complete — you're in the home stretch!)"

    # Papers already seen — coach uses this to avoid repetition
    papers_seen_text = (
        ", ".join(sorted(session.papers_seen)) if session.papers_seen
        else "none yet"
    )

    # Goals
    goals_text = (
        "\n".join(f"  • {g}" for g in session.goals)
        if session.goals else "  (not stated — infer from track and phase)"
    )

    phase_title = phase["title"] if phase else f"Week {session.current_week}"
    phase_desc = phase["description"] if phase else ""

    return f"""
════════════════════════════════════════
LEARNER PROFILE (dynamic — use this to personalise every response)
════════════════════════════════════════
Track:          {role_key}
Current week:   {session.current_week} / 13
Current phase:  {phase_title}
Phase focus:    {phase_desc}
Explanation depth requested: {depth}

LEARNER GOALS
{goals_text}

PROGRESS SNAPSHOT
  Tasks completed: {session.tasks_done_count()}
  Exercises done this session: {session.exercises_done}
  Topics explored: {', '.join(list(session.topics_explored)[-8:]) or 'none yet'}

UPCOMING TASKS (next 3 on the learner's plate)
{next_task_lines}

PAPERS ALREADY SEEN THIS SESSION (do NOT recommend these again)
  {papers_seen_text}
════════════════════════════════════════"""


# ── Public interface ───────────────────────────────────────────────────────────

def respond(
    client:  anthropic.Anthropic,
    query:   str,
    session: SessionContext,
    depth:   str = "intermediate",
) -> str:
    """
    Learning Coach response to a learner query.

    Args:
        client:  Anthropic client
        query:   The learner's question or topic to explain
        session: Current session context (track, week, history, progress, goals)
        depth:   "introductory" | "intermediate" | "advanced"

    Returns:
        str: The mentor's teaching response (may include paper recommendations)
    """
    learner_context = _build_learner_context(session, depth)
    recent_history  = session.format_history_for_prompt(n=5)
    week_context    = format_week_context(session.track.value, session.current_week)

    user_content = (
        f"{learner_context}\n\n"
        f"CURRENT WEEK CONTENT\n{week_context}\n\n"
        f"RECENT CONVERSATION\n{recent_history}\n\n"
        f"━━━ STUDENT QUESTION (depth: {depth}) ━━━\n{query}"
    )

    # ── First API call ─────────────────────────────────────────────────────────
    # We pass tools=[_PAPER_SEARCH_TOOL] so Claude knows it CAN search arXiv.
    # If Claude decides to search, stop_reason == "tool_use" and response.content
    # contains a tool_use block with the query Claude chose.
    # If Claude answers directly, stop_reason == "end_turn" and we're done.
    messages = [{"role": "user", "content": user_content}]

    response = client.messages.create(
        model=AGENT_MODEL,
        max_tokens=AGENT_MAX_TOKENS,
        system=_build_system_prompt(session),
        tools=[_PAPER_SEARCH_TOOL],
        messages=messages,
    )

    # ── Tool use loop ──────────────────────────────────────────────────────────
    # Runs 0 or 1 times for paper_search (Claude rarely needs to search twice).
    # The loop structure handles the general case correctly regardless.
    while response.stop_reason == "tool_use":
        # Find the tool_use block Claude returned — it contains the tool name
        # and the inputs Claude chose (e.g. {"query": "RAG pipelines", "max_results": 3})
        tool_block = next(b for b in response.content if b.type == "tool_use")

        # Execute our function with the inputs Claude chose
        try:
            results = _fetch_arxiv_papers(
                query=tool_block.input["query"],
                max_results=tool_block.input.get("max_results", 3),
            )
        except Exception:
            # arXiv is down or timed out — fall back to the curated PHASE_PAPERS list
            phase_id = _WEEK_TO_PHASE.get(session.current_week, "portfolio")
            results  = _get_papers_for_phase(phase_id, session.track.value)[:3]

        # Grow the messages list:
        #   assistant turn = Claude's response including the tool_use block
        #   user turn      = our tool_result (tool results always go in a user turn)
        # tool_use_id links this result to the exact tool call Claude made.
        messages.append({"role": "assistant", "content": response.content})
        messages.append({
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_block.id,
                "content": json.dumps({"papers": results}),
            }],
        })

        # Second API call — Claude now reads the arXiv results and writes its answer
        response = client.messages.create(
            model=AGENT_MODEL,
            max_tokens=AGENT_MAX_TOKENS,
            system=_build_system_prompt(session),
            tools=[_PAPER_SEARCH_TOOL],
            messages=messages,
        )

    # stop_reason == "end_turn" — Claude has written its final answer
    reply = response.content[-1].text if response.content else ""

    # Track topics and any papers mentioned in this response
    session.note_topic(query[:60])
    _track_papers_mentioned(reply, session)

    return reply


def recommend_papers(
    client:  anthropic.Anthropic,
    topic:   str,
    session: SessionContext,
) -> str:
    """
    Dedicated paper / resource recommendation for a given topic.
    Called when the learner explicitly asks for reading lists or resources.
    """
    return respond(
        client=client,
        query=f"Give me a curated reading list for: {topic}. Include the most important papers and resources, explain why each matters for my track and current phase, and tell me what order to read them in.",
        session=session,
        depth="intermediate",
    )


# ── Internal helpers ───────────────────────────────────────────────────────────

def _track_papers_mentioned(reply: str, session: SessionContext) -> None:
    """
    Scan the coach's reply for paper titles from the library and mark them seen
    so they aren't recommended again in the same session.
    """
    reply_lower = reply.lower()
    for papers in PHASE_PAPERS.values():
        for paper in papers:
            if paper["title"].lower() in reply_lower:
                session.note_paper_seen(paper["title"])
