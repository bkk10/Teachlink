let currentCourseId = null;
let editingCourseId = null;
let currentCourseStatus = null;
let courses = [];
let sortableInstances = [];
let currentModules = [];
let preferredCourseId = null;

$(document).ready(function() {
    console.log('Course management JS loaded');
    preferredCourseId = new URLSearchParams(window.location.search).get('open_course');
    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            const unsafe = !/^(GET|HEAD|OPTIONS|TRACE)$/.test(settings.type);
            if (unsafe) {
                xhr.setRequestHeader('X-CSRFToken', getCSRFToken());
            }
        }
    });
    loadCourses();
    initEventListeners();
});

function initEventListeners() {
    // Tab switching
    $('.tab-btn').click(function() {
        const tab = $(this).data('tab');
        $('.tab-btn').removeClass('active text-blue-600 border-blue-600').addClass('text-gray-500');
        $(this).addClass('active text-blue-600 border-blue-600').removeClass('text-gray-500');
        
        $('.tab-content').addClass('hidden');
        $('#' + tab + 'Tab').removeClass('hidden');
    });
    
    // Lesson type change
    $('#lessonType').change(function() {
        const type = $(this).val();
        if (type === 'VIDEO') {
            $('#contentField').hide();
            $('#urlField').show();
            $('#fileField').hide();
        } else if (type === 'RESOURCE') {
            $('#contentField').hide();
            $('#urlField').hide();
            $('#fileField').show();
        } else {
            $('#contentField').show();
            $('#urlField').hide();
            $('#fileField').hide();
        }
    });

    // Drag & drop for lesson resource upload
    $('#lessonDropzone').on('click', function() {
        $('#lessonFile').trigger('click');
    });

    $('#lessonFile').on('change', function() {
        const file = this.files && this.files[0] ? this.files[0] : null;
        $('#lessonFileName').text(file ? file.name : 'No file selected');
    });

    $('#lessonDropzone').on('dragover', function(e) {
        e.preventDefault();
        e.stopPropagation();
        $(this).addClass('dragover');
    });

    $('#lessonDropzone').on('dragleave drop', function(e) {
        e.preventDefault();
        e.stopPropagation();
        $(this).removeClass('dragover');
    });

    $('#lessonDropzone').on('drop', function(e) {
        const files = e.originalEvent.dataTransfer.files;
        if (files && files.length > 0) {
            $('#lessonFile')[0].files = files;
            $('#lessonFileName').text(files[0].name);
        }
    });
    
    // Modal buttons
    $('#addCourseBtn').click(() => openCourseModal());
    $('#cancelCourseBtn').click(() => closeCourseModal());
    $('#saveCourseBtn').click(() => saveCourse());
    
    $('#addModuleBtn').click(() => openModuleModal());
    $('#cancelModuleBtn').click(() => closeModuleModal());
    $('#saveModuleBtn').click(() => saveModule());
    
    $('#cancelLessonBtn').click(() => closeLessonModal());
    $('#saveLessonBtn').click(() => saveLesson());
    
    $('#addQuizBtn').click(() => openAssessmentModal('quiz'));
    $('#addAssignmentBtn').click(() => openAssessmentModal('assignment'));
    $('#addCatBtn').click(() => openAssessmentModal('cat'));
    
    $('#cancelAssessmentBtn').click(() => closeAssessmentModal());
    $('#saveAssessmentBtn').click(() => saveAssessment());
    
    $('#editCourseBtn').click(() => openCourseModal(currentCourseId));
    $('#publishCourseBtn').click(() => publishCourse());
}

function getAuthToken() {
    // For session-based authentication, we don't need a token
    // The session cookie is automatically sent with requests
    return '';  // Return empty string, no token needed
}

function getCSRFToken() {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, 10) === 'csrftoken=') {
                cookieValue = decodeURIComponent(cookie.substring(10));
                break;
            }
        }
    }
    return cookieValue;
}
function loadCourses() {
    console.log('Loading courses...');
    $.ajax({
        url: '/api/courses/courses/',
        method: 'GET',
        // Remove the headers line - session cookie handles authentication
        success: function(data) {
            console.log('Courses loaded:', data);
            courses = data;
            displayCourses();
        },
        error: function(xhr) {
            console.error('Failed to load courses', xhr.status, xhr.responseText);
            if (handleAuthError(xhr)) return;
            $('#courseList').html('<div class="p-4 text-red-500">Failed to load courses</div>');
        }
    });
}

