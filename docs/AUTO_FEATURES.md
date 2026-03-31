# Auto Feature Documentation

Generated from Python module/class/function docstrings and tagged comments.

- Generated: 2026-03-29 21:28 UTC
- Files scanned: 62
- Files with extracted feature docs: 35

## How To Improve This Output

- Add meaningful docstrings to modules, views, services, and models.
- Add tagged comments like `# FEATURE: ...` for key capabilities.
- Re-run this script after code updates.

## `analytics/models.py`

**Module:** Analytics and Risk Detection Models for TeachLink

**Classes**

- `RiskHistory`: Historical tracking of student risk scores
- `EngagementMetrics`: Detailed engagement tracking for students
- `LessonDifficulty`: Track lesson difficulty based on student performance
- `Alert`: System-generated alerts for teachers
  - `acknowledge`: Mark alert as acknowledged
  - `resolve`: Mark alert as resolved
- `InterventionLog`: Track teacher interventions and their effectiveness
  - `calculate_improvement`: Calculate improvement percentage based on risk scores
- `LessonInteraction`: Track student interactions with lessons

## `analytics/scripts/test_risk_engine.py`

**Module:** Test the Risk Engine with our existing test data

## `analytics/scripts/test_services.py`

**Module:** Quick test script for analytics services

**Functions**

- `test_risk_engine`: Test if risk engine can calculate risk scores
- `test_alert_generation`: Test if alerts are being generated
- `test_difficulty_analyzer`: Test difficulty analysis

## `analytics/services/alert_generator.py`

**Module:** Alert Generator Service

**Classes**

- `AlertGenerator`: Generates alerts based on risk scores and behavioral patterns
  - `check_and_generate_alerts`: Check for conditions that should trigger alerts
  - `get_active_alerts`: Get all active alerts, optionally filtered
  - `resolve_old_alerts`: Auto-resolve alerts that are older than specified days

## `analytics/services/cache_services.py`

**Module:** Redis Caching Service for TeachLink

**Classes**

- `CacheService`: Service for managing Redis cache
  - `get_key`: Generate cache key
  - `get`: Get value from cache
  - `set`: Set value in cache with TTL
  - `delete`: Delete value from cache
  - `delete_pattern`: Delete all keys matching pattern
  - `get_or_set`: Get from cache or execute function and cache result
  - `clear_user_cache`: Clear all cache entries for a user
  - `clear_course_cache`: Clear all cache entries for a course
- `DashboardCache`: Cache management for dashboard data
  - `get_teacher_dashboard`: Get cached teacher dashboard
  - `set_teacher_dashboard`: Cache teacher dashboard
  - `invalidate_teacher_dashboard`: Invalidate teacher dashboard cache
  - `get_student_dashboard`: Get cached student dashboard
  - `set_student_dashboard`: Cache student dashboard
  - `invalidate_student_dashboard`: Invalidate student dashboard cache
- `RiskCache`: Cache management for risk data
  - `get_risk_distribution`: Get cached risk distribution
  - `set_risk_distribution`: Cache risk distribution
  - `invalidate_risk_distribution`: Invalidate all risk distribution caches for teacher
- `DifficultyCache`: Cache management for difficulty data
  - `get_hardest_lessons`: Get cached hardest lessons
  - `set_hardest_lessons`: Cache hardest lessons
  - `invalidate_difficulty_cache`: Invalidate difficulty caches

## `analytics/services/difficulty_analyzer.py`

**Module:** Difficulty Analyzer Service

**Classes**

- `DifficultyAnalyzer`: Analyzes lesson difficulty using updated inputs:
  - `analyze_lesson_difficulty`: Calculate comprehensive difficulty score for a lesson
  - `analyze_course_difficulties`: Analyze difficulty for all lessons in a course
  - `get_hardest_lessons`: Get the hardest lessons across all courses or specific course

## `analytics/services/risk_engine.py`

**Module:** Risk Engine Service

**Classes**

- `RiskEngine`: Longitudinal risk scoring engine.
  - `calculate_student_risk`: Calculate risk score and trend for a student enrollment.
  - `batch_calculate_risk`: Batch calculate risk scores for all active enrollments
  - `get_risk_trend`: Get risk score trend for a student over time

