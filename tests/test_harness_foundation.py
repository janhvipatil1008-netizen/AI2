from config import CareerTrack
from context.session import SessionContext
from curriculum.topics import get_topics_for_week
from harness.context_builder import (
    HarnessContext,
    build_basic_harness_context,
    build_task_harness_context,
    summarize_text_for_context,
)
from harness.guardrails import safe_metadata, truncate_text
from harness.output_validators import is_non_empty_text, normalize_score
from harness.prompt_templates import (
    build_interview_feedback_prompt,
    build_learning_content_prompt,
    build_portfolio_feedback_prompt,
    build_practice_generation_prompt,
    build_quiz_evaluation_prompt,
)
from harness.rubrics import INTERVIEW_RUBRIC, PORTFOLIO_RUBRIC, QUIZ_RUBRIC, get_rubric
from harness.run_records import (
    HarnessRunRecord,
    create_run_record,
    create_usage_event,
    run_record_to_usage_event,
)
from harness.usage_policy import DEFAULT_DAILY_GENERATION_LIMIT, can_generate


def _session():
    return SessionContext(track=CareerTrack.AI_PM)


def _topic():
    return get_topics_for_week("aipm", 1)[0]


def test_harness_context_can_be_created():
    context = HarnessContext(
        track_label="AI Product Manager",
        topic_id="topic-1",
        topic_title="Prompting",
        topic_description="Learn prompting basics",
    )

    assert context.topic_id == "topic-1"
    assert context.progress == {}
    assert context.notes == {}


def test_build_basic_harness_context_does_not_mutate_session():
    session = _session()
    topic = _topic()
    before = session.to_dict()

    context = build_basic_harness_context(
        session=session,
        topic=topic,
        track_label="AI Product Manager",
        freshness_label="Stable",
    )

    assert session.to_dict() == before
    assert context.topic_id == topic.topic_id
    assert context.topic_title == topic.topic_title
    assert context.topic_description == topic.description
    assert context.module_title == topic.module_title
    assert context.freshness_label == "Stable"
    assert context.progress["learn"] == "not_started"
    assert context.notes["reflection"] == ""
    assert context.prior_content["content"] == ""
    assert context.usage_summary["total_events"] == 0


def test_summarize_text_for_context_short_text_unchanged():
    assert summarize_text_for_context("hello") == "hello"
    assert summarize_text_for_context("  hello  ") == "hello"
    assert summarize_text_for_context("") == ""


def test_summarize_text_for_context_truncates_long_text():
    long_text = "x" * 800
    result = summarize_text_for_context(long_text, max_chars=700)
    assert result.endswith("... [truncated]")
    assert len(result) == 700 + len("... [truncated]")


def test_summarize_text_for_context_exact_boundary():
    text = "a" * 700
    assert summarize_text_for_context(text, max_chars=700) == text
    text_plus_one = "a" * 701
    assert "... [truncated]" in summarize_text_for_context(text_plus_one, max_chars=700)


def test_build_basic_harness_context_includes_completion_percent():
    session = _session()
    topic = _topic()
    context = build_basic_harness_context(
        session=session,
        topic=topic,
        track_label="AI Product Manager",
        freshness_label="Stable",
    )
    assert isinstance(context.completion_percent, int)
    assert context.completion_percent == 0


def test_build_basic_harness_context_completion_percent_reflects_progress():
    session = _session()
    topic = _topic()
    session.mark_topic_step(topic.topic_id, "learn", "done")

    context = build_basic_harness_context(
        session=session,
        topic=topic,
        track_label="AI Product Manager",
    )
    assert context.completion_percent > 0


def test_build_basic_harness_context_includes_generated_learning_content():
    session = _session()
    topic = _topic()
    context = build_basic_harness_context(
        session=session,
        topic=topic,
        track_label="AI Product Manager",
    )
    assert isinstance(context.generated_learning_content, str)
    assert context.generated_learning_content == ""


