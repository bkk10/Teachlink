"""
Risk Engine Service
Calculates student risk scores and trend direction over time.
"""
from decimal import Decimal
from datetime import timedelta
from typing import Dict, Optional, Any, List

from django.conf import settings
from django.utils import timezone

from courses.models import Enrollment
from analytics.models import RiskHistory

class RiskEngine:
    """
    Longitudinal risk scoring engine.
    Outputs risk score in range 0.0-1.0 plus trend direction.
    """
    
    # Weights for composite risk score
    WEIGHTS = {
        'progress': Decimal('0.40'),
        'quiz': Decimal('0.40'),
        'inactivity': Decimal('0.20'),
    }
    
    STABLE_DELTA = Decimal('0.05')
    HISTORY_SCORE_EPSILON = Decimal('0.001')

    @classmethod
    def _resolve_weights(cls, course) -> Dict[str, Decimal]:
        """Resolve weights: defaults, optional course-level overrides, fall back to settings."""
        weights = cls.WEIGHTS.copy()

        # Course-level override fields (if implemented) should be stored as JSON/dict
        if hasattr(course, 'risk_weights') and isinstance(course.risk_weights, dict):
            for key in ['progress', 'quiz', 'inactivity']:
                if key in course.risk_weights:
                    try:
                        value = Decimal(str(course.risk_weights[key]))
                        if Decimal('0') <= value <= Decimal('1'):
                            weights[key] = value
                    except Exception:
                        pass

        # Settings override for global test/capstone tuning
        config_weights = settings.TEACHLINK_CONFIG.get('RISK_WEIGHTS', {}) if hasattr(settings, 'TEACHLINK_CONFIG') else {}
        for key in ['progress', 'quiz', 'inactivity']:
            if key in config_weights:
                try:
                    value = Decimal(str(config_weights[key]))
                    if Decimal('0') <= value <= Decimal('1'):
                        weights[key] = value
                except Exception:
                    pass

        # Normalize to ensure sum to 1.0
        total = weights.get('progress', Decimal('0')) + weights.get('quiz', Decimal('0')) + weights.get('inactivity', Decimal('0'))
        if total == Decimal('0'):
            return cls.WEIGHTS.copy()

        return {
            'progress': (weights['progress'] / total).quantize(Decimal('0.01')),
            'quiz': (weights['quiz'] / total).quantize(Decimal('0.01')),
            'inactivity': (weights['inactivity'] / total).quantize(Decimal('0.01')),
        }

    @classmethod
    def calculate_student_risk(cls, enrollment_id: str) -> Optional[Dict[str, Any]]:
        """
        Calculate risk score and trend for a student enrollment.
        Uses mastery-based approach: recent passing scores demonstrate competence.
        Returns a dict with score (0.0-1.0), level, trend and components.
        """
        try:
            enrollment = Enrollment.objects.select_related(
                'student', 'course'
            ).get(id=enrollment_id)
        except Enrollment.DoesNotExist:
            return None
        
        previous_risk_score = cls._get_previous_risk_score(enrollment)

        # Inputs
        progress_pct = cls._sanitize_percentage(enrollment.progress_percentage)
        days_inactive = max(0, int(enrollment.days_since_last_activity))

        # Calculate quiz performance using mastery-based approach
        quiz_avg_pct, recent_quiz_performance, has_recent_pass = cls._calculate_mastery_based_quiz_score(enrollment)
        
        # Convert inputs to risk components (0.0-1.0, higher means worse)
        progress_risk = Decimal('1.0') - (progress_pct / Decimal('100'))
        quiz_risk = Decimal('1.0') - (quiz_avg_pct / Decimal('100'))
        inactivity_risk = cls._calculate_inactivity_risk(days_inactive)
        
        # Dynamic weight adjustment: if student has recent passes, reduce progress penalty
        weights = cls._resolve_weights(enrollment.course)
        
        # If student has recent quiz passes (demonstrated mastery), reduce progress risk weight
        if has_recent_pass and quiz_avg_pct >= Decimal('60'):
            # Student is showing competence - progress matters less than demonstrated ability
            adjusted_weights = {
                'progress': Decimal('0.25'),
                'quiz': Decimal('0.50'),
                'inactivity': Decimal('0.25'),
            }
        else:
            adjusted_weights = weights

        risk_score = (
            (progress_risk * adjusted_weights['progress']) +
            (quiz_risk * adjusted_weights['quiz']) +
            (inactivity_risk * adjusted_weights['inactivity'])
        )
        risk_score = cls._clamp_decimal(risk_score, Decimal('0.0'), Decimal('1.0'))

        risk_level = cls._determine_risk_level(risk_score)
        risk_trend = cls._determine_risk_trend(previous_risk_score, risk_score)
        
        # Calculate engagement - boosted if recent quiz activity
        recency_score = max(Decimal('0.0'), Decimal('1.0') - (Decimal(days_inactive) / Decimal('14.0')))
        completion_rate = progress_pct / Decimal('100')
        quiz_rate = quiz_avg_pct / Decimal('100')
        
        # If student took quizzes recently, boost engagement
        if has_recent_pass:
            recency_score = max(recency_score, Decimal('0.8'))
        
        engagement_score = (
            recency_score * Decimal('0.4') +
            completion_rate * Decimal('0.3') +
            quiz_rate * Decimal('0.3')
        )
        engagement_score = cls._clamp_decimal(engagement_score, Decimal('0.0'), Decimal('1.0'))
        engagement_pct = float(engagement_score * Decimal('100'))
        
        result = {
            'enrollment_id': str(enrollment.id),
            'student_id': str(enrollment.student.id),
            'student_name': enrollment.student.display_name,
            'course_id': str(enrollment.course.id),
            'course_title': enrollment.course.title,
            'risk_score': float(risk_score),
            'previous_risk_score': float(previous_risk_score),
            'risk_level': risk_level,
            'risk_trend': risk_trend,
            'components': {
                'performance': float(quiz_avg_pct),
                'progress': float(progress_pct),
                'engagement': round(engagement_pct, 1),
                'inactivity': float(inactivity_risk),
                'days_inactive': days_inactive,
                'recent_quiz_performance': float(recent_quiz_performance) if recent_quiz_performance else None,
                'has_recent_pass': has_recent_pass,
            },
            'contributing_factors': cls._identify_contributing_factors(
                progress_pct=progress_pct,
                quiz_avg_pct=quiz_avg_pct,
                inactivity_risk=inactivity_risk,
                days_inactive=days_inactive,
                has_recent_pass=has_recent_pass,
            ),
            'calculated_at': timezone.now().isoformat()
        }
        
        cls._save_risk_history(enrollment, result)
        
        enrollment.risk_score = risk_score
        enrollment.risk_level = risk_level
        enrollment.engagement_score = engagement_score
        enrollment.save(update_fields=['risk_score', 'risk_level', 'engagement_score'])
        
        return result
    
    @classmethod
    def _sanitize_percentage(cls, value: Any) -> Decimal:
        """Normalize percentage value to 0-100 range."""
        try:
            pct = Decimal(str(value))
        except Exception:
            pct = Decimal('0')
        return cls._clamp_decimal(pct, Decimal('0'), Decimal('100'))
    
    @classmethod
    def _calculate_inactivity_risk(cls, days_inactive: int) -> Decimal:
        """
        Map inactivity days to normalized risk (0.0-1.0).
        Uses critical threshold from settings (default 14 days).
        """
        critical_days = int(
            settings.TEACHLINK_CONFIG.get('INACTIVITY_DAYS_CRITICAL', 14)
        )
        if critical_days <= 0:
            critical_days = 14
        return cls._clamp_decimal(
            Decimal(days_inactive) / Decimal(critical_days),
            Decimal('0.0'),
            Decimal('1.0'),
        )
    
    @classmethod
    def _get_previous_risk_score(cls, enrollment: Enrollment) -> Decimal:
        """
        Previous risk score input for trend analysis.
        Priority: latest history entry, then enrollment.risk_score.
        """
        latest_history = RiskHistory.objects.filter(
            enrollment=enrollment
        ).order_by('-calculated_at').first()

        if latest_history and latest_history.risk_score is not None:
            return cls._clamp_decimal(
                Decimal(str(latest_history.risk_score)),
                Decimal('0.0'),
                Decimal('1.0'),
            )
        if enrollment.risk_score is not None:
            return cls._clamp_decimal(
                Decimal(str(enrollment.risk_score)),
                Decimal('0.0'),
                Decimal('1.0'),
            )
        return Decimal('0.0')

    @classmethod
    def _calculate_mastery_based_quiz_score(cls, enrollment: Enrollment):
        """
        Calculate quiz score using mastery-based approach.
        
        Strategy:
        - Look at attempts from last 30 days
        - Use best score as indicator of demonstrated mastery
        - Weight recent attempts more heavily
        - If student has passed any quiz recently, boost the score
        
        Returns: (effective_score, recent_best_score, has_recent_pass)
        """
        from assessments.models import QuizAttempt
        from django.db.models import Max, Avg
        
        now = timezone.now()
        thirty_days_ago = now - timedelta(days=30)
        seven_days_ago = now - timedelta(days=7)
        
        # Get all completed attempts for this enrollment's course
        all_attempts = QuizAttempt.objects.filter(
            student=enrollment.student,
            quiz__lesson__module__course=enrollment.course,
            status=QuizAttempt.Status.COMPLETED
        ).order_by('-submitted_at')
        
        if not all_attempts.exists():
            return Decimal('0'), None, False
        
        # Check for recent passing attempts (within 30 days)
        recent_attempts = all_attempts.filter(submitted_at__gte=thirty_days_ago)
        recent_best = recent_attempts.aggregate(max_score=Max('score_percentage'))['max_score']
        has_recent_pass = recent_attempts.filter(passed=True).exists()
        
        # Calculate mastery score with heavy recency weighting
        # Strategy: 70% weight on best recent score, 30% on historical average
        if recent_best:
            recent_best_pct = Decimal(str(recent_best))
        else:
            recent_best_pct = Decimal('0')
        
        # Historical average (all attempts)
        historical_avg = all_attempts.aggregate(avg_score=Avg('score_percentage'))['avg_score']
        if historical_avg:
            historical_pct = Decimal(str(historical_avg))
        else:
            historical_pct = Decimal('0')
        
        # Special case: if student has recent passing scores, use best recent score
        # with only light consideration of historical failures
        if has_recent_pass and recent_best_pct >= Decimal('60'):
            # Student has demonstrated mastery recently
            # Use 85% best recent, 15% historical to avoid extreme swings
            effective_score = (recent_best_pct * Decimal('0.85')) + (historical_pct * Decimal('0.15'))
        elif recent_attempts.exists():
            # Has recent attempts but no passes - use 60% recent, 40% historical
            effective_score = (recent_best_pct * Decimal('0.60')) + (historical_pct * Decimal('0.40'))
        else:
            # No recent attempts - use historical with penalty for staleness
            last_attempt = all_attempts.first()
            if last_attempt and last_attempt.submitted_at:
                days_since_last = (now - last_attempt.submitted_at).days
                staleness_factor = max(Decimal('0.5'), Decimal('1.0') - (Decimal(days_since_last) / Decimal('60')))
                effective_score = historical_pct * staleness_factor
            else:
                effective_score = historical_pct
        
        return (
            cls._clamp_decimal(effective_score, Decimal('0'), Decimal('100')),
            float(recent_best_pct) if recent_best else None,
            has_recent_pass
        )
    
    @classmethod
    def _determine_risk_level(cls, risk_score: Decimal) -> str:
        """Determine risk level from normalized score (0.0-1.0)."""
        if risk_score >= Decimal('0.70'):
            return RiskHistory.RiskLevel.HIGH
        elif risk_score >= Decimal('0.40'):
            return RiskHistory.RiskLevel.MEDIUM
        return RiskHistory.RiskLevel.LOW
    
    @classmethod
    def _determine_risk_trend(cls, previous: Decimal, current: Decimal) -> str:
        """
        Determine trend direction.
        Stable takes precedence when delta is within +/- 0.05.
        """
        if abs(current - previous) <= cls.STABLE_DELTA:
            return 'STABLE'
        if current < previous:
            return 'IMPROVING'
        return 'DECLINING'

    @classmethod
    def _identify_contributing_factors(
        cls,
        progress_pct: Decimal,
        quiz_avg_pct: Decimal,
        inactivity_risk: Decimal,
        days_inactive: int,
        has_recent_pass: bool = False,
    ) -> List[Dict[str, Any]]:
        """Identify major drivers of current risk score."""
        factors = []
        
        # Only flag low progress if student hasn't shown mastery recently
        if progress_pct < Decimal('40') and not has_recent_pass:
            factors.append({
                'factor': 'Low course progress',
                'score': float(progress_pct),
                'impact': 'high' if progress_pct < Decimal('25') else 'medium'
            })
        elif progress_pct < Decimal('40') and has_recent_pass:
            # Student has passed quizzes but low progress - suggest lesson completion
            factors.append({
                'factor': 'Low lesson completion (despite quiz mastery)',
                'score': float(progress_pct),
                'impact': 'medium'
            })
        
        # Quiz performance factor - reduced if recent passes exist
        if quiz_avg_pct < Decimal('50') and not has_recent_pass:
            factors.append({
                'factor': 'Low quiz performance',
                'score': float(quiz_avg_pct),
                'impact': 'high' if quiz_avg_pct < Decimal('35') else 'medium'
            })
        elif quiz_avg_pct < Decimal('50') and has_recent_pass:
            # Student has recent passes but average is low due to old failures
            factors.append({
                'factor': 'Historical quiz failures (recent attempts show improvement)',
                'score': float(quiz_avg_pct),
                'impact': 'low'
            })
        
        if inactivity_risk >= Decimal('0.50'):
            factors.append({
                'factor': 'Inactivity',
                'score': float(inactivity_risk),
                'days_inactive': days_inactive,
                'impact': 'high' if inactivity_risk >= Decimal('0.80') else 'medium'
            })
        
        # Add positive factor if student has recent passes
        if has_recent_pass and quiz_avg_pct >= Decimal('60'):
            factors.append({
                'factor': 'Recent quiz mastery demonstrated',
                'score': float(quiz_avg_pct),
                'impact': 'positive'
            })
        
        return factors
    
    @classmethod
    def _save_risk_history(cls, enrollment, result):
        """
        Save risk assessment to history table.
        Deduplicate noisy recalculations when score/level is unchanged.
        """
        now = timezone.now()
        new_score = Decimal(str(result['risk_score'])).quantize(Decimal('0.001'))
        new_level = result['risk_level']

        latest_entry = RiskHistory.objects.filter(
            enrollment=enrollment
        ).order_by('-calculated_at').first()

        # Skip if there is no meaningful change from the latest stored snapshot.
        if latest_entry:
            latest_score = Decimal(str(latest_entry.risk_score)).quantize(Decimal('0.001'))
            if (
                latest_entry.risk_level == new_level and
                abs(new_score - latest_score) <= cls.HISTORY_SCORE_EPSILON
            ):
                return

        # Extra guard: avoid multiple identical rows in the same minute window.
        one_minute_ago = now - timedelta(minutes=1)
        recent_duplicate = RiskHistory.objects.filter(
            enrollment=enrollment,
            calculated_at__gte=one_minute_ago,
            risk_level=new_level,
        ).order_by('-calculated_at').first()
        if recent_duplicate:
            recent_score = Decimal(str(recent_duplicate.risk_score)).quantize(Decimal('0.001'))
            if abs(new_score - recent_score) <= cls.HISTORY_SCORE_EPSILON:
                return

        RiskHistory.objects.create(
            student=enrollment.student,
            course=enrollment.course,
            enrollment=enrollment,
            risk_score=new_score,
            risk_level=new_level,
            performance_score=Decimal(str(result['components']['performance'] / 100)),
            progress_score=Decimal(str(result['components']['progress'] / 100)),
            engagement_score=Decimal(str(result['components']['engagement'] / 100)),
            contributing_factors=result['contributing_factors']
        )
    
    @classmethod
    def batch_calculate_risk(cls, course_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Batch calculate risk scores for all active enrollments
        """
        from courses.models import Enrollment
        
        enrollments = Enrollment.objects.filter(
            status=Enrollment.Status.ACTIVE
        )
        
        if course_id:
            enrollments = enrollments.filter(course_id=course_id)
        
        results = []
        for enrollment in enrollments:
            try:
                result = cls.calculate_student_risk(str(enrollment.id))
                if result:
                    results.append(result)
            except Exception as e:
                print(f"Error calculating risk for {enrollment.id}: {e}")
        
        return results
    
    @classmethod
    def get_risk_trend(cls, student_id: str, course_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """
        Get risk score trend for a student over time
        Returns normalized scores (0.0-1.0)
        """
        history = RiskHistory.objects.filter(
            student_id=student_id,
            course_id=course_id,
            calculated_at__gte=timezone.now() - timedelta(days=days)
        ).order_by('calculated_at')
        
        return [
            {
                'date': h.calculated_at.date(),
                'risk_score': float(h.risk_score),
                'risk_level': h.risk_level,
                'performance': float(h.performance_score),
                'progress': float(h.progress_score),
                'engagement': float(h.engagement_score)
            }
            for h in history
        ]

    @staticmethod
    def _clamp_decimal(value: Decimal, minimum: Decimal, maximum: Decimal) -> Decimal:
        """Clamp Decimal value to [minimum, maximum]."""
        return max(minimum, min(maximum, value))