## `assessments/admin.py`

**Module:** Assessment Admin Configuration

## `assessments/models.py`

**Module:** Assessment and Quiz Management Models for TeachLink

**Classes**

- `Quiz`: Quiz/Assessment model linked to a lesson
  - `update_statistics`: Update cached quiz statistics
- `Question`: Question model for quizzes
  - `correct_rate`: Percentage of times answered correctly
  - `update_difficulty`: Update difficulty index based on correct rate
- `Answer`: Answer options for multiple choice questions
- `QuizAttempt`: Student quiz attempt tracking
  - `save`: Override save to validate enrollment
  - `calculate_score`: Calculate score based on responses
  - `complete`: Complete the quiz attempt
  - `update_enrollment_performance`: Update student's enrollment average quiz score
- `QuestionResponse`: Detailed response tracking for analytics

## `assessments/scripts/create_test_quiz.py`

**Module:** Create test quiz with questions and answers for TeachLink

## `assessments/scripts/test_quiz_api.py`

**Module:** Test Quiz API endpoints using requests

## `assessments/scripts/test_quiz_edge_cases.py`

**Module:** Test edge cases for quiz system

**Functions**

- `create_api_request`: Helper to create an authenticated API request
- `find_student_with_attempts`: Find a student who has fewer than max_attempts completed attempts
- `cleanup_active_attempts`: Clean up any active attempts for this student and quiz
- `test_attempt_limit`: Test 1: Attempt limit enforcement
- `test_time_limit`: Test 2: Time limit enforcement
- `test_empty_responses`: Test 3: Empty responses should score 0%
- `test_invalid_question_ids`: Test 4: Invalid question IDs should be handled gracefully
- `test_duplicate_completion`: Test 5: Duplicate submission should be blocked
- `test_enrollment_validation`: Test 6: Cannot attempt quiz without enrollment
- `test_edge_cases`: Main test runner

## `assessments/scripts/test_quiz_flow.py`

**Module:** Test the complete quiz attempt flow

## `assessments/scripts/verify_quiz_data.py`

**Module:** Verify quiz data and statistics

## `assessments/serializers.py`

**Module:** Assessment serializers for TeachLink

**Classes**

- `AnswerSerializer`: Answer serializer for multiple choice
- `AnswerDetailSerializer`: Answer serializer for teachers (shows correct flag)
- `QuestionSerializer`: Question serializer for teachers
- `QuestionStudentSerializer`: Question serializer for students (no correct answers)
- `QuizSerializer`: Quiz serializer for teachers
- `QuizDetailSerializer`: Detailed quiz serializer with questions
- `QuizStudentSerializer`: Quiz serializer for students
- `QuizAttemptSerializer`: Quiz attempt serializer
- `QuizAttemptDetailSerializer`: Detailed attempt serializer with responses
  - `get_questions`: Get questions with student's answers and correct answers
- `QuizAttemptStartSerializer`: Serializer for starting a quiz attempt
- `QuizSubmitSerializer`: Serializer for submitting quiz answers

## `assessments/signals.py`

**Functions**

- `update_quiz_question_count`: Update quiz total_questions when questions are added/removed
- `update_quiz_statistics_on_attempt`: Update quiz statistics when a new attempt is completed

## `assessments/urls.py`

**Module:** Assessment URLs for TeachLink

## `assessments/views.py`

**Module:** Assessment views for TeachLink

**Functions**

- `cls_quiz_has_attempts`: Return True when any student has started/submitted an attempt for this quiz.

**Classes**

- `QuizViewSet`: ViewSet for Quiz operations
  - `perform_create`: Create quiz and link to lesson
  - `start`: Start a quiz attempt
  - `submit`: Submit quiz answers
  - `my_attempts`: Get current student's quiz attempts
- `QuestionViewSet`: ViewSet for Question operations
  - `perform_create`: Create question and auto-set order
- `AnswerViewSet`: ViewSet for Answer operations
  - `perform_create`: Create answer and auto-set order
- `QuizAttemptViewSet`: ViewSet for viewing quiz attempts
  - `quiz_performance`: Get performance analytics for a quiz

## `courses/admin.py`

**Module:** Course Management Admin Configuration

