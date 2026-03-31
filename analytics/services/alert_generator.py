"""
Alert Generator Service
Detects at-risk students and generates appropriate alerts
"""
from decimal import Decimal
from django.utils import timezone
from django.db.models import Avg
from datetime import timedelta
from courses.models import Enrollment
from analytics.models import Alert
from analytics.services.risk_engine import RiskEngine
from typing import List, Dict, Any, Optional
from assessments.models import QuizAttempt

class AlertGenerator:
    """
    Generates alerts based on risk scores and behavioral patterns
    """
    
    @classmethod
    def check_and_generate_alerts(
        cls,
        enrollment_id: Optional[str] = None,
        course_id: Optional[str] = None,
        recalculate_risk: bool = False,
    ) -> List[Alert]:
        """
        Check for conditions that should trigger alerts
        """
        alerts: List[Alert] = []
        
        # First, clean up old alerts for inactive or improved enrollments
        cls._resolve_old_alerts()
        
        # Get active enrollments to check
        enrollments = Enrollment.objects.filter(
            status=Enrollment.Status.ACTIVE
        ).select_related('student', 'course')
        
        if enrollment_id:
            enrollments = enrollments.filter(id=enrollment_id)
        if course_id:
            enrollments = enrollments.filter(course_id=course_id)
        
        for enrollment in enrollments:
            # Use existing enrollment risk by default to avoid duplicate recalculations/history noise.
            risk_result = cls._get_risk_snapshot(
                enrollment=enrollment,
                recalculate_risk=recalculate_risk,
            )
            
            if not risk_result:
                continue

            # Keep unresolved alerts synchronized with the current enrollment state.
            cls._resolve_stale_enrollment_alerts(enrollment, risk_result)
            
            # Check different alert conditions
            dropout_alerts = cls._check_dropout_risk(enrollment, risk_result)
            if dropout_alerts:
                alerts.extend(dropout_alerts)
                
            performance_alerts = cls._check_performance_drop(enrollment)
            if performance_alerts:
                alerts.extend(performance_alerts)
                
            disengagement_alerts = cls._check_disengagement(enrollment, risk_result)
            if disengagement_alerts:
                alerts.extend(disengagement_alerts)
                
            schedule_alerts = cls._check_behind_schedule(enrollment, risk_result)
            if schedule_alerts:
                alerts.extend(schedule_alerts)
                
            failure_alerts = cls._check_multiple_failures(enrollment)
            if failure_alerts:
                alerts.extend(failure_alerts)
        
        return alerts
    
    @classmethod
    def _resolve_old_alerts(cls) -> int:
        """
        Resolve (close) alerts that are no longer relevant:
        1. Alerts for inactive/missing enrollments
        2. HIGH/CRITICAL alerts where enrollment risk is no longer HIGH/CRITICAL
        3. Any risk alert where enrollment risk is now LOW
        Returns count of resolved alerts
        """
        resolved_count = 0

        # 0) Collapse duplicate unresolved alerts (same student/course/type).
        duplicate_candidates = Alert.objects.filter(
            status__in=[Alert.Status.ACTIVE, Alert.Status.ACKNOWLEDGED],
            alert_type__in=[
                Alert.AlertType.DROPOUT_RISK,
                Alert.AlertType.PERFORMANCE_DROP,
                Alert.AlertType.DISENGAGEMENT,
                Alert.AlertType.MULTIPLE_FAILURES,
                Alert.AlertType.BEHIND_SCHEDULE,
            ],
        ).order_by('-generated_at')

        seen_keys = set()
        for alert in duplicate_candidates:
            key = (str(alert.student_id), str(alert.course_id or ''), alert.alert_type)
            if key in seen_keys:
                alert.status = Alert.Status.RESOLVED
                alert.resolved_at = timezone.now()
                alert.intervention_outcome = "Auto-resolved duplicate alert"
                alert.save(update_fields=['status', 'resolved_at', 'intervention_outcome'])
                resolved_count += 1
                continue
            seen_keys.add(key)
        
        old_alerts = Alert.objects.filter(
            status__in=[Alert.Status.ACTIVE, Alert.Status.ACKNOWLEDGED],
            alert_type__in=[
                Alert.AlertType.DROPOUT_RISK,
                Alert.AlertType.PERFORMANCE_DROP,
                Alert.AlertType.DISENGAGEMENT,
                Alert.AlertType.MULTIPLE_FAILURES,
                Alert.AlertType.BEHIND_SCHEDULE,
            ],
        ).select_related('enrollment', 'student', 'course')
        
        for alert in old_alerts:
            should_resolve = False
            reason = None
            enrollment = alert.enrollment

            # Backfill missing enrollment relation for older records.
            if enrollment is None and alert.student_id and alert.course_id:
                enrollment = Enrollment.objects.filter(
                    student_id=alert.student_id,
                    course_id=alert.course_id,
                ).order_by('-updated_at').first()
                if enrollment and alert.enrollment_id is None:
                    alert.enrollment = enrollment
                    alert.save(update_fields=['enrollment'])
            
            if enrollment is None:
                should_resolve = True
                reason = "No matching enrollment found"
            elif enrollment.status != Enrollment.Status.ACTIVE:
                should_resolve = True
                reason = f"Enrollment status changed to {enrollment.status}"
            else:
                current_risk = (enrollment.risk_level or 'UNKNOWN').upper()

                # Dropout risk alerts should only exist when student is High/Critical risk.
                if (
                    alert.alert_type == Alert.AlertType.DROPOUT_RISK and
                    current_risk not in ['HIGH', 'CRITICAL']
                ):
                    should_resolve = True
                    reason = f"Dropout risk no longer high/critical (current: {current_risk})"

                # High/critical severity alerts should not linger when risk has improved.
                elif (
                    alert.severity in [Alert.Severity.HIGH, Alert.Severity.CRITICAL] and
                    current_risk not in ['HIGH', 'CRITICAL']
                ):
                    should_resolve = True
                    reason = f"Severe alert no longer matched by current risk level ({current_risk})"

                # All risk alerts are stale when current risk is LOW.
                elif current_risk == 'LOW':
                    should_resolve = True
                    reason = "Risk improved to LOW"
            
            if should_resolve:
                alert.status = Alert.Status.RESOLVED
                alert.resolved_at = timezone.now()
                alert.intervention_outcome = reason or "Auto-resolved"
                alert.save(update_fields=['status', 'resolved_at', 'intervention_outcome'])
                resolved_count += 1
        
        return resolved_count

    @classmethod
    def _get_risk_snapshot(cls, enrollment: Enrollment, recalculate_risk: bool) -> Optional[Dict[str, Any]]:
        """Return a risk payload compatible with alert checks."""
        if recalculate_risk:
            return RiskEngine.calculate_student_risk(str(enrollment.id))

        progress_pct = float(enrollment.progress_percentage or 0)
        quiz_pct = float(enrollment.average_quiz_score or 0)
        days_inactive = max(0, int(enrollment.days_since_last_activity))

        recency_score = max(0.0, 1.0 - (days_inactive / 14.0))
        completion_rate = max(0.0, min(1.0, progress_pct / 100.0))
        quiz_rate = max(0.0, min(1.0, quiz_pct / 100.0))
        engagement_pct = (recency_score * 40.0) + (completion_rate * 30.0) + (quiz_rate * 30.0)

        return {
            'risk_score': float(enrollment.risk_score or 0),
            'risk_level': (enrollment.risk_level or 'UNKNOWN').upper(),
            'components': {
                'performance': quiz_pct,
                'progress': progress_pct,
                'engagement': round(engagement_pct, 1),
                'days_inactive': days_inactive,
            },
        }

    @classmethod
    def _resolve_stale_enrollment_alerts(cls, enrollment: Enrollment, risk_result: Dict[str, Any]) -> int:
        """
        Resolve unresolved alerts for this enrollment when severity no longer matches current risk.
        """
        unresolved = Alert.objects.filter(
            enrollment=enrollment,
            status__in=[Alert.Status.ACTIVE, Alert.Status.ACKNOWLEDGED],
            alert_type__in=[
                Alert.AlertType.DROPOUT_RISK,
                Alert.AlertType.PERFORMANCE_DROP,
                Alert.AlertType.DISENGAGEMENT,
                Alert.AlertType.MULTIPLE_FAILURES,
                Alert.AlertType.BEHIND_SCHEDULE,
            ],
        )
        current_risk = (risk_result.get('risk_level') or 'UNKNOWN').upper()
        resolved = 0
        for alert in unresolved:
            should_resolve = False

            # Dropout risk only makes sense when high/critical.
            if alert.alert_type == Alert.AlertType.DROPOUT_RISK and current_risk not in ['HIGH', 'CRITICAL']:
                should_resolve = True
            # High severity alerts should not remain when student is not high/critical risk.
            elif alert.severity in [Alert.Severity.HIGH, Alert.Severity.CRITICAL] and current_risk not in ['HIGH', 'CRITICAL']:
                should_resolve = True
            # If risk is low, resolve all active risk alerts.
            elif current_risk == 'LOW':
                should_resolve = True

            if should_resolve:
                alert.status = Alert.Status.RESOLVED
                alert.resolved_at = timezone.now()
                alert.intervention_outcome = f"Auto-resolved after risk update ({current_risk})"
                alert.save(update_fields=['status', 'resolved_at', 'intervention_outcome'])
                resolved += 1
        return resolved
    
    @classmethod
    def _check_dropout_risk(cls, enrollment: Enrollment, risk_result: Dict[str, Any]) -> List[Alert]:
        """
        Generate dropout risk alert for high-risk students
        """
        alerts: List[Alert] = []
        
        risk_level = risk_result['risk_level']
        risk_score = risk_result['risk_score']
        
        if risk_level in ['HIGH', 'CRITICAL']:
            # Check if already have active alert or very recent duplicate.
            existing = Alert.objects.filter(
                student=enrollment.student,
                course=enrollment.course,
                alert_type=Alert.AlertType.DROPOUT_RISK,
                status__in=[Alert.Status.ACTIVE, Alert.Status.ACKNOWLEDGED]
            ).exists() or cls._has_recent_alert(
                enrollment=enrollment,
                alert_type=Alert.AlertType.DROPOUT_RISK,
                cooldown_minutes=180,
            )
            
            if not existing:
                # Determine severity
                severity = Alert.Severity.CRITICAL if risk_level == 'CRITICAL' else Alert.Severity.HIGH
                
                # Create alert
                alert = Alert.objects.create(
                    teacher=enrollment.course.teacher,
                    student=enrollment.student,
                    course=enrollment.course,
                    enrollment=enrollment,
                    alert_type=Alert.AlertType.DROPOUT_RISK,
                    severity=severity,
                    title=f"Dropout Risk: {enrollment.student.display_name}",  # type: ignore
                    message=cls._generate_dropout_message(enrollment, risk_result),
                    recommendation=cls._generate_dropout_recommendation(enrollment, risk_result),
                    risk_score=Decimal(str(risk_score)),
                    engagement_score=Decimal(str(risk_result['components']['engagement'] / 100)),
                    progress_percentage=enrollment.progress_percentage
                )
                alerts.append(alert)
        
        return alerts
    
    @classmethod
    def _check_performance_drop(cls, enrollment: Enrollment) -> List[Alert]:
        """
        Check for significant drop in quiz performance
        """
        alerts: List[Alert] = []
        
        # Get recent attempts (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_attempts = QuizAttempt.objects.filter(
            student=enrollment.student,
            quiz__lesson__module__course=enrollment.course,
            submitted_at__gte=thirty_days_ago,
            status=QuizAttempt.Status.COMPLETED
        ).order_by('-submitted_at')
        
        if recent_attempts.count() >= 2:
            # Compare most recent with average of previous
            latest = recent_attempts.first()
            previous = recent_attempts[1:]
            
            if previous and latest:
                prev_avg = previous.aggregate(Avg('score_percentage'))['score_percentage__avg']
                
                if prev_avg and latest.score_percentage and latest.score_percentage < prev_avg - 20:  # Drop of 20+ points
                    # Check if alert already exists
                    existing = Alert.objects.filter(
                        student=enrollment.student,
                        course=enrollment.course,
                        alert_type=Alert.AlertType.PERFORMANCE_DROP,
                        status__in=[Alert.Status.ACTIVE, Alert.Status.ACKNOWLEDGED],
                        generated_at__gte=thirty_days_ago
                    ).exists() or cls._has_recent_alert(
                        enrollment=enrollment,
                        alert_type=Alert.AlertType.PERFORMANCE_DROP,
                        cooldown_minutes=180,
                    )
                    
                    if not existing:
                        alert = Alert.objects.create(
                            teacher=enrollment.course.teacher,
                            student=enrollment.student,
                            course=enrollment.course,
                            enrollment=enrollment,
                            alert_type=Alert.AlertType.PERFORMANCE_DROP,
                            severity=Alert.Severity.MEDIUM,
                            title=f"Performance Drop: {enrollment.student.display_name}",  # type: ignore
                            message=f"Quiz score dropped from {prev_avg:.1f}% to {latest.score_percentage:.1f}%",
                            recommendation="Review recent quiz questions and offer additional practice.",
                            progress_percentage=enrollment.progress_percentage
                        )
                        alerts.append(alert)
        
        return alerts
    
    @classmethod
    def _check_disengagement(cls, enrollment: Enrollment, risk_result: Dict[str, Any]) -> List[Alert]:
        """
        Check for disengagement (inactivity + low engagement)
        """
        alerts: List[Alert] = []
        
        days_inactive = enrollment.days_since_last_activity
        engagement_score = risk_result['components']['engagement']
        
        if days_inactive >= 7 and engagement_score < 30:  # 30% threshold
            existing = Alert.objects.filter(
                student=enrollment.student,
                course=enrollment.course,
                alert_type=Alert.AlertType.DISENGAGEMENT,
                status__in=[Alert.Status.ACTIVE, Alert.Status.ACKNOWLEDGED]
            ).exists() or cls._has_recent_alert(
                enrollment=enrollment,
                alert_type=Alert.AlertType.DISENGAGEMENT,
                cooldown_minutes=180,
            )
            
            if not existing:
                risk_level = (risk_result.get('risk_level') or '').upper()
                if days_inactive >= 14 and risk_level in ['HIGH', 'CRITICAL']:
                    severity = Alert.Severity.HIGH
                else:
                    severity = Alert.Severity.MEDIUM
                
                alert = Alert.objects.create(
                    teacher=enrollment.course.teacher,
                    student=enrollment.student,
                    course=enrollment.course,
                    enrollment=enrollment,
                    alert_type=Alert.AlertType.DISENGAGEMENT,
                    severity=severity,
                    title=f"Student Disengaged: {enrollment.student.display_name}",  # type: ignore
                    message=f"No activity for {days_inactive} days. Engagement score: {engagement_score:.1f}%",
                    recommendation="Send a check-in message and offer support.",
                    engagement_score=Decimal(str(engagement_score / 100)),
                    progress_percentage=enrollment.progress_percentage
                )
                alerts.append(alert)
        
        return alerts
    
    @classmethod
    def _check_behind_schedule(cls, enrollment: Enrollment, risk_result: Dict[str, Any]) -> List[Alert]:
        """
        Check if student is significantly behind schedule
        """
        alerts: List[Alert] = []
        
        # Avoid generating behind-schedule alerts for LOW-risk snapshots.
        current_risk_level = (risk_result.get('risk_level') or '').upper()
        if current_risk_level == 'LOW':
            return alerts

        progress_score = float(risk_result['components']['progress'])
        expected_progress = cls._get_expected_progress(enrollment)
        progress_deficit = float(expected_progress) - float(enrollment.progress_percentage or 0)
        
        # Require a meaningful deficit to reduce noisy repeats.
        if progress_score < expected_progress and float(enrollment.progress_percentage) < expected_progress and progress_deficit >= 8:
            severity = (
                Alert.Severity.HIGH
                if progress_deficit >= 25 and current_risk_level in ['HIGH', 'CRITICAL']
                else Alert.Severity.MEDIUM
            )
            active_alert = Alert.objects.filter(
                student=enrollment.student,
                course=enrollment.course,
                alert_type=Alert.AlertType.BEHIND_SCHEDULE,
                status__in=[Alert.Status.ACTIVE, Alert.Status.ACKNOWLEDGED]
            ).order_by('-generated_at').first()

            if active_alert:
                previous_progress = float(active_alert.progress_percentage or 0)
                previous_deficit = float(expected_progress) - previous_progress
                severity_changed = active_alert.severity != severity
                deficit_changed = abs(progress_deficit - previous_deficit) > 5

                # Keep a single active alert row; refresh only when signal materially changes.
                if severity_changed or deficit_changed:
                    active_alert.severity = severity
                    active_alert.message = (
                        f"Behind schedule: {enrollment.progress_percentage:.1f}% completed vs expected {expected_progress:.1f}% for the course timeline."
                    )
                    active_alert.recommendation = "Consider adjusting deadlines or providing catch-up resources."
                    active_alert.progress_percentage = enrollment.progress_percentage
                    active_alert.generated_at = timezone.now()
                    active_alert.save(
                        update_fields=[
                            'severity',
                            'message',
                            'recommendation',
                            'progress_percentage',
                            'generated_at',
                        ]
                    )
                return alerts

            if cls._has_recent_alert(
                enrollment=enrollment,
                alert_type=Alert.AlertType.BEHIND_SCHEDULE,
                cooldown_minutes=60,
            ):
                return alerts

            alert = Alert.objects.create(
                teacher=enrollment.course.teacher,
                student=enrollment.student,
                course=enrollment.course,
                enrollment=enrollment,
                alert_type=Alert.AlertType.BEHIND_SCHEDULE,
                severity=severity,
                title=f"Behind Schedule: {enrollment.student.display_name}",  # type: ignore
                message=(
                    f"Behind schedule: {enrollment.progress_percentage:.1f}% completed vs expected {expected_progress:.1f}% for course timeline."
                ),
                recommendation="Consider adjusting deadlines or providing catch-up resources.",
                progress_percentage=enrollment.progress_percentage
            )
            alerts.append(alert)
        
        return alerts
    
    @classmethod
    def _check_multiple_failures(cls, enrollment: Enrollment) -> List[Alert]:
        """
        Check for multiple failed quiz attempts
        """
        alerts: List[Alert] = []
        
        # Get failed attempts in last 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)
        failed_attempts = QuizAttempt.objects.filter(
            student=enrollment.student,
            quiz__lesson__module__course=enrollment.course,
            submitted_at__gte=thirty_days_ago,
            status=QuizAttempt.Status.COMPLETED,
            passed=False
        ).count()
        
        if failed_attempts >= 3:
            existing = Alert.objects.filter(
                student=enrollment.student,
                course=enrollment.course,
                alert_type=Alert.AlertType.MULTIPLE_FAILURES,
                status__in=[Alert.Status.ACTIVE, Alert.Status.ACKNOWLEDGED],
                generated_at__gte=thirty_days_ago
            ).exists() or cls._has_recent_alert(
                enrollment=enrollment,
                alert_type=Alert.AlertType.MULTIPLE_FAILURES,
                cooldown_minutes=720,
            )
            
            if not existing:
                alert = Alert.objects.create(
                    teacher=enrollment.course.teacher,
                    student=enrollment.student,
                    course=enrollment.course,
                    enrollment=enrollment,
                    alert_type=Alert.AlertType.MULTIPLE_FAILURES,
                    severity=Alert.Severity.MEDIUM,
                    title=f"Multiple Quiz Failures: {enrollment.student.display_name}",  # type: ignore
                    message=f"{failed_attempts} failed quiz attempts in the last 30 days",
                    recommendation="Identify difficult topics and offer remedial instruction.",
                    progress_percentage=enrollment.progress_percentage
                )
                alerts.append(alert)
        
        return alerts
    
    @classmethod
    def _generate_dropout_message(cls, enrollment: Enrollment, risk_result: Dict[str, Any]) -> str:
        """Generate detailed dropout risk message"""
        days_inactive = enrollment.days_since_last_activity
        progress = enrollment.progress_percentage
        engagement = risk_result['components']['engagement']
        
        message = f"Student at {risk_result['risk_level']} risk of dropout. "
        message += f"Progress: {progress:.1f}%, "
        
        if days_inactive > 0:
            message += f"Inactive for {days_inactive} days, "
        
        if engagement < 50:
            message += f"Engagement score: {engagement:.1f}%, "
        
        message += f"Quiz average: {enrollment.average_quiz_score:.1f}%"
        
        return message

    @classmethod
    def _has_recent_alert(cls, enrollment: Enrollment, alert_type: str, cooldown_minutes: int = 120) -> bool:
        """
        Protect against rapid alert spam for the same student/course/type.
        Includes recently resolved alerts to prevent resolve/recreate loops.
        """
        cutoff = timezone.now() - timedelta(minutes=max(1, cooldown_minutes))
        return Alert.objects.filter(
            student=enrollment.student,
            course=enrollment.course,
            alert_type=alert_type,
            generated_at__gte=cutoff,
            status__in=[Alert.Status.ACTIVE, Alert.Status.ACKNOWLEDGED, Alert.Status.RESOLVED],
        ).exists()
    
    @classmethod
    def _generate_dropout_recommendation(cls, enrollment: Enrollment, risk_result: Dict[str, Any]) -> str:
        """Generate recommendation based on risk factors"""
        recommendations = []
        
        if enrollment.days_since_last_activity > 7:
            recommendations.append("Send personalized check-in email")
        
        if risk_result['components']['performance'] < 60:
            recommendations.append("Schedule one-on-one tutoring session")
        
        if risk_result['components']['progress'] < 50:
            recommendations.append("Consider deadline extension")
        
        if risk_result['components']['engagement'] < 30:
            recommendations.append("Increase communication frequency")
        
        if not recommendations:
            recommendations.append("Review student progress and offer encouragement")
        
        return " | ".join(recommendations)

    @classmethod
    def _get_expected_progress(cls, enrollment: Enrollment) -> float:
        """
        Estimate expected progress percentage using course timeline when available.
        Falls back to 50% for untimed courses.
        """
        course = enrollment.course
        today = timezone.now().date()
        if course.start_date and course.end_date and course.end_date > course.start_date:
            total_days = max(1, (course.end_date - course.start_date).days)
            elapsed_days = (today - course.start_date).days
            elapsed_days = max(0, min(elapsed_days, total_days))
            expected = (elapsed_days / total_days) * 100.0
            # Keep target practical for active monitoring.
            return max(10.0, min(90.0, expected))
        return 50.0
    
    @classmethod
    def get_active_alerts(cls, teacher_id: Optional[str] = None, course_id: Optional[str] = None) -> List[Alert]:
        """
        Get all active alerts, optionally filtered
        """
        alerts = Alert.objects.filter(
            status__in=[Alert.Status.ACTIVE, Alert.Status.ACKNOWLEDGED]
        ).select_related('student', 'course', 'teacher')
        
        if teacher_id:
            alerts = alerts.filter(teacher_id=teacher_id)
        if course_id:
            alerts = alerts.filter(course_id=course_id)
        
        return alerts.order_by('-severity', 'generated_at')
    
    @classmethod
    def resolve_old_alerts(cls, days: int = 30) -> int:
        """
        Auto-resolve alerts that are older than specified days
        """
        cutoff = timezone.now() - timedelta(days=days)
        old_alerts = Alert.objects.filter(
            status__in=[Alert.Status.ACTIVE, Alert.Status.ACKNOWLEDGED],
            generated_at__lt=cutoff
        )
        
        count = old_alerts.update(
            status=Alert.Status.EXPIRED,
            resolved_at=timezone.now()
        )
        
        return count
