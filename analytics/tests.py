from django.test import TestCase
from analytics.services.difficulty_analyzer import DifficultyAnalyzer
from django.contrib.auth import get_user_model
from courses.models import Course, Enrollment
from analytics.models import Alert
from analytics.services.alert_generator import AlertGenerator
from decimal import Decimal

User = get_user_model()


class DifficultyClassificationTests(TestCase):
	def test_weighted_thresholds_classification(self):
		# Scores below 0.30 should be LOW
		self.assertEqual(DifficultyAnalyzer._determine_difficulty_classification(0.0), 'LOW')
		self.assertEqual(DifficultyAnalyzer._determine_difficulty_classification(0.29), 'LOW')
		# Scores between 0.30 and 0.59 should be MEDIUM
		self.assertEqual(DifficultyAnalyzer._determine_difficulty_classification(0.30), 'MEDIUM')
		self.assertEqual(DifficultyAnalyzer._determine_difficulty_classification(0.59), 'MEDIUM')
		# Scores 0.60 and above should be HIGH
		self.assertEqual(DifficultyAnalyzer._determine_difficulty_classification(0.60), 'HIGH')
		self.assertEqual(DifficultyAnalyzer._determine_difficulty_classification(1.0), 'HIGH')

	def test_failure_rate_classification(self):
		self.assertEqual(DifficultyAnalyzer._determine_difficulty_from_failure_rate(0.0), 'LOW')
		self.assertEqual(DifficultyAnalyzer._determine_difficulty_from_failure_rate(0.29), 'LOW')
		self.assertEqual(DifficultyAnalyzer._determine_difficulty_from_failure_rate(0.30), 'MEDIUM')
		self.assertEqual(DifficultyAnalyzer._determine_difficulty_from_failure_rate(0.59), 'MEDIUM')
		self.assertEqual(DifficultyAnalyzer._determine_difficulty_from_failure_rate(0.60), 'HIGH')


class AlertResolutionTests(TestCase):
	def setUp(self):
		self.teacher = User.objects.create_user(
			email='teacher@example.com',
			username='teacher',
			display_name='Teacher One',
			role='TEACHER',
			password='pass'
		)
		self.student = User.objects.create_user(
			email='student@example.com',
			username='student',
			display_name='Student One',
			role='STUDENT',
			password='pass'
		)
		self.course = Course.objects.create(
			title='Test Course',
			teacher=self.teacher
		)
		self.enrollment = Enrollment.objects.create(
			student=self.student,
			course=self.course,
			progress_percentage=Decimal('20.00'),
			average_quiz_score=Decimal('50.00'),
			risk_score=Decimal('0.80'),
			risk_level='HIGH'
		)

	def test_dropout_alert_auto_resolve_on_risk_improvement(self):
		# Create an active dropout alert
		alert = Alert.objects.create(
			teacher=self.teacher,
			student=self.student,
			course=self.course,
			enrollment=self.enrollment,
			alert_type=Alert.AlertType.DROPOUT_RISK,
			severity=Alert.Severity.HIGH,
			status=Alert.Status.ACTIVE,
			title='Test Dropout',
			message='At risk',
		)

		# Now simulate risk improving on enrollment
		self.enrollment.risk_level = 'LOW'
		self.enrollment.save(update_fields=['risk_level'])

		resolved_count = AlertGenerator._resolve_old_alerts()
		alert.refresh_from_db()
		self.assertEqual(alert.status, Alert.Status.RESOLVED)
		self.assertGreaterEqual(resolved_count, 1)
