let currentCourseId = null;
let editingCourseId = null;
let currentCourseStatus = null;
let courses = [];
let sortableInstances = [];
let currentModules = [];
let preferredCourseId = null;
let focusModeRequested = false;
let currentAssessments = [];

$(document).ready(function() {
    console.log('Course management JS loaded');
    preferredCourseId = new URLSearchParams(window.location.search).get('open_course');
    focusModeRequested = !!preferredCourseId;
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

    // Quick upload in Lesson Overview
    $('#quickUploadDropzone').on('click', function() {
        $('#quickUploadFile').trigger('click');
    });

    $('#quickUploadFile').on('change', function() {
        const file = this.files && this.files[0] ? this.files[0] : null;
        $('#quickUploadFileName').text(file ? file.name : 'No file selected');
    });

    $('#quickUploadDropzone').on('dragover', function(e) {
        e.preventDefault();
        e.stopPropagation();
        $(this).addClass('dragover');
    });

    $('#quickUploadDropzone').on('dragleave drop', function(e) {
        e.preventDefault();
        e.stopPropagation();
        $(this).removeClass('dragover');
    });

    $('#quickUploadDropzone').on('drop', function(e) {
        const files = e.originalEvent.dataTransfer.files;
        if (files && files.length > 0) {
            $('#quickUploadFile')[0].files = files;
            $('#quickUploadFileName').text(files[0].name);
            if (!$('#quickUploadTitle').val()) {
                $('#quickUploadTitle').val(files[0].name.replace(/\.[^/.]+$/, ''));
            }
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
    
    $(document).off('click', '#addQuizBtn').on('click', '#addQuizBtn', function() { openAssessmentModal('quiz'); });
    $(document).off('click', '#addAssignmentBtn').on('click', '#addAssignmentBtn', function() { openAssessmentModal('assignment'); });
    $(document).off('click', '#addCatBtn').on('click', '#addCatBtn', function() { openAssessmentModal('cat'); });
    
    $(document).off('click', '#cancelAssessmentBtn').on('click', '#cancelAssessmentBtn', function() { closeAssessmentModal(); });
    $(document).off('click', '#saveAssessmentBtn').on('click', '#saveAssessmentBtn', function() { saveAssessment(); });
    $(document).off('change', '#assessmentLesson').on('change', '#assessmentLesson', function() {
        populateCatSourceQuizzes();
        saveCatDraft();
    });
    $(document).off('input change', '#assessmentTitle, #assessmentDescription, #assessmentPassingScore, #assessmentQuestionText, #answerOption1, #answerOption2, #answerOption3, #answerOption4, #correctAnswerIndex, #catDurationMinutes, #catSourceQuiz, #catCopyQuestions')
        .on('input change', '#assessmentTitle, #assessmentDescription, #assessmentPassingScore, #assessmentQuestionText, #answerOption1, #answerOption2, #answerOption3, #answerOption4, #correctAnswerIndex, #catDurationMinutes, #catSourceQuiz, #catCopyQuestions', function() {
            saveCatDraft();
        });
    
    $('#editCourseBtn').click(() => openCourseModal(currentCourseId));
    $('#publishCourseBtn').click(() => publishCourse());
    $('#backToCoursesBtn').click(() => disableFocusMode());
    $('#quickUploadBtn').click(() => uploadQuickResource());
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
        window.location.href = `/dashboard/courses/?open_course=${id}`;
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
        } else {
            disableFocusMode(false);
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
    const selectedCourse = courses.find(c => String(c.id) === String(courseId));
    if (selectedCourse) {
        $('#courseTitle').text(selectedCourse.title || 'Untitled Course');
        $('#courseDescription').text(selectedCourse.description || 'No description');
    }

    // Load page sections immediately so course opens even if detail endpoint fails.
    loadStudents(courseId);
    loadModules(courseId);
    loadAssessments(courseId);
    loadDifficulty(courseId);

    // Try to enrich with extra fields (like enrollment key) in background.
    loadCourseDetails(courseId, true);

    if (focusModeRequested) {
        enableFocusMode();
    }

    const contentEl = document.getElementById('courseContent');
    if (contentEl) {
        contentEl.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

function enableFocusMode() {
    $('.course-grid').addClass('focus-mode');
    $('#backToCoursesBtn').removeClass('hidden');
}

function disableFocusMode(reloadWithoutQuery = true) {
    if (reloadWithoutQuery) {
        window.location.href = '/dashboard/courses/';
        return;
    }
    $('.course-grid').removeClass('focus-mode');
    $('#backToCoursesBtn').addClass('hidden');
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
    $('#difficultyList').html('<tr><td colspan="5" class="text-muted text-center py-3">Loading difficulty data...</td></tr>');
    $('#quickUploadTitle').val('');
    $('#quickUploadFile').val('');
    $('#quickUploadFileName').text('No file selected');
    $('#quickUploadMinutes').val('15');
    const moduleSelect = $('#quickUploadModule');
    if (moduleSelect.length) {
        moduleSelect.html('<option value="">Add a module first</option>');
        moduleSelect.prop('disabled', true);
    }
}

function loadCourseDetails(courseId, silent = false) {
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
        },
        error: function(xhr) {
            console.error('Failed to load course details', xhr.status, xhr.responseText);
            if (handleAuthError(xhr)) return;
            if (!silent) {
                alert('Unable to load full course details right now, but the workspace is still available.');
            }
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
            populateQuickUploadModules(currentModules);
            displayModules(modules);
        },
        error: function(xhr) {
            console.error('Failed to load modules', xhr.status, xhr.responseText);
            if (handleAuthError(xhr)) return;
            $('#modulesContainer').html('<p class="text-red-500 text-center py-8">Failed to load modules.</p>');
            populateQuickUploadModules([]);
        }
    });
}

function populateQuickUploadModules(modules) {
    const select = $('#quickUploadModule');
    if (!select.length) return;

    if (!modules || !modules.length) {
        select.html('<option value="">Add a module first</option>');
        select.prop('disabled', true);
        return;
    }

    select.empty();
    modules.forEach(module => {
        select.append($('<option>').val(module.id).text(module.title || 'Untitled Module'));
    });
    select.prop('disabled', false);
}

function loadDifficulty(courseId) {
    $.ajax({
        url: `/api/dashboard/difficulty/?course_id=${courseId}`,
        method: 'GET',
        success: function(data) {
            displayDifficulty(data && data.hardest_lessons ? data.hardest_lessons : []);
        },
        error: function(xhr) {
            console.error('Failed to load difficulty data', xhr.status, xhr.responseText);
            if (handleAuthError(xhr)) return;
            $('#difficultyList').html('<tr><td colspan="5" class="text-danger text-center py-3">Failed to load difficulty data.</td></tr>');
        }
    });
}

function displayDifficulty(rows) {
    if (!rows || rows.length === 0) {
        $('#difficultyList').html('<tr><td colspan="5" class="text-muted text-center py-3">No lesson difficulty data yet.</td></tr>');
        return;
    }

    const badge = function(level) {
        const key = (level || 'UNKNOWN').toUpperCase();
        if (key === 'HIGH' || key === 'HARD' || key === 'VERY_HARD') {
            return '<span class="risk-badge risk-high">HIGH</span>';
        }
        if (key === 'MEDIUM') {
            return '<span class="risk-badge risk-medium">MEDIUM</span>';
        }
        if (key === 'LOW' || key === 'EASY' || key === 'VERY_EASY') {
            return '<span class="risk-badge risk-low">LOW</span>';
        }
        return '<span class="risk-badge">UNKNOWN</span>';
    };

    const html = rows.map(row => {
        const failureRate = Math.round((Number(row.failure_rate || 0) * 100) * 10) / 10;
        const attemptIntensity = Math.round((Number(row.attempt_intensity || 0) * 100) * 10) / 10;
        const accessCoverage = Math.round(Number(row.access_coverage_pct || 0) * 10) / 10;
        const accessCount = Number(row.access_count || 0);
        return `
            <tr>
                <td>${row.lesson_title || 'Untitled Lesson'}</td>
                <td>${badge(row.difficulty_level)}</td>
                <td>${failureRate}%</td>
                <td title="Average completed quiz attempts per student, normalized so 3 attempts per student = 100%.">${attemptIntensity}%</td>
                <td title="Total students who accessed this lesson: ${accessCount}">${accessCoverage}%</td>
            </tr>
        `;
    }).join('');

    $('#difficultyList').html(html);
}

function displayModules(modules) {
    if (!modules || modules.length === 0) {
        $('#modulesContainer').html('<p class="text-gray-500 text-center py-8">No modules yet. Click "Add Module" to start building your course.</p>');
        return;
    }
    
    let html = '';
    
    modules.forEach((module) => {
        html += `
            <div class="module-container" data-id="${module.id}">
                <div class="module-header">
                    <div class="module-title-wrap">
                        <button type="button" class="module-toggle-btn" data-module="${module.id}" aria-expanded="true" title="Collapse/Expand">
                            <i class="fas fa-chevron-down"></i>
                        </button>
                        <span class="module-title-main">${module.title || 'Untitled Topic'}</span>
                    </div>
                    <div>
                        <button class="add-lesson-btn btn btn-sm btn-outline-primary module-inline-action" data-module="${module.id}">
                            <i class="fas fa-plus mr-1"></i>Add File
                        </button>
                    </div>
                </div>
                <div class="lessons-container" id="moduleBody-${module.id}" data-module="${module.id}">
        `;
        
        if (module.lessons && module.lessons.length > 0) {
            module.lessons.forEach(lesson => {
                const fileExt = getLessonFileExtension(lesson);
                const displayExt = fileExt || 'FILE';
                const resourceTone = lesson.content_type === 'RESOURCE' ? 'resource-tone' : '';
                html += `
                    <div class="lesson-item" data-id="${lesson.id}">
                        <div class="lesson-row-inner">
                            <div class="lesson-file-wrap">
                                <span class="lesson-doc-icon">
                                    <i class="far fa-file"></i>
                                    <span class="lesson-doc-ext">${displayExt}</span>
                                </span>
                                <div>
                                    <a href="/dashboard/lesson/${lesson.id}/open/" class="lesson-link ${resourceTone}" target="_blank" rel="noopener">
                                        ${lesson.title || 'Untitled Lesson'}
                                    </a>
                                    <span class="lesson-file-ext">${displayExt}</span>
                                </div>
                            </div>
                            <div class="lesson-meta">
                                ${lesson.estimated_minutes || 0} min
                            </div>
                        </div>
                    </div>
                `;
            });
        } else {
            html += '<p class="text-gray-500 text-sm py-2 px-1">No files in this topic yet. Use "Add File" or Quick File Upload.</p>';
        }
        
        html += `</div></div>`;
    });
    
    $('#modulesContainer').html(html);
    initDragAndDrop();
    
    $('.add-lesson-btn').click(function() {
        const moduleId = $(this).data('module');
        openLessonModal(moduleId);
    });

    $('.module-toggle-btn').click(function(e) {
        e.stopPropagation();
        const moduleId = $(this).data('module');
        const body = $(`#moduleBody-${moduleId}`);
        const expanded = $(this).attr('aria-expanded') === 'true';
        body.slideToggle(150);
        $(this).attr('aria-expanded', expanded ? 'false' : 'true');
        $(this).toggleClass('collapsed', expanded);
    });
}

function getLessonFileExtension(lesson) {
    const fromResource = (lesson && lesson.resource_file) ? String(lesson.resource_file) : '';
    const fromUrl = (lesson && lesson.external_url) ? String(lesson.external_url) : '';
    const fromTitle = (lesson && lesson.title) ? String(lesson.title) : '';
    const candidate = fromResource || fromUrl || fromTitle;
    const match = candidate.match(/\.([A-Za-z0-9]+)(?:$|[?#])/);
    if (match && match[1]) {
        return match[1].toUpperCase().slice(0, 4);
    }
    if (lesson && lesson.content_type === 'VIDEO') return 'MP4';
    if (lesson && lesson.content_type === 'QUIZ') return 'QUIZ';
    if (lesson && lesson.content_type === 'TEXT') return 'DOC';
    return 'FILE';
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
            const rows = Array.isArray(assessments) ? assessments : (assessments.results || []);
            currentAssessments = rows;
            displayAssessments(rows);
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
                <div class="text-xs text-gray-500 mb-2">
                    <i class="fas fa-book-open mr-1"></i>${assessment.lesson_title || 'Lesson not set'}
                    <span class="mx-2">|</span>
                    <i class="fas fa-list-ol mr-1"></i>${assessment.question_count || assessment.total_questions || 0} questions
                </div>
                <div class="flex justify-between text-xs text-gray-500">
                    <span><i class="fas fa-clock mr-1"></i>${assessment.time_limit_minutes || 0} min</span>
                    <span><i class="fas fa-star mr-1"></i>${assessment.passing_score || 0}% to pass</span>
                </div>
                <div class="mt-3 d-flex gap-2">
                    <a class="btn btn-sm btn-primary" href="/dashboard/teacher/quizzes/${assessment.id}/builder/">
                        <i class="fas fa-pen-to-square me-1"></i>Set Questions
                    </a>
                    <a class="btn btn-sm btn-outline-secondary" href="/dashboard/teacher/courses/${currentCourseId}/analytics/" target="_blank" rel="noopener">
                        <i class="fas fa-chart-line me-1"></i>Analytics
                    </a>
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

function uploadQuickResource() {
    if (!currentCourseId) {
        alert('Select a course first.');
        return;
    }

    const moduleId = $('#quickUploadModule').val();
    if (!moduleId) {
        alert('Select a module before uploading.');
        return;
    }

    const file = $('#quickUploadFile')[0].files[0];
    if (!file) {
        alert('Choose a file to upload.');
        return;
    }

    const titleInput = ($('#quickUploadTitle').val() || '').trim();
    const lessonTitle = titleInput || file.name.replace(/\.[^/.]+$/, '');
    const minutes = $('#quickUploadMinutes').val() || '15';

    const formData = new FormData();
    formData.append('module', moduleId);
    formData.append('title', lessonTitle);
    formData.append('content_type', 'RESOURCE');
    formData.append('estimated_minutes', minutes);
    formData.append('resource_file', file);

    $.ajax({
        url: '/api/courses/lessons/',
        method: 'POST',
        processData: false,
        contentType: false,
        data: formData,
        success: function() {
            $('#quickUploadTitle').val('');
            $('#quickUploadFile').val('');
            $('#quickUploadFileName').text('No file selected');
            $('#quickUploadMinutes').val('15');
            loadModules(currentCourseId);
        },
        error: function(xhr) {
            console.error('Quick upload failed', xhr.status, xhr.responseText);
            if (handleAuthError(xhr)) return;
            alert('Failed to upload file. Confirm module selection and file type, then try again.');
        }
    });
}

function openAssessmentModal(type) {
    $('#assessmentType').val(type);
    $('#assessmentModalTitle').text('Add ' + type.charAt(0).toUpperCase() + type.slice(1));
    $('#assessmentForm')[0].reset();
    populateAssessmentLessons();
    toggleAssessmentMode(type);
    populateCatSourceQuizzes();
    if (type === 'cat') {
        loadCatDraft();
    }
    $('#assessmentModal').removeClass('hidden');
    $('#assessmentTitle').trigger('focus');
}

function closeAssessmentModal() {
    $('#assessmentModal').addClass('hidden');
    $('#saveAssessmentBtn').prop('disabled', false).text('Save');
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
        $('#catWizard').addClass('hidden');
        $('#assessmentNonQuizHint').addClass('hidden');
        $('#assessmentQuestionText, #answerOption1, #answerOption2, #answerOption3, #answerOption4, #correctAnswerIndex').prop('disabled', false);
        $('#saveAssessmentBtn').text('Save Quiz');
    } else if (type === 'cat') {
        $('#catWizard').removeClass('hidden');
        $('#assessmentNonQuizHint').addClass('hidden');
        $('#assessmentQuestionText, #answerOption1, #answerOption2, #answerOption3, #answerOption4, #correctAnswerIndex').prop('disabled', false);
        $('#saveAssessmentBtn').text('Save CAT');
    } else {
        $('#catWizard').addClass('hidden');
        $('#assessmentNonQuizHint').removeClass('hidden');
        $('#assessmentQuestionText, #answerOption1, #answerOption2, #answerOption3, #answerOption4, #correctAnswerIndex').prop('disabled', true);
        $('#saveAssessmentBtn').text('Save');
    }
}

function saveAssessment() {
    const type = $('#assessmentType').val();
    if (type !== 'quiz' && type !== 'cat') {
        alert('Assignment workflow is not configured yet. Use Quiz or CAT.');
        return;
    }
    const isCat = type === 'cat';

    const lessonId = $('#assessmentLesson').val();
    if (!lessonId) {
        alert('Select a lesson for this quiz.');
        return;
    }

    const quizPayload = {
        lesson: lessonId,
        title: ($('#assessmentTitle').val() || '').trim(),
        description: ($('#assessmentDescription').val() || '').trim(),
        quiz_type: 'MCQ',
        passing_score: Number($('#assessmentPassingScore').val() || 70),
        time_limit_minutes: isCat ? Number($('#catDurationMinutes').val() || 30) : 0,
        max_attempts: isCat ? 1 : 3,
        is_published: true
    };

    const questionText = ($('#assessmentQuestionText').val() || '').trim();
    const options = [
        ($('#answerOption1').val() || '').trim(),
        ($('#answerOption2').val() || '').trim(),
        ($('#answerOption3').val() || '').trim(),
        ($('#answerOption4').val() || '').trim()
    ];
    const optionEntries = options
        .map((text, idx) => ({ idx: idx, text: text }))
        .filter(entry => !!entry.text);

    if (!quizPayload.title) {
        alert('Quiz title is required.');
        return;
    }

    if (questionText && optionEntries.length < 2) {
        alert('Provide at least two options for the question.');
        return;
    }

    const correctIndex = Number($('#correctAnswerIndex').val() || 1) - 1;
    const selectedCorrectOriginal = optionEntries.some(entry => entry.idx === correctIndex)
        ? correctIndex
        : optionEntries[0].idx;
    const catSourceQuizId = isCat ? ($('#catSourceQuiz').val() || '') : '';
    const catCopyQuestions = isCat && $('#catCopyQuestions').is(':checked') && !!catSourceQuizId;

    const saveBtn = $('#saveAssessmentBtn');
    const originalBtnText = saveBtn.text();
    saveBtn.prop('disabled', true).text('Saving...');

    upsertQuizForLesson(lessonId, quizPayload, function(quiz) {
        const tasks = [];

        if (catCopyQuestions && catSourceQuizId && String(catSourceQuizId) !== String(quiz.id)) {
            tasks.push(function(next) {
                copyQuestionsFromQuiz(catSourceQuizId, quiz.id, function(err) {
                    next(err);
                });
            });
        }

        if (questionText && optionEntries.length >= 2) {
            tasks.push(function(next) {
                createQuestionWithAnswers(
                    quiz.id,
                    questionText,
                    optionEntries.map((entry, visualOrder) => ({
                        text: entry.text,
                        is_correct: entry.idx === selectedCorrectOriginal,
                        order: visualOrder + 1
                    })),
                    function(err) { next(err); }
                );
            });
        }

        runSequential(tasks, function(err) {
            saveBtn.prop('disabled', false).text(originalBtnText);
            if (err) {
                alert(err);
            } else {
                if (isCat) clearCatDraft();
                alert(isCat ? 'CAT saved successfully.' : 'Assessment saved successfully.');
            }
            closeAssessmentModal();
            loadAssessments(currentCourseId);
        });
    }, function(xhr) {
        saveBtn.prop('disabled', false).text(originalBtnText);
        console.error('Failed to create/update quiz', xhr.status, xhr.responseText);
        if (handleAuthError(xhr)) return;
        alert(readApiError(xhr, 'Failed to save assessment. Check lesson selection and form values.'));
    });
}

function upsertQuizForLesson(lessonId, quizPayload, onSuccess, onError) {
    $.ajax({
        url: `/api/assessments/quizzes/?lesson=${lessonId}`,
        method: 'GET',
        success: function(listData) {
            const quizzes = Array.isArray(listData) ? listData : (listData.results || []);
            if (quizzes.length > 0) {
                const existingId = quizzes[0].id;
                $.ajax({
                    url: `/api/assessments/quizzes/${existingId}/`,
                    method: 'PATCH',
                    contentType: 'application/json',
                    data: JSON.stringify({
                        title: quizPayload.title,
                        description: quizPayload.description,
                        passing_score: quizPayload.passing_score,
                        quiz_type: 'MCQ',
                        is_published: true
                    }),
                    success: onSuccess,
                    error: onError
                });
                return;
            }

            $.ajax({
                url: '/api/assessments/quizzes/',
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify(quizPayload),
                success: onSuccess,
                error: onError
            });
        },
        error: onError
    });
}

function createQuestionWithAnswers(quizId, questionText, answers, done) {
    const questionPayload = {
        quiz: quizId,
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
            if (!answers || !answers.length) {
                done(null);
                return;
            }
            let processed = 0;
            let failed = false;
            answers.forEach(answer => {
                $.ajax({
                    url: '/api/assessments/answers/',
                    method: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify({
                        question: question.id,
                        text: answer.text,
                        is_correct: !!answer.is_correct,
                        order: answer.order || 1
                    }),
                    error: function(xhr) {
                        failed = true;
                        console.error('Failed to create answer', xhr.status, xhr.responseText);
                    },
                    complete: function() {
                        processed += 1;
                        if (processed === answers.length) {
                            done(failed ? 'Assessment saved, but some answers failed to save.' : null);
                        }
                    }
                });
            });
        },
        error: function(xhr) {
            console.error('Failed to create question', xhr.status, xhr.responseText);
            done(readApiError(xhr, 'Assessment saved, but question creation failed.'));
        }
    });
}

function copyQuestionsFromQuiz(sourceQuizId, targetQuizId, done) {
    $.ajax({
        url: `/api/assessments/quizzes/${sourceQuizId}/`,
        method: 'GET',
        success: function(sourceQuiz) {
            const sourceQuestions = sourceQuiz && sourceQuiz.questions ? sourceQuiz.questions : [];
            if (!sourceQuestions.length) {
                done(null);
                return;
            }

            const tasks = sourceQuestions.map(sourceQuestion => function(next) {
                const sourceAnswers = (sourceQuestion.answers || []).map((answer, idx) => ({
                    text: answer.text,
                    is_correct: !!answer.is_correct,
                    order: Number(answer.order || idx + 1)
                }));
                createQuestionWithAnswers(
                    targetQuizId,
                    sourceQuestion.text || 'Copied Question',
                    sourceAnswers,
                    function(err) { next(err); }
                );
            });

            runSequential(tasks, function(err) {
                done(err);
            });
        },
        error: function(xhr) {
            console.error('Failed to fetch source quiz', xhr.status, xhr.responseText);
            done(readApiError(xhr, 'CAT saved, but failed to copy questions from source quiz.'));
        }
    });
}

function runSequential(tasks, done) {
    if (!tasks || !tasks.length) {
        done(null);
        return;
    }
    let index = 0;
    const next = function(err) {
        if (err) {
            done(err);
            return;
        }
        if (index >= tasks.length) {
            done(null);
            return;
        }
        const task = tasks[index];
        index += 1;
        task(next);
    };
    next(null);
}

function getCatDraftKey() {
    return `teachlink_cat_draft_${currentCourseId || 'none'}`;
}

function saveCatDraft() {
    if ($('#assessmentType').val() !== 'cat') return;
    const draft = {
        lesson: $('#assessmentLesson').val() || '',
        title: ($('#assessmentTitle').val() || '').trim(),
        description: ($('#assessmentDescription').val() || '').trim(),
        passingScore: $('#assessmentPassingScore').val() || '70',
        duration: $('#catDurationMinutes').val() || '30',
        sourceQuiz: $('#catSourceQuiz').val() || '',
        copyQuestions: $('#catCopyQuestions').is(':checked'),
        questionText: ($('#assessmentQuestionText').val() || '').trim(),
        option1: ($('#answerOption1').val() || '').trim(),
        option2: ($('#answerOption2').val() || '').trim(),
        option3: ($('#answerOption3').val() || '').trim(),
        option4: ($('#answerOption4').val() || '').trim(),
        correctIndex: $('#correctAnswerIndex').val() || '1'
    };
    try {
        window.localStorage.setItem(getCatDraftKey(), JSON.stringify(draft));
    } catch (e) {}
}

function loadCatDraft() {
    try {
        const raw = window.localStorage.getItem(getCatDraftKey());
        if (!raw) return;
        const draft = JSON.parse(raw);
        if (draft.lesson) $('#assessmentLesson').val(draft.lesson);
        if (draft.title) $('#assessmentTitle').val(draft.title);
        if (draft.description) $('#assessmentDescription').val(draft.description);
        if (draft.passingScore) $('#assessmentPassingScore').val(draft.passingScore);
        if (draft.duration) $('#catDurationMinutes').val(draft.duration);
        populateCatSourceQuizzes();
        if (draft.sourceQuiz) $('#catSourceQuiz').val(draft.sourceQuiz);
        $('#catCopyQuestions').prop('checked', !!draft.copyQuestions);
        if (draft.questionText) $('#assessmentQuestionText').val(draft.questionText);
        if (draft.option1) $('#answerOption1').val(draft.option1);
        if (draft.option2) $('#answerOption2').val(draft.option2);
        if (draft.option3) $('#answerOption3').val(draft.option3);
        if (draft.option4) $('#answerOption4').val(draft.option4);
        if (draft.correctIndex) $('#correctAnswerIndex').val(draft.correctIndex);
    } catch (e) {}
}

function clearCatDraft() {
    try {
        window.localStorage.removeItem(getCatDraftKey());
    } catch (e) {}
}

function populateCatSourceQuizzes() {
    const select = $('#catSourceQuiz');
    if (!select.length) return;
    const selectedLessonId = $('#assessmentLesson').val();
    let html = '<option value="">Start from scratch</option>';
    (currentAssessments || []).forEach(quiz => {
        if (selectedLessonId && String(quiz.lesson) === String(selectedLessonId)) return;
        html += `<option value="${quiz.id}">${quiz.title || 'Untitled Quiz'} (${quiz.lesson_title || 'No lesson'})</option>`;
    });
    select.html(html);
}

function readApiError(xhr, fallbackMessage) {
    if (!xhr || !xhr.responseText) return fallbackMessage;
    try {
        const payload = JSON.parse(xhr.responseText);
        if (typeof payload === 'string') return payload;
        if (payload.detail) return payload.detail;
        const key = Object.keys(payload)[0];
        if (!key) return fallbackMessage;
        const value = payload[key];
        if (Array.isArray(value) && value.length) return String(value[0]);
        return typeof value === 'string' ? value : fallbackMessage;
    } catch (err) {
        return fallbackMessage;
    }
}