function handleAuthError(xhr) {
    if (xhr && (xhr.status === 401 || xhr.status === 403)) {
        const nextUrl = encodeURIComponent(window.location.pathname + window.location.search);
        alert('Your session expired or you are not authenticated for this action. Please login again.');
        window.location.href = `/dashboard/login/?next=${nextUrl}`;
        return true;
    }
    return false;
}

function displayCourses() {
    if (courses.length === 0) {
        $('#courseList').html('<div class="p-4 text-gray-500 text-center">No courses yet</div>');
        return;
    }
    
    let html = '<div class="course-cards">';
    courses.forEach(course => {
        const status = (course.status || 'DRAFT').toUpperCase();
        const avgProgress = Number(course.avg_progress || 0).toFixed(1);
        const coverClass = `cover-${(Number(course.total_lessons || 0) + Number(course.total_students || 0)) % 6}`;
        const shortTitle = (course.title || 'Untitled Course').length > 44
            ? `${course.title.slice(0, 44)}...`
            : (course.title || 'Untitled Course');
        const subtitle = `${status}${course.expected_hours ? ` | ${course.expected_hours} HRS` : ''}`;
        const preview = `${course.total_students || 0} students | ${course.total_lessons || 0} lessons`;

        html += `
            <div class="course-card ${currentCourseId === course.id ? 'active' : ''}" data-id="${course.id}">
                <div class="course-cover ${coverClass}"></div>
                <div class="course-body">
                    <h4 class="course-title">${shortTitle}</h4>
                    <div class="course-subtitle">${subtitle}</div>
                    <div class="course-preview">${preview}</div>
                </div>
                <div class="course-footer">
                    <div class="course-complete">${avgProgress}% complete</div>
                    <button type="button" class="course-menu-btn analyze-course-btn" data-id="${course.id}" title="View analysis">
                        <i class="fas fa-ellipsis-v"></i>
                    </button>
                </div>
            </div>
        `;
    });
    html += '</div>';
    
    $('#courseList').html(html);
    
    $('.course-card').click(function() {
        const id = $(this).data('id');
        selectCourse(id);
    });

    $('.analyze-course-btn').click(function(e) {
        e.stopPropagation();
        const courseId = $(this).data('id');
        window.open(`/dashboard/teacher/courses/${courseId}/analytics/`, '_blank');
    });

    if (preferredCourseId) {
        const exists = courses.some(c => String(c.id) === String(preferredCourseId));
        if (exists) {
            selectCourse(preferredCourseId);
            preferredCourseId = null;
        }
    }
}

function selectCourse(courseId) {
    currentCourseId = courseId;
    $('.course-card').removeClass('active');
    $(`.course-card[data-id="${courseId}"]`).addClass('active');
    
    $('#emptyState').addClass('hidden');
    $('#courseContent').removeClass('hidden');
    resetCoursePanels();
    loadCourseDetails(courseId);
}

function resetCoursePanels() {
    $('#courseTitle').text('Loading course...');
    $('#courseDescription').text('');
    $('#courseEnrollmentKey').text('-');
    currentCourseStatus = null;
    $('#totalStudents').text('0');
    $('#totalLessons').text('0');
    $('#totalAssessments').text('0');
    $('#totalHours').text('0');
    $('#studentsList').html('<p class="text-gray-500 col-span-3 text-center py-8">Loading enrolled students...</p>');
    $('#modulesContainer').html('<p class="text-gray-500 text-center py-8">Loading modules...</p>');
    $('#assessmentsList').html('<p class="text-gray-500 col-span-2 text-center py-8">Loading assessments...</p>');
}

