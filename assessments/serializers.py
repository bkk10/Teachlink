"""
Assessment serializers for Teachly
"""
from rest_framework import serializers
from django.utils import timezone
from .models import Quiz, Question, Answer, QuizAttempt, QuestionResponse
from courses.serializers import LessonSerializer

class AnswerSerializer(serializers.ModelSerializer):
    """Answer serializer for multiple choice"""
    class Meta:
        model = Answer
        fields = ['id', 'text', 'is_correct', 'order']
        extra_kwargs = {
            'is_correct': {'write_only': True}  # Hide correct answer from students
        }


class AnswerDetailSerializer(serializers.ModelSerializer):
    """Answer serializer for teachers (shows correct flag)"""
    class Meta:
        model = Answer
        fields = ['id', 'text', 'is_correct', 'order']


class QuestionSerializer(serializers.ModelSerializer):
    """Question serializer for teachers"""
    answers = AnswerDetailSerializer(many=True, read_only=True)
    
    class Meta:
        model = Question
        fields = [
            'id', 'question_type', 'text', 'correct_answer',
            'points', 'order', 'explanation',
            'answers', 'difficulty_index', 'correct_rate',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'difficulty_index', 'correct_rate',
            'created_at', 'updated_at'
        ]


class QuestionStudentSerializer(serializers.ModelSerializer):
    """Question serializer for students (no correct answers)"""
    answers = AnswerSerializer(many=True, read_only=True)
    
    class Meta:
        model = Question
        fields = [
            'id', 'question_type', 'text', 'points', 'order',
            'answers'
        ]


class QuizSerializer(serializers.ModelSerializer):
    """Quiz serializer for teachers"""
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    question_count = serializers.IntegerField(source='total_questions', read_only=True)
    
    class Meta:
        model = Quiz
        fields = [
            'id', 'lesson', 'lesson_title', 'title', 'description',
            'quiz_type', 'time_limit_minutes', 'passing_score',
            'max_attempts', 'shuffle_questions', 'show_answers',
            'is_published', 'total_questions', 'total_attempts',
            'average_score', 'pass_rate', 'created_at', 'updated_at', 'question_count'
        ]
        read_only_fields = [
            'id', 'total_questions', 'total_attempts',
            'average_score', 'pass_rate', 'created_at', 'updated_at'
        ]


class QuizDetailSerializer(serializers.ModelSerializer):
    """Detailed quiz serializer with questions"""
    questions = QuestionSerializer(many=True, read_only=True)
    lesson = LessonSerializer(read_only=True)
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    
    class Meta:
        model = Quiz
        fields = QuizSerializer.Meta.fields + ['questions','lesson_title']


