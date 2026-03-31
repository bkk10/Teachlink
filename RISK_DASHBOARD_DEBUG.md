# Risk Dashboard vs Alerts Discrepancy Investigation

## Issue Summary
Dashboard shows "High Risk = 0" but alerts show "High = 26"

---

## 1. DASHBOARD RISK DISTRIBUTION CODE

### Location: `dashboard/views.py` (Lines 1982-2008)
**Function:** `TeacherRiskAnalyticsAPI` - API endpoint for risk distribution pie chart

```python
# Base queryset - filter for ACTIVE enrollments only
enrollments = Enrollment.objects.filter(
    course__teacher=teacher,
    status='ACTIVE'  # KEY FILTER: Only ACTIVE enrollments
)

if course_id:
    enrollments = enrollments.filter(course_id=course_id)

# Risk distribution pie chart
risk_counts = enrollments.values('risk_level').annotate(
    count=Count('id')
).order_by('risk_level')

risk_distribution = {
    'labels': [],
    'data': [],
    'colors': [],
}

color_map = {
    'LOW': '#10b981',
    'MEDIUM': '#f59e0b',
    'HIGH': '#ef4444',
    'CRITICAL': '#7f1d1d',
    'UNKNOWN': '#6b7280',
}

label_map = {
    'LOW': 'Low Risk',
    'MEDIUM': 'Medium Risk',
    'HIGH': 'High Risk',
    'CRITICAL': 'Critical',
    'UNKNOWN': 'Unknown',
}

for item in risk_counts:
    level = item['risk_level']
    risk_distribution['labels'].append(label_map.get(level, level))
    risk_distribution['data'].append(item['count'])  # THIS WOULD BE 0 IF NO HIGH RISK ENROLLMENTS
    risk_distribution['colors'].append(color_map.get(level, '#6b7280'))
```

### Location: `dashboard/views.py` (Lines 2326-2410)
**Function:** `TeacherDashboardCachedAPI._calculate_dashboard_data()` - Cached dashboard data

```python
# Get teacher's courses
courses = Course.objects.filter(teacher=teacher, status='PUBLISHED')
course_ids = courses.values_list('id', flat=True)

# Get active enrollments
enrollments = Enrollment.objects.filter(
    course_id__in=course_ids,
    status='ACTIVE'  # KEY FILTER: Only ACTIVE
).select_related('student', 'course')

# Calculate KPIs by counting enrollments with specific risk_level
high_risk_count = enrollments.filter(risk_level__in=['HIGH', 'CRITICAL']).count()
medium_risk_count = enrollments.filter(risk_level='MEDIUM').count()
low_risk_count = enrollments.filter(risk_level='LOW').count()

# Risk distribution returned to frontend
'risk_distribution': {
    'labels': ['Low Risk', 'Medium Risk', 'High Risk', 'Critical'],
    'data': [low_risk_count, medium_risk_count, high_risk_count,
            enrollments.filter(risk_level='CRITICAL').count()],
    'colors': ['#10b981', '#f59e0b', '#ef4444', '#7f1d1d'],
}
```

**Key Point:** Dashboard counts **Enrollments by risk_level field**, filtered for `status='ACTIVE'`

---

## 2. ALERT COUNTS CODE

### Location: `dashboard/views.py` (Lines 2130-2180)
**Function:** `TeachersAlertListAPI` - Lists alerts with severity filter

```python
# Base queryset for alerts
alerts = Alert.objects.filter(
    teacher=teacher,
    status__in=['ACTIVE', 'ACKNOWLEDGED']
)

if course_id:
    alerts = alerts.filter(course_id=course_id)

# Count alerts by severity (NOT connected to Enrollment.risk_level)
severity_counts = {
    'CRITICAL': 0,
    'HIGH': 0,
    'MEDIUM': 0,
    'LOW': 0,
    'INFO': 0,
}
for item in alerts.values('severity').annotate(count=Count('id')):
    severity = item.get('severity')
    if severity in severity_counts:
        severity_counts[severity] = item['count']  # THIS SHOWS 26 HIGH severity alerts
```

**Key Point:** Alert counts based on **Alert.severity field**, which is INDEPENDENT of Enrollment.risk_level

---

## 3. ALERT SEVERITY DETERMINATION

### Location: `analytics/services/alert_generator.py` (Lines 65-80)
**Function:** `AlertGenerator._check_dropout_risk()` - Creates alerts based on risk_level

```python
# Get latest risk assessment from enrollment
risk_level = risk_result['risk_level']  # From RiskEngine calculation
risk_score = risk_result['risk_score']

if risk_level in ['HIGH', 'CRITICAL']:
    # Check if already have active alert
    existing = Alert.objects.filter(
        student=enrollment.student,
        course=enrollment.course,
        alert_type=Alert.AlertType.DROPOUT_RISK,
        status__in=[Alert.Status.ACTIVE, Alert.Status.ACKNOWLEDGED]
    ).exists()
    
    if not existing:
        # SEVERITY is determined from RISK_LEVEL
        # HIGH risk_level -> HIGH severity alert
        # CRITICAL risk_level -> CRITICAL severity alert
        severity = Alert.Severity.CRITICAL if risk_level == 'CRITICAL' else Alert.Severity.HIGH
        
        alert = Alert.objects.create(
            teacher=enrollment.course.teacher,
            student=enrollment.student,
            course=enrollment.course,
            enrollment=enrollment,
            alert_type=Alert.AlertType.DROPOUT_RISK,
            severity=severity,
            title=f"Dropout Risk: {enrollment.student.display_name}",
            message=cls._generate_dropout_message(enrollment, risk_result),
            recommendation=cls._generate_dropout_recommendation(enrollment, risk_result),
            # ... other fields
        )
```

