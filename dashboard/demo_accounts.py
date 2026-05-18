"""Ensure demo login accounts exist (lightweight; no course seeding)."""
from __future__ import annotations

import logging

from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)

DEMO_TEACHER_EMAIL = 'demo.teacher@teachlink.com'
DEMO_STUDENT_EMAIL = 'demo.student01@teachlink.com'
DEMO_TEACHER_PASSWORD = 'DemoTeach123!'
DEMO_STUDENT_PASSWORD = 'DemoStudent123!'


def ensure_minimal_demo_accounts() -> bool:
    """
    Create demo teacher/student users when missing.
    Returns True if any account was created.
    """
    User = get_user_model()
    created = False

    if not User.objects.filter(email__iexact=DEMO_TEACHER_EMAIL, is_active=True).exists():
        User.objects.create_user(
            email=DEMO_TEACHER_EMAIL,
            username='demo_teacher',
            display_name='Demo Teacher',
            role='TEACHER',
            password=DEMO_TEACHER_PASSWORD,
            is_active=True,
        )
        created = True
        logger.info('Created minimal demo teacher account')

    if not User.objects.filter(
        role='STUDENT',
        email__istartswith='demo.student',
        email__iendswith='@teachlink.com',
        is_active=True,
    ).exists():
        User.objects.create_user(
            email=DEMO_STUDENT_EMAIL,
            username='demo_student01',
            display_name='Demo Student',
            role='STUDENT',
            password=DEMO_STUDENT_PASSWORD,
            is_active=True,
        )
        created = True
        logger.info('Created minimal demo student account')

    return created