class QuizStudentSerializer(serializers.ModelSerializer):
    """Quiz serializer for students"""
    questions = QuestionStudentSerializer(many=True, read_only=True)
    attempts_remaining = serializers.SerializerMethodField()
    best_score = serializers.SerializerMethodField()
    
    class Meta:
        model = Quiz
        fields = [
            'id', 'title', 'description', 'time_limit_minutes',
            'passing_score', 'max_attempts', 'shuffle_questions',
            'questions', 'attempts_remaining', 'best_score'
        ]
    
    def get_attempts_remaining(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            attempt_count = QuizAttempt.objects.filter(
                student=request.user,
                quiz=obj,
                status=QuizAttempt.Status.COMPLETED
            ).count()
            return max(0, obj.max_attempts - attempt_count)
        return obj.max_attempts
    
    def get_best_score(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            best = QuizAttempt.objects.filter(
                student=request.user,
                quiz=obj,
                status=QuizAttempt.Status.COMPLETED
            ).order_by('-score_percentage').first()
            return best.score_percentage if best else None
        return None


class QuizAttemptSerializer(serializers.ModelSerializer):
    """Quiz attempt serializer"""
    student_name = serializers.CharField(source='student.display_name', read_only=True)
    quiz_title = serializers.CharField(source='quiz.title', read_only=True)
    
    class Meta:
        model = QuizAttempt
        fields = [
            'id', 'student', 'student_name', 'quiz', 'quiz_title',
            'attempt_number', 'status', 'started_at', 'submitted_at',
            'time_spent_seconds', 'score', 'score_percentage',
            'max_possible_score', 'passed', 'feedback'
        ]
        read_only_fields = [
            'id', 'student', 'attempt_number', 'started_at',
            'score', 'score_percentage', 'max_possible_score',
            'passed', 'time_spent_seconds'
        ]


class QuizAttemptDetailSerializer(serializers.ModelSerializer):
    """Detailed attempt serializer with responses"""
    questions = serializers.SerializerMethodField()
    
    class Meta:
        model = QuizAttempt
        fields = QuizAttemptSerializer.Meta.fields + ['responses', 'questions']
    
    def get_questions(self, obj):
        """Get questions with student's answers and correct answers"""
        if obj.quiz.show_answers or self.context.get('is_teacher'):
            data = []
            for question in obj.quiz.questions.all():
                question_data = QuestionSerializer(question).data
                question_data['student_answer'] = obj.responses.get(str(question.id))
                
                # Add correct answer info
                if question.question_type == 'MCQ':
                    correct_answer = question.answers.filter(is_correct=True).first()
                    question_data['correct_answer_id'] = str(correct_answer.id) if correct_answer else None
                    question_data['correct_answer_text'] = correct_answer.text if correct_answer else None
                else:
                    question_data['correct_answer'] = question.correct_answer
                
                data.append(question_data)
            return data
        return []


class QuizAttemptStartSerializer(serializers.Serializer):
    """Serializer for starting a quiz attempt"""
    quiz_id = serializers.UUIDField()
    
    def validate(self, attrs):
        quiz_id = attrs.get('quiz_id')
        request = self.context.get('request')
        
        try:
            quiz = Quiz.objects.get(id=quiz_id, is_published=True)
        except Quiz.DoesNotExist:
            raise serializers.ValidationError("Quiz not found or not published")
        
        # Check if student is enrolled
        from courses.models import Enrollment
        if not Enrollment.objects.filter(
            student=request.user,
            course=quiz.lesson.module.course,
            status='ACTIVE'
        ).exists():
            raise serializers.ValidationError("You must be enrolled in the course to take this quiz")
        
        # Check attempt limit
        attempt_count = QuizAttempt.objects.filter(
            student=request.user,
            quiz=quiz,
            status=QuizAttempt.Status.COMPLETED
        ).count()
        
        if attempt_count >= quiz.max_attempts:
            raise serializers.ValidationError(f"Maximum attempts ({quiz.max_attempts}) reached")
        
        attrs['quiz'] = quiz
        attrs['attempt_number'] = attempt_count + 1
        return attrs


class QuizSubmitSerializer(serializers.Serializer):
    """Serializer for submitting quiz answers"""
    attempt_id = serializers.UUIDField()
    responses = serializers.DictField(
        child=serializers.CharField(),
        help_text="Dictionary of {question_id: answer_id or text}"
    )
    
    def validate(self, attrs):
        attempt_id = attrs.get('attempt_id')
        request = self.context.get('request')
        
        try:
            attempt = QuizAttempt.objects.get(
                id=attempt_id,
                student=request.user,
                status=QuizAttempt.Status.IN_PROGRESS
            )
        except QuizAttempt.DoesNotExist:
            raise serializers.ValidationError("Active quiz attempt not found")
        
        # Check time limit
        if attempt.quiz.time_limit_minutes > 0:
            elapsed = (timezone.now() - attempt.started_at).total_seconds() / 60
            if elapsed > attempt.quiz.time_limit_minutes:
                attempt.status = QuizAttempt.Status.TIMED_OUT
                attempt.save()
                raise serializers.ValidationError("Time limit exceeded")
        
        attrs['attempt'] = attempt
        return attrs