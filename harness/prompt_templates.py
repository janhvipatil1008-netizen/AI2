"""Prompt templates for harness-backed AI learning workflows."""

from harness.context_builder import HarnessContext
from harness.rubrics import get_rubric


_PRACTICE_PROMPTS = {
    "quiz": (
        "Generate a structured quiz with exactly this format:\n\n"
        "Title:\n"
        "Instructions:\n"
        "5 Questions:\n"
        "Answer Key:\n"
        "Explanation:\n\n"
        "Keep it practical and beginner-friendly."
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
        "Generate interview practice material with exactly this format:\n\n"
        "Title:\n"
        "How To Practice:\n"
        "8 Interview Questions:\n"
        "What Strong Answers Should Include:\n"
        "Common Mistakes:\n\n"
        "Cover beginner to intermediate difficulty."
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
    if quiz_content:
        prompt += f"\nQuiz Questions:\n{quiz_content}\n"
    prompt += (
        f"\nLearner's Answers:\n{answers}\n\n"
        f"{get_rubric('quiz')}\n\n"
        "Evaluate the answers using exactly this structure:\n\n"
        "Overall Score: X/10\n"
        "Correct Understanding:\n"
        "Mistakes / Gaps:\n"
        "Explanation of Correct Answers:\n"
        "What To Revise:\n"
        "Next Action:\n\n"
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
    if task_content:
        prompt += f"\nPortfolio Task:\n{task_content}\n"
    prompt += (
        f"\nLearner's Submission:\n{submission}\n\n"
        f"{get_rubric('portfolio')}\n\n"
        "Review the submission using exactly this structure:\n\n"
        "Overall Feedback:\n"
        "What Is Strong:\n"
        "What Can Improve:\n"
        "Missing Details:\n"
        "Suggested Improved Version:\n"
        "Portfolio Readiness Score: X/10\n"
        "Next Action:\n\n"
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
    if interview_content:
        prompt += f"\nInterview Practice Questions:\n{interview_content}\n"
    prompt += (
        f"\nLearner's Answer:\n{answer}\n\n"
        f"{get_rubric('interview')}\n\n"
        "Review the answer using exactly this structure:\n\n"
        "Overall Score: X/10\n"
        "Clarity:\n"
        "Accuracy:\n"
        "Depth:\n"
        "Interview Readiness:\n"
        "Improved Answer:\n"
        "What To Practice Next:\n\n"
        "Be encouraging but honest. Use plain text without markdown."
    )
    return prompt