## `courses/models.py`

**Module:** Course Management Models for TeachLink

**Functions**

- `default_course_key`: Generate a short enrollment key for students.

**Classes**

- `Course`: Main course container created by teachers
  - `total_students`: Get total enrolled students
  - `total_modules`: Get total modules in course
  - `total_lessons`: Get total lessons across all modules
  - `publish`: Publish the course
- `Module`: Course module/unit container
  - `total_lessons`: Get total lessons in module
  - `completed_lessons_count`: Get completed lessons count for a student
- `Lesson`: Individual lesson/content unit
  - `has_quiz`: Check if lesson has associated quiz
  - `total_views`: Get total views count
  - `update_difficulty`: Update lesson difficulty based on:
- `LessonCompletion`: Track student lesson completion
- `Enrollment`: Student enrollment in a course
  - `update_progress`: Calculate and update course progress percentage
  - `update_last_activity`: Update last activity timestamp
  - `mark_completed`: Mark enrollment as completed
  - `days_since_last_activity`: Get days since last activity
  - `is_at_risk`: Quick check if student is at risk
  - `is_inactive`: Check if student is inactive (>7 days)

## `courses/scripts/seed_courses.py`

**Module:** Seed script for course test data

## `courses/scripts/test_courses_api.py`

**Module:** Test script for Course API endpoints

## `courses/serializers.py`

**Module:** Course Management Serializers

**Classes**

- `LessonSerializer`: Lesson serializer
- `LessonDetailSerializer`: Detailed lesson serializer with completion status
- `ModuleSerializer`: Module serializer with lessons
- `ModuleDetailSerializer`: Detailed module serializer with full lesson details
- `CourseSerializer`: Course list/overview serializer
- `CourseDetailSerializer`: Detailed course serializer with related data
  - `get_enrollment_status`: Get current user's enrollment status
  - `get_student_progress`: Get detailed progress for current student
- `EnrollmentSerializer`: Enrollment serializer
- `EnrollmentDetailSerializer`: Detailed enrollment serializer for analytics
- `LessonCompletionSerializer`: Lesson completion serializer

## `courses/urls.py`

**Module:** Course Management URLs

## `courses/views.py`

**Module:** Course Management Views

**Classes**

- `CourseViewSet`: ViewSet for Course operations
  - `perform_create`: Set teacher as current user and email enrollment key.
  - `enroll`: Enroll current student in course
  - `publish`: Publish a teacher's course so students can enroll.
  - `regenerate_enrollment_key`: Regenerate enrollment key and email it to the teacher.
  - `unpublish`: Unpublish a teacher's course and move it back to draft.
  - `unenroll`: Unenroll from course
- `ModuleViewSet`: ViewSet for Module operations
  - `perform_create`: Auto-set order if not provided
- `LessonViewSet`: ViewSet for Lesson operations
  - `perform_create`: Auto-set order if not provided
  - `complete`: Mark lesson as completed
- `EnrollmentViewSet`: ViewSet for Enrollment operations
  - `my_enrollments`: Get current student's enrollments
  - `update_risk`: Manually update risk score for enrollment

## `dashboard/context_processor.py`

**Module:** Context processors for dashboard templates

**Functions**

- `navigation_context`: Add navigation menu and counts to template context

## `dashboard/middleware.py`

**Module:** Middleware to store JWT token in session for template access

**Classes**

- `TokenMiddleware`: Store JWT token from Authorization header in session
  - `process_request`: Extract token from Authorization header and store in session
  - `process_response`: Clean up any sensitive data if needed

## `dashboard/scripts/test_dashboard.py`

**Module:** Test dashboard functionality

## `dashboard/urls_html.py`

**Module:** HTML dashboard URLs for TeachLink.

## `dashboard/views.py`

**Module:** Dashboard Views for TeachLink

**Functions**

