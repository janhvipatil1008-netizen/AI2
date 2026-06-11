"""Prompt templates for harness-backed AI learning workflows."""

from harness.context_builder import HarnessContext
from harness.rubrics import get_rubric


_PRACTICE_PROMPTS = {
    "quiz": (
        "Generate a 5-question multiple-choice quiz. "
        "Use exactly this format for every question — no other sections:\n\n"
        "Q1. [question text]\n"
        "A) [option]\n"
        "B) [option]\n"
        "C) [option]\n"
        "D) [option]\n"
        "ANSWER: [A, B, C, or D]\n"
        "EXPLANATION: [one sentence explaining why that answer is correct]\n\n"
        "Repeat for Q2 through Q5. Keep it beginner-friendly."
    ),
    "portfolio_task": (
        "Generate a hands-on portfolio task with exactly this format:\n\n"
        "Title:\n"
        "Goal:\n"
        "Scenario:\n"
        "Task Instructions:\n"
        "Expected Deliverable:\n"
        "Simple Rubric:\n"
        "Bonus Challenge:\n\n"
        "Keep it achievable in 1-2 hours for a beginner."
    ),
    "interview_practice": (
        "Generate 8 to 12 interview questions a learner should be able to answer "
        "on this topic. Questions only — no model answers, no tips, no sections.\n\n"
        "Use exactly this format:\n\n"
        "Q1. [question]\n\n"
        "Q2. [question]\n\n"
        "Continue through Q8–Q12.\n\n"
        "Order: first 3 conceptual (testing core understanding), then 3 scenario-based "
        "(applying to a real situation), then 2–6 behavioral or advanced. "
        "Beginner to mid-level. No answers, no headers, no commentary."
    ),
}


def build_learning_content_prompt(context: HarnessContext) -> str:
    prompt = (
        "You are an expert learning coach. Generate structured beginner-friendly learning "
        "content for the following topic.\n\n"
        f"Track: {context.track_label}\n"
    )
    if context.module_title:
        prompt += f"Module: {context.module_title}\n"
    prompt += (
        f"Topic: {context.topic_title}\n"
        f"Description: {context.topic_description}\n\n"
        "Generate content using exactly this structure:\n\n"
        "Title:\n"
        "Simple Explanation:\n"
        "Why This Matters:\n"
        "Real-World Example:\n"
        "Key Concepts:\n"
        "Common Mistakes:\n"
        "How To Apply This:\n"
        "Quick Recap:\n\n"
        "Keep it practical and beginner-friendly. Be concise but complete. "
        "Use plain text without markdown headers or bullet symbols."
    )
    return prompt


def build_practice_generation_prompt(context: HarnessContext, practice_type: str) -> str:
    prompt = (
        "You are an expert learning coach. Generate structured practice material "
        "for the following topic.\n\n"
        f"Track: {context.track_label}\n"
    )
    if context.module_title:
        prompt += f"Module: {context.module_title}\n"
    prompt += (
        f"Topic: {context.topic_title}\n"
        f"Description: {context.topic_description}\n\n"
    )
    if context.generated_learning_content:
        prompt += (
            "Learning Content (the exact explanation this learner just studied — "
            "every question, task, and scenario must test something specifically "
            "covered in this content, not general topic knowledge):\n"
            f"{context.generated_learning_content}\n\n"
        )
    prompt += (
        f"{_PRACTICE_PROMPTS[practice_type]}\n"
        "Use plain text without markdown. Be role-aware and syllabus-agnostic."
    )
    return prompt


def build_quiz_evaluation_prompt(
    context: HarnessContext,
    quiz_content: str,
    answers: str,
) -> str:
    prompt = (
        "You are an expert AI learning coach evaluating a learner's quiz answers.\n\n"
        f"Topic: {context.topic_title}\n"
        f"Track: {context.track_label}\n"
    )
    if context.generated_learning_content:
        prompt += (
            f"\nLearning Content (what this learner studied before the quiz):\n"
            f"{context.generated_learning_content}\n"
        )
    if quiz_content:
        prompt += f"\nQuiz Questions:\n{quiz_content}\n"
    prompt += (
        f"\nLearner's Answers:\n{answers}\n\n"
        f"{get_rubric('quiz')}\n\n"
        "Evaluate the answers using exactly this structure:\n\n"
        "Overall Score: X/10\n"
        "Correct Understanding:\n"
        "Mistakes / Gaps (for each: name the content section it relates to, then restate the correct idea in one sentence):\n"
        "Explanation of Correct Answers:\n"
        "What To Revise:\n"
        "Closing (1–2 sentences in your own warm voice — invite the learner to think about what they "
        "would say to explain this topic to someone else, or what question is still open for them. "
        "Speak directly to the learner; no reference to any part of the interface):\n\n"
        "Be encouraging but accurate. Use plain text without markdown."
    )
    return prompt


def build_portfolio_feedback_prompt(
    context: HarnessContext,
    task_content: str,
    submission: str,
) -> str:
    prompt = (
        "You are an expert AI learning coach reviewing a learner's portfolio task submission.\n\n"
        f"Topic: {context.topic_title}\n"
        f"Track: {context.track_label}\n"
    )
    if context.generated_learning_content:
        prompt += (
            f"\nLearning Content (what this learner studied before the task):\n"
            f"{context.generated_learning_content}\n"
        )
    if task_content:
        prompt += f"\nPortfolio Task:\n{task_content}\n"
    prompt += (
        f"\nLearner's Submission:\n{submission}\n\n"
        f"{get_rubric('portfolio')}\n\n"
        "Review the submission using exactly this structure:\n\n"
        "Overall Feedback:\n"
        "What Is Strong:\n"
        "What Can Improve (for each point: name the content section it relates to, then restate the correct approach in one sentence):\n"
        "Missing Details:\n"
        "Suggested Improved Version:\n"
        "Portfolio Readiness Score: X/10\n"
        "Closing (1–2 sentences in your own warm voice — invite the learner to reflect on what they "
        "would say this topic is really about, or what they would do differently next time. "
        "Speak directly to the learner; no reference to any part of the interface):\n\n"
        "Be encouraging but honest. Use plain text without markdown."
    )
    return prompt


def build_interview_feedback_prompt(
    context: HarnessContext,
    interview_content: str,
    answer: str,
) -> str:
    prompt = (
        "You are an expert AI learning coach reviewing a learner's interview practice answer.\n\n"
        f"Topic: {context.topic_title}\n"
        f"Track: {context.track_label}\n"
    )
    if context.generated_learning_content:
        prompt += (
            f"\nLearning Content (what this learner studied before the practice):\n"
            f"{context.generated_learning_content}\n"
        )
    if interview_content:
        prompt += f"\nInterview Practice Questions:\n{interview_content}\n"
    prompt += (
        f"\nLearner's Answer:\n{answer}\n\n"
        f"{get_rubric('interview')}\n\n"
        "Review the answer using exactly this structure:\n\n"
        "Overall Score: X/10\n"
        "Clarity:\n"
        "Accuracy (if there are gaps: name the content section and restate the correct idea in one sentence):\n"
        "Depth (if shallow: name the content section that goes deeper and restate the key insight in one sentence):\n"
        "Interview Readiness:\n"
        "Improved Answer:\n"
        "Closing (1–2 sentences in your own warm voice — invite the learner to think about what they "
        "would say if asked this question cold tomorrow, or what part of their answer they are least "
        "confident in. Speak directly to the learner; no reference to any part of the interface):\n\n"
        "Be encouraging but honest. Use plain text without markdown."
    )
    return prompt
