# TeachLink Objective-To-Evidence Matrix

## Purpose

This matrix connects the original TeachLink proposal objectives to concrete implementation evidence so the project can be defended clearly during submission, demonstration, and viva.

## Positioning Statement

**TeachLink is a rule-based, explainable student risk detection and intervention support system.**

It is not presented as a machine learning system. Its intelligence comes from explicit analytics rules, explainable risk factors, difficulty analysis, and action-oriented alerts.

## Matrix

| Proposal Objective | Implemented Feature | Where It Is Visible | Evidence In Code |
| --- | --- | --- | --- |
| Track student academic progress across enrolled courses | Enrollment progress tracking from lesson completion records | Teacher `My Students`, teacher student detail, student dashboard, student `My Courses` | `courses/models.py` (`Enrollment.update_progress`), `dashboard/views.py`, `dashboard/templates/dashboard/teacher/students.html`, `dashboard/templates/dashboard/student/courses.html` |
| Detect at-risk students early using rule-based analytics | Composite risk engine using progress deficit, quiz deficit, and inactivity | Teacher dashboard summary, student list, teacher student detail, student learning status block | `analytics/services/risk_engine.py`, `dashboard/views.py`, `dashboard/templates/dashboard/teacher/dashboard.html`, `dashboard/templates/dashboard/student/dashboard.html` |
| Explain why a student is at risk | Risk explainability with factor breakdown and contribution percentages | Teacher student detail and student overview cards | `analytics/services/risk_engine.py`, `dashboard/templates/dashboard/teacher/student_detail.html`, `dashboard/templates/dashboard/student/dashboard.html` |
| Monitor student engagement levels | Engagement score derived from recency, completion, and quiz participation | Student dashboard learning status, teacher/student data payloads | `analytics/services/risk_engine.py`, `dashboard/views.py` |
| Identify difficult learning topics | Lesson difficulty analysis based on failure rate, attempt intensity, and re-access intensity | Teacher dashboard `Most Difficult Topics`, course analytics views | `analytics/services/difficulty_analyzer.py`, `dashboard/templates/dashboard/teacher/dashboard.html`, `dashboard/templates/dashboard/teacher/course_analytics.html` |
| Generate early warning alerts for intervention | Alert types: dropout risk, behind schedule, disengagement, performance drop, multiple failures | Teacher dashboard recent alerts, teacher alerts center, student notifications | `analytics/services/alert_generator.py`, `dashboard/views.py`, `dashboard/templates/dashboard/teacher/alerts.html`, `dashboard/templates/dashboard/student/dashboard.html` |
| Provide actionable intervention guidance | Recommended next action for each risk case and alert recommendation text | Teacher dashboard focus students, teacher student detail, recent alerts | `dashboard/views.py` (`_recommended_teacher_action`), `analytics/services/alert_generator.py`, `dashboard/templates/dashboard/teacher/dashboard.html`, `dashboard/templates/dashboard/teacher/student_detail.html` |
| Support student self-correction | Student-facing dashboard with risk, engagement, next action, recent attempts, notifications, and course workspace | Student overview and `My Courses` | `dashboard/views.py`, `dashboard/templates/dashboard/student/dashboard.html`, `dashboard/templates/dashboard/student/courses.html` |
| Provide lesson-level learning access | Notes, completion, quiz access, and difficulty reporting on lesson workflow | Student `My Courses`, lesson page, quiz pages | `dashboard/templates/dashboard/student/courses.html`, `dashboard/templates/dashboard/student/lesson_view.html`, `dashboard/templates/dashboard/student/course_quizzes.html` |
| Enable quiz-based assessment and automatic scoring | Quiz publishing, attempt tracking, score calculation, pass/fail state, attempts history | Student quiz workflow, teacher assessment analytics, recent quiz attempts | `assessments/models.py`, `dashboard/views.py`, `dashboard/templates/dashboard/student/quiz_take.html`, `dashboard/templates/dashboard/student/quiz_attempts.html` |
| Show analytics visually for teachers | Risk distribution, risk trend, assessment score distribution, difficult topics | Teacher dashboard | `dashboard/views.py` (`TeacherDashboardAPI`), `dashboard/templates/dashboard/teacher/dashboard.html` |
| Maintain secure user-role separation | Separate teacher/student roles with role-specific dashboards and navigation | Login flow, teacher dashboard, student dashboard | `users` app models/views, `dashboard/views.py`, `dashboard/templates/dashboard/base.html` |

## Strongest Screenshots To Capture

1. Teacher dashboard top section showing:
   - risk engine summary
   - students needing attention
   - labeled charts
2. Teacher student detail showing:
   - risk score
   - risk level
   - primary factors
   - recommended intervention
3. Teacher alerts center showing:
   - alert types
   - recommendation
   - risk/progress metrics
4. Teacher difficult topics table showing:
   - lesson title
   - difficulty level
   - failure rate
   - access/re-access signal
5. Student overview showing:
   - learning status
   - risk score
   - engagement
   - recommended next step
6. Student `My Courses` page showing:
   - lessons
   - lesson notes
   - quiz actions
   - progress
7. Student lesson page showing:
   - content
   - mark complete
   - report difficulty
8. Student quiz attempt history showing:
   - multiple attempts
   - best score context

## Best Verbal Framing During Presentation

Use short, examiner-friendly phrasing:

- "The risk score is rule-based and explainable."
- "Each alert is tied to a measurable trigger."
- "Students can also self-correct because they see their own status and next action."
- "Topic difficulty is inferred from failure rate, repeated attempts, and lesson re-access patterns."
- "The system supports intervention, not just reporting."

## Evidence Checklist Before Final Submission

- Teacher dashboard screenshots captured with fully populated charts
- Student dashboard screenshots captured with non-empty quiz and notification data
- At least one high-risk, one medium-risk, and one low-risk student visible in evidence
- At least one difficult topic example visible
- At least one alert workflow visible
- Demo data regenerated immediately before screenshots using:

```powershell
python manage.py create_demo_classroom --fresh
```
