"""Plain-text rubrics for the AI² harness evaluation layer."""

QUIZ_RUBRIC = (
    "Evaluation Rubric — Quiz\n"
    "Correctness: Are the answers factually accurate and aligned with the topic?\n"
    "Reasoning: Does the learner demonstrate logical reasoning, not just recall?\n"
    "Coverage of Key Concepts: Does the learner address the main ideas in the topic?\n"
    "Clarity: Are answers expressed clearly and without ambiguity?\n"
    "Ability to Identify Gaps: Does the learner acknowledge uncertainty or areas for further study?\n"
    "Score: Assign an overall score from 0 to 10 based on the above dimensions."
)

PORTFOLIO_RUBRIC = (
    "Evaluation Rubric — Portfolio Task\n"
    "Problem Understanding: Does the submission show genuine understanding of the task goal?\n"
    "Practical Application: Is the work grounded in realistic, hands-on thinking?\n"
    "Completeness: Does the submission address all required components?\n"
    "Clarity: Is the work well-organized and easy to follow?\n"
    "Portfolio Readiness: Could this work be shown to an employer or included in a professional portfolio?\n"
    "Improvement Potential: Are there clear, actionable ways the learner could strengthen the work?\n"
    "Score: Assign a portfolio readiness score from 0 to 10 based on the above dimensions."
)

INTERVIEW_RUBRIC = (
    "Evaluation Rubric — Interview Practice\n"
    "Clarity: Is the answer expressed clearly and easy to follow?\n"
    "Accuracy: Is the answer factually correct and relevant to the question?\n"
    "Depth: Does the answer go beyond surface-level to show real understanding?\n"
    "Structure: Is the answer logically organized (e.g., context, action, result)?\n"
    "Confidence: Does the answer project knowledge and composure without overreaching?\n"
    "Interview Readiness: Would this answer perform well in a real interview?\n"
    "Score: Assign an overall score from 0 to 10 based on the above dimensions."
)

_RUBRIC_MAP = {
    "quiz": QUIZ_RUBRIC,
    "portfolio": PORTFOLIO_RUBRIC,
    "interview": INTERVIEW_RUBRIC,
}


def get_rubric(rubric_type: str) -> str:
    rubric = _RUBRIC_MAP.get(rubric_type)
    if rubric is None:
        valid = ", ".join(_RUBRIC_MAP)
        raise ValueError(
            f"Unknown rubric_type '{rubric_type}'. Valid options: {valid}."
        )
    return rubric
