"""
Context processors for dashboard templates
Provides navigation menus and counts
"""
import logging

from django.utils import timezone
from django.db.models import Avg
from analytics.models import Alert
from courses.models import Enrollment

logger = logging.getLogger(__name__)


def navigation_context(request):
    """Add navigation menu and counts to template context"""
    context = {}

    if request.user.is_authenticated:
        try:
            _apply_navigation_counts(request, context)
        except Exception:
            logger.exception('navigation_context failed')
            context.setdefault('alert_count', 0)
            context.setdefault('unread_count', 0)
    return context


def _apply_navigation_counts(request, context):
    if request.user.is_teacher:
        context['alert_count'] = Alert.objects.filter(
            teacher=request.user,
            status__in=['ACTIVE', 'ACKNOWLEDGED']
        ).count()

    if request.user.is_student:
        active_enrollments = Enrollment.objects.filter(
            student=request.user,
            status='ACTIVE'
        ).select_related('course')
        context['student_active_courses'] = active_enrollments.count()
        context['student_avg_progress'] = round(
            float(active_enrollments.aggregate(avg=Avg('progress_percentage'))['avg'] or 0), 1
        )

        total_active = active_enrollments.count()
        unpaid_count = active_enrollments.filter(is_fee_paid=False).count()

        if total_active == 0:
            payment_status = "No Active Courses"
            payment_tone = "secondary"
        elif unpaid_count == 0:
            payment_status = "Paid"
            payment_tone = "success"
        elif unpaid_count == total_active:
            payment_status = "Not Paid"
            payment_tone = "danger"
        else:
            payment_status = "Partially Paid"
            payment_tone = "warning"
        unpaid_courses = list(
            active_enrollments.filter(is_fee_paid=False)
            .values_list('course__title', flat=True)
        )

        upcoming = active_enrollments.filter(
            course__end_date__isnull=False,
            course__end_date__gte=timezone.now().date()
        ).order_by('course__end_date').first()

        upcoming_deadline = None
        if upcoming and upcoming.course.end_date:
            upcoming_deadline = {
                'course_title': upcoming.course.title,
                'days_left': (upcoming.course.end_date - timezone.now().date()).days
            }

        risk_rank = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3, 'CRITICAL': 4, 'UNKNOWN': 0}
        reverse_risk = {v: k for k, v in risk_rank.items()}
        highest_risk_value = 0
        for level in active_enrollments.values_list('risk_level', flat=True):
            highest_risk_value = max(highest_risk_value, risk_rank.get(level, 0))
        risk_level = reverse_risk.get(highest_risk_value, 'UNKNOWN')
        risk_tone = {
            'LOW': 'success',
            'MEDIUM': 'warning',
            'HIGH': 'danger',
            'CRITICAL': 'danger',
            'UNKNOWN': 'secondary'
        }.get(risk_level, 'secondary')

        context['student_payment_status'] = payment_status
        context['student_payment_tone'] = payment_tone
        context['student_unpaid_count'] = unpaid_count
        context['student_unpaid_courses'] = unpaid_courses
        context['student_upcoming_deadline'] = upcoming_deadline
        context['student_risk_snapshot'] = risk_level
        context['student_risk_tone'] = risk_tone
        unread_alerts = Alert.objects.filter(
            student=request.user,
            status=Alert.Status.ACTIVE
        ).select_related('course').order_by('-generated_at')
        deduped_unread = []
        seen_keys = set()
        for alert in unread_alerts[:200]:
            key = (str(alert.course_id or ''), alert.alert_type)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            deduped_unread.append(alert)
        context['unread_count'] = len(deduped_unread)
        latest_unread = deduped_unread[0] if deduped_unread else None
        context['latest_unread_title'] = latest_unread.title if latest_unread else ''
        context['latest_unread_course'] = latest_unread.course.title if latest_unread and latest_unread.course else ''
