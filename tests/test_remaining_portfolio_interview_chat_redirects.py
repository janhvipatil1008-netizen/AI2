"""
Verifies that ALL remaining Portfolio Task and Interview Practice redirect
sources have been fixed — covering both topic_detail.html (fixed in f1fd631)
and topics.html (fixed in this pass).

Documentation-only tests — no HTTP calls, no server, no API.
"""

import os
import re

TOPIC_DETAIL_PATH = os.path.join(
    os.path.dirname(__file__), "..", "templates", "topic_detail.html"
)
TOPICS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "templates", "topics.html"
)
JS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "static", "topic_detail.js"
)


def _topic_detail() -> str:
    with open(TOPIC_DETAIL_PATH, encoding="utf-8") as f:
        return f.read()


def _topics() -> str:
    with open(TOPICS_PATH, encoding="utf-8") as f:
        return f.read()


def _js() -> str:
    with open(JS_PATH, encoding="utf-8") as f:
        return f.read()


# ── topics.html — portfolio task no longer redirects to /chat ─────────────────

def test_topics_portfolio_task_not_a_chat_link():
    """topics.html Portfolio Task link no longer points to /chat/."""
    html = _topics()
    # Extract the button row block
    row_start = html.find('<div class="topic-button-row">')
    row_end = html.find('</div>', row_start)
    row_block = html[row_start:row_end]
    # Find the Portfolio Task link within that block
    pt_match = re.search(r'href="([^"]*)"[^>]*>Portfolio Task', row_block)
    assert pt_match, "Portfolio Task link not found in topic-button-row"
    assert "/chat/" not in pt_match.group(1), (
        f"Portfolio Task still links to chat: {pt_match.group(1)}"
    )


def test_topics_portfolio_task_links_to_topic_detail():
    """topics.html Portfolio Task links to /topic/<session>/<topic>#ai-portfolio-task."""
    html = _topics()
    row_start = html.find('<div class="topic-button-row">')
    row_end = html.find('</div>', row_start)
    row_block = html[row_start:row_end]
    assert "#ai-portfolio-task" in row_block, (
        "Portfolio Task in topics.html should anchor to #ai-portfolio-task on topic detail"
    )


def test_topics_portfolio_task_no_portfolio_prompt():
    """topics.html Portfolio Task no longer uses portfolio_prompt variable (chat pattern)."""
    html = _topics()
    row_start = html.find('<div class="topic-button-row">')
    row_end = html.find('</div>', row_start)
    row_block = html[row_start:row_end]
    assert "portfolio_prompt" not in row_block, (
        "portfolio_prompt still used in topic-button-row — still using chat redirect pattern"
    )


# ── topics.html — interview practice no longer redirects to /chat ─────────────

def test_topics_interview_practice_not_a_chat_link():
    """topics.html Interview Practice link no longer points to /chat/."""
    html = _topics()
    row_start = html.find('<div class="topic-button-row">')
    row_end = html.find('</div>', row_start)
    row_block = html[row_start:row_end]
    ip_match = re.search(r'href="([^"]*)"[^>]*>Interview Practice', row_block)
    assert ip_match, "Interview Practice link not found in topic-button-row"
    assert "/chat/" not in ip_match.group(1), (
        f"Interview Practice still links to chat: {ip_match.group(1)}"
    )


def test_topics_interview_practice_links_to_topic_detail():
    """topics.html Interview Practice links to /topic/<session>/<topic>#ai-interview-practice."""
    html = _topics()
    row_start = html.find('<div class="topic-button-row">')
    row_end = html.find('</div>', row_start)
    row_block = html[row_start:row_end]
    assert "#ai-interview-practice" in row_block, (
        "Interview Practice in topics.html should anchor to #ai-interview-practice on topic detail"
    )


def test_topics_interview_practice_no_interview_prompt():
    """topics.html Interview Practice no longer uses interview_prompt variable (chat pattern)."""
    html = _topics()
    row_start = html.find('<div class="topic-button-row">')
    row_end = html.find('</div>', row_start)
    row_block = html[row_start:row_end]
    assert "interview_prompt" not in row_block, (
        "interview_prompt still used in topic-button-row — still using chat redirect pattern"
    )


# ── topics.html — Learn and Quiz still use /chat (category A — intentional) ───