function loadCourseDetails(courseId) {
    $.ajax({
        url: `/api/courses/courses/${courseId}/`,
        method: 'GET',
        // headers: { 'Authorization': 'Bearer ' + getAuthToken() },
        success: function(course) {
            $('#courseTitle').text(course.title);
            $('#courseDescription').text(course.description || 'No description');
            $('#courseEnrollmentKey').text(course.enrollment_key || '-');
            $('#totalStudents').text(course.total_students || 0);
            $('#totalLessons').text(course.total_lessons || 0);
            currentCourseStatus = course.status || 'DRAFT';
            const publishBtn = $('#publishCourseBtn');
            if (currentCourseStatus === 'PUBLISHED') {
                publishBtn.removeClass('btn-success').addClass('btn-warning');
                publishBtn.html('<i class="fas fa-eye-slash mr-2"></i>Unpublish');
            } else {
                publishBtn.removeClass('btn-warning').addClass('btn-success');
                publishBtn.html('<i class="fas fa-globe mr-2"></i>Publish');
            }
            
            loadStudents(courseId);
            loadModules(courseId);
            loadAssessments(courseId);
        },
        error: function(xhr) {
            console.error('Failed to load course details', xhr.status, xhr.responseText);
            if (handleAuthError(xhr)) return;
            alert('Unable to load this course right now.');
        }
    });
}

function loadStudents(courseId) {
    $.ajax({
        url: `/api/courses/enrollments/?course=${courseId}&status=ACTIVE`,
        method: 'GET',
        // headers: { 'Authorization': 'Bearer ' + getAuthToken() },
        success: function(students) {
            displayStudents(students);
        },
        error: function(xhr) {
            console.error('Failed to load students', xhr.status, xhr.responseText);
            if (handleAuthError(xhr)) return;
            $('#studentsList').html('<p class="text-red-500 col-span-3 text-center py-8">Failed to load students.</p>');
        }
    });
}

function displayStudents(students) {
    if (!students || students.length === 0) {
        $('#studentsList').html('<p class="text-gray-500 col-span-3 text-center py-8">No students enrolled yet</p>');
        return;
    }
    
    let html = '';
    students.forEach(student => {
        const riskClass = {
            'HIGH': 'risk-high',
            'MEDIUM': 'risk-medium',
            'LOW': 'risk-low'
        }[student.risk_level] || '';
        
        html += `
            <div class="student-card bg-white rounded-lg shadow p-4">
                <div class="flex items-center justify-between mb-2">
                    <h4 class="font-medium">${student.student_name}</h4>
                    <span class="risk-badge ${riskClass}">${student.risk_level}</span>
                </div>
                <div class="text-sm text-gray-500 mb-2">Progress: ${student.progress_percentage}%</div>
                <div class="w-full bg-gray-200 rounded-full h-2 mb-3">
                    <div class="bg-blue-600 h-2 rounded-full" style="width: ${student.progress_percentage}%"></div>
                </div>
                <div class="flex justify-between text-xs text-gray-500">
                    <span><i class="far fa-clock mr-1"></i>Last: ${new Date(student.last_activity).toLocaleDateString()}</span>
                </div>
            </div>
        `;
    });
    
    $('#studentsList').html(html);
}

function loadModules(courseId) {
    $.ajax({
        url: `/api/courses/modules/?course=${courseId}`,
        method: 'GET',
        // headers: { 'Authorization': 'Bearer ' + getAuthToken() },
        success: function(modules) {
            currentModules = modules || [];
            displayModules(modules);
        },
        error: function(xhr) {
            console.error('Failed to load modules', xhr.status, xhr.responseText);
            if (handleAuthError(xhr)) return;
            $('#modulesContainer').html('<p class="text-red-500 text-center py-8">Failed to load modules.</p>');
        }
    });
}

function displayModules(modules) {
    if (!modules || modules.length === 0) {
        $('#modulesContainer').html('<p class="text-gray-500 text-center py-8">No modules yet. Click "Add Module" to start building your course.</p>');
        return;
    }
    
    let html = '';
    
    modules.forEach((module, index) => {
        html += `
            <div class="module-container" data-id="${module.id}">
                <div class="module-header">
                    <div class="flex items-center">
                        <i class="fas fa-grip-vertical text-gray-400 mr-2 cursor-move"></i>
                        <span class="font-medium">${module.title}</span>
                    </div>
                    <div>
                        <button class="add-lesson-btn text-blue-600 hover:text-blue-800 mr-2" data-module="${module.id}">
                            <i class="fas fa-plus mr-1"></i>Add Lesson
                        </button>
                        <button class="text-gray-400 hover:text-red-600">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
                <div class="lessons-container" data-module="${module.id}">
        `;
        
        if (module.lessons && module.lessons.length > 0) {
            module.lessons.forEach(lesson => {
                html += `
                    <div class="lesson-item" data-id="${lesson.id}">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center">
                                <i class="fas fa-grip-vertical text-gray-400 mr-2 cursor-move"></i>
                                <i class="fas ${getLessonIcon(lesson.content_type)} mr-2 text-gray-500"></i>
                                <span>${lesson.title}</span>
                            </div>
                            <div>
                                <span class="text-xs text-gray-500 mr-3">${lesson.estimated_minutes} min</span>
                                <button class="text-gray-400 hover:text-blue-600 mr-2">
                                    <i class="fas fa-edit"></i>
                                </button>
                                <button class="text-gray-400 hover:text-red-600">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                `;
            });
        }
        
        html += `</div></div>`;
    });
    
    $('#modulesContainer').html(html);
    initDragAndDrop();
    
    $('.add-lesson-btn').click(function() {
        const moduleId = $(this).data('module');
        openLessonModal(moduleId);
    });
}

