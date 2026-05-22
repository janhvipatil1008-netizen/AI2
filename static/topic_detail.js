(function () {
  'use strict';

  const _cfg       = window.AI2_TOPIC_DETAIL;
  const _sessionId = _cfg.sessionId;
  const _topicId   = _cfg.topicId;

  // POST /topic/content/generate; reload page on success.
  async function generateContent(refresh) {
    const btn      = document.getElementById('ai-content-btn');
    const feedback = document.getElementById('ai-content-feedback');
    const origText = btn.textContent;
    btn.disabled     = true;
    btn.textContent  = refresh ? 'Refreshing…' : 'Generating…';
    feedback.textContent = '';
    try {
      const res = await fetch(_cfg.topicContentGenerateUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({session_id: _sessionId, topic_id: _topicId, refresh: refresh}),
      });
      if (res.ok) {
        window.location.reload();
      } else {
        const data = await res.json().catch(function () { return {}; });
        feedback.textContent = data.detail || 'Generation failed. Please try again.';
        feedback.className   = 'ai-content-feedback ai-content-feedback-err';
        btn.disabled    = false;
        btn.textContent = origText;
      }
    } catch (e) {
      console.warn('generateContent error:', e);
      feedback.textContent = 'Network error. Please try again.';
      feedback.className   = 'ai-content-feedback ai-content-feedback-err';
      btn.disabled    = false;
      btn.textContent = origText;
    }
  }

  // POST /topic/practice/generate; reload page on success.
  async function generatePractice(practiceType, refresh) {
    const btnId      = 'practice-btn-'      + practiceType;
    const feedbackId = 'practice-feedback-' + practiceType;
    const btn      = document.getElementById(btnId);
    const feedback = document.getElementById(feedbackId);
    const origText = btn.textContent;
    btn.disabled     = true;
    btn.textContent  = refresh ? 'Refreshing…' : 'Generating…';
    if (feedback) feedback.textContent = '';
    try {
      const res = await fetch(_cfg.topicPracticeGenerateUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          session_id:    _sessionId,
          topic_id:      _topicId,
          practice_type: practiceType,
          refresh:       refresh,
        }),
      });
      if (res.ok) {
        window.location.reload();
      } else {
        const data = await res.json().catch(function () { return {}; });
        if (feedback) {
          feedback.textContent = data.detail || 'Generation failed. Please try again.';
          feedback.className   = 'ai-content-feedback ai-content-feedback-err';
        }
        btn.disabled    = false;
        btn.textContent = origText;
      }
    } catch (e) {
      console.warn('generatePractice error:', e);
      if (feedback) {
        feedback.textContent = 'Network error. Please try again.';
        feedback.className   = 'ai-content-feedback ai-content-feedback-err';
      }
      btn.disabled    = false;
      btn.textContent = origText;
    }
  }

  // Wrap markStep for content-section "Mark Done" buttons: disables btn, shows "Done ✓" on success.
  async function markStepFromContent(btn, step) {
    const origText = btn.textContent;
    btn.disabled = true;
    const ok = await markStep(step, 'done');
    if (ok) {
      btn.textContent = 'Done ✓';
      setTimeout(function () { btn.textContent = origText; btn.disabled = false; }, 2000);
    } else {
      btn.disabled = false;
    }
  }

  // POST /topic/progress, update badge + completion bar. Returns true/false, never throws.
  async function markStep(step, status) {
    try {
      const res = await fetch(_cfg.topicProgressUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({session_id: _sessionId, topic_id: _topicId, step: step, status: status}),
      });
      if (!res.ok) {
        console.warn('Progress update failed for step:', step, res.status);
        return false;
      }
      const data  = await res.json();
      const label = data.topic_progress[step].replace(/_/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
      const badge = document.getElementById('status-' + step);
      badge.textContent = label;
      badge.className   = 'step-status-badge step-status-' + data.topic_progress[step].replace(/_/g, '-');
      document.getElementById('completion-percent').textContent = data.completion_percent + '%';
      document.getElementById('completion-fill').style.width    = data.completion_percent + '%';
      return true;
    } catch (e) {
      console.warn('Progress update error for step:', step, e);
      return false;
    }
  }

  // Action-button click: mark in_progress then navigate. Failure never blocks navigation.
  document.querySelectorAll('[data-topic-action]').forEach(function (link) {
    link.addEventListener('click', async function (e) {
      e.preventDefault();
      const step    = this.dataset.step;
      const chatUrl = this.dataset.chatUrl;
      await markStep(step, 'in_progress');
      window.location.href = chatUrl;
    });
  });

  // Shared low-level helper: POST one todo to /todos/create. Returns true/false, never throws.
  async function createPlannerTodo(title, todoType, dueLabel) {
    try {
      const res = await fetch(_cfg.todosCreateUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          session_id:      _sessionId,
          title:           title,
          todo_type:       todoType,
          linked_topic_id: _topicId,
          due_label:       dueLabel,
        }),
      });
      if (!res.ok) console.warn('createPlannerTodo failed:', title, res.status);
      return res.ok;
    } catch (e) {
      console.warn('createPlannerTodo error:', title, e);
      return false;
    }
  }

  // Per-step "Add to Today / Add to This Week" buttons.
  async function addToPlanner(btn) {
    const origText = btn.textContent;
    btn.disabled = true;
    const ok = await createPlannerTodo(btn.dataset.todoTitle, btn.dataset.todoType, btn.dataset.dueLabel);
    btn.textContent = ok ? 'Added ✓' : 'Error';
    setTimeout(function () { btn.textContent = origText; btn.disabled = false; }, 2000);
  }

  // POST /topic/notes; update badge and completion bar in-place on success.
  async function saveReflection() {
    const btn      = document.getElementById('reflection-save-btn');
    const feedback = document.getElementById('reflection-feedback');
    const origText = btn.textContent;
    btn.disabled = true;
    feedback.textContent = '';
    try {
      const res = await fetch(_cfg.topicNotesUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          session_id:       _sessionId,
          topic_id:         _topicId,
          reflection:       document.getElementById('reflection-text').value,
          confusions:       document.getElementById('confusions-text').value,
          application_idea: document.getElementById('application-text').value,
        }),
      });
      if (res.ok) {
        const data        = await res.json();
        feedback.textContent = 'Reflection saved ✓';
        feedback.className   = 'reflection-feedback reflection-feedback-ok';
        const reflStatus  = data.topic_progress['reflection'];
        const label       = reflStatus.replace(/_/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
        const badge       = document.getElementById('status-reflection');
        badge.textContent = label;
        badge.className   = 'step-status-badge step-status-' + reflStatus.replace(/_/g, '-');
        document.getElementById('completion-percent').textContent = data.completion_percent + '%';
        document.getElementById('completion-fill').style.width    = data.completion_percent + '%';
      } else {
        feedback.textContent = 'Failed to save. Please try again.';
        feedback.className   = 'reflection-feedback reflection-feedback-err';
      }
    } catch (e) {
      console.warn('Save reflection error:', e);
      feedback.textContent = 'Network error. Please try again.';
      feedback.className   = 'reflection-feedback reflection-feedback-err';
    } finally {
      btn.disabled    = false;
      btn.textContent = origText;
    }
  }

  // POST /quiz/submit — save learner's quiz answers in-place.
  async function saveQuizAnswers() {
    const btn      = document.getElementById('quiz-save-btn');
    const feedback = document.getElementById('quiz-submission-feedback');
    const text     = document.getElementById('quiz-submission-text').value;
    const origText = btn.textContent;
    btn.disabled    = true;
    btn.textContent = 'Saving…';
    feedback.textContent = '';
    feedback.className   = 'quiz-submission-feedback';
    try {
      const res = await fetch(_cfg.quizSubmitUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({session_id: _sessionId, topic_id: _topicId, answers: text}),
      });
      if (res.ok) {
        feedback.textContent = 'Answers saved ✓';
        feedback.className   = 'quiz-submission-feedback quiz-feedback-ok';
      } else {
        const data = await res.json().catch(function () { return {}; });
        feedback.textContent = data.detail || 'Save failed. Please try again.';
        feedback.className   = 'quiz-submission-feedback quiz-feedback-err';
      }
    } catch (e) {
      console.warn('saveQuizAnswers error:', e);
      feedback.textContent = 'Network error. Please try again.';
      feedback.className   = 'quiz-submission-feedback quiz-feedback-err';
    } finally {
      btn.disabled    = false;
      btn.textContent = origText;
    }
  }

  // POST /quiz/evaluate — reload on success.
  async function evaluateQuiz(refresh) {
    const btn      = document.getElementById('quiz-evaluate-btn');
    const feedback = document.getElementById('quiz-submission-feedback');
    const origText = btn ? btn.textContent : 'Evaluate Answers';
    if (btn) { btn.disabled = true; btn.textContent = 'Evaluating…'; }
    if (feedback) { feedback.textContent = ''; feedback.className = 'quiz-submission-feedback'; }
    try {
      const res = await fetch(_cfg.quizEvaluateUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({session_id: _sessionId, topic_id: _topicId, refresh: refresh}),
      });
      if (res.ok) {
        window.location.reload();
      } else {
        const data = await res.json().catch(function () { return {}; });
        if (feedback) {
          feedback.textContent = data.detail || 'Evaluation failed. Please try again.';
          feedback.className   = 'quiz-submission-feedback quiz-feedback-err';
        }
        if (btn) { btn.disabled = false; btn.textContent = origText; }
      }
    } catch (e) {
      console.warn('evaluateQuiz error:', e);
      if (feedback) {
        feedback.textContent = 'Network error. Please try again.';
        feedback.className   = 'quiz-submission-feedback quiz-feedback-err';
      }
      if (btn) { btn.disabled = false; btn.textContent = origText; }
    }
  }

  // POST /portfolio/submit — save learner's submission in-place.
  async function savePortfolioSubmission() {
    const btn      = document.getElementById('portfolio-save-btn');
    const feedback = document.getElementById('portfolio-submission-feedback');
    const text     = document.getElementById('portfolio-submission-text').value;
    const origText = btn.textContent;
    btn.disabled    = true;
    btn.textContent = 'Saving…';
    feedback.textContent = '';
    feedback.className   = 'portfolio-submission-feedback';
    try {
      const res = await fetch(_cfg.portfolioSubmitUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({session_id: _sessionId, topic_id: _topicId, submission: text}),
      });
      if (res.ok) {
        feedback.textContent = 'Submission saved ✓';
        feedback.className   = 'portfolio-submission-feedback portfolio-feedback-ok';
      } else {
        const data = await res.json().catch(function () { return {}; });
        feedback.textContent = data.detail || 'Save failed. Please try again.';
        feedback.className   = 'portfolio-submission-feedback portfolio-feedback-err';
      }
    } catch (e) {
      console.warn('savePortfolioSubmission error:', e);
      feedback.textContent = 'Network error. Please try again.';
      feedback.className   = 'portfolio-submission-feedback portfolio-feedback-err';
    } finally {
      btn.disabled    = false;
      btn.textContent = origText;
    }
  }

  // POST /portfolio/feedback — reload on success.
  async function getPortfolioFeedback(refresh) {
    const btn      = document.getElementById('portfolio-feedback-btn');
    const feedback = document.getElementById('portfolio-submission-feedback');
    const origText = btn ? btn.textContent : 'Get AI Feedback';
    if (btn) { btn.disabled = true; btn.textContent = 'Reviewing…'; }
    if (feedback) { feedback.textContent = ''; feedback.className = 'portfolio-submission-feedback'; }
    try {
      const res = await fetch(_cfg.portfolioFeedbackUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({session_id: _sessionId, topic_id: _topicId, refresh: refresh}),
      });
      if (res.ok) {
        window.location.reload();
      } else {
        const data = await res.json().catch(function () { return {}; });
        if (feedback) {
          feedback.textContent = data.detail || 'Feedback failed. Please try again.';
          feedback.className   = 'portfolio-submission-feedback portfolio-feedback-err';
        }
        if (btn) { btn.disabled = false; btn.textContent = origText; }
      }
    } catch (e) {
      console.warn('getPortfolioFeedback error:', e);
      if (feedback) {
        feedback.textContent = 'Network error. Please try again.';
        feedback.className   = 'portfolio-submission-feedback portfolio-feedback-err';
      }
      if (btn) { btn.disabled = false; btn.textContent = origText; }
    }
  }

  // POST /interview/submit — save learner's interview answer in-place.
  async function saveInterviewAnswer() {
    const btn      = document.getElementById('interview-save-btn');
    const feedback = document.getElementById('interview-submission-feedback');
    const text     = document.getElementById('interview-submission-text').value;
    const origText = btn.textContent;
    btn.disabled    = true;
    btn.textContent = 'Saving…';
    feedback.textContent = '';
    feedback.className   = 'interview-submission-feedback';
    try {
      const res = await fetch(_cfg.interviewSubmitUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({session_id: _sessionId, topic_id: _topicId, answer: text}),
      });
      if (res.ok) {
        feedback.textContent = 'Answer saved ✓';
        feedback.className   = 'interview-submission-feedback interview-feedback-ok';
      } else {
        const data = await res.json().catch(function () { return {}; });
        feedback.textContent = data.detail || 'Save failed. Please try again.';
        feedback.className   = 'interview-submission-feedback interview-feedback-err';
      }
    } catch (e) {
      console.warn('saveInterviewAnswer error:', e);
      feedback.textContent = 'Network error. Please try again.';
      feedback.className   = 'interview-submission-feedback interview-feedback-err';
    } finally {
      btn.disabled    = false;
      btn.textContent = origText;
    }
  }

  // POST /interview/feedback — reload on success.
  async function getInterviewFeedback(refresh) {
    const btn      = document.getElementById('interview-feedback-btn');
    const feedback = document.getElementById('interview-submission-feedback');
    const origText = btn ? btn.textContent : 'Get AI Feedback';
    if (btn) { btn.disabled = true; btn.textContent = 'Reviewing…'; }
    if (feedback) { feedback.textContent = ''; feedback.className = 'interview-submission-feedback'; }
    try {
      const res = await fetch(_cfg.interviewFeedbackUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({session_id: _sessionId, topic_id: _topicId, refresh: refresh}),
      });
      if (res.ok) {
        window.location.reload();
      } else {
        const data = await res.json().catch(function () { return {}; });
        if (feedback) {
          feedback.textContent = data.detail || 'Feedback failed. Please try again.';
          feedback.className   = 'interview-submission-feedback interview-feedback-err';
        }
        if (btn) { btn.disabled = false; btn.textContent = origText; }
      }
    } catch (e) {
      console.warn('getInterviewFeedback error:', e);
      if (feedback) {
        feedback.textContent = 'Network error. Please try again.';
        feedback.className   = 'interview-submission-feedback interview-feedback-err';
      }
      if (btn) { btn.disabled = false; btn.textContent = origText; }
    }
  }

  // One-click suggested plan: Learn + Quiz as daily, Portfolio Task + Interview Practice as weekly.
  async function addSuggestedPlan(btn) {
    const origText   = btn.textContent;
    const topicTitle = btn.dataset.topicTitle;
    btn.disabled = true;
    const results = await Promise.all([
      createPlannerTodo('Learn: '              + topicTitle, 'daily',  'Today'),
      createPlannerTodo('Quiz: '               + topicTitle, 'daily',  'Today'),
      createPlannerTodo('Portfolio Task: '     + topicTitle, 'weekly', 'This Week'),
      createPlannerTodo('Interview Practice: ' + topicTitle, 'weekly', 'This Week'),
    ]);
    btn.textContent = results.every(Boolean) ? 'Suggested Plan Added ✓' : 'Some items failed';
    setTimeout(function () { btn.textContent = origText; btn.disabled = false; }, 2000);
  }

  // Expose all functions globally so onclick="..." handlers can reach them.
  window.generateContent         = generateContent;
  window.generatePractice        = generatePractice;
  window.markStepFromContent     = markStepFromContent;
  window.markStep                = markStep;
  window.addToPlanner            = addToPlanner;
  window.saveReflection          = saveReflection;
  window.saveQuizAnswers         = saveQuizAnswers;
  window.evaluateQuiz            = evaluateQuiz;
  window.savePortfolioSubmission = savePortfolioSubmission;
  window.getPortfolioFeedback    = getPortfolioFeedback;
  window.saveInterviewAnswer     = saveInterviewAnswer;
  window.getInterviewFeedback    = getInterviewFeedback;
  window.addSuggestedPlan        = addSuggestedPlan;
}());