def test_topics_learn_still_uses_chat():
    """topics.html Learn button still correctly links to /chat/ (chat quick action)."""
    html = _topics()
    row_start = html.find('<div class="topic-button-row">')
    row_end = html.find('</div>', row_start)
    row_block = html[row_start:row_end]
    assert re.search(r'href="/chat/[^"]*"[^>]*>Learn', row_block), (
        "Learn chat link was unexpectedly removed from topics.html"
    )


def test_topics_quiz_still_uses_chat():
    """topics.html Quiz button still correctly links to /chat/ (chat quick action)."""
    html = _topics()
    row_start = html.find('<div class="topic-button-row">')
    row_end = html.find('</div>', row_start)
    row_block = html[row_start:row_end]
    assert re.search(r'href="/chat/[^"]*"[^>]*>Quiz', row_block), (
        "Quiz chat link was unexpectedly removed from topics.html"
    )


# ── topic_detail.html — already fixed in f1fd631, confirm still correct ───────

def test_topic_detail_portfolio_task_not_a_chat_link():
    """topic_detail.html Portfolio Task journey step does not link to /chat/."""
    html = _topic_detail()
    portfolio_block = html[html.find("<h3>Portfolio Task</h3>"):html.find("<h3>Interview Practice</h3>")]
    assert "/chat/" not in portfolio_block


def test_topic_detail_portfolio_task_calls_generate_practice():
    """topic_detail.html Portfolio Task button calls generatePractice('portfolio_task', false)."""
    html = _topic_detail()
    portfolio_block = html[html.find("<h3>Portfolio Task</h3>"):html.find("<h3>Interview Practice</h3>")]
    assert "generatePractice('portfolio_task', false)" in portfolio_block


def test_topic_detail_interview_practice_not_a_chat_link():
    """topic_detail.html Interview Practice journey step does not link to /chat/."""
    html = _topic_detail()
    interview_start = html.find("<h3>Interview Practice</h3>")
    reflection_start = html.find("<h3>Reflection")
    interview_block = html[interview_start:reflection_start]
    assert "/chat/" not in interview_block


def test_topic_detail_interview_practice_calls_generate_practice():
    """topic_detail.html Interview Practice button calls generatePractice('interview_practice', false)."""
    html = _topic_detail()
    interview_start = html.find("<h3>Interview Practice</h3>")
    reflection_start = html.find("<h3>Reflection")
    interview_block = html[interview_start:reflection_start]
    assert "generatePractice('interview_practice', false)" in interview_block


# ── topic_detail.html — no data-topic-action on portfolio/interview cards ─────

def test_topic_detail_portfolio_no_data_topic_action():
    """topic_detail.html Portfolio Task journey card has no data-topic-action."""
    html = _topic_detail()
    portfolio_block = html[html.find("<h3>Portfolio Task</h3>"):html.find("<h3>Interview Practice</h3>")]
    assert "data-topic-action" not in portfolio_block


def test_topic_detail_interview_no_data_topic_action():
    """topic_detail.html Interview Practice journey card has no data-topic-action."""
    html = _topic_detail()
    interview_start = html.find("<h3>Interview Practice</h3>")
    reflection_start = html.find("<h3>Reflection")
    interview_block = html[interview_start:reflection_start]
    assert "data-topic-action" not in interview_block


# ── /chat still present for Learn/Quiz on topic_detail.html ──────────────────

def test_topic_detail_chat_links_preserved_for_learn_and_quiz():
    """topic_detail.html still has /chat/ links — Learn and Quiz steps unchanged."""
    assert "/chat/" in _topic_detail()


# ── static/topic_detail.js — no changes needed or made ───────────────────────

def test_topic_detail_js_generate_practice_exists():
    """generatePractice() still exists in topic_detail.js — no JS changes were made."""
    assert "generatePractice" in _js()


def test_topic_detail_js_data_topic_action_handler_exists():
    """[data-topic-action] handler still exists in topic_detail.js — not removed."""
    assert "data-topic-action" in _js()


# ── no portfolio_prompt / interview_prompt anywhere outside allowed pages ─────

def test_portfolio_prompt_not_in_topic_detail():
    """portfolio_prompt (chat redirect pattern) not used in topic_detail.html."""
    assert "portfolio_prompt" not in _topic_detail()


def test_interview_prompt_not_in_topic_detail():
    """interview_prompt (chat redirect pattern) not used in topic_detail.html."""
    assert "interview_prompt" not in _topic_detail()
