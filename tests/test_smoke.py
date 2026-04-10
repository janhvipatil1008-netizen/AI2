"""
Phase 2.1 — Smoke Tests
"Does the app load and respond?"

Covers:
  - /health endpoint
  - Landing page renders with track cards
  - All three track card values present
  - Static assets accessible
  - TEST_MODE badge visible
"""


def test_health_endpoint(api):
    """GET /health returns 200 with status:ok and confirms test_mode is on."""
    r = api.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["test_mode"] is True


def test_landing_page_loads(page):
    """The landing page returns 200 and the <title> mentions AI²."""
    page.goto("/")
    assert page.title() in ("AI² — Choose Your Track", "AI²")


def test_landing_hero_text_present(page):
    """Landing page contains the hero headline."""
    page.goto("/")
    hero = page.locator("h1").first
    assert hero.is_visible()
    text = hero.inner_text()
    assert "AI" in text or "Career" in text


def test_all_three_track_cards_present(page):
    """Three career track cards (aipm, evals, context) are all rendered."""
    page.goto("/")
    cards = page.locator(".track-card")
    assert cards.count() == 3

    values = [cards.nth(i).get_attribute("data-value") for i in range(3)]
    assert "aipm"    in values
    assert "evals"   in values
    assert "context" in values


def test_track_card_names_visible(page):
    """Each card shows its human-readable label."""
    page.goto("/")
    page_text = page.locator("body").inner_text()
    assert "AI Product Manager"  in page_text
    assert "AI Evals Specialist" in page_text
    assert "Context Engineer"    in page_text


def test_test_mode_badge_visible(page):
    """The TEST MODE badge appears in the header when AI2_TEST_MODE=1."""
    page.goto("/")
    badge = page.locator(".test-badge")
    assert badge.count() > 0
    assert "TEST" in badge.first.inner_text()


def test_static_css_accessible(api):
    """The stylesheet at /static/style.css returns 200."""
    r = api.get("/static/style.css")
    assert r.status_code == 200
    assert "background" in r.text   # sanity: it's actual CSS


def test_static_js_accessible(api):
    """The JS file at /static/app.js returns 200."""
    r = api.get("/static/app.js")
    assert r.status_code == 200


def test_invalid_route_returns_404(api):
    """A nonexistent route returns 404 and not an unhandled exception."""
    r = api.get("/this-route-does-not-exist")
    assert r.status_code == 404


def test_feature_pills_on_landing(page):
    """The feature pills (Learning Coach, MCQ Quizzes, etc.) are visible."""
    page.goto("/")
    pills = page.locator(".pill")
    assert pills.count() >= 4
    pill_texts = [pills.nth(i).inner_text() for i in range(pills.count())]
    combined = " ".join(pill_texts)
    assert "Learning Coach" in combined or "Quiz" in combined
