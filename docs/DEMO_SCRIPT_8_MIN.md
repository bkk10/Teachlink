# TeachLink 5-8 Minute Demo Script

## Demo Goal

Tell one clear story:

**TeachLink detects risk early, explains it clearly, and guides both teacher and student toward action.**

## Demo Setup

Refresh the demo data before presenting:

```powershell
python manage.py create_demo_classroom --fresh
```

Use these accounts:

- Teacher: `demo.teacher@teachlink.com`
- Student: `demo.student01@teachlink.com`

## Recommended Flow

### 1. Opening Context (20-30 seconds)

Say:

"TeachLink is a rule-based, explainable student risk detection and intervention support system for teachers and students. It combines progress tracking, quiz performance, inactivity monitoring, topic difficulty analysis, and alert generation."

### 2. Teacher Dashboard Overview (60-90 seconds)

Open teacher dashboard.

Point out:

- KPI cards
- risk engine summary
- students needing attention
- charts
- recent alerts
- most difficult topics

Say:

"This dashboard is designed to make the intelligence visible immediately. The teacher can see risk distribution, which students need attention, the main alert signals, and which lessons are hardest for the class."

### 3. Explain The Risk Engine (45-60 seconds)

Stay on teacher dashboard and highlight the risk summary and one focus student.

Say:

"The risk score is rule-based and explainable. It combines course progress, quiz performance, and inactivity. Instead of giving only a label, the system also shows the strongest driver and suggests an intervention."

### 4. Teacher Student Detail View (60-90 seconds)

Open one medium-risk or high-risk student detail page.

Point out:

- risk score
- risk band
- trend/history
- factor breakdown
- alerts for that student
- recommended next step

Say:

"This view answers three questions for the teacher: Is the student at risk, why are they at risk, and what should the teacher do next?"

### 5. Alerts As Early Warning (45-60 seconds)

Open teacher alerts page.

Point out:

- alert type
- severity
- recommendation
- progress/risk snapshot

Say:

"The system does not stop at analytics. It turns risk into actionable alerts such as behind schedule, disengagement, dropout risk, performance drop, and repeated quiz failure."

### 6. Topic Difficulty Analysis (45-60 seconds)

Return to dashboard or open course analytics.

Point out:

- difficult topics table
- failure rate
- attempt intensity
- access/re-access signal

Say:

"TeachLink also identifies difficult lessons using class behavior. It does not rely on one metric only. It combines failure rate with repeated quiz attempts and repeated lesson access to highlight where students struggle."

### 7. Switch To Student View (15-20 seconds)

Log out and log in as a demo student.

Say:

"The student side is important because risk detection should also support self-correction."

### 8. Student Overview (60-90 seconds)

Open student overview.

Point out:

- learning status
- risk score and band
- engagement
- inactivity
- recent attempts
- notifications
- recommended next step

Say:

"The student can see their own learning status, understand the current risk score, review recent quiz performance, and get a focused next action. This supports self-monitoring instead of leaving analytics only to the teacher."

### 9. Student My Courses Workflow (60-90 seconds)

Open `My Courses`.

Point out:

- course progress
- lesson list
- lesson notes
- direct quiz action
- mark complete
- report difficulty

Then open one lesson.

Say:

"This is the student learning workspace. The student can access lessons, mark them complete, take quizzes, and report difficulty to the teacher. That keeps the workflow connected rather than making the dashboard a read-only screen."

### 10. Close With Academic Framing (20-30 seconds)

Say:

"The main contribution of TeachLink is not machine learning. It is a practical, explainable, rule-based early warning system that helps teachers identify struggling students earlier and helps students understand how to improve."

## If The Examiner Asks "What Makes It Intelligent?"

Answer:

"Its intelligence is in the analytics rules and explainability. It combines multiple measurable signals, classifies risk levels, detects difficult topics, and generates intervention-oriented alerts. The goal is explainable support, not black-box prediction."

## If The Examiner Asks "Why Not Machine Learning?"

Answer:

"For this project, a rule-based model was more realistic, easier to validate academically, and better aligned with the available data. It also makes the output more transparent to teachers and students."

## If The Examiner Asks "How Is Engagement Calculated?"

Answer:

"Engagement is derived from recent activity, lesson completion progress, and quiz participation. It is shown as a score and used as one of the monitoring indicators rather than a hidden label."

## Backup Talking Points

- "Risk is visible on both teacher and student sides."
- "Alerts are tied to measurable thresholds."
- "Topic difficulty is lesson-level, not just course-level."
- "The student side supports self-correction."
- "The analytics are explainable and aligned with the proposal scope."

## Final Demo Checklist

- Regenerate demo data before presenting
- Confirm teacher dashboard charts are loaded
- Confirm alerts are non-empty
- Confirm one student has medium/high risk
- Confirm student recent attempts are visible
- Confirm at least one lesson page opens correctly
- Confirm at least one quiz is published and accessible