def test_build_basic_harness_context_summarizes_saved_learning_content():
    session = _session()
    topic = _topic()
    session.save_generated_topic_content(
        topic_id=topic.topic_id,
        content="This is some generated learning content.",
        model="test-mock",
    )
    context = build_basic_harness_context(
        session=session,
        topic=topic,
        track_label="AI Product Manager",
    )
    assert "generated learning content" in context.generated_learning_content


def test_build_task_harness_context_sets_task_type():
    session = _session()
    topic = _topic()
    context = build_task_harness_context(
        session=session,
        topic=topic,
        track_label="AI Product Manager",
        task_type="quiz_generation",
    )
    assert context.task_type == "quiz_generation"


def test_build_task_harness_context_summarizes_learner_input():
    session = _session()
    topic = _topic()
    context = build_task_harness_context(
        session=session,
        topic=topic,
        track_label="AI Product Manager",
        task_type="quiz_evaluation",
        learner_input="  My quiz answers here.  ",
    )
    assert context.learner_input_summary == "My quiz answers here."


def test_build_task_harness_context_truncates_long_learner_input():
    session = _session()
    topic = _topic()
    long_input = "answer " * 200
    context = build_task_harness_context(
        session=session,
        topic=topic,
        track_label="AI Product Manager",
        task_type="quiz_evaluation",
        learner_input=long_input,
    )
    assert "... [truncated]" in context.learner_input_summary


def test_build_task_harness_context_quiz_evaluation_includes_practice_content():
    session = _session()
    topic = _topic()
    session.save_generated_topic_practice(
        topic_id=topic.topic_id,
        practice_type="quiz",
        content="Quiz content here.",
        model="test-mock",
    )
    context = build_task_harness_context(
        session=session,
        topic=topic,
        track_label="AI Product Manager",
        task_type="quiz_evaluation",
        learner_input="my answers",
    )
    assert "Quiz content here" in context.generated_practice_content


def test_build_task_harness_context_portfolio_feedback_includes_practice_content():
    session = _session()
    topic = _topic()
    session.save_generated_topic_practice(
        topic_id=topic.topic_id,
        practice_type="portfolio_task",
        content="Portfolio task content here.",
        model="test-mock",
    )
    context = build_task_harness_context(
        session=session,
        topic=topic,
        track_label="AI Product Manager",
        task_type="portfolio_feedback",
        learner_input="my submission",
    )
    assert "Portfolio task content here" in context.generated_practice_content


def test_build_task_harness_context_interview_feedback_includes_practice_content():
    session = _session()
    topic = _topic()
    session.save_generated_topic_practice(
        topic_id=topic.topic_id,
        practice_type="interview_practice",
        content="Interview practice content here.",
        model="test-mock",
    )
    context = build_task_harness_context(
        session=session,
        topic=topic,
        track_label="AI Product Manager",
        task_type="interview_feedback",
        learner_input="my interview answer",
    )
    assert "Interview practice content here" in context.generated_practice_content


def test_build_task_harness_context_generation_tasks_leave_practice_content_empty():
    session = _session()
    topic = _topic()
    for task_type in ("learning_content", "quiz_generation", "portfolio_task_generation", "interview_practice_generation"):
        context = build_task_harness_context(
            session=session,
            topic=topic,
            track_label="AI Product Manager",
            task_type=task_type,
        )
        assert context.generated_practice_content == "", f"expected empty for task_type={task_type}"


def test_build_task_harness_context_unknown_task_type_does_not_crash():
    session = _session()
    topic = _topic()
    context = build_task_harness_context(
        session=session,
        topic=topic,
        track_label="AI Product Manager",
        task_type="totally_unknown_type",
    )
    assert context.task_type == "totally_unknown_type"
    assert context.generated_practice_content == ""


