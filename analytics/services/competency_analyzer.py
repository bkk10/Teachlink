"""
Analytics services for competency tracking and difficulty analysis.
Phase 2: Per-competency performance aggregation and proficiency levels.
"""
from decimal import Decimal
from typing import Dict, List, Tuple
from django.db.models import Q, Count, Avg, Sum
from courses.models import Competency, Lesson
from analytics.models import CompetencyPerformance
from assessments.models import QuizAttempt, Question


class CompetencyAnalyzer:
    """
    Analyze student performance on specific competencies.
    Aggregates question-level data to per-competency scores.
    """
    
    @staticmethod
    def update_student_competency_performance(student_id: str, quiz_attempt_id: str, course_id: str) -> Dict[str, List[str]]:
        """
        Update CompetencyPerformance records for a student after a quiz attempt.
        Called when a QuizAttempt is completed.
        
        Args:
            student_id: Student UUID
            quiz_attempt_id: QuizAttempt UUID
            course_id: Course UUID
            
        Returns:
            Dict with updated competencies
        """
        from django.contrib.auth import get_user_model
        from courses.models import Course
        
        User = get_user_model()
        
        try:
            student = User.objects.get(id=student_id)
            quiz_attempt = QuizAttempt.objects.get(id=quiz_attempt_id)
            course = Course.objects.get(id=course_id)
        except Exception as e:
            return {"error": str(e)}
        
        # Get all questions in the quiz with their competencies
        questions_with_competencies = Question.objects.filter(
            quiz=quiz_attempt.quiz
        ).prefetch_related('competencies')
        
        # Parse quiz attempt responses
        responses = quiz_attempt.responses or {}  # JSON format: {question_id: {answer, is_correct}}
        
        # Aggregate by competency
        competency_performance = {}
        
        for question in questions_with_competencies:
            if not question.competencies.exists():
                continue
            
            # Check if this question was answered in the attempt
            question_response = responses.get(str(question.id), {})
            is_correct = question_response.get('is_correct', False)
            
            # Update performance for each competency
            for competency in question.competencies.all():
                if competency.id not in competency_performance:
                    competency_performance[competency.id] = {
                        'competency': competency,
                        'attempts': 0,
                        'correct': 0,
                    }
                
                competency_performance[competency.id]['attempts'] += 1
                if is_correct:
                    competency_performance[competency.id]['correct'] += 1
        
        # Update or create CompetencyPerformance records
        updated_competencies = []
        
        for competency_id, perf_data in competency_performance.items():
            competency = perf_data['competency']
            attempts = perf_data['attempts']
            correct = perf_data['correct']
            
            # Calculate score percentage
            score_percentage = Decimal(correct * 100 / attempts) if attempts > 0 else Decimal('0.00')
            
            # Get or create CompetencyPerformance
            comp_perf, created = CompetencyPerformance.objects.get_or_create(
                student=student,
                competency=competency,
                course=course,
                defaults={
                    'score_percentage': score_percentage,
                    'attempts_count': attempts,
                    'correct_count': correct,
                }
            )
            
            if not created:
                # Update existing record
                comp_perf.attempts_count += attempts
                comp_perf.correct_count += correct
                comp_perf.score_percentage = Decimal(
                    comp_perf.correct_count * 100 / comp_perf.attempts_count
                ) if comp_perf.attempts_count > 0 else Decimal('0.00')
                comp_perf.save()
            
            # Update proficiency level
            comp_perf.update_proficiency_level()
            
            updated_competencies.append(str(competency.id))
        
        return {
            "status": "success",
            "updated_competencies": updated_competencies,
            "count": len(updated_competencies)
        }
    
    @staticmethod
    def get_student_competency_heatmap(student_id: str, course_id: str) -> Dict[str, List[Dict]]:
        """
        Get heatmap of student competency performance for a course.
        Used for dashboard visualization.
        
        Args:
            student_id: Student UUID
            course_id: Course UUID
            
        Returns:
            Dict with competencies grouped by category and performance levels
        """
        from django.contrib.auth import get_user_model
        from courses.models import Course
        
        User = get_user_model()
        
        try:
            student = User.objects.get(id=student_id)
            course = Course.objects.get(id=course_id)
        except Exception:
            return {}
        
        # Get all CompetencyPerformance records
        perfs = CompetencyPerformance.objects.filter(
            student=student,
            course=course
        ).select_related('competency')
        
        # Group by category
        heatmap = {}
        for perf in perfs:
            category = perf.competency.category or 'Uncategorized'
            
            if category not in heatmap:
                heatmap[category] = []
            
            heatmap[category].append({
                'competency_id': str(perf.competency.id),
                'competency_name': perf.competency.name,
                'score_percentage': float(perf.score_percentage),
                'proficiency_level': perf.proficiency_level,
                'attempts_count': perf.attempts_count,
            })
        
        return heatmap
    
    @staticmethod
    def get_course_competency_difficulty_analysis(course_id: str) -> Dict[str, Dict]:
        """
        Analyze which competencies are causing difficulty across the course.
        Helps teachers identify which topics need more instruction.
        
        Args:
            course_id: Course UUID
            
        Returns:
            Dict with difficulty metrics per competency
        """
        from courses.models import Course, Competency
        
        course = Course.objects.get(id=course_id)
        
        # Get all competencies in the course
        competencies = Competency.objects.filter(course=course)
        
        analysis = {}
        
        for competency in competencies:
            perfs = CompetencyPerformance.objects.filter(
                competency=competency
            ).aggregate(
                avg_score=Avg('score_percentage'),
                student_count=Count('student', distinct=True),
                novice_count=Count('id', filter=Q(proficiency_level='NOVICE')),
                developing_count=Count('id', filter=Q(proficiency_level='DEVELOPING')),
                proficient_count=Count('id', filter=Q(proficiency_level='PROFICIENT')),
                advanced_count=Count('id', filter=Q(proficiency_level='ADVANCED')),
            )
            
            total_records = sum([
                perfs['novice_count'] or 0,
                perfs['developing_count'] or 0,
                perfs['proficient_count'] or 0,
                perfs['advanced_count'] or 0,
            ])
            
            analysis[str(competency.id)] = {
                'competency_name': competency.name,
                'category': competency.category,
                'average_score': float(perfs['avg_score'] or 0),
                'student_count': perfs['student_count'] or 0,
                'proficiency_distribution': {
                    'NOVICE': perfs['novice_count'] or 0,
                    'DEVELOPING': perfs['developing_count'] or 0,
                    'PROFICIENT': perfs['proficient_count'] or 0,
                    'ADVANCED': perfs['advanced_count'] or 0,
                },
                'difficulty_level': CompetencyAnalyzer._determine_difficulty_level(
                    float(perfs['avg_score'] or 0)
                )
            }
        
        return analysis
    
    @staticmethod
    def _determine_difficulty_level(avg_score: float) -> str:
        """Determine difficulty level based on average score"""
        if avg_score >= 85:
            return 'LOW'
        elif avg_score >= 60:
            return 'MEDIUM'
        else:
            return 'HIGH'
