# AI² Portfolio and Interview Redirect Audit

**Date:** 2026-05-25
**Environment:** Production — Render
**App URL:** https://ai2-platform.onrender.com
**Purpose:** Audit why Portfolio Task and Interview Practice buttons redirect to /chat instead of staying on topic detail

---

## 1. Current Behavior

When a learner clicks **"Get Task"** (Portfolio Task) or **"Practice"** (Interview Practice) from the topic detail journey steps, they are navigated away from the topic detail page and redirected to:

```
/chat/{session_id}?prompt=<url-encoded topic prompt>
```

This drops the learner into the general chat interface — losing the structured topic context, the topic detail sidebar, the submission forms, and all progress indicators that are only visible on the topic detail page.

The redirect happens **immediately** — before any content is generated. The learner lands in chat with a pre-filled prompt and must wait for the orchestrator/Claude to respond there, away from the structured topic flow.

---

## 2. Expected Structured Learning Behavior

The topic detail page already contains a **complete structured flow** for both Portfolio Task and Interview Practice:

- An AI-generated content panel (`#ai-portfolio-task`, `#ai-interview-practice`) that renders the Claude-generated task/practice content **inline on the page**
- A submission textarea for the learner to write their answer
- Save Submission and Get AI Feedback buttons that POST to `/portfolio/submit`, `/portfolio/feedback`, `/interview/submit`, `/interview/feedback`
- Score display, reviewed-at metadata, and feedback text — all rendered within the topic detail page

**Expected beta behavior:** Clicking "Get Task" or "Practice" in the journey step cards should scroll to or trigger `generatePractice('portfolio_task')` / `generatePractice('interview_practice')` — keeping the learner on the topic detail page and populating the structured AI content panels that already exist below.

The full structured submission/feedback loop is already built. The redirect to `/chat` bypasses it entirely.

---

## 3. Files and Routes Involved

### Template — journey step cards with redirect links
**File:** `templates/topic_detail.html` — lines 522–528 (Portfolio Task) and 555–561 (Interview Practice)

```html
<!-- Portfolio Task — line 522 -->
<a class="topic-action-btn"
   href="/chat/{{ session_id }}?prompt={{ topic.portfolio_prompt | urlencode }}"
   data-topic-action
   data-step="portfolio_task"
   data-status="in_progress"
   data-chat-url="/chat/{{ session_id }}?prompt={{ topic.portfolio_prompt | urlencode }}">
  Get Task
</a>

<!-- Interview Practice — line 555 -->
<a class="topic-action-btn"
   href="/chat/{{ session_id }}?prompt={{ topic.interview_prompt | urlencode }}"
   data-topic-action
   data-step="interview_practice"
   data-status="in_progress"
   data-chat-url="/chat/{{ session_id }}?prompt={{ topic.interview_prompt | urlencode }}">
  Practice
</a>
```

### JavaScript — event handler that executes the redirect
**File:** `static/topic_detail.js` — lines 122–131

```javascript
// Action-button click: mark in_progress then navigate. Failure never blocks navigation.
document.querySelectorAll('[data-topic-action]').forEach(function (link) {
  link.addEventListener('click', async function (e) {
    e.preventDefault();
    const step    = this.dataset.step;
    const chatUrl = this.dataset.chatUrl;
    await markStep(step, 'in_progress');
    window.location.href = chatUrl;   // ← THIS is the redirect
  });
});
```

The `data-chat-url` attribute on both `<a>` elements points to `/chat/{session_id}?prompt=...`. The JS intercepts the click, marks the step `in_progress`, then navigates to `chatUrl`.

### Existing structured generate function — already in topic_detail.js
**File:** `static/topic_detail.js` — lines 40–80

```javascript
async function generatePractice(practiceType, refresh) {
  // POSTs to /topic/practice/generate
  // Reloads the page on success — content appears in the topic detail AI panels
}
```

This function already exists and is already wired to the **"Generate Portfolio Task"** and **"Generate Interview Practice"** buttons in the AI content sections further down the page (lines 261–269 and 356–364 of the template). It works correctly and stays on topic detail.

---

## 4. Existing Structured Endpoints

The following structured routes already exist and are registered in `app.py`:

