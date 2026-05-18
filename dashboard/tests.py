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