function getLessonIcon(type) {
    const icons = {
        'VIDEO': 'fa-video',
        'TEXT': 'fa-file-alt',
        'QUIZ': 'fa-question-circle',
        'RESOURCE': 'fa-paperclip'
    };
    return icons[type] || 'fa-file';
}

function initDragAndDrop() {
    // Clear previous instances
    sortableInstances.forEach(instance => instance.destroy());
    sortableInstances = [];
    
    // Module reordering
    const moduleContainer = document.getElementById('modulesContainer');
    if (moduleContainer) {
        sortableInstances.push(new Sortable(moduleContainer, {
            animation: 150,
            handle: '.module-header',
            onEnd: function() {
                updateModuleOrder();
            }
        }));
    }
    
    // Lesson reordering within modules
    $('.lessons-container').each(function() {
        sortableInstances.push(new Sortable(this, {
            group: 'lessons',
            animation: 150,
            handle: '.lesson-item',
            onEnd: function(evt) {
                updateLessonOrder(evt);
            }
        }));
    });
}

function updateModuleOrder() {
    const modules = [];
    $('.module-container').each(function(index) {
        modules.push({
            id: $(this).data('id'),
            order: index
        });
    });
    
    $.ajax({
        url: '/api/courses/modules/bulk_update_order/',
        method: 'POST',
        // headers: { 
        //     'Authorization': 'Bearer ' + getAuthToken(),
        //     'Content-Type': 'application/json'
        // },
        contentType: 'application/json',
        data: JSON.stringify({ modules: modules })
    });
}

function updateLessonOrder(evt) {
    const moduleId = $(evt.to).data('module');
    const lessons = [];
    
    $(`[data-module="${moduleId}"] .lesson-item`).each(function(index) {
        lessons.push({
            id: $(this).data('id'),
            order: index
        });
    });
    
    $.ajax({
        url: '/api/courses/lessons/bulk_update_order/',
        method: 'POST',
        // headers: { 
        //     'Authorization': 'Bearer ' + getAuthToken(),
        //     'Content-Type': 'application/json'
        // },
        contentType: 'application/json',
        data: JSON.stringify({ lessons: lessons })
    });
}

function loadAssessments(courseId) {
    $.ajax({
        url: `/api/assessments/quizzes/?course=${courseId}`,
        method: 'GET',
        // headers: { 'Authorization': 'Bearer ' + getAuthToken() },
        success: function(assessments) {
            displayAssessments(assessments);
        },
        error: function(xhr) {
            console.error('Failed to load assessments', xhr.status, xhr.responseText);
            if (handleAuthError(xhr)) return;
            $('#assessmentsList').html('<p class="text-red-500 col-span-2 text-center py-8">Failed to load assessments.</p>');
        }
    });
}

function displayAssessments(assessments) {
    if (!assessments || assessments.length === 0) {
        $('#assessmentsList').html('<p class="text-gray-500 col-span-2 text-center py-8">No assessments yet</p>');
        return;
    }
    
    let html = '';
    assessments.forEach(assessment => {
        const typeClass = {
            'quiz': 'type-quiz',
            'assignment': 'type-assignment',
            'cat': 'type-cat'
        }[assessment.quiz_type?.toLowerCase()] || 'type-quiz';
        
        html += `
            <div class="assessment-card">
                <div class="flex justify-between items-start mb-2">
                    <h4 class="font-medium">${assessment.title}</h4>
                    <span class="assessment-type ${typeClass}">${assessment.quiz_type || 'Quiz'}</span>
                </div>
                <p class="text-sm text-gray-600 mb-3">${assessment.description || 'No description'}</p>
                <div class="flex justify-between text-xs text-gray-500">
                    <span><i class="fas fa-clock mr-1"></i>${assessment.time_limit_minutes || 0} min</span>
                    <span><i class="fas fa-star mr-1"></i>${assessment.passing_score || 0}% to pass</span>
                </div>
            </div>
        `;
    });
    
    $('#assessmentsList').html(html);
}

