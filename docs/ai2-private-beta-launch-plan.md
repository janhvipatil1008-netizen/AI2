# AI² Private Beta Launch Plan

## 1. Private Beta Goal

The private beta goal is to validate whether learners genuinely learn better with AI².

The beta should test the full learning loop:

learn -> practice -> quiz -> portfolio/interview feedback -> reflection -> improvement

The beta should also validate cost, retention, and user experience before offering a public free trial.

## 2. Target Beta Users

Start with 20-50 learners who are likely to give useful feedback:

- AI Product Manager aspirants
- AI Builder beginners
- Interview-prep learners
- Learners who want structured AI upskilling
- Learners comfortable giving honest product feedback

This group is small enough to support manually and large enough to reveal repeated patterns.

## 3. First Learning Path to Launch

Launch one focused path first:

**Recommended:** AI Product Manager Foundations

Alternative: AI Builder Foundations

One path is better than many because it keeps onboarding, lessons, prompts, rubrics, feedback, and outcome measurement easier to debug. A focused path also makes it easier to compare learner progress because users are moving through similar topics.

## 4. Minimum Beta Feature Set

Must-have beta features:

- Signup/login
- Topic learning flow
- Base lesson generation/cache
- Practice task generation
- Quiz evaluation
- Portfolio feedback
- Interview feedback
- Todos/progress tracking
- Baseline/post-topic outcome endpoints
- Usage limits behind flag
- Storage health/debug checks
- Simple feedback collection

The first beta does not need a polished admin product. It needs reliable learning loops and enough observability to understand what is working.

## 5. What We Should Not Build Yet

Avoid building these before beta signals are clear:

- Payments
- Certificates
- Mobile app
- Community features
- Complex gamification
- Multi-model routing
- Advanced admin analytics
- Mentor marketplace
- Kubernetes/microservices

These can wait until the core learning loop has evidence.

## 6. Beta Onboarding Flow

Simple first-session flow:

1. Signup/login
2. Choose learning goal
3. Choose level
4. Start first recommended topic
5. Answer baseline question
6. Read lesson
7. Complete practice
8. Submit quiz
9. Save reflection
10. Answer post-topic question
11. See improvement summary

The flow should make the learner feel progress quickly, ideally within one topic.

## 7. First-Session Activation Metric

Primary activation:

- Learner completes one topic
- Learner submits one quiz
- Learner saves one reflection
- Learner completes baseline and post-topic outcome

Backup activation:

- Learner completes two topics within 48 hours

The primary metric validates the full learning loop. The backup metric captures learners who engage even if they skip a specific step.

## 8. Learning Outcome Metrics

Track:

- Baseline score
- Post-topic score
- Improvement delta
- Quiz score
- Portfolio readiness score
- Interview readiness score
- Topic completion rate
- Path completion rate

The most important early signal is whether average improvement delta is positive and whether learners believe the feedback helped.

## 9. Retention Metrics

Track:

- Day 1 return
- Day 3 return
- Day 7 return
- Topics completed per learner
- Practice tasks completed
- Feedback requests per learner
- Drop-off point

Retention should be interpreted with qualitative feedback. If learners do not return, ask whether the issue was content quality, unclear next steps, time commitment, or lack of perceived value.

## 10. Cost and Usage Metrics

Track:

- Claude calls per learner
- Shared cache hit rate
- Usage-limit blocks
- Average cost per active learner
- Most expensive flows
- Failed Claude calls

The goal is not to optimize cost too early. The goal is to understand which flows drive value and which flows drive cost.

## 11. Feedback Collection

Ask simple questions after topic work and AI feedback:

- Did this topic help you understand the concept better?
- Was the AI feedback useful?
- What confused you?
- What would make you come back tomorrow?
- Would you pay for this after the free trial?
- What price feels reasonable?

Keep feedback collection lightweight. A few consistent questions are more useful than a long survey nobody completes.

## 12. Beta Success Criteria

Practical success criteria:

- 20-50 users onboarded
- At least 40% complete first topic
- At least 25% return within 7 days
- Average improvement delta is positive
- Cache hit rate improves after repeated usage
- Cost per learner is measurable
- Top 10 bugs/pain points identified

The beta is successful if it produces clear learning, retention, cost, and product-quality signals.

## 13. Public Free Trial Readiness Criteria

AI² is ready for a public free trial when:

- No data loss after restart
- Todos/progress DB-first flags are tested
- Content cache works
- Usage limits work
- Debug endpoints are protected in production
- Privacy/terms pages exist
- Onboarding is clear
- First path is stable
- Cost per learner is understood

Do not launch publicly until the basics are reliable and the cost envelope is known.

## 14. 30-Day Free Trial Strategy

Recommended free trial:

- No credit card required
- 30 days free
- Limited AI actions
- Unlimited cached lesson review
- Collect willingness-to-pay data
- Introduce paid plans only after beta signals

This reduces friction and helps measure real interest before building billing.

## 15. Manual Tracking Sheet

Use a simple manual tracker for the first cohort:

| Learner name/email | Signup date | First topic completed | Baseline score | Post score | Improvement | Day 7 returned | Feedback notes | Willingness to pay |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
|  |  | Yes/No |  |  |  | Yes/No |  |  |
|  |  | Yes/No |  |  |  | Yes/No |  |  |
|  |  | Yes/No |  |  |  | Yes/No |  |  |

Keep this manual until the repeated reporting needs are obvious.

## 16. Immediate Next Build Priorities

Recommended next build order:

1. Add simple onboarding goal/level selection
2. Add UI for baseline/post-topic learning outcome
3. Add feedback form after AI feedback
4. Add simple beta admin metrics view
5. Add privacy/terms pages

These are enough to support the first private beta without over-engineering.
