"""
Verifies that Portfolio Task and Interview Practice actions in
templates/topic_detail.html no longer redirect to /chat and instead
call generatePractice() to stay within the structured topic flow.

Documentation-only tests — no HTTP calls, no server, no API.
"""

import os
import re

TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "templates", "topic_detail.html"
)
JS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "static", "topic_detail.js"
)


def _html() -> str:
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        return f.read()


def _js() -> str:
    with open(JS_PATH, encoding="utf-8") as f:
        return f.read()


# ── Portfolio Task — no longer redirects to /chat ─────────────────────────────

def test_portfolio_task_action_not_a_chat_link():
    """Portfolio Task journey step no longer has href pointing to /chat."""
    html = _html()
    # Find the portfolio task journey step card block
    portfolio_block = html[html.find("<h3>Portfolio Task</h3>"):html.find("<h3>Interview Practice</h3>")]
    assert "/chat/" not in portfolio_block, (
        "Portfolio Task journey step still contains a /chat/ link"
    )


def test_portfolio_task_no_data_topic_action():
    """Portfolio Task button no longer carries data-topic-action (the redirect trigger)."""
    html = _html()
    portfolio_block = html[html.find("<h3>Portfolio Task</h3>"):html.find("<h3>Interview Practice</h3>")]
    assert "data-topic-action" not in portfolio_block, (
        "Portfolio Task still has data-topic-action attribute which triggers the /chat redirect"
    )


def test_portfolio_task_no_data_chat_url():
    """Portfolio Task button no longer carries data-chat-url attribute."""
    html = _html()
    portfolio_block = html[html.find("<h3>Portfolio Task</h3>"):html.find("<h3>Interview Practice</h3>")]
    assert "data-chat-url" not in portfolio_block


def test_portfolio_task_button_calls_generate_practice():
    """Portfolio Task button calls generatePractice('portfolio_task', false)."""
    html = _html()
    portfolio_block = html[html.find("<h3>Portfolio Task</h3>"):html.find("<h3>Interview Practice</h3>")]
    assert "generatePractice('portfolio_task', false)" in portfolio_block, (
        "Portfolio Task button does not call generatePractice('portfolio_task', false)"
    )


def test_portfolio_task_is_a_button_element():
    """Portfolio Task action is a <button> element, not an <a> tag."""
    html = _html()
    portfolio_block = html[html.find("<h3>Portfolio Task</h3>"):html.find("<h3>Interview Practice</h3>")]
    # Should have a button with the generate practice call
    assert re.search(r'<button[^>]+generatePractice\(', portfolio_block), (
        "Portfolio Task action should be a <button> element calling generatePractice"
    )


# ── Interview Practice — no longer redirects to /chat ────────────────────────

def test_interview_practice_action_not_a_chat_link():
    """Interview Practice journey step no longer has href pointing to /chat."""
    html = _html()
    # Find the interview practice journey step card block
    interview_start = html.find("<h3>Interview Practice</h3>")
    reflection_start = html.find("<h3>Reflection")
    interview_block = html[interview_start:reflection_start]
    assert "/chat/" not in interview_block, (
        "Interview Practice journey step still contains a /chat/ link"
    )


def test_interview_practice_no_data_topic_action():
    """Interview Practice button no longer carries data-topic-action."""
    html = _html()
    interview_start = html.find("<h3>Interview Practice</h3>")
    reflection_start = html.find("<h3>Reflection")
    interview_block = html[interview_start:reflection_start]
    assert "data-topic-action" not in interview_block, (
        "Interview Practice still has data-topic-action attribute which triggers the /chat redirect"
    )


def test_interview_practice_no_data_chat_url():
    """Interview Practice button no longer carries data-chat-url attribute."""
    html = _html()
    interview_start = html.find("<h3>Interview Practice</h3>")
    reflection_start = html.find("<h3>Reflection")
    interview_block = html[interview_start:reflection_start]
    assert "data-chat-url" not in interview_block


def test_interview_practice_button_calls_generate_practice():
    """Interview Practice button calls generatePractice('interview_practice', false)."""
    html = _html()
    interview_start = html.find("<h3>Interview Practice</h3>")
    reflection_start = html.find("<h3>Reflection")
    interview_block = html[interview_start:reflection_start]
    assert "generatePractice('interview_practice', false)" in interview_block, (
        "Interview Practice button does not call generatePractice('interview_practice', false)"
    )


def test_interview_practice_is_a_button_element():
    """Interview Practice action is a <button> element, not an <a> tag."""
    html = _html()
    interview_start = html.find("<h3>Interview Practice</h3>")
    reflection_start = html.find("<h3>Reflection")
    interview_block = html[interview_start:reflection_start]
    assert re.search(r'<button[^>]+generatePractice\(', interview_block), (
        "Interview Practice action should be a <button> element calling generatePractice"
    )


# ── Chat quick actions elsewhere are preserved ────────────────────────────────

def test_chat_links_still_exist_for_learn_and_quiz():
    """Learn and Quiz steps still use /chat/ links — only portfolio/interview changed."""
    html = _html()
    assert "/chat/" in html, (
        "All /chat/ references were removed — Learn and Quiz steps should still use /chat/"
    )


def test_data_topic_action_still_exists_elsewhere():
    """data-topic-action still exists on other step cards (Learn, Quiz)."""
    html = _html()
    assert "data-topic-action" in html, (
        "data-topic-action was globally removed — it should still exist on Learn and Quiz steps"
    )


# ── Static JS unchanged ───────────────────────────────────────────────────────

def test_topic_detail_js_generate_practice_function_present():
    """generatePractice() function still exists in topic_detail.js — no JS changes needed."""
    assert "generatePractice" in _js()


def test_topic_detail_js_data_topic_action_handler_present():
    """The [data-topic-action] click handler still exists in JS (used by Learn/Quiz)."""
    assert "data-topic-action" in _js()


# ── Route URLs unchanged ──────────────────────────────────────────────────────

def test_portfolio_practice_generate_url_still_in_js():
    """/topic/practice/generate URL is still referenced in topic_detail.js."""
    assert "topicPracticeGenerateUrl" in _js() or "/topic/practice/generate" in _js()


def test_portfolio_submit_url_still_configured():
    """/portfolio/submit URL config still present in template."""
    assert "portfolioSubmitUrl" in _html()


def test_interview_submit_url_still_configured():
    """/interview/submit URL config still present in template."""
    assert "interviewSubmitUrl" in _html()
