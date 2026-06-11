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

  // ── Interactive MCQ quiz player ───────────────────────────────────────────

  var _quiz = { questions: [], idx: 0, answers: [] };

  function _parseQuizContent(text) {
    var questions = [];
    var parts = text.split(/(?=Q\d+\.)/);
    for (var i = 0; i < parts.length; i++) {
      var part = parts[i].trim();
      var qMatch = part.match(/^Q\d+\.\s*([\s\S]+?)(?=\nA\))/);
      if (!qMatch) continue;
      var questionText = qMatch[1].trim();
      var optA = (part.match(/^A\)\s*(.+)$/m) || [])[1];
      var optB = (part.match(/^B\)\s*(.+)$/m) || [])[1];
      var optC = (part.match(/^C\)\s*(.+)$/m) || [])[1];
      var optD = (part.match(/^D\)\s*(.+)$/m) || [])[1];
      var answerMatch = part.match(/^ANSWER:\s*([A-D])/im);
      var explanationMatch = part.match(/^EXPLANATION:\s*(.+)$/im);
      if (!optA || !optB || !answerMatch) continue;
      questions.push({
        text:        questionText,
        options:     { A: optA.trim(), B: optB.trim(), C: optC ? optC.trim() : '', D: optD ? optD.trim() : '' },
        answer:      answerMatch[1].toUpperCase(),
        explanation: explanationMatch ? explanationMatch[1].trim() : '',
      });
    }
    return questions;
  }

  function _renderQuizQuestion(idx) {
    var q        = _quiz.questions[idx];
    var total    = _quiz.questions.length;
    var progress = document.getElementById('quiz-progress');
    var qText    = document.getElementById('quiz-question-text');
    var options  = document.getElementById('quiz-options');
    var result   = document.getElementById('quiz-result');
    var nextBtn  = document.getElementById('quiz-next-btn');
    var finalDiv = document.getElementById('quiz-final-report');

    progress.textContent = 'Question ' + (idx + 1) + ' of ' + total;
    qText.textContent    = q.text;
    result.style.display = 'none';
    result.className     = 'td-quiz-result';
    result.textContent   = '';
    if (nextBtn)  nextBtn.style.display  = 'none';
    if (finalDiv) finalDiv.style.display = 'none';

    options.innerHTML = '';
    var letters = ['A', 'B', 'C', 'D'];
    for (var j = 0; j < letters.length; j++) {
      var letter = letters[j];
      var text   = q.options[letter];
      if (!text) continue;
      var btn = document.createElement('button');
      btn.className = 'td-quiz-opt';
      btn.textContent = letter + ')  ' + text;
      btn.dataset.letter = letter;
      btn.onclick = (function (l) { return function () { quizSelectOption(l); }; })(letter);
      options.appendChild(btn);
    }
  }

  function quizSelectOption(letter) {
    var q       = _quiz.questions[_quiz.idx];
    var correct = letter === q.answer;
    _quiz.answers.push({ idx: _quiz.idx, chosen: letter, correct: correct });

    // Highlight option buttons
    var opts = document.querySelectorAll('#quiz-options .td-quiz-opt');
    for (var i = 0; i < opts.length; i++) {
      opts[i].disabled = true;
      if (opts[i].dataset.letter === q.answer) opts[i].classList.add('td-quiz-opt--correct');
      else if (opts[i].dataset.letter === letter && !correct) opts[i].classList.add('td-quiz-opt--wrong');
    }

    // Show result
    var result = document.getElementById('quiz-result');
    result.className   = 'td-quiz-result ' + (correct ? 'td-quiz-result--correct' : 'td-quiz-result--wrong');
    result.textContent = (correct ? 'Correct. ' : 'Not quite — the answer is ' + q.answer + '. ') + q.explanation;
    result.style.display = 'block';

    // Show next/finish
    var isLast = _quiz.idx + 1 >= _quiz.questions.length;
    if (isLast) {
      var finalDiv = document.getElementById('quiz-final-report');
      if (finalDiv) {
        var score   = _quiz.answers.filter(function (a) { return a.correct; }).length;
        var scoreEl = document.getElementById('quiz-score-display');
        if (scoreEl) scoreEl.textContent = 'You got ' + score + ' of ' + _quiz.questions.length + ' correct.';
        finalDiv.style.display = 'block';
      }
    } else {
      var nextBtn = document.getElementById('quiz-next-btn');
      if (nextBtn) nextBtn.style.display = 'inline-block';
    }
  }

  function quizNextQuestion() {
    _quiz.idx += 1;
    _renderQuizQuestion(_quiz.idx);
  }

  function _buildQuizAnswersText() {
    var lines = [];
    for (var i = 0; i < _quiz.answers.length; i++) {
      var a = _quiz.answers[i];
      var q = _quiz.questions[a.idx];
      lines.push('Q' + (a.idx + 1) + ': ' + a.chosen + (a.correct ? ' (correct)' : ' — correct: ' + q.answer));
    }
    return lines.join('\n');
  }

  async function quizSubmitAndEvaluate() {
    var btn      = document.getElementById('quiz-player-submit-btn');
    var feedback = document.getElementById('quiz-player-feedback');
    if (btn) { btn.disabled = true; btn.textContent = 'Saving…'; }

    var answersText = _buildQuizAnswersText();
    document.getElementById('quiz-submission-text').value = answersText;

    try {
      await fetch(_cfg.quizSubmitUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({session_id: _sessionId, topic_id: _topicId, answers: answersText}),
      });
    } catch (e) { console.warn('quiz save error:', e); }

    if (btn) btn.textContent = 'Evaluating…';
    try {
      var res = await fetch(_cfg.quizEvaluateUrl, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({session_id: _sessionId, topic_id: _topicId, refresh: false}),
      });
      if (res.ok) {
        window.location.reload();
      } else {
        var data = await res.json().catch(function () { return {}; });
        if (feedback) {
          feedback.textContent = data.detail || 'Evaluation failed. Please try again.';
          feedback.className   = 'quiz-submission-feedback quiz-feedback-err';
        }
        if (btn) { btn.disabled = false; btn.textContent = 'Get AI feedback'; }
      }
    } catch (e) {
      console.warn('quiz evaluate error:', e);
      if (feedback) {
        feedback.textContent = 'Network error. Please try again.';
        feedback.className   = 'quiz-submission-feedback quiz-feedback-err';
      }
      if (btn) { btn.disabled = false; btn.textContent = 'Get AI feedback'; }
    }
  }

  function initInteractiveQuiz() {
    var rawEl = document.getElementById('quiz-raw-content');
    if (!rawEl) return;
    var questions = _parseQuizContent(rawEl.value);
    if (questions.length < 2) {
      // Old format — show legacy display
      var legacyEl = document.getElementById('quiz-legacy');
      var legacyContent = document.getElementById('quiz-legacy-content');
      var submissionTa = document.getElementById('quiz-submission-text');
      if (legacyEl)      legacyEl.style.display      = 'block';
      if (legacyContent) legacyContent.textContent    = rawEl.value;
      if (submissionTa)  submissionTa.style.display   = '';
      return;
    }
    _quiz.questions = questions;
    _quiz.idx       = 0;
    _quiz.answers   = [];
    var playerEl = document.getElementById('quiz-player');
    if (playerEl) playerEl.style.display = 'block';
    _renderQuizQuestion(0);
  }

  document.addEventListener('DOMContentLoaded', function () {
    if (document.getElementById('quiz-raw-content')) initInteractiveQuiz();
  });

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
  window.quizSelectOption        = quizSelectOption;
  window.quizNextQuestion        = quizNextQuestion;
  window.quizSubmitAndEvaluate   = quizSubmitAndEvaluate;
  window.initInteractiveQuiz     = initInteractiveQuiz;
  window.savePortfolioSubmission = savePortfolioSubmission;
  window.getPortfolioFeedback    = getPortfolioFeedback;
  window.saveInterviewAnswer     = saveInterviewAnswer;
  window.getInterviewFeedback    = getInterviewFeedback;
  window.addSuggestedPlan        = addSuggestedPlan;
}());