function openCourseModal(courseId = null) {
    editingCourseId = courseId;
    $('#courseModalTitle').text(courseId ? 'Edit Course' : 'Create New Course');
    if (courseId) {
        const course = courses.find(c => c.id === courseId);
        $('#courseTitleInput').val(course.title);
        $('#courseDescriptionInput').val(course.description);
    } else {
        $('#courseForm')[0].reset();
    }
    $('#courseModal').removeClass('hidden');
}

function closeCourseModal() {
    $('#courseModal').addClass('hidden');
    editingCourseId = null;
}

function saveCourse() {
    const data = {
        title: $('#courseTitleInput').val(),
        description: $('#courseDescriptionInput').val()
    };
    const isEditing = !!editingCourseId;
    
    $.ajax({
        url: isEditing ? `/api/courses/courses/${editingCourseId}/` : '/api/courses/courses/',
        method: isEditing ? 'PUT' : 'POST',
        // headers: { 
        //     'Authorization': 'Bearer ' + getAuthToken(),
        //     'Content-Type': 'application/json'
        // },
        contentType: 'application/json',
        data: JSON.stringify(data),
        success: function(savedCourse) {
            closeCourseModal();
            loadCourses();
            if (isEditing && currentCourseId) {
                loadCourseDetails(currentCourseId);
                return;
            }
            if (!isEditing && savedCourse && savedCourse.id) {
                currentCourseId = savedCourse.id;
                selectCourse(savedCourse.id);
            }
        }
    });
}

function publishCourse() {
    if (!currentCourseId) return;
    const endpoint = currentCourseStatus === 'PUBLISHED' ? 'unpublish' : 'publish';
    
    $.ajax({
        url: `/api/courses/courses/${currentCourseId}/${endpoint}/`,
        method: 'POST',
        // headers: { 'Authorization': 'Bearer ' + getAuthToken() },
        success: function() {
            loadCourseDetails(currentCourseId);
            loadCourses();
        }
    });
}

function openModuleModal() {
    $('#moduleForm')[0].reset();
    $('#moduleModal').removeClass('hidden');
}

function closeModuleModal() {
    $('#moduleModal').addClass('hidden');
}

function saveModule() {
    const data = {
        course: currentCourseId,
        title: $('#moduleTitle').val(),
        description: $('#moduleDescription').val()
    };
    
    $.ajax({
        url: '/api/courses/modules/',
        method: 'POST',
        // headers: { 
        //     'Authorization': 'Bearer ' + getAuthToken(),
        //     'Content-Type': 'application/json'
        // },
        contentType: 'application/json',
        data: JSON.stringify(data),
        success: function() {
            closeModuleModal();
            loadModules(currentCourseId);
        }
    });
}

function openLessonModal(moduleId) {
    $('#lessonModuleId').val(moduleId);
    $('#lessonForm')[0].reset();
    $('#lessonFileName').text('No file selected');
    $('#fileField').hide();
    $('#urlField').hide();
    $('#contentField').show();
    $('#lessonModal').removeClass('hidden');
}

function closeLessonModal() {
    $('#lessonModal').addClass('hidden');
}

function saveLesson() {
    const type = $('#lessonType').val();
    const formData = new FormData();
    formData.append('module', $('#lessonModuleId').val());
    formData.append('title', $('#lessonTitle').val());
    formData.append('content_type', type);
    formData.append('estimated_minutes', $('#lessonMinutes').val() || '15');
    
    if (type === 'VIDEO') {
        formData.append('video_url', $('#lessonUrl').val() || '');
    } else if (type === 'RESOURCE') {
        const file = $('#lessonFile')[0].files[0];
        if (!file) {
            alert('Please select a file to upload.');
            return;
        }
        formData.append('resource_file', file);
    } else {
        formData.append('content_text', $('#lessonContent').val() || '');
    }
    
    $.ajax({
        url: '/api/courses/lessons/',
        method: 'POST',
        processData: false,
        contentType: false,
        data: formData,
        success: function() {
            closeLessonModal();
            loadModules(currentCourseId);
        },
        error: function(xhr) {
            console.error('Failed to save lesson', xhr.status, xhr.responseText);
            if (handleAuthError(xhr)) return;
            alert('Failed to save lesson. Check required fields and try again.');
        }
    });
}

