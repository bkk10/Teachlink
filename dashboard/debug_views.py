from django.shortcuts import render, get_object_or_404
from courses.models import Course, Lesson


def templates_index(request):
    # Choose a sample course if available, otherwise render empty index
    course = Course.objects.first()
    breadcrumbs = [
        {"label": "My Courses", "url": "/courses/"},
        {"label": course.name if course else 'Sample Course', "active": True}
    ]
    context = {'course': course, 'breadcrumbs': breadcrumbs}
    return render(request, 'debug_templates/debug_course_dashboard.html', context)


def debug_lesson(request):
    lesson = Lesson.objects.first()
    breadcrumbs = [
        {"label": "My Courses", "url": "/courses/"},
        {"label": lesson.course.name if lesson else 'Sample Course', "url": "/",},
        {"label": lesson.title if lesson else 'Sample Lesson', "active": True}
    ]
    return render(request, 'debug_templates/debug_lesson_detail.html', {'lesson': lesson, 'breadcrumbs': breadcrumbs})