def test_prompt_template_functions_return_non_empty_strings():
    context = HarnessContext(
        track_label="AI Product Manager",
        topic_id="topic-1",
        topic_title="RAG Basics",
        topic_description="Retrieval augmented generation",
    )

    prompts = [
        build_learning_content_prompt(context),
        build_practice_generation_prompt(context, "quiz"),
        build_quiz_evaluation_prompt(context, "Quiz content", "Answers"),
        build_portfolio_feedback_prompt(context, "Task", "Submission"),
        build_interview_feedback_prompt(context, "Interview", "Answer"),
    ]

    assert all(prompt.strip() for prompt in prompts)
    assert all("RAG Basics" in prompt for prompt in prompts)


def test_learning_prompt_includes_required_sections():
    context = HarnessContext(
        track_label="Context Engineer",
        topic_id="topic-1",
        topic_title="Context Windows",
        topic_description="Manage model context effectively",
    )

    prompt = build_learning_content_prompt(context)

    for heading in [
        "Title:",
        "Simple Explanation:",
        "Why This Matters:",
        "Real-World Example:",
        "Key Concepts:",
        "Common Mistakes:",
        "How To Apply This:",
        "Quick Recap:",
    ]:
        assert heading in prompt
    assert "Context Windows" in prompt
    assert "Context Engineer" in prompt
    assert "AIPM" not in prompt
    assert "AI Product Manager" not in prompt


def test_practice_generation_prompts_include_required_sections():
    context = HarnessContext(
        track_label="Context Engineer",
        topic_id="topic-1",
        topic_title="Retrieval Quality",
        topic_description="Improve retrieval quality",
    )

    quiz_prompt = build_practice_generation_prompt(context, "quiz")
    portfolio_prompt = build_practice_generation_prompt(context, "portfolio_task")
    interview_prompt = build_practice_generation_prompt(context, "interview_practice")

    for heading in ["Title:", "Instructions:", "5 Questions:", "Answer Key:", "Explanation:"]:
        assert heading in quiz_prompt
    for heading in [
        "Title:",
        "Goal:",
        "Scenario:",
        "Task Instructions:",
        "Expected Deliverable:",
        "Simple Rubric:",
        "Bonus Challenge:",
    ]:
        assert heading in portfolio_prompt
    for heading in [
        "Title:",
        "How To Practice:",
        "8 Interview Questions:",
        "What Strong Answers Should Include:",
        "Common Mistakes:",
    ]:
        assert heading in interview_prompt

    for prompt in [quiz_prompt, portfolio_prompt, interview_prompt]:
        assert "Retrieval Quality" in prompt
        assert "AIPM" not in prompt
        assert "AI Product Manager" not in prompt


def test_evaluation_and_feedback_prompts_include_score_wording():
    context = HarnessContext(
        track_label="Context Engineer",
        topic_id="topic-1",
        topic_title="Evaluation Design",
        topic_description="Design AI evals",
    )

    quiz_prompt = build_quiz_evaluation_prompt(context, "Quiz content", "Answers")
    portfolio_prompt = build_portfolio_feedback_prompt(context, "Task", "Submission")
    interview_prompt = build_interview_feedback_prompt(context, "Interview", "Answer")

    for heading in [
        "Overall Score: X/10",
        "Correct Understanding:",
        "Mistakes / Gaps:",
        "Explanation of Correct Answers:",
        "What To Revise:",
        "Next Action:",
    ]:
        assert heading in quiz_prompt
    for heading in [
        "Overall Feedback:",
        "What Is Strong:",
        "What Can Improve:",
        "Missing Details:",
        "Suggested Improved Version:",
        "Portfolio Readiness Score: X/10",
        "Next Action:",
    ]:
        assert heading in portfolio_prompt
    for heading in [
        "Overall Score: X/10",
        "Clarity:",
        "Accuracy:",
        "Depth:",
        "Interview Readiness:",
        "Improved Answer:",
        "What To Practice Next:",
    ]:
        assert heading in interview_prompt

    for prompt in [quiz_prompt, portfolio_prompt, interview_prompt]:
        assert "Evaluation Design" in prompt
        assert "AIPM" not in prompt
        assert "AI Product Manager" not in prompt