function openAssessmentModal(type) {
    $('#assessmentType').val(type);
    $('#assessmentModalTitle').text('Add ' + type.charAt(0).toUpperCase() + type.slice(1));
    $('#assessmentForm')[0].reset();
    populateAssessmentLessons();
    toggleAssessmentMode(type);
    $('#assessmentModal').removeClass('hidden');
}

function closeAssessmentModal() {
    $('#assessmentModal').addClass('hidden');
}

function populateAssessmentLessons() {
    let options = [];
    currentModules.forEach(module => {
        (module.lessons || []).forEach(lesson => {
            options.push({
                id: lesson.id,
                label: `${module.title} - ${lesson.title}`
            });
        });
    });

    if (!options.length) {
        $('#assessmentLesson').html('<option value="">No lessons available. Add a lesson first.</option>');
        return;
    }

    const html = options.map(o => `<option value="${o.id}">${o.label}</option>`).join('');
    $('#assessmentLesson').html(html);
}

function toggleAssessmentMode(type) {
    if (type === 'quiz') {
        $('#assessmentNonQuizHint').addClass('hidden');
        $('#assessmentQuestionText, #answerOption1, #answerOption2, #answerOption3, #answerOption4, #correctAnswerIndex').prop('disabled', false);
    } else {
        $('#assessmentNonQuizHint').removeClass('hidden');
        $('#assessmentQuestionText, #answerOption1, #answerOption2, #answerOption3, #answerOption4, #correctAnswerIndex').prop('disabled', true);
    }
}

function saveAssessment() {
    const type = $('#assessmentType').val();
    if (type !== 'quiz') {
        alert('Auto-grading is currently configured for quizzes. Please create a quiz.');
        return;
    }

    const lessonId = $('#assessmentLesson').val();
    if (!lessonId) {
        alert('Select a lesson for this quiz.');
        return;
    }

    const quizPayload = {
        lesson: lessonId,
        title: $('#assessmentTitle').val(),
        description: $('#assessmentDescription').val() || '',
        quiz_type: 'MCQ',
        passing_score: Number($('#assessmentPassingScore').val() || 70),
        is_published: true
    };

    const questionText = $('#assessmentQuestionText').val();
    const options = [
        $('#answerOption1').val(),
        $('#answerOption2').val(),
        $('#answerOption3').val(),
        $('#answerOption4').val()
    ];

    if (!quizPayload.title || !questionText || !options[0] || !options[1]) {
        alert('Quiz title, question, and at least two options are required.');
        return;
    }

    const correctIndex = Number($('#correctAnswerIndex').val() || 1) - 1;

    $.ajax({
        url: '/api/assessments/quizzes/',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(quizPayload),
        success: function(quiz) {
            const questionPayload = {
                quiz: quiz.id,
                question_type: 'MCQ',
                text: questionText,
                points: 1
            };

            $.ajax({
                url: '/api/assessments/questions/',
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify(questionPayload),
                success: function(question) {
                    const validOptions = options.filter(Boolean);
                    let created = 0;
                    if (!validOptions.length) {
                        closeAssessmentModal();
                        loadAssessments(currentCourseId);
                        return;
                    }

                    validOptions.forEach((text, idx) => {
                        $.ajax({
                            url: '/api/assessments/answers/',
                            method: 'POST',
                            contentType: 'application/json',
                            data: JSON.stringify({
                                question: question.id,
                                text: text,
                                is_correct: idx === correctIndex
                            }),
                            complete: function() {
                                created += 1;
                                if (created === validOptions.length) {
                                    closeAssessmentModal();
                                    loadAssessments(currentCourseId);
                                }
                            }
                        });
                    });
                },
                error: function(xhr) {
                    console.error('Failed to create question', xhr.status, xhr.responseText);
                    alert('Quiz created, but question creation failed.');
                }
            });
        },
        error: function(xhr) {
            console.error('Failed to create quiz', xhr.status, xhr.responseText);
            if (handleAuthError(xhr)) return;
            alert('Failed to create quiz. Check lesson selection and form values.');
        }
    });
}