| Endpoint | Method | Purpose |
|---|---|---|
| `/topic/{session_id}/{topic_id}` | GET | Topic detail page |
| `/topics/{session_id}` | GET | Topics list page |
| `/topic/content/generate` | POST | Generate lesson content (Claude), reload in-place |
| `/topic/practice/generate` | POST | Generate portfolio task or interview practice (Claude), reload in-place |
| `/topic/progress` | POST | Mark a topic step status |
| `/topic/notes` | POST | Save reflection notes |
| `/portfolio/submit` | POST | Save learner's portfolio submission text |
| `/portfolio/feedback` | POST | Get Claude feedback on portfolio submission |
| `/interview/submit` | POST | Save learner's interview answer text |
| `/interview/feedback` | POST | Get Claude feedback on interview answer |
| `/quiz/submit` | POST | Submit quiz answer |
| `/topic/outcome/baseline` | POST | Record baseline outcome |
| `/topic/outcome/post` | POST | Record post-topic outcome |

**All the endpoints needed for a fully structured on-page portfolio and interview flow already exist.** The redirect to `/chat` is not a missing-endpoint problem — it is a template/JS wiring problem.

---

## 5. Root Cause

**Two connected issues in the journey step cards section of `templates/topic_detail.html`:**

### Issue A — Wrong link target
The `<a>` elements for Portfolio Task (line 523) and Interview Practice (line 556) have `href` and `data-chat-url` both set to `/chat/{session_id}?prompt=...`. This is the **old quick-action pattern** from the chat sidebar — where pre-filled prompts send the learner to the general chat.

### Issue B — JS blindly follows `data-chat-url`
`static/topic_detail.js` lines 122–131 attach a click handler to every `[data-topic-action]` element and unconditionally navigate to `this.dataset.chatUrl`. Since both journey step cards carry this attribute and a `/chat/...` URL, every click triggers the redirect.

**The AI content sections lower on the same page** (lines 243–400 of the template) already have the correct wiring: `generatePractice('portfolio_task')` and `generatePractice('interview_practice')` buttons that POST to `/topic/practice/generate` and reload the page with generated content. The journey step card buttons are duplicating the entry point but pointing to the wrong destination.

**This is old quick-action chat behavior that was not updated when the structured topic detail flow was built.** No backend routes are missing. No orchestrator logic needs to change.

---

## 6. Recommended Fix

**Safest implementation — template-only change, no route or backend changes:**

### Step 1 — Replace the redirect `<a>` links with scroll-to-generate buttons

In `templates/topic_detail.html`, replace the two `<a class="topic-action-btn" data-topic-action ...>` elements with buttons that either:
- Call `generatePractice('portfolio_task', false)` / `generatePractice('interview_practice', false)` directly (generates immediately and reloads), **or**
- Scroll the page to the existing AI content section (`#ai-portfolio-task` / `#ai-interview-practice`) if content already exists

### Step 2 — Remove `data-topic-action` from these two elements
Once the links are replaced with buttons using `onclick`, the `[data-topic-action]` JS handler in `topic_detail.js` no longer applies, eliminating the redirect path without touching the JS file.

### What NOT to change
- Do **not** remove or modify `orchestrator.py`
- Do **not** change any route URLs (`/portfolio/submit`, `/interview/submit`, etc.)
- Do **not** change the chat quick-action behavior in `chat.html` or `app.js` — those are separate and correct for the chat interface
- Do **not** remove the `/chat/{session_id}?prompt=...` pattern — it is still used for Learn and Quiz steps (lines 457–494) and works correctly there

---

## 7. Test Plan

After the fix is applied, verify:

| Test | How to verify |
|---|---|
| Clicking Portfolio Task stays on topic detail | Click "Get Task" → page reloads in-place, no navigation to `/chat` |
| Clicking Interview Practice stays on topic detail | Click "Practice" → page reloads in-place, no navigation to `/chat` |
| Structured portfolio content appears on page | After generation, `#ai-portfolio-task` section renders Claude content |
| Structured interview content appears on page | After generation, `#ai-interview-practice` section renders Claude content |
| Submission textarea and Save/Feedback buttons work | Save and Feedback buttons POST to `/portfolio/submit`, `/portfolio/feedback` |
| Chat quick actions (Learn, Quiz) still redirect to `/chat` | Learn and Quiz step buttons still navigate to `/chat?prompt=...` as before |
| No route URL changes | All existing endpoint paths unchanged |
| No Claude/provider changes | Same models, same orchestrator, same tool routing |
| Step status marks in_progress on click | `markStep()` still called before generating |

**Automated test additions recommended:**
- `test_portfolio_task_endpoint_returns_200` — POST `/topic/practice/generate` with `practice_type=portfolio_task`
- `test_interview_practice_endpoint_returns_200` — POST `/topic/practice/generate` with `practice_type=interview_practice`
- `test_portfolio_submit_endpoint_exists` — POST `/portfolio/submit`
- `test_interview_submit_endpoint_exists` — POST `/interview/submit`

---

*This report is documentation only. No runtime behavior, routes, templates, static files, schema, or data were modified to produce it.*