def test_rubrics_are_non_empty():
    assert QUIZ_RUBRIC.strip()
    assert PORTFOLIO_RUBRIC.strip()
    assert INTERVIEW_RUBRIC.strip()


def test_quiz_rubric_contains_expected_dimensions():
    for dimension in ["Correctness", "Reasoning", "Coverage of Key Concepts", "Clarity", "Ability to Identify Gaps"]:
        assert dimension in QUIZ_RUBRIC, f"QUIZ_RUBRIC missing: {dimension}"


def test_portfolio_rubric_contains_expected_dimensions():
    for dimension in [
        "Problem Understanding",
        "Practical Application",
        "Completeness",
        "Clarity",
        "Portfolio Readiness",
        "Improvement Potential",
    ]:
        assert dimension in PORTFOLIO_RUBRIC, f"PORTFOLIO_RUBRIC missing: {dimension}"


def test_interview_rubric_contains_expected_dimensions():
    for dimension in ["Clarity", "Accuracy", "Depth", "Structure", "Confidence", "Interview Readiness"]:
        assert dimension in INTERVIEW_RUBRIC, f"INTERVIEW_RUBRIC missing: {dimension}"


def test_get_rubric_returns_quiz_rubric():
    assert get_rubric("quiz") == QUIZ_RUBRIC


def test_get_rubric_returns_portfolio_rubric():
    assert get_rubric("portfolio") == PORTFOLIO_RUBRIC


def test_get_rubric_returns_interview_rubric():
    assert get_rubric("interview") == INTERVIEW_RUBRIC


def test_get_rubric_raises_for_invalid_type():
    import pytest
    with pytest.raises(ValueError, match="Unknown rubric_type"):
        get_rubric("unknown")
    with pytest.raises(ValueError):
        get_rubric("")
    with pytest.raises(ValueError):
        get_rubric("QUIZ")


def test_quiz_evaluation_prompt_includes_rubric():
    context = HarnessContext(
        track_label="Context Engineer",
        topic_id="topic-1",
        topic_title="Prompt Design",
        topic_description="Learn prompt design",
    )
    prompt = build_quiz_evaluation_prompt(context, "Quiz content", "Answers")
    assert "Evaluation Rubric" in prompt
    assert "Correctness" in prompt
    assert "Reasoning" in prompt


def test_portfolio_feedback_prompt_includes_rubric():
    context = HarnessContext(
        track_label="Context Engineer",
        topic_id="topic-1",
        topic_title="Portfolio Design",
        topic_description="Build portfolio tasks",
    )
    prompt = build_portfolio_feedback_prompt(context, "Task", "Submission")
    assert "Evaluation Rubric" in prompt
    assert "Problem Understanding" in prompt
    assert "Portfolio Readiness" in prompt


def test_interview_feedback_prompt_includes_rubric():
    context = HarnessContext(
        track_label="Context Engineer",
        topic_id="topic-1",
        topic_title="Interview Prep",
        topic_description="Practice interview answers",
    )
    prompt = build_interview_feedback_prompt(context, "Interview", "Answer")
    assert "Evaluation Rubric" in prompt
    assert "Depth" in prompt
    assert "Interview Readiness" in prompt


def test_evaluation_prompts_still_include_output_structure():
    context = HarnessContext(
        track_label="Context Engineer",
        topic_id="topic-1",
        topic_title="Eval Structures",
        topic_description="Check output structure preservation",
    )

    quiz_prompt = build_quiz_evaluation_prompt(context, "Quiz", "Answers")
    for heading in ["Overall Score: X/10", "Correct Understanding:", "Mistakes / Gaps:", "Next Action:"]:
        assert heading in quiz_prompt

    portfolio_prompt = build_portfolio_feedback_prompt(context, "Task", "Submission")
    for heading in ["Overall Feedback:", "Portfolio Readiness Score: X/10", "Next Action:"]:
        assert heading in portfolio_prompt

    interview_prompt = build_interview_feedback_prompt(context, "Interview", "Answer")
    for heading in ["Overall Score: X/10", "Clarity:", "Interview Readiness:", "Improved Answer:"]:
        assert heading in interview_prompt


