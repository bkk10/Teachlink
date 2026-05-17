"""
CSV Import API Views for TeachLink
Handles CSV import operations, history, and audit logging
"""
import csv
import io
import logging
from datetime import datetime
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from assessments.import_models import ImportHistory, ImportRecord
from assessments.models import Quiz, QuizAttempt
from courses.models import Course, Enrollment
from users.models import User

logger = logging.getLogger(__name__)


class CSVImportAPIView(APIView):
    """
    API endpoint for importing CSV assessment scores
    Stores audit trail and creates quiz attempts
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        """Process CSV file and create import records"""
        if request.user.role not in ['TEACHER', 'ADMIN']:
            return Response(
                {'error': 'Only teachers can import scores'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get uploaded file
        csv_file = request.FILES.get('file')
        course_id = request.data.get('course_id')
        
        if not csv_file:
            return Response(
                {'error': 'No file uploaded'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get course if specified
        course = None
        print(f"DEBUG: course_id from request = {course_id}")
        if course_id:
            try:
                course = Course.objects.get(
                    id=course_id,
                    teacher=request.user
                )
                print(f"DEBUG: Found course = {course.title}")
            except Course.DoesNotExist:
                print(f"DEBUG: Course not found or access denied for course_id={course_id}, teacher={request.user.email}")
                return Response(
                    {'error': 'Course not found or access denied'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Create import history record
        import_history = ImportHistory.objects.create(
            teacher=request.user,
            course=course,
            file_name=csv_file.name,
            original_file=csv_file,
            status=ImportHistory.Status.PROCESSING,
            total_records=0,
            success_count=0,
            error_count=0
        )
        
        try:
            # Parse CSV
            csv_file.seek(0)
            decoded_file = csv_file.read().decode('utf-8-sig')
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)
            
            # Validate headers
            required_headers = ['Student Email', 'Assessment Name', 'Score', 'Date']
            headers = reader.fieldnames or []
            missing_headers = [h for h in required_headers if h not in headers]
            
            if missing_headers:
                import_history.mark_failed(
                    f"Missing required headers: {', '.join(missing_headers)}"
                )
                return Response({
                    'error': f"Missing required headers: {', '.join(missing_headers)}",
                    'import_id': str(import_history.id)
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Process records
            records = []
            row_number = 0
            students_affected = []
            
            for row in reader:
                row_number += 1
                
                # Parse row data
                email = row.get('Student Email', '').strip()
                assessment_name = row.get('Assessment Name', '').strip()
                score_str = row.get('Score', '').strip()
                date_str = row.get('Date', '').strip()
                
                # Validate required fields
                if not all([email, assessment_name, score_str, date_str]):
                    ImportRecord.objects.create(
                        import_history=import_history,
                        row_number=row_number,
                        raw_data=row,
                        student_email=email or 'N/A',
                        assessment_name=assessment_name or 'N/A',
                        score=0,
                        date=timezone.now().date(),
                        status=ImportRecord.Status.ERROR,
                        message='Missing required fields'
                    )
                    import_history.error_count += 1
                    continue
                
                # Parse score
                try:
                    score = float(score_str)
                    if score < 0 or score > 100:
                        raise ValueError("Score must be between 0 and 100")
                except ValueError as e:
                    ImportRecord.objects.create(
                        import_history=import_history,
                        row_number=row_number,
                        raw_data=row,
                        student_email=email,
                        assessment_name=assessment_name,
                        score=0,
                        date=timezone.now().date(),
                        status=ImportRecord.Status.ERROR,
                        message=f'Invalid score: {str(e)}'
                    )
                    import_history.error_count += 1
                    continue
                
                # Parse date
                try:
                    # Try multiple date formats
                    for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%m-%d-%Y']:
                        try:
                            parsed_date = datetime.strptime(date_str, fmt).date()
                            break
                        except ValueError:
                            continue
                    else:
                        raise ValueError("Unable to parse date")
                except Exception as e:
                    ImportRecord.objects.create(
                        import_history=import_history,
                        row_number=row_number,
                        raw_data=row,
                        student_email=email,
                        assessment_name=assessment_name,
                        score=score,
                        date=timezone.now().date(),
                        status=ImportRecord.Status.ERROR,
                        message=f'Invalid date format: {str(e)}'
                    )
                    import_history.error_count += 1
                    continue
                
                # Find student
                try:
                    student = User.objects.get(
                        email__iexact=email,
                        role='STUDENT'
                    )
                except User.DoesNotExist:
                    ImportRecord.objects.create(
                        import_history=import_history,
                        row_number=row_number,
                        raw_data=row,
                        student_email=email,
                        assessment_name=assessment_name,
                        score=score,
                        date=parsed_date,
                        status=ImportRecord.Status.ERROR,
                        message=f'Student not found: {email}'
                    )
                    import_history.error_count += 1
                    continue
                
                # Find quiz/assessment
                quiz = None
                search_course = course
                
                # If no course specified, try to find quiz in any course
                if not search_course:
                    # Try to find the quiz in any course
                    quiz = Quiz.objects.filter(
                        title__iexact=assessment_name
                    ).first()
                    
                    if not quiz:
                        quiz = Quiz.objects.filter(
                            title__icontains=assessment_name
                        ).first()
                else:
                    # Try exact match first in specified course
                    quiz = Quiz.objects.filter(
                        title__iexact=assessment_name,
                        lesson__module__course=course
                    ).first()
                    
                    # Try partial match
                    if not quiz:
                        quiz = Quiz.objects.filter(
                            title__icontains=assessment_name,
                            lesson__module__course=course
                        ).first()
                
                # Try partial match in specified course
                if not quiz:
                    quiz = Quiz.objects.filter(
                        title__icontains=assessment_name,
                        lesson__module__course=course
                    ).first()
                
                # If still no quiz found in course, create one automatically
                if not quiz and search_course:
                    print(f"DEBUG: Attempting to auto-create quiz '{assessment_name}' in course '{search_course.title}'")
                    try:
                        from courses.models import Module, Lesson
                        
                        # Get or create first module
                        module = Module.objects.filter(course=search_course).first()
                        if not module:
                            # Create a default module if none exists
                            module = Module.objects.create(
                                course=search_course,
                                title='Imported Assessments',
                                description='Auto-created module for imported assessments',
                                order=1
                            )
                            print(f"Created new module: {module.title}")
                        
                        # Find or create a lesson without a quiz
                        lesson = None
                        lessons = Lesson.objects.filter(module=module).order_by('order')
                        
                        for l in lessons:
                            # Check if lesson already has a quiz (OneToOne relationship)
                            if not Quiz.objects.filter(lesson=l).exists():
                                lesson = l
                                break
                        
                        if not lesson:
                            # Create a new lesson for this assessment
                            next_order = lessons.count() + 1
                            lesson = Lesson.objects.create(
                                module=module,
                                title=assessment_name,
                                content_type='QUIZ',
                                is_published=True,
                                order=next_order
                            )
                            print(f"Created new lesson: {lesson.title}")
                        
                        # Create the quiz on this lesson - mark as EXTERNAL type for imported assessments
                        quiz = Quiz.objects.create(
                            lesson=lesson,
                            title=assessment_name,
                            description=f'Auto-created from CSV import on {timezone.now().strftime("%Y-%m-%d")}. This is an external/imported assessment.',
                            time_limit_minutes=60,
                            passing_score=50,
                            max_attempts=1,
                            is_published=True,
                            total_questions=0,  # 0 indicates imported/external assessment
                            quiz_type='EXTERNAL'  # Mark as external/imported assessment
                        )
                        print(f"✓ Created external quiz: {assessment_name} (ID: {quiz.id})")
                        
                    except Exception as e:
                        import traceback
                        print(f"✗ FAILED to create quiz: {e}")
                        print(f"TRACEBACK: {traceback.format_exc()}")
                        # Re-raise for now to see the error
                        raise
                
                if not quiz:
                    ImportRecord.objects.create(
                        import_history=import_history,
                        row_number=row_number,
                        raw_data=row,
                        student_email=email,
                        assessment_name=assessment_name,
                        score=score,
                        date=parsed_date,
                        status=ImportRecord.Status.ERROR,
                        message=f'Assessment not found: {assessment_name}'
                    )
                    import_history.error_count += 1
                    continue
                
                # Check enrollment - auto-enroll if not enrolled
                enrollment = Enrollment.objects.filter(
                    student=student,
                    course=quiz.lesson.module.course,
                    status='ACTIVE'
                ).first()
                
                if not enrollment:
                    # Auto-enroll student in the course for import
                    try:
                        enrollment, created = Enrollment.objects.get_or_create(
                            student=student,
                            course=quiz.lesson.module.course,
                            defaults={'status': Enrollment.Status.ACTIVE}
                        )
                        if created:
                            enrollment.status = Enrollment.Status.ACTIVE
                            enrollment.save(update_fields=['status'])
                    except Exception as enroll_err:
                        ImportRecord.objects.create(
                            import_history=import_history,
                            row_number=row_number,
                            raw_data=row,
                            student_email=email,
                            assessment_name=assessment_name,
                            score=score,
                            date=parsed_date,
                            status=ImportRecord.Status.ERROR,
                            message=f'Failed to auto-enroll student: {str(enroll_err)}'
                        )
                        import_history.error_count += 1
                        continue
                
                # Create quiz attempt
                try:
                    with transaction.atomic():
                        # Use current date for imported attempts (not CSV date)
                        # This ensures risk calculations treat imports as recent activity
                        now = timezone.now()
                        
                        # Check for existing attempt today to avoid duplicates
                        existing_attempt = QuizAttempt.objects.filter(
                            student=student,
                            quiz=quiz,
                            submitted_at__date=now.date()
                        ).first()
                        
                        if existing_attempt:
                            # Update existing attempt instead of creating duplicate
                            attempt = existing_attempt
                            attempt.score_percentage = score
                            attempt.score = score
                            attempt.passed = score >= quiz.passing_score
                            attempt.responses = {'imported': True, 'source': 'csv', 'updated': True}
                            attempt.save()
                            message = 'Updated existing attempt'
                            
                            # Create lesson interaction to track access (fixes access count bug)
                            try:
                                from analytics.models import LessonInteraction
                                LessonInteraction.objects.get_or_create(
                                    student=student,
                                    lesson=quiz.lesson,
                                    interaction_type=LessonInteraction.InteractionType.VIEW,
                                    defaults={'created_at': now}
                                )
                            except Exception as interaction_err:
                                logger.warning(f"Failed to create lesson interaction for updated attempt: {interaction_err}")
                        else:
                            # Create new attempt with current timestamp
                            attempt_number = QuizAttempt.objects.filter(
                                student=student,
                                quiz=quiz
                            ).count() + 1
                            
                            attempt = QuizAttempt.objects.create(
                                student=student,
                                quiz=quiz,
                                attempt_number=attempt_number,
                                status=QuizAttempt.Status.COMPLETED,
                                score=score,
                                score_percentage=score,
                                max_possible_score=100,
                                passed=score >= quiz.passing_score,
                                started_at=now,
                                submitted_at=now,
                                responses={'imported': True, 'source': 'csv'}
                            )
                            message = 'Successfully imported'
                            
                            # Create lesson interaction to track access (fixes access count bug)
                            try:
                                from analytics.models import LessonInteraction
                                LessonInteraction.objects.get_or_create(
                                    student=student,
                                    lesson=quiz.lesson,
                                    interaction_type=LessonInteraction.InteractionType.VIEW,
                                    defaults={'created_at': now}
                                )
                            except Exception as interaction_err:
                                logger.warning(f"Failed to create lesson interaction for imported attempt: {interaction_err}")
                        
                        # Auto-complete lesson if student passed the quiz
                        if attempt.passed:
                            try:
                                from courses.models import LessonCompletion, Lesson
                                lesson = quiz.lesson
                                completion, created = LessonCompletion.objects.get_or_create(
                                    student=student,
                                    lesson=lesson,
                                    defaults={
                                        'completed_at': now,
                                        'time_spent_seconds': 3600
                                    }
                                )
                                if created:
                                    print(f"Auto-completed lesson {lesson.title} for {student.email}")
                                    
                                # Recalculate enrollment progress
                                total_lessons = Lesson.objects.filter(
                                    module__course=enrollment.course,
                                    is_published=True
                                ).count()
                                completed_lessons = LessonCompletion.objects.filter(
                                    student=student,
                                    lesson__module__course=enrollment.course
                                ).count()
                                if total_lessons > 0:
                                    enrollment.progress_percentage = (completed_lessons / total_lessons) * 100
                                    enrollment.save(update_fields=['progress_percentage'])
                                    print(f"Updated progress for {student.email}: {enrollment.progress_percentage}%")
                            except Exception as lesson_err:
                                print(f"Failed to auto-complete lesson: {lesson_err}")
                                import traceback
                                traceback.print_exc()
                                pass
                        
                        # Update quiz statistics
                        quiz.update_statistics()
                        
                        # Create import record
                        import_record = ImportRecord.objects.create(
                            import_history=import_history,
                            row_number=row_number,
                            raw_data=row,
                            student_email=email,
                            assessment_name=assessment_name,
                            score=score,
                            date=parsed_date,
                            status=ImportRecord.Status.SUCCESS,
                            message=message,
                            student=student,
                            quiz=quiz,
                            attempt=attempt
                        )
                        
                        # Track student for risk recalculation
                        if str(student.id) not in students_affected:
                            students_affected.append(str(student.id))
                        
                        # Update enrollment performance and trigger risk recalculation
                        attempt.update_enrollment_performance()
                        
                        # Trigger full risk engine recalculation
                        from analytics.services.risk_engine import RiskEngine
                        from analytics.services.alert_generator import AlertGenerator
                        try:
                            RiskEngine.calculate_student_risk(str(enrollment.id))
                            AlertGenerator.check_and_generate_alerts(enrollment_id=str(enrollment.id))
                        except Exception as risk_err:
                            logger.warning(f"Risk recalculation failed for {student.id}: {risk_err}")
                        
                        import_history.success_count += 1
                        
                except Exception as e:
                    logger.exception(f"Failed to create attempt for {email}: {e}")
                    ImportRecord.objects.create(
                        import_history=import_history,
                        row_number=row_number,
                        raw_data=row,
                        student_email=email,
                        assessment_name=assessment_name,
                        score=score,
                        date=parsed_date,
                        status=ImportRecord.Status.ERROR,
                        message=f'Failed to create attempt: {str(e)}'
                    )
                    import_history.error_count += 1
                    continue
            
            # Update import history with course reference
            import_history.total_records = row_number
            import_history.students_affected = students_affected
            import_history.risk_recalculated = True
            if course:
                import_history.course = course
            import_history.mark_completed()
            
            # Update quiz statistics
            for quiz in Quiz.objects.filter(
                id__in=ImportRecord.objects.filter(
                    import_history=import_history,
                    quiz__isnull=False
                ).values_list('quiz', flat=True).distinct()
            ):
                quiz.update_statistics()
            
            return Response({
                'success': True,
                'import_id': str(import_history.id),
                'file_name': csv_file.name,
                'total_records': import_history.total_records,
                'success_count': import_history.success_count,
                'error_count': import_history.error_count,
                'success_rate': import_history.success_rate,
                'students_affected': len(students_affected),
                'message': f'Import completed. {import_history.success_count} records imported successfully, {import_history.error_count} errors.'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"IMPORT ERROR: {str(e)}")
            print(f"TRACEBACK: {error_details}")
            logger.exception(f"CSV import failed: {e}")
            import_history.mark_failed(str(e))
            return Response({
                'error': str(e),
                'import_id': str(import_history.id)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def import_history_list(request):
    """Get list of import history for current teacher"""
    if request.user.role not in ['TEACHER', 'ADMIN']:
        return Response(
            {'error': 'Access denied'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Filter by course if provided
    course_id = request.query_params.get('course_id')
    
    imports = ImportHistory.objects.filter(teacher=request.user)
    
    if course_id:
        imports = imports.filter(course_id=course_id)
    
    # Pagination
    limit = int(request.query_params.get('limit', 20))
    offset = int(request.query_params.get('offset', 0))
    
    total = imports.count()
    imports = imports[offset:offset + limit]
    
    data = []
    for imp in imports:
        data.append({
            'id': str(imp.id),
            'file_name': imp.file_name,
            'course': {
                'id': str(imp.course.id),
                'title': imp.course.title
            } if imp.course else None,
            'status': imp.status,
            'total_records': imp.total_records,
            'success_count': imp.success_count,
            'error_count': imp.error_count,
            'success_rate': imp.success_rate,
            'started_at': imp.started_at.isoformat(),
            'completed_at': imp.completed_at.isoformat() if imp.completed_at else None,
            'processing_time_seconds': imp.processing_time_seconds,
            'is_rolled_back': imp.is_rolled_back,
            'can_download': bool(imp.original_file),
            'students_affected_count': len(imp.students_affected)
        })
    
    return Response({
        'imports': data,
        'total': total,
        'limit': limit,
        'offset': offset
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def import_history_detail(request, import_id):
    """Get detailed information about a specific import"""
    if request.user.role not in ['TEACHER', 'ADMIN']:
        return Response(
            {'error': 'Access denied'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    import_history = get_object_or_404(
        ImportHistory,
        id=import_id,
        teacher=request.user
    )
    
    # Get all records
    records = []
    for record in import_history.records.all():
        records.append({
            'id': str(record.id),
            'row_number': record.row_number,
            'student_email': record.student_email,
            'assessment_name': record.assessment_name,
            'score': float(record.score),
            'date': record.date.isoformat(),
            'status': record.status,
            'message': record.message,
            'is_edited': record.is_edited,
            'edited_at': record.edited_at.isoformat() if record.edited_at else None,
            'original_score': float(record.original_score) if record.original_score else None,
            'student': {
                'id': str(record.student.id),
                'name': record.student.display_name
            } if record.student else None,
            'quiz': {
                'id': str(record.quiz.id),
                'title': record.quiz.title
            } if record.quiz else None,
            'attempt_id': str(record.attempt.id) if record.attempt else None
        })
    
    return Response({
        'id': str(import_history.id),
        'file_name': import_history.file_name,
        'course': {
            'id': str(import_history.course.id),
            'title': import_history.course.title
        } if import_history.course else None,
        'status': import_history.status,
        'total_records': import_history.total_records,
        'success_count': import_history.success_count,
        'error_count': import_history.error_count,
        'warning_count': import_history.warning_count,
        'success_rate': import_history.success_rate,
        'started_at': import_history.started_at.isoformat(),
        'completed_at': import_history.completed_at.isoformat() if import_history.completed_at else None,
        'processing_time_seconds': import_history.processing_time_seconds,
        'error_log': import_history.error_log,
        'is_rolled_back': import_history.is_rolled_back,
        'rolled_back_at': import_history.rolled_back_at.isoformat() if import_history.rolled_back_at else None,
        'students_affected': import_history.students_affected,
        'risk_recalculated': import_history.risk_recalculated,
        'records': records
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def rollback_import(request, import_id):
    """Rollback an import by deleting all associated records"""
    # Immediate console logging
    print(f"ROLLBACK REQUEST: user={request.user.email}, role={request.user.role}, import_id={import_id}")
    logger.info(f"Rollback requested by {request.user.email} (role: {request.user.role}) for import {import_id}")
    
    # Check role
    user_role = request.user.role
    if user_role not in ['TEACHER', 'ADMIN']:
        msg = f'Access denied - role "{user_role}" not in [TEACHER, ADMIN]'
        print(f"ROLLBACK DENIED: {msg}")
        logger.warning(f"Rollback denied: {msg}")
        return Response(
            {'error': msg},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Get the import history
    try:
        if user_role == 'ADMIN':
            import_history = ImportHistory.objects.get(id=import_id)
            print(f"ROLLBACK: Admin accessing import {import_id}")
        else:
            import_history = ImportHistory.objects.get(id=import_id, teacher=request.user)
            print(f"ROLLBACK: Teacher accessing own import {import_id}")
    except ImportHistory.DoesNotExist:
        print(f"ROLLBACK DENIED: Import {import_id} not found or doesn't belong to teacher")
        # Check if import exists at all
        if ImportHistory.objects.filter(id=import_id).exists():
            return Response(
                {'error': 'Import exists but belongs to another teacher. Cannot rollback.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return Response(
            {'error': 'Import not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    if import_history.is_rolled_back:
        return Response(
            {'error': 'This import has already been rolled back'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        deleted_count = import_history.rollback(request.user)
        msg = f'Import rolled back successfully. {deleted_count} records deleted.'
        print(f"ROLLBACK SUCCESS: {msg}")
        logger.info(f"Import {import_id} rolled back by {request.user.email}. {deleted_count} records deleted.")
        
        return Response({
            'success': True,
            'message': msg,
            'import_id': str(import_history.id),
            'deleted_records': deleted_count
        })
    except Exception as e:
        logger.exception(f"Rollback failed for import {import_id}: {e}")
        print(f"ROLLBACK ERROR: {str(e)}")
        return Response({
            'error': f'Failed to rollback import: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def edit_import_record(request, record_id):
    """Edit a specific imported record (score, date, etc.)"""
    if request.user.role not in ['TEACHER', 'ADMIN']:
        return Response(
            {'error': 'Access denied'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    record = get_object_or_404(
        ImportRecord,
        id=record_id,
        import_history__teacher=request.user
    )
    
    new_score = request.data.get('score')
    
    if new_score is None:
        return Response(
            {'error': 'New score is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        new_score = float(new_score)
        if new_score < 0 or new_score > 100:
            raise ValueError("Score must be between 0 and 100")
    except ValueError as e:
        return Response(
            {'error': f'Invalid score: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Edit the record
    old_score = float(record.score)
    record.edit_score(new_score, request.user)
    
    return Response({
        'success': True,
        'message': 'Score updated successfully',
        'record_id': str(record.id),
        'old_score': old_score,
        'new_score': new_score,
        'is_edited': record.is_edited,
        'edited_at': record.edited_at.isoformat() if record.edited_at else None
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_import_record(request, record_id):
    """Delete a specific imported record and its associated attempt"""
    if request.user.role not in ['TEACHER', 'ADMIN']:
        return Response(
            {'error': 'Access denied'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    record = get_object_or_404(
        ImportRecord,
        id=record_id,
        import_history__teacher=request.user
    )
    
    try:
        record.delete_record()
        
        return Response({
            'success': True,
            'message': 'Record deleted successfully',
            'record_id': str(record.id)
        })
    except Exception as e:
        return Response({
            'error': f'Failed to delete record: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_import_template(request):
    """Download CSV template for import"""
    if request.user.role not in ['TEACHER', 'ADMIN']:
        return Response(
            {'error': 'Access denied'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="assessment_import_template.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Student Email', 'Assessment Name', 'Score', 'Date'])
    writer.writerow(['student@example.com', 'Introduction to Machine Learning', '85', '2024-01-15'])
    writer.writerow(['student2@example.com', 'Introduction to Machine Learning', '92', '2024-01-15'])
    
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_import_csv(request, import_id):
    """Download the original CSV file for an import"""
    if request.user.role not in ['TEACHER', 'ADMIN']:
        return Response(
            {'error': 'Access denied'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    import_history = get_object_or_404(
        ImportHistory,
        id=import_id,
        teacher=request.user
    )
    
    if not import_history.original_file:
        return Response(
            {'error': 'Original file not available'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    response = FileResponse(
        import_history.original_file.open(),
        content_type='text/csv'
    )
    response['Content-Disposition'] = f'attachment; filename="{import_history.file_name}"'
    return response
