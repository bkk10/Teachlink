from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
import random
from typing import Dict, List, Tuple

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Avg, Count
from django.utils import timezone

from analytics.models import Alert, LessonDifficulty, LessonInteraction, RiskHistory
from analytics.services.alert_generator import AlertGenerator
from analytics.services.difficulty_analyzer import DifficultyAnalyzer
from analytics.services.risk_engine import RiskEngine
from assessments.models import Answer, Question, Quiz, QuizAttempt
from courses.models import Course, Enrollment, Lesson, LessonCompletion, Module


class Command(BaseCommand):
    help = "Create a realistic demo classroom with explainable risk, alerts, quiz history, and difficulty signals."

    STUDENT_SPECS = [
        ("BKR", "bkr"),
        ("Amina Yusuf", "amina_yusuf"),
        ("Brian Kibet", "brian_kibet"),
        ("Carol Njeri", "carol_njeri"),
        ("Dennis Otieno", "dennis_otieno"),
        ("Esther Mwangi", "esther_mwangi"),
        ("Faith Achieng", "faith_achieng"),
        ("Kelvin Muli", "kelvin_muli"),
        ("Lydia Chebet", "lydia_chebet"),
        ("Mark Kiptoo", "mark_kiptoo"),
        ("Neema Juma", "neema_juma"),
        ("Peter Barasa", "peter_barasa"),
    ]

    COURSE_BLUEPRINTS = [
        {
            "title": "Demo Course 1",
            "description": "Frontend foundations with practical lessons, quizzes, and recovery support.",
            "start_offset": 28,
            "end_offset": 42,
            "modules": [
                {
                    "title": "Web Basics",
                    "lessons": [
                        "HTML Structure",
                        "Forms and Inputs",
                        "CSS Layout",
                        "Flexbox Practice",
                        "JavaScript Foundations",
                    ],
                },
                {
                    "title": "Applied Build",
                    "lessons": [
                        "DOM Events",
                        "Validation Flows",
                        "Responsive Design",
                        "Accessibility Review",
                        "Mini Project Sprint",
                    ],
                },
            ],
        },
        {
            "title": "Demo Course 2",
            "description": "Data skills with analysis lessons and more demanding assessment recovery patterns.",
            "start_offset": 35,
            "end_offset": 35,
            "modules": [
                {
                    "title": "Data Essentials",
                    "lessons": [
                        "Data Types",
                        "Cleaning Basics",
                        "Spreadsheets",
                        "Charts and Visuals",
                        "Reading Patterns",
                    ],
                },
                {
                    "title": "Applied Analysis",
                    "lessons": [
                        "Descriptive Stats",
                        "Trends and Ratios",
                        "Reporting Findings",
                        "Insight Writing",
                        "Mini Analysis Task",
                    ],
                },
            ],
        },
        {
            "title": "Demo Course 3",
            "description": "Digital study skills focused on retention, reflection, and structured progress.",
            "start_offset": 21,
            "end_offset": 56,
            "modules": [
                {
                    "title": "Learning Habits",
                    "lessons": [
                        "Goal Setting",
                        "Study Planning",
                        "Focused Practice",
                        "Reflection Journals",
                        "Feedback Loops",
                    ],
                },
                {
                    "title": "Execution",
                    "lessons": [
                        "Revision Routine",
                        "Peer Discussion",
                        "Recall Practice",
                        "Progress Review",
                        "Action Plan",
                    ],
                },
            ],
        },
    ]

    PROFILE_PATTERNS = {
        "steady": {
            "completed_lessons": (7, 9),
            "days_inactive": (0, 2),
            "score_bands": [(82, 96), (78, 91), (85, 97)],
            "attempt_plan": [1, 1, 1, 1],
            "login_count": (18, 28),
            "paid": True,
        },
        "recovering": {
            "completed_lessons": (5, 7),
            "days_inactive": (2, 4),
            "score_bands": [(42, 58), (68, 81), (70, 84)],
            "attempt_plan": [2, 2, 1, 1],
            "login_count": (12, 20),
            "paid": True,
        },
        "inconsistent": {
            "completed_lessons": (4, 6),
            "days_inactive": (4, 6),
            "score_bands": [(74, 84), (38, 56), (55, 70)],
            "attempt_plan": [1, 2, 1, 0],
            "login_count": (8, 14),
            "paid": True,
        },
        "at_risk": {
            "completed_lessons": (2, 4),
            "days_inactive": (7, 10),
            "score_bands": [(24, 38), (36, 49), (28, 44)],
            "attempt_plan": [2, 2, 1, 0],
            "login_count": (3, 8),
            "paid": False,
        },
        "critical": {
            "completed_lessons": (1, 2),
            "days_inactive": (12, 18),
            "score_bands": [(8, 22), (18, 31), (0, 12)],
            "attempt_plan": [2, 2, 0, 0],
            "login_count": (1, 3),
            "paid": False,
        },
    }

    QUIZ_PLAN = {
        1: {"published": True, "title_suffix": "Checkpoint", "question_count": 4},
        2: {"published": True, "title_suffix": "Practice Quiz", "question_count": 4},
        4: {"published": True, "title_suffix": "Mastery Quiz", "question_count": 5},
        6: {"published": True, "title_suffix": "Scenario Quiz", "question_count": 4},
        8: {"published": False, "title_suffix": "Extension Quiz", "question_count": 3},
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "--fresh",
            action="store_true",
            help="Delete existing demo teacher/students and rebuild the demo classroom from scratch.",
        )
        parser.add_argument(
            "--students",
            type=int,
            default=12,
            help="Number of demo students to create (max 12).",
        )

    def handle(self, *args, **options):
        random.seed(20260330)
        student_count = max(6, min(int(options["students"]), len(self.STUDENT_SPECS)))

        if options["fresh"]:
            self._purge_existing_demo_data()

        teacher = self._ensure_teacher()
        students = self._ensure_students(student_count)
        courses = self._ensure_courses_and_content(teacher)

        self._clear_demo_activity(courses, students)
        self._seed_learning_activity(courses, students)
        self._refresh_demo_analytics(courses)
        self._print_seed_summary(courses)

        self.stdout.write(self.style.SUCCESS("Demo classroom created/updated successfully."))
        self.stdout.write(self.style.WARNING("Login Credentials"))
        self.stdout.write("Teacher: demo.teacher@teachlink.com / DemoTeach123!")
        self.stdout.write("Students: demo.student01@teachlink.com ... / DemoStudent123!")

    def _purge_existing_demo_data(self) -> None:
        User = get_user_model()
        demo_students = User.objects.filter(email__startswith="demo.student")
        demo_teacher = User.objects.filter(email="demo.teacher@teachlink.com")
        demo_teacher.delete()
        demo_students.delete()

    def _ensure_teacher(self):
        User = get_user_model()
        teacher, _ = User.objects.get_or_create(
            email="demo.teacher@teachlink.com",
            defaults={
                "username": "demo_teacher",
                "display_name": "Demo Teacher",
                "role": "TEACHER",
                "is_active": True,
                "email_verified": True,
            },
        )
        teacher.set_password("DemoTeach123!")
        teacher.save()
        return teacher

    def _ensure_students(self, count: int):
        User = get_user_model()
        students = []
        for index, (display_name, username) in enumerate(self.STUDENT_SPECS[:count], start=1):
            email = f"demo.student{index:02d}@teachlink.com"
            student, _ = User.objects.get_or_create(
                email=email,
                defaults={
                    "username": username,
                    "display_name": display_name,
                    "role": "STUDENT",
                    "is_active": True,
                    "email_verified": True,
                },
            )
            student.display_name = display_name
            student.username = username
            student.role = "STUDENT"
            student.is_active = True
            student.email_verified = True
            student.set_password("DemoStudent123!")
            student.save()
            students.append(student)
        return students

    def _ensure_courses_and_content(self, teacher) -> List[Course]:
        courses: List[Course] = []
        today = timezone.now().date()

        for blueprint in self.COURSE_BLUEPRINTS:
            course, _ = Course.objects.get_or_create(
                teacher=teacher,
                title=blueprint["title"],
                defaults={
                    "description": blueprint["description"],
                    "status": Course.Status.PUBLISHED,
                    "start_date": today - timedelta(days=blueprint["start_offset"]),
                    "end_date": today + timedelta(days=blueprint["end_offset"]),
                    "expected_hours": 48,
                },
            )
            course.description = blueprint["description"]
            course.status = Course.Status.PUBLISHED
            course.start_date = today - timedelta(days=blueprint["start_offset"])
            course.end_date = today + timedelta(days=blueprint["end_offset"])
            course.expected_hours = 48
            course.save()
            courses.append(course)

            for module_index, module_spec in enumerate(blueprint["modules"], start=1):
                module, _ = Module.objects.get_or_create(
                    course=course,
                    order=module_index,
                    defaults={
                        "title": module_spec["title"],
                        "description": f"{module_spec['title']} for {course.title}",
                        "estimated_minutes": 120,
                    },
                )
                module.title = module_spec["title"]
                module.description = f"{module_spec['title']} for {course.title}"
                module.estimated_minutes = 120
                module.save()

                for lesson_index, lesson_title in enumerate(module_spec["lessons"], start=1):
                    global_order = ((module_index - 1) * 5) + lesson_index
                    lesson, _ = Lesson.objects.get_or_create(
                        module=module,
                        order=global_order,
                        defaults={
                            "title": lesson_title,
                            "content_type": Lesson.ContentType.TEXT,
                            "content_text": (
                                f"{lesson_title} lesson notes for {course.title}. "
                                "This content is seeded for realistic dashboard demonstrations."
                            ),
                            "estimated_minutes": 18 + lesson_index,
                            "is_published": True,
                        },
                    )
                    lesson.title = lesson_title
                    lesson.content_type = Lesson.ContentType.TEXT
                    lesson.content_text = (
                        f"{lesson_title} lesson notes for {course.title}. "
                        "This content is seeded for realistic dashboard demonstrations."
                    )
                    lesson.estimated_minutes = 18 + lesson_index
                    lesson.is_published = True
                    lesson.save()

                    quiz_plan = self.QUIZ_PLAN.get(global_order)
                    if quiz_plan:
                        quiz, _ = Quiz.objects.get_or_create(
                            lesson=lesson,
                            defaults={
                                "title": f"{lesson.title} {quiz_plan['title_suffix']}",
                                "description": f"Assessment for {lesson.title}",
                                "quiz_type": Quiz.QuizType.MULTIPLE_CHOICE,
                                "time_limit_minutes": 12,
                                "passing_score": 70,
                                "max_attempts": 3,
                                "shuffle_questions": False,
                                "show_answers": True,
                                "is_published": quiz_plan["published"],
                            },
                        )
                        quiz.title = f"{lesson.title} {quiz_plan['title_suffix']}"
                        quiz.description = f"Assessment for {lesson.title}"
                        quiz.quiz_type = Quiz.QuizType.MULTIPLE_CHOICE
                        quiz.time_limit_minutes = 12
                        quiz.passing_score = 70
                        quiz.max_attempts = 3
                        quiz.shuffle_questions = False
                        quiz.show_answers = True
                        quiz.is_published = quiz_plan["published"]
                        quiz.save()
                        self._reset_quiz_questions(quiz, course.title, lesson.title, quiz_plan["question_count"])

        return courses

    def _reset_quiz_questions(self, quiz: Quiz, course_title: str, lesson_title: str, question_count: int) -> None:
        quiz.questions.all().delete()

        prompts = [
            (
                f"What is the main goal of {lesson_title} in {course_title}?",
                [
                    ("Apply the lesson concept correctly in practice", True),
                    ("Skip understanding and memorize only the title", False),
                    ("Ignore prior feedback and work alone", False),
                    ("Finish quickly without checking accuracy", False),
                ],
            ),
            (
                f"Which action best supports success in {lesson_title}?",
                [
                    ("Review examples before attempting the task", True),
                    ("Avoid practice and wait for the final exam", False),
                    ("Ignore mistakes from earlier attempts", False),
                    ("Rely only on guesses", False),
                ],
            ),
            (
                f"When a student struggles with {lesson_title}, what should happen next?",
                [
                    ("Revisit the concept and attempt guided practice", True),
                    ("Stop the course immediately", False),
                    ("Delete previous feedback", False),
                    ("Skip to the last lesson with no review", False),
                ],
            ),
            (
                f"Why does {lesson_title} matter in {course_title}?",
                [
                    ("It contributes directly to course progress and assessment readiness", True),
                    ("It has no effect on overall performance", False),
                    ("It is unrelated to course outcomes", False),
                    ("It only matters after course completion", False),
                ],
            ),
            (
                f"What habit improves performance in {lesson_title}?",
                [
                    ("Consistent practice with feedback", True),
                    ("Long inactivity gaps", False),
                    ("Skipping quizzes entirely", False),
                    ("Only reading the title of the lesson", False),
                ],
            ),
        ]

        for index, (question_text, answers) in enumerate(prompts[:question_count], start=1):
            question = Question.objects.create(
                quiz=quiz,
                question_type=Question.QuestionType.MULTIPLE_CHOICE,
                text=question_text,
                points=1,
                order=index,
            )
            for answer_index, (answer_text, is_correct) in enumerate(answers, start=1):
                Answer.objects.create(
                    question=question,
                    text=answer_text,
                    is_correct=is_correct,
                    order=answer_index,
                )

        quiz.total_questions = quiz.questions.count()
        quiz.save(update_fields=["total_questions"])

    def _clear_demo_activity(self, courses: List[Course], students: List) -> None:
        course_ids = [course.id for course in courses]
        student_ids = [student.id for student in students]

        Alert.objects.filter(course_id__in=course_ids, student_id__in=student_ids).delete()
        RiskHistory.objects.filter(course_id__in=course_ids, student_id__in=student_ids).delete()
        QuizAttempt.objects.filter(
            student_id__in=student_ids,
            quiz__lesson__module__course_id__in=course_ids,
        ).delete()
        LessonCompletion.objects.filter(
            student_id__in=student_ids,
            lesson__module__course_id__in=course_ids,
        ).delete()
        LessonInteraction.objects.filter(
            student_id__in=student_ids,
            lesson__module__course_id__in=course_ids,
        ).delete()
        LessonDifficulty.objects.filter(lesson__module__course_id__in=course_ids).delete()
        Enrollment.objects.filter(student_id__in=student_ids, course_id__in=course_ids).delete()

    def _seed_learning_activity(self, courses: List[Course], students: List) -> None:
        now = timezone.now()

        for course_index, course in enumerate(courses):
            lessons = list(
                Lesson.objects.filter(module__course=course, is_published=True).order_by("module__order", "order")
            )
            quizzes = list(
                Quiz.objects.filter(lesson__module__course=course, lesson__order__in=[1, 2, 4, 6]).order_by("lesson__order")
            )

            for student_index, student in enumerate(students):
                profile_name = self._profile_name_for(student_index, course_index)
                profile = self.PROFILE_PATTERNS[profile_name]
                completed_count = self._bounded_random(*profile["completed_lessons"])
                days_inactive = self._bounded_random(*profile["days_inactive"])

                enrollment = Enrollment.objects.create(
                    student=student,
                    course=course,
                    status=Enrollment.Status.ACTIVE,
                    is_fee_paid=profile["paid"],
                    last_activity=now - timedelta(days=days_inactive),
                    login_count=self._bounded_random(*profile["login_count"]),
                    total_time_spent_seconds=0,
                    progress_percentage=Decimal("0.00"),
                    average_quiz_score=Decimal("0.00"),
                    risk_score=Decimal("0.00"),
                    risk_level="UNKNOWN",
                    engagement_score=Decimal("0.00"),
                )

                self._seed_lesson_activity(
                    enrollment=enrollment,
                    lessons=lessons,
                    completed_count=completed_count,
                    days_inactive=days_inactive,
                    now=now,
                    profile_name=profile_name,
                )

                self._seed_quiz_attempts(
                    enrollment=enrollment,
                    quizzes=quizzes,
                    score_bands=profile["score_bands"],
                    attempt_plan=profile["attempt_plan"],
                    now=now,
                    course_index=course_index,
                    student_index=student_index,
                )

                enrollment.update_progress()
                enrollment.average_quiz_score = (
                    QuizAttempt.objects.filter(
                        student=student,
                        quiz__lesson__module__course=course,
                        status=QuizAttempt.Status.COMPLETED,
                    ).aggregate(avg=Avg("score_percentage"))["avg"] or Decimal("0.00")
                )
                enrollment.save(update_fields=["progress_percentage", "average_quiz_score", "last_activity", "login_count", "total_time_spent_seconds"])

                self._seed_historical_risk(enrollment, now)
                RiskEngine.calculate_student_risk(str(enrollment.id))

    def _seed_lesson_activity(
        self,
        enrollment: Enrollment,
        lessons: List[Lesson],
        completed_count: int,
        days_inactive: int,
        now,
        profile_name: str,
    ) -> None:
        completed_lessons = lessons[:completed_count]
        total_time_spent = 0

        for lesson_index, lesson in enumerate(completed_lessons, start=1):
            completion_time = now - timedelta(days=max(days_inactive, 1) + max(0, completed_count - lesson_index))
            time_spent = 600 + (lesson_index * 90)
            total_time_spent += time_spent
            LessonCompletion.objects.create(
                student=enrollment.student,
                lesson=lesson,
                completed_at=completion_time,
                time_spent_seconds=time_spent,
            )

            view_count = 1
            if profile_name in ["recovering", "inconsistent"]:
                view_count = 2 if lesson.order in [2, 4, 6] else 1
            if profile_name in ["at_risk", "critical"]:
                view_count = 3 if lesson.order in [2, 4] else 2

            for view_index in range(view_count):
                LessonInteraction.objects.create(
                    student=enrollment.student,
                    lesson=lesson,
                    enrollment=enrollment,
                    interaction_type=LessonInteraction.InteractionType.VIEW,
                    timestamp=completion_time - timedelta(hours=view_index * 4),
                    duration_seconds=300 + (view_index * 60),
                    user_agent="TeachLink Demo Seeder",
                )

        if completed_count < len(lessons):
            next_lesson = lessons[completed_count]
            revisit_count = 2 if profile_name in ["recovering", "inconsistent"] else 3 if profile_name in ["at_risk", "critical"] else 1
            for revisit_index in range(revisit_count):
                LessonInteraction.objects.create(
                    student=enrollment.student,
                    lesson=next_lesson,
                    enrollment=enrollment,
                    interaction_type=LessonInteraction.InteractionType.VIEW,
                    timestamp=now - timedelta(days=max(days_inactive - 1, 0), hours=revisit_index * 3),
                    duration_seconds=240 + (revisit_index * 45),
                    user_agent="TeachLink Demo Seeder",
                )
                total_time_spent += 240 + (revisit_index * 45)

        enrollment.total_time_spent_seconds = total_time_spent

    def _seed_quiz_attempts(
        self,
        enrollment: Enrollment,
        quizzes: List[Quiz],
        score_bands: List[Tuple[int, int]],
        attempt_plan: List[int],
        now,
        course_index: int,
        student_index: int,
    ) -> None:
        attempt_number_by_quiz: Dict[str, int] = {}

        for quiz_index, quiz in enumerate(quizzes):
            attempts_to_create = attempt_plan[quiz_index] if quiz_index < len(attempt_plan) else 0
            if attempts_to_create <= 0:
                continue

            for attempt_index in range(attempts_to_create):
                band_index = min(attempt_index, len(score_bands) - 1)
                lower, upper = score_bands[band_index]
                base_score = self._bounded_random(lower, upper)
                variation = ((student_index + course_index + quiz_index + attempt_index) % 5) - 2
                score_pct = max(0, min(100, base_score + variation))
                max_points = Decimal(str(quiz.total_questions or 4))
                score_points = (Decimal(str(score_pct)) / Decimal("100")) * max_points
                attempt_number = attempt_number_by_quiz.get(str(quiz.id), 0) + 1
                attempt_number_by_quiz[str(quiz.id)] = attempt_number
                submitted_at = now - timedelta(days=max(int(enrollment.days_since_last_activity) - attempt_index, 0), hours=(quiz_index * 5) + attempt_index)
                started_at = submitted_at - timedelta(minutes=10 + (attempt_index * 3))

                QuizAttempt.objects.create(
                    student=enrollment.student,
                    quiz=quiz,
                    attempt_number=attempt_number,
                    status=QuizAttempt.Status.COMPLETED,
                    started_at=started_at,
                    submitted_at=submitted_at,
                    time_spent_seconds=max(60, int((submitted_at - started_at).total_seconds())),
                    score=score_points.quantize(Decimal("0.01")),
                    score_percentage=Decimal(str(score_pct)).quantize(Decimal("0.01")),
                    max_possible_score=max_points.quantize(Decimal("0.01")),
                    passed=score_pct >= quiz.passing_score,
                    responses={},
                    user_agent="TeachLink Demo Seeder",
                )

            quiz.update_statistics()

    def _seed_historical_risk(self, enrollment: Enrollment, now) -> None:
        snapshots = [
            {
                "days_ago": 14,
                "progress": max(0, float(enrollment.progress_percentage) - 18.0),
                "quiz": max(0, float(enrollment.average_quiz_score) - 15.0),
                "days_inactive": min(14, int(enrollment.days_since_last_activity) + 5),
            },
            {
                "days_ago": 7,
                "progress": max(0, float(enrollment.progress_percentage) - 8.0),
                "quiz": max(0, float(enrollment.average_quiz_score) - 6.0),
                "days_inactive": min(14, int(enrollment.days_since_last_activity) + 2),
            },
        ]

        for snapshot in snapshots:
            risk_score, risk_level, engagement_score, factors = self._calculate_snapshot_metrics(
                progress_pct=snapshot["progress"],
                quiz_avg_pct=snapshot["quiz"],
                days_inactive=snapshot["days_inactive"],
            )
            entry = RiskHistory.objects.create(
                student=enrollment.student,
                course=enrollment.course,
                enrollment=enrollment,
                risk_score=risk_score,
                risk_level=risk_level,
                performance_score=(Decimal(str(snapshot["quiz"])) / Decimal("100")).quantize(Decimal("0.001")),
                progress_score=(Decimal(str(snapshot["progress"])) / Decimal("100")).quantize(Decimal("0.001")),
                engagement_score=engagement_score,
                contributing_factors=factors,
            )
            RiskHistory.objects.filter(id=entry.id).update(
                calculated_at=now - timedelta(days=snapshot["days_ago"])
            )

    def _calculate_snapshot_metrics(self, progress_pct: float, quiz_avg_pct: float, days_inactive: int):
        progress_risk = Decimal("1.0") - (Decimal(str(progress_pct)) / Decimal("100"))
        quiz_risk = Decimal("1.0") - (Decimal(str(quiz_avg_pct)) / Decimal("100"))
        inactivity_risk = RiskEngine._calculate_inactivity_risk(days_inactive)
        risk_score = (
            (progress_risk * RiskEngine.WEIGHTS["progress"]) +
            (quiz_risk * RiskEngine.WEIGHTS["quiz"]) +
            (inactivity_risk * RiskEngine.WEIGHTS["inactivity"])
        ).quantize(Decimal("0.001"))
        risk_level = RiskEngine._determine_risk_level(risk_score)

        recency_score = max(Decimal("0.0"), Decimal("1.0") - (Decimal(days_inactive) / Decimal("14.0")))
        completion_rate = Decimal(str(progress_pct)) / Decimal("100")
        quiz_rate = Decimal(str(quiz_avg_pct)) / Decimal("100")
        engagement_score = (
            recency_score * Decimal("0.4") +
            completion_rate * Decimal("0.3") +
            quiz_rate * Decimal("0.3")
        ).quantize(Decimal("0.001"))
        factors = RiskEngine._identify_contributing_factors(
            progress_pct=Decimal(str(progress_pct)),
            quiz_avg_pct=Decimal(str(quiz_avg_pct)),
            inactivity_risk=inactivity_risk,
            days_inactive=days_inactive,
        )
        return risk_score, risk_level, engagement_score, factors

    def _refresh_demo_analytics(self, courses: List[Course]) -> None:
        for course in courses:
            DifficultyAnalyzer.analyze_course_difficulties(str(course.id))

        for enrollment in Enrollment.objects.filter(course__in=courses, status=Enrollment.Status.ACTIVE):
            RiskEngine.calculate_student_risk(str(enrollment.id))

        for course in courses:
            AlertGenerator.check_and_generate_alerts(course_id=str(course.id))

    def _print_seed_summary(self, courses: List[Course]) -> None:
        self.stdout.write(self.style.HTTP_INFO("Demo Data Summary"))
        for course in courses:
            enrollments = Enrollment.objects.filter(course=course, status=Enrollment.Status.ACTIVE)
            risk_breakdown = {
                item["risk_level"]: item["count"]
                for item in enrollments.values("risk_level").annotate(count=Count("id"))
            }
            alert_count = Alert.objects.filter(
                course=course,
                status__in=[Alert.Status.ACTIVE, Alert.Status.ACKNOWLEDGED],
            ).count()
            quiz_count = Quiz.objects.filter(lesson__module__course=course, is_published=True).count()
            hardest = (
                LessonDifficulty.objects.filter(lesson__module__course=course)
                .order_by("-difficulty_score")
                .values_list("lesson__title", "difficulty_level", "failure_rate")
                .first()
            )
            hardest_label = (
                f"{hardest[0]} ({hardest[1]}, failure {(float(hardest[2]) * 100):.0f}%)"
                if hardest
                else "No difficulty data"
            )
            avg_progress = enrollments.aggregate(avg=Avg("progress_percentage"))["avg"] or Decimal("0.00")
            avg_quiz = enrollments.aggregate(avg=Avg("average_quiz_score"))["avg"] or Decimal("0.00")

            self.stdout.write(
                f"- {course.title}: "
                f"{enrollments.count()} students | "
                f"Risk {risk_breakdown} | "
                f"Avg Progress {float(avg_progress):.1f}% | "
                f"Avg Quiz {float(avg_quiz):.1f}% | "
                f"Published Quizzes {quiz_count} | "
                f"Active Alerts {alert_count} | "
                f"Hardest Topic {hardest_label}"
            )

    def _profile_name_for(self, student_index: int, course_index: int) -> str:
        if student_index == 0:
            return ["recovering", "at_risk", "steady"][course_index % 3]
        order = ["steady", "recovering", "inconsistent", "at_risk", "critical"]
        return order[(student_index + (course_index * 2)) % len(order)]

    @staticmethod
    def _bounded_random(minimum: int, maximum: int) -> int:
        return random.randint(minimum, maximum)
