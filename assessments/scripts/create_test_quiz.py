#!/usr/bin/env python
"""
Create test quiz with questions and answers for Teachly
Run: python manage.py shell < scripts/create_test_quiz.py
"""
import django
import os
import sys
from decimal import Decimal

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'teachly.settings.development')
django.setup()

from django.contrib.auth import get_user_model
from courses.models import Course, Module, Lesson, Enrollment
from assessments.models import Quiz, Question, Answer, QuizAttempt
from django.utils import timezone

User = get_user_model()

def create_test_quiz():
    print("=" * 60)
    print("📝 CREATING TEST QUIZ WITH QUESTIONS AND ANSWERS")
    print("=" * 60)
    
    # 1. Get or create a lesson for the quiz
    try:
        # Try to get existing lesson from Web Development course
        lesson = Lesson.objects.filter(
            module__course__title__icontains='Web Development',
            content_type='TEXT'
        ).first()
        
        if not lesson:
            # Create a test lesson if none exists
            course = Course.objects.filter(title__icontains='Web Development').first()
            if not course:
                teacher = User.objects.filter(role='TEACHER').first()
                course = Course.objects.create(
                    title='Test Course',
                    description='Course for testing quizzes',
                    teacher=teacher,
                    status='PUBLISHED'
                )
            
            module = Module.objects.create(
                course=course,
                title='Test Module',
                description='Module for testing',
                order=1
            )
            
            lesson = Lesson.objects.create(
                module=module,
                title='Test Quiz Lesson',
                content_type='TEXT',
                content_text='This lesson contains a test quiz',
                is_published=True,
                order=1
            )
            print(f"✅ Created test lesson: {lesson.title}")
        else:
            print(f"✅ Using existing lesson: {lesson.title}")
        
        # 2. Create or update quiz
        quiz, created = Quiz.objects.update_or_create(
            lesson=lesson,
            defaults={
                'title': 'HTML Fundamentals Quiz',
                'description': 'Test your knowledge of HTML basics',
                'quiz_type': 'MCQ',
                'time_limit_minutes': 15,
                'passing_score': 70,
                'max_attempts': 3,
                'shuffle_questions': True,
                'show_answers': True,
                'is_published': True
            }
        )
        
        if created:
            print(f"✅ Created new quiz: {quiz.title}")
        else:
            print(f"✅ Updated existing quiz: {quiz.title}")
        
        # 3. Delete existing questions to avoid duplicates
        Question.objects.filter(quiz=quiz).delete()
        print("🧹 Cleared existing questions")
        
        # 4. Create questions with answers
        questions_data = [
            {
                'text': 'What does HTML stand for?',
                'question_type': 'MCQ',
                'points': 10,
                'order': 1,
                'answers': [
                    {'text': 'Hyper Text Markup Language', 'is_correct': True, 'order': 1},
                    {'text': 'High Tech Modern Language', 'is_correct': False, 'order': 2},
                    {'text': 'Hyper Transfer Markup Language', 'is_correct': False, 'order': 3},
                    {'text': 'Home Tool Markup Language', 'is_correct': False, 'order': 4},
                ]
            },
            {
                'text': 'Which tag is used for the largest heading in HTML?',
                'question_type': 'MCQ',
                'points': 10,
                'order': 2,
                'answers': [
                    {'text': '<h1>', 'is_correct': True, 'order': 1},
                    {'text': '<heading>', 'is_correct': False, 'order': 2},
                    {'text': '<h6>', 'is_correct': False, 'order': 3},
                    {'text': '<head>', 'is_correct': False, 'order': 4},
                ]
            },
            {
                'text': 'Which tag is used to create a hyperlink?',
                'question_type': 'MCQ',
                'points': 10,
                'order': 3,
                'answers': [
                    {'text': '<a>', 'is_correct': True, 'order': 1},
                    {'text': '<link>', 'is_correct': False, 'order': 2},
                    {'text': '<href>', 'is_correct': False, 'order': 3},
                    {'text': '<url>', 'is_correct': False, 'order': 4},
                ]
            },
            {
                'text': 'What is the correct HTML for inserting an image?',
                'question_type': 'MCQ',
                'points': 10,
                'order': 4,
                'answers': [
                    {'text': '<img src="image.jpg" alt="description">', 'is_correct': True, 'order': 1},
                    {'text': '<image src="image.jpg">', 'is_correct': False, 'order': 2},
                    {'text': '<img href="image.jpg">', 'is_correct': False, 'order': 3},
                    {'text': '<picture src="image.jpg">', 'is_correct': False, 'order': 4},
                ]
            },
            {
                'text': 'Which tag creates an unordered list?',
                'question_type': 'MCQ',
                'points': 10,
                'order': 5,
                'answers': [
                    {'text': '<ul>', 'is_correct': True, 'order': 1},
                    {'text': '<ol>', 'is_correct': False, 'order': 2},
                    {'text': '<li>', 'is_correct': False, 'order': 3},
                    {'text': '<list>', 'is_correct': False, 'order': 4},
                ]
            },
            {
                'text': 'True or False: HTML is a programming language.',
                'question_type': 'TF',
                'points': 5,
                'order': 6,
                'correct_answer': 'false',
                'answers': []  # No answers needed for TF
            },
            {
                'text': 'Which attribute specifies a unique identifier for an element?',
                'question_type': 'MCQ',
                'points': 10,
                'order': 7,
                'answers': [
                    {'text': 'id', 'is_correct': True, 'order': 1},
                    {'text': 'class', 'is_correct': False, 'order': 2},
                    {'text': 'name', 'is_correct': False, 'order': 3},
                    {'text': 'key', 'is_correct': False, 'order': 4},
                ]
            },
            {
                'text': 'What does CSS stand for?',
                'question_type': 'MCQ',
                'points': 10,
                'order': 8,
                'answers': [
                    {'text': 'Cascading Style Sheets', 'is_correct': True, 'order': 1},
                    {'text': 'Computer Style Sheets', 'is_correct': False, 'order': 2},
                    {'text': 'Creative Style System', 'is_correct': False, 'order': 3},
                    {'text': 'Colorful Style Sheets', 'is_correct': False, 'order': 4},
                ]
            },
            {
                'text': 'Which property is used to change the background color?',
                'question_type': 'MCQ',
                'points': 10,
                'order': 9,
                'answers': [
                    {'text': 'background-color', 'is_correct': True, 'order': 1},
                    {'text': 'color', 'is_correct': False, 'order': 2},
                    {'text': 'bgcolor', 'is_correct': False, 'order': 3},
                    {'text': 'background', 'is_correct': False, 'order': 4},
                ]
            },
            {
                'text': 'True or False: JavaScript and Java are the same language.',
                'question_type': 'TF',
                'points': 5,
                'order': 10,
                'correct_answer': 'false',
                'answers': []
            },
        ]
        
        for q_data in questions_data:
            # Create question
            answers_data = q_data.pop('answers', [])
            correct_answer = q_data.pop('correct_answer', '')
            
            question = Question.objects.create(
                quiz=quiz,
                **q_data
            )
            
            if correct_answer:
                question.correct_answer = correct_answer
                question.save()
            
            # Create answers for MCQ
            for a_data in answers_data:
                Answer.objects.create(
                    question=question,
                    **a_data
                )
            
            print(f"  ✅ Created Q{question.order}: {question.text[:50]}...")
        
        # Update quiz question count
        quiz.total_questions = quiz.questions.count()
        quiz.save()
        
        print(f"\n📊 Quiz Summary:")
        print(f"  - Quiz ID: {quiz.id}")
        print(f"  - Title: {quiz.title}")
        print(f"  - Questions: {quiz.total_questions}")
        print(f"  - Total Points: {sum(q.points for q in quiz.questions.all())}")
        print(f"  - Passing Score: {quiz.passing_score}%")
        print(f"  - Max Attempts: {quiz.max_attempts}")
        
        return quiz
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    quiz = create_test_quiz()
    if quiz:
        print("\n" + "=" * 60)
        print("✅ TEST QUIZ CREATED SUCCESSFULLY!")
        print(f"🔗 API Endpoints:")
        print(f"   GET  /api/assessments/quizzes/{quiz.id}/ - View quiz")
        print(f"   POST /api/assessments/quizzes/{quiz.id}/start/ - Start attempt")
        print(f"   POST /api/assessments/quizzes/{quiz.id}/submit/ - Submit answers")
        print("=" * 60)