---

## 4. THE TWO MODELS: risk_level vs severity

### Enrollment Model: `courses/models.py`
```python
risk_level = models.CharField(
    max_length=20,
    choices=[
        ('LOW', 'Low Risk'),
        ('MEDIUM', 'Medium Risk'),
        ('HIGH', 'High Risk'),
        ('CRITICAL', 'Critical Risk'),
        ('UNKNOWN', 'Unknown'),
    ],
    default='UNKNOWN'
)
```

### Alert Model: `analytics/models.py` (Lines 267-340)
```python
class Severity(models.TextChoices):
    CRITICAL = 'CRITICAL', 'Critical'
    HIGH = 'HIGH', 'High'
    MEDIUM = 'MEDIUM', 'Medium'
    LOW = 'LOW', 'Low'
    INFO = 'INFO', 'Informational'

severity = models.CharField(
    max_length=20,
    choices=Severity.choices,
    default=Severity.MEDIUM
)
```

---

## ROOT CAUSE ANALYSIS

### Why Dashboard Shows "High Risk = 0"
1. Dashboard queries: `Enrollment.objects.filter(status='ACTIVE')`
2. Counts enrollments WHERE `risk_level='HIGH'` or `'CRITICAL'`
3. If 0 enrollments have these levels → Dashboard shows 0

### Why Alerts Show "High = 26"
1. Alerts were created with `severity=Alert.Severity.HIGH`
2. Alert creation based on Enrollment.risk_level (which may have been HIGH when alert was created)
3. Alert.severity and Enrollment.risk_level are **INDEPENDENT FIELDS**
4. Even if Enrollment.risk_level changed or was cleared → Alert.severity stays the same

### Possible Scenarios for This Discrepancy

**Scenario 1:** Enrollment risk_level was changed after alerts were created
- Alerts created when enrollment.risk_level='HIGH' → severity='HIGH'
- Later, enrollment.risk_level changed to 'UNKNOWN', 'LOW', 'MEDIUM', or status changed to not 'ACTIVE'
- Dashboard counts 0 HIGH or CRITICAL (filtered for ACTIVE status)
- Alerts still show 26 HIGH (severity never changed)

**Scenario 2:** Enrollment status changed
- Alerts created when enrollment.status='ACTIVE'
- Later, enrollment.status changed to 'DROPPED', 'COMPLETED', 'INACTIVE'
- Dashboard filters: status='ACTIVE' → doesn't see these enrollments
- Alerts still active (not filtered by enrollment.status)

**Scenario 3:** Enrollments were soft-deleted or archived
- Historical alerts remain
- Current ACTIVE enrollments have no HIGH risk level

---

## DEBUGGING STEPS

To find the root cause, check:

```python
# 1. Check if there are HIGH risk enrollments with ACTIVE status
Enrollment.objects.filter(
    status='ACTIVE',
    risk_level__in=['HIGH', 'CRITICAL']
).count()

# 2. Check HIGH severity alerts
Alert.objects.filter(
    teacher=teacher,
    severity='HIGH',
    status__in=['ACTIVE', 'ACKNOWLEDGED']
).count()

# 3. For each HIGH severity alert, check the enrollment status and risk_level
alerts_high = Alert.objects.filter(
    severity='HIGH'
).select_related('enrollment').values(
    'id', 'enrollment__risk_level', 'enrollment__status'
)
for alert in alerts_high:
    print(f"Alert {alert['id']}: enrollment.risk_level={alert['enrollment__risk_level']}, status={alert['enrollment__status']}")

# 4. Check if enrollment risk_level was updated after alerts were created
alert_with_enrollment = Alert.objects.filter(
    severity='HIGH'
).select_related('enrollment').first()
print(f"Alert generated_at: {alert_with_enrollment.generated_at}")
print(f"Enrollment updated_at: {alert_with_enrollment.enrollment.updated_at if hasattr(alert_with_enrollment.enrollment, 'updated_at') else 'N/A'}")
```

---

## SUMMARY TABLE

| Metric | Dashboard | Alerts | Source |
|--------|-----------|--------|--------|
| **Data Source** | Enrollment.risk_level | Alert.severity | Two independent fields |
| **Filter** | status='ACTIVE' | status IN (ACTIVE, ACKNOWLEDGED) | Independent filtering |
| **Query** | `Enrollment.filter(risk_level='HIGH')` | `Alert.filter(severity='HIGH')` | Independent queries |
| **Value Example** | 0 HIGH | 26 HIGH | Mismatch = Data inconsistency |
| **Root Cause** | Enrollments don't have HIGH risk_level | Alerts were created with HIGH severity | Historical data vs current state |