- `difficulty_display_label`: Normalize stored difficulty codes to 3-band display labels.
- `custom_login`: Custom login view that redirects to appropriate dashboard
- `custom_register`: Custom registration view with role-based redirects.
- `custom_logout`: Session logout for dashboard web views
- `profile_view`: Unified profile page for teacher/student/admin users
- `courses_overview`: Role-aware courses and learning materials page
- `open_lesson_material`: Track lesson material usage and redirect to the material link/file.
- `teacher_dashboard`: Main teacher dashboard view
- `teacher_course_analytics`: Course-specific analytics page for teachers.
- `teacher_quiz_builder`: Teacher page to configure quiz/CAT settings and questions.
- `student_dashboard`: Main student dashboard view
- `student_course_quizzes`: Student list of quizzes/CATs for a specific enrolled course.
- `student_quiz_attempts`: Student attempt summary page for a specific quiz/CAT.
- `student_quiz_review`: Student question-by-question quiz review page.
- `risk_detail`: Detailed student view for a teacher (risk + performance)
- `alerts_center`: Alert management center for teachers
- `export_students_csv`: Export student data to CSV
- `teacher_students`: Teacher view listing all students in the teacher's courses
- `student_enroll_by_key`: Allow a student to enroll in a published course using enrollment key.
- `teacher_payments`: Teacher view for payment status of enrolled students.
- `admin_dashboard`: System-wide dashboard for staff/admin users

**Classes**

- `TeacherDashboardAPI`: API endpoints for teacher dashboard data
  - `get`: Get all dashboard data in one request
- `StudentDashboardAPI`: API endpoints for student dashboard data
  - `get`: Get student's dashboard data
  - `post`: Handle student actions like reporting difficulty
- `StudentNotificationAPI`: Student notification actions such as marking as read.
- `RiskDataAPI`: API for risk-related data visualizations
- `StudentRiskDetailAPI`: Detailed risk data for a specific student
  - `get`: Get detailed risk history for a student
- `AlertManagementAPI`: API for managing alerts
  - `get`: Get alerts with filtering
  - `post`: Update alert status
- `DifficultyAPI`: API for difficulty analytics
  - `get`: Get difficulty data for charts
- `TeacherDashboardCachedAPI`: Teacher dashboard API with Redis caching
  - `post`: Invalidate cache
- `DifficultyCachedAPI`: Difficulty data API with caching
  - `post`: Invalidate difficulty cache

## `dashboard/views_cached.py`

**Module:** Dashboard Views with Redis Caching

**Functions**

- `difficulty_display_label`: Normalize stored difficulty codes to 3-band display labels.

**Classes**

- `TeacherDashboardCachedAPI`: Teacher dashboard API with Redis caching
  - `post`: Invalidate cache
- `RiskDataCachedAPI`: Risk data API with caching
  - `post`: Invalidate risk cache
- `DifficultyCachedAPI`: Difficulty data API with caching
  - `post`: Invalidate difficulty cache

## `users/models.py`

**Module:** Custom User Model for TeachLink

**Classes**

- `User`: Custom user model supporting Teacher and Student roles
  - `update_last_activity`: Update user's last activity timestamp
- `UserSession`: Track user sessions for engagement monitoring
  - `end_session`: Mark session as ended

## `users/permissions.py`

**Module:** Custom permissions for TeachLink.

**Classes**

- `IsTeacher`: Allow access only to teachers.
- `IsStudent`: Allow access only to students.
- `IsTeacherOrReadOnly`: Allow teachers to create/update/delete.

## `users/serializers.py`

**Classes**

- `UserSerializer`: Public user profile serializer
- `UserDetailSerializer`: Detailed user serializer for profile pages
- `RegisterSerializer`: User registration serializer
  - `validate`: Validate that passwords match
- `LoginSerializer`: User login serializer
  - `validate`: Validate login credentials
- `UserSessionSerializer`: User session serializer

## `users/views.py`

**Classes**

- `UserViewSet`: ViewSet for viewing user profiles (read-only).
  - `get_serializer_class`: Use detail serializer for retrieve action
  - `get_queryset`: Filter queryset based on user role
- `RegisterView`: API endpoint for user registration.
- `LoginView`: API endpoint for user login.
- `LogoutView`: API endpoint for user logout.
- `UserProfileView`: API endpoint for getting/updating the current user's profile.
  - `get_object`: Return the current authenticated user
  - `perform_update`: Update user profile
- `UserSessionsView`: API endpoint for viewing user's active sessions.
  - `get_queryset`: Return user's active sessions
- `ChangePasswordView`: API endpoint for changing password.
