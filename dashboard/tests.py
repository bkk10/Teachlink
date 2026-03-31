from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model


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