def test_can_generate_returns_expected_booleans():
    assert can_generate({}) is True
    assert can_generate({"total_events": DEFAULT_DAILY_GENERATION_LIMIT - 1}) is True
    assert can_generate({"total_events": DEFAULT_DAILY_GENERATION_LIMIT}) is False
    assert can_generate({"total_events": 2}, limit=2) is False


def test_create_run_record_creates_required_fields():
    record = create_run_record(
        event_type="quiz_evaluation",
        topic_id="topic-1",
        model="claude-test",
        source="test_mode",
        metadata={"score": 8},
    )

    assert isinstance(record, HarnessRunRecord)
    assert record.run_id
    assert record.event_type == "quiz_evaluation"
    assert record.topic_id == "topic-1"
    assert record.model == "claude-test"
    assert record.source == "test_mode"
    assert record.status == "success"
    assert record.metadata == {"score": 8}
    assert record.created_at


def test_run_record_to_usage_event_maps_run_id_to_event_id():
    record = create_run_record(
        event_type="quiz_evaluation",
        topic_id="topic-1",
        model="claude-test",
        source="test_mode",
        metadata={"score": 8},
    )
    event = run_record_to_usage_event(record)

    assert event["event_id"] == record.run_id
    assert event["event_type"] == record.event_type
    assert event["topic_id"] == record.topic_id
    assert event["model"] == record.model
    assert event["source"] == record.source
    assert event["status"] == record.status
    assert event["metadata"] == record.metadata
    assert event["created_at"] == record.created_at


def test_create_usage_event_returns_usage_event_dict():
    event = create_usage_event(
        event_type="portfolio_feedback",
        topic_id="topic-2",
        model="claude-sonnet",
        source="claude",
        status="success",
        metadata={"score": 7},
    )

    assert event["event_id"]
    assert event["event_type"] == "portfolio_feedback"
    assert event["topic_id"] == "topic-2"
    assert event["model"] == "claude-sonnet"
    assert event["source"] == "claude"
    assert event["status"] == "success"
    assert event["metadata"] == {"score": 7}
    assert event["created_at"]


def test_create_usage_event_metadata_defaults_to_empty_dict():
    event = create_usage_event(event_type="topic_learning_content")
    assert event["metadata"] == {}


def test_create_usage_event_created_at_is_present_and_non_empty():
    event = create_usage_event(event_type="topic_learning_content")
    assert isinstance(event["created_at"], str)
    assert event["created_at"]


def test_create_usage_event_preserves_source_and_status():
    event = create_usage_event(
        event_type="quiz_evaluation",
        source="cache",
        status="error",
    )
    assert event["source"] == "cache"
    assert event["status"] == "error"


def test_create_usage_event_unique_event_ids():
    e1 = create_usage_event(event_type="x")
    e2 = create_usage_event(event_type="x")
    assert e1["event_id"] != e2["event_id"]


def test_truncate_text_truncates_long_strings():
    assert truncate_text("abcdef", max_chars=3) == "abc"
    assert truncate_text("short", max_chars=10) == "short"


def test_safe_metadata_removes_sensitive_keys():
    result = safe_metadata(
        topic_id="topic-1",
        prompt="full prompt",
        answer="full answer",
        submission="full submission",
        content="full content",
        full_text="full text",
        model="claude-test",
    )

    assert result == {"topic_id": "topic-1", "model": "claude-test"}


def test_is_non_empty_text_works():
    assert is_non_empty_text("hello") is True
    assert is_non_empty_text("  ") is False
    assert is_non_empty_text(None) is False


def test_normalize_score_works():
    assert normalize_score(0) == 0
    assert normalize_score("8") == 8
    assert normalize_score(10) == 10
    assert normalize_score(11) is None
    assert normalize_score(-1) is None
    assert normalize_score("bad") is None
