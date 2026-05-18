from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from unittest.mock import patch
from courses.models import Course


class DashboardAuthFlowTests(TestCase):
    def setUp(self):
        self.User = get_user_model()

    def test_register_page_loads(self):
        response = self.client.get(reverse('dashboard_register'))
        self.assertEqual(response.status_code, 200)

    def test_register_student_success(self):
        response = self.client.post(reverse('dashboard_register'), {
            'email': 'new.student@example.com',
            'username': 'newstudent',
            'display_name': 'New Student',
            'role': 'STUDENT',
            'password': 'StrongPass123!',
            'password_confirm': 'StrongPass123!',
        })
        self.assertRedirects(response, reverse('student_dashboard'))
        self.assertTrue(self.User.objects.filter(email='new.student@example.com').exists())

    def test_profile_update(self):
        user = self.User.objects.create_user(
            email='teacher.profile@example.com',
            username='teacherprofile',
            display_name='Teacher Profile',
            role='TEACHER',
            password='StrongPass123!',
        )
        self.client.force_login(user)

        response = self.client.post(reverse('dashboard_profile'), {
            'action': 'profile',
            'display_name': 'Teacher Updated',
            'bio': 'Updated bio text',
        })
        self.assertRedirects(response, reverse('dashboard_profile'))

        user.refresh_from_db()
        self.assertEqual(user.display_name, 'Teacher Updated')
        self.assertEqual(user.bio, 'Updated bio text')

    def test_password_change(self):
        user = self.User.objects.create_user(
            email='student.password@example.com',
            username='studentpassword',
            display_name='Student Password',
            role='STUDENT',
            password='StrongPass123!',
        )
        self.client.force_login(user)

        response = self.client.post(reverse('dashboard_profile'), {
            'action': 'password',
            'old_password': 'StrongPass123!',
            'new_password': 'NewStrongPass123!',
            'confirm_password': 'NewStrongPass123!',
        })
        self.assertRedirects(response, reverse('dashboard_profile'))

        user.refresh_from_db()
        self.assertTrue(user.check_password('NewStrongPass123!'))

    def test_demo_login_get_redirects_to_custom_login(self):
        response = self.client.get(reverse('demo_login'))
        self.assertRedirects(response, reverse('custom_login'))

    def test_demo_login_teacher_success(self):
        self.User.objects.create_user(
            email='demo.teacher@teachlink.com',
            username='demo_teacher_test',
            display_name='Demo Teacher',
            role='TEACHER',
            password='StrongPass123!',
            is_active=True,
        )
        response = self.client.post(reverse('demo_login'), {'role': 'TEACHER'})
        self.assertRedirects(response, reverse('teacher_dashboard'))

    def test_demo_login_student_success(self):
        self.User.objects.create_user(
            email='demo.student01@teachlink.com',
            username='demo_student_test',
            display_name='Demo Student',
            role='STUDENT',
            password='StrongPass123!',
            is_active=True,
        )
        response = self.client.post(reverse('demo_login'), {'role': 'STUDENT'})
        self.assertRedirects(response, reverse('student_dashboard'))

    def test_demo_login_handles_internal_error(self):
        self.User.objects.create_user(
            email='demo.teacher@teachlink.com',
            username='demo_teacher_err',
            display_name='Demo Teacher',
            role='TEACHER',
            password='StrongPass123!',
            is_active=True,
        )
        with patch('dashboard.views._login_and_redirect_by_role', side_effect=Exception('boom')):
            response = self.client.post(reverse('demo_login'), {'role': 'TEACHER'})
        self.assertRedirects(response, reverse('custom_login'))
        self.assertNotIn('_auth_user_id', self.client.session)


class DashboardApiResilienceTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.teacher = self.User.objects.create_user(
            email='api.teacher@example.com',
            username='apiteacher',
            display_name='API Teacher',
            role='TEACHER',
            password='StrongPass123!',
            is_active=True,
        )
        self.client.force_login(self.teacher)
        self.course = Course.objects.create(
            title='API Course',
            description='Course for API resilience tests',
            teacher=self.teacher,
            status=Course.Status.PUBLISHED,
        )

    @patch('dashboard.views.DifficultyAnalyzer.analyze_course_difficulties', side_effect=Exception('difficulty-write-failed'))
    @patch('dashboard.views.AlertGenerator._resolve_old_alerts', side_effect=Exception('resolve-failed'))
    @patch('dashboard.views.AlertGenerator.check_and_generate_alerts', side_effect=Exception('alert-write-failed'))
    @patch('dashboard.views._is_sqlite_backend', return_value=False)
    def test_teacher_api_survives_refresh_failures(self, _sqlite_mock, _alerts_mock, _resolve_mock, _difficulty_mock):
        response = self.client.get(reverse('teacher_api'))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('kpi', payload)
        self.assertIn('courses', payload)

    @patch('dashboard.views.DifficultyAnalyzer.analyze_course_difficulties', side_effect=Exception('difficulty-write-failed'))
    @patch('dashboard.views._is_sqlite_backend', return_value=False)
    def test_difficulty_api_survives_refresh_failures(self, _sqlite_mock, _difficulty_mock):
        response = self.client.get(reverse('difficulty_api'), {'course_id': str(self.course.id)})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('distribution', payload)
        self.assertIn('hardest_lessons', payload)

    @patch('dashboard.views.AlertGenerator._resolve_old_alerts', side_effect=Exception('resolve-failed'))
    @patch('dashboard.views._is_sqlite_backend', return_value=False)
    def test_alerts_api_survives_resolve_failures(self, _sqlite_mock, _resolve_mock):
        response = self.client.get(reverse('alerts_api'))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('alerts', payload)
        self.assertIn('summary', payload)

    def test_session_login_with_signed_cookie_sessions(self):
        from django.test import RequestFactory
        from dashboard.views import _session_login

        request = RequestFactory().get('/')
        request.session = self.client.session

        with patch('dashboard.views._uses_signed_cookie_sessions', return_value=True):
            with patch('dashboard.views.login') as mock_login:
                _session_login(request, self.teacher)
                mock_login.assert_called_once_with(request, self.teacher)


class DashboardPageFlowTests(TestCase):
    """Smoke-test key teacher and student HTML pages."""

    def setUp(self):
        self.User = get_user_model()

    def _create_demo_teacher(self):
        return self.User.objects.create_user(
            email='flow.teacher@teachlink.com',
            username='flow_teacher',
            display_name='Flow Teacher',
            role='TEACHER',
            password='StrongPass123!',
            is_active=True,
        )

    def _create_demo_student(self):
        return self.User.objects.create_user(
            email='flow.student01@teachlink.com',
            username='flow_student',
            display_name='Flow Student',
            role='STUDENT',
            password='StrongPass123!',
            is_active=True,
        )

    def test_teacher_core_pages_load(self):
        teacher = self._create_demo_teacher()
        Course.objects.create(
            title='Flow Course',
            description='Course for page flow tests',
            teacher=teacher,
            status=Course.Status.PUBLISHED,
        )
        self.client.force_login(teacher)

        for route_name in (
            'teacher_dashboard',
            'dashboard_courses',
            'alerts_center',
            'dashboard_profile',
        ):
            response = self.client.get(reverse(route_name))
            self.assertEqual(response.status_code, 200, msg=route_name)

    def test_student_core_pages_load(self):
        teacher = self._create_demo_teacher()
        student = self._create_demo_student()
        course = Course.objects.create(
            title='Student Flow Course',
            description='Course for student page flow tests',
            teacher=teacher,
            status=Course.Status.PUBLISHED,
        )
        from courses.models import Enrollment
        Enrollment.objects.create(
            student=student,
            course=course,
            status=Enrollment.Status.ACTIVE,
        )
        self.client.force_login(student)

        for route_name in (
            'student_dashboard',
            'dashboard_courses',
            'dashboard_profile',
        ):
            response = self.client.get(reverse(route_name))
            self.assertEqual(response.status_code, 200, msg=route_name)

    @patch('dashboard.views._uses_signed_cookie_sessions', return_value=True)
    def test_teacher_courses_renders_without_static_manifest(self, _signed_mock):
        from django.template.loader import render_to_string

        teacher = self._create_demo_teacher()
        with self.settings(
            STATICFILES_STORAGE='whitenoise.storage.CompressedStaticFilesStorage',
        ):
            html = render_to_string(
                'dashboard/teacher/courses.html',
                {'courses': Course.objects.filter(teacher=teacher)},
            )
        self.assertIn('Course Management', html)


class DemoAccountsTests(TestCase):
    def test_ensure_minimal_demo_accounts_creates_users(self):
        from dashboard.demo_accounts import ensure_minimal_demo_accounts

        User = get_user_model()
        User.objects.filter(email__icontains='demo.').delete()

        created = ensure_minimal_demo_accounts()
        self.assertTrue(created)
        self.assertTrue(User.objects.filter(email='demo.teacher@teachlink.com').exists())
        self.assertTrue(User.objects.filter(email='demo.student01@teachlink.com').exists())

        created_again = ensure_minimal_demo_accounts()
        self.assertFalse(created_again)
