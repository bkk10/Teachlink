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
        $('.tab-btn').removeClass('active text-blue-600 border-blue-600 bg-blue-50/50 font-semibold')
                      .addClass('text-gray-500 border-transparent font-medium');
        $(this).addClass('active text-blue-600 border-blue-600 bg-blue-50/50 font-semibold')
               .removeClass('text-gray-500 border-transparent font-medium');

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
    $(document).off('click', '#addAssignmentBtn').on('click', '#addAssignmentBtn', function() { alert('Assignment workflow coming soon. Use Quiz for now.'); });
    $(document).off('click', '#addCatBtn').on('click', '#addCatBtn', function() { openAssessmentModal('cat'); });
    
    $(document).off('click', '#cancelAssessmentBtn').on('click', '#cancelAssessmentBtn', function() { closeAssessmentModal(); });
    $(document).off('click', '#saveAssessmentBtn').on('click', '#saveAssessmentBtn', function() { saveAssessment(); });
    
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
        const expectedHours = course.expected_hours ? parseFloat(course.expected_hours) : null;
        const hoursText = expectedHours && !isNaN(expectedHours) ? ` | ${Math.round(expectedHours)} HRS` : '';
        const subtitle = `${status}${hoursText}`;
        const preview = `${course.total_students || 0} students | ${course.total_lessons || 0} lessons`;
        
        // Health badge with risk border color and tooltip
        let healthBadge = '';
        let riskBorderClass = '';
        const highRisk = parseInt(course.high_risk_count) || 0;
        const mediumRisk = parseInt(course.medium_risk_count) || 0;
        const lowRisk = parseInt(course.low_risk_count) || 0;
        
        if (highRisk > 0) {
            healthBadge = `<span class="badge bg-danger text-white" style="font-size: 0.65rem; position: absolute; top: 8px; right: 8px; cursor: help;" title="${highRisk} student${highRisk !== 1 ? 's' : ''} at high risk (risk score >70%)${mediumRisk > 0 ? `, ${mediumRisk} at medium risk` : ''}${lowRisk > 0 ? `, ${lowRisk} at low risk` : ''}">${highRisk} high risk</span>`;
            riskBorderClass = 'border-danger';
        } else if (mediumRisk > 0) {
            healthBadge = `<span class="badge bg-warning text-dark" style="font-size: 0.65rem; position: absolute; top: 8px; right: 8px; cursor: help;" title="${mediumRisk} student${mediumRisk !== 1 ? 's' : ''} at medium risk (risk score 30-70%)${lowRisk > 0 ? `, ${lowRisk} at low risk` : ''}">${mediumRisk} medium risk</span>`;
            riskBorderClass = 'border-warning';
        } else if (lowRisk > 0) {
            healthBadge = `<span class="badge bg-success text-white" style="font-size: 0.65rem; position: absolute; top: 8px; right: 8px; cursor: help;" title="${lowRisk} student${lowRisk !== 1 ? 's' : ''} at low risk (risk score <30%)">${lowRisk} low risk</span>`;
            riskBorderClass = 'border-success';
        }

        html += `
            <div class="course-card ${currentCourseId === course.id ? 'active' : ''} ${riskBorderClass}" data-id="${course.id}" style="position: relative;">
                ${healthBadge}
                <div class="course-cover ${coverClass}"></div>
                <div class="course-body">
                    <h4 class="course-title">${shortTitle}</h4>
                    <div class="course-subtitle">${subtitle}</div>
                    <div class="course-preview">${preview}</div>
                </div>
                <div class="course-footer">
                    <div class="course-complete" title="Average progress percentage across all enrolled students">${avgProgress}% avg progress</div>
                    <div class="dropdown">
                        <button type="button" class="course-menu-btn" data-bs-toggle="dropdown" aria-expanded="false" onclick="event.stopPropagation();">
                            <i class="fas fa-ellipsis-v"></i>
                        </button>
                        <ul class="dropdown-menu dropdown-menu-end">
                            <li><a class="dropdown-item" href="/dashboard/courses/?open_course=${course.id}"><i class="fas fa-layer-group me-2"></i>Manage Course</a></li>
                            <li><a class="dropdown-item" href="/dashboard/teacher/courses/${course.id}/analytics/" target="_blank"><i class="fas fa-chart-line me-2"></i>Risk Overview</a></li>
                            <li><hr class="dropdown-divider"></li>
                            <li><a class="dropdown-item" href="/dashboard/courses/?open_course=${course.id}&add_lesson=1"><i class="fas fa-plus me-2"></i>Add Lesson</a></li>
                        </ul>
                    </div>
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
    
    // Build unified student table
    let html = `
        <div class="overflow-x-auto">
            <table class="table align-middle mb-0">
                <thead class="table-light">
                    <tr>
                        <th>Student</th>
                        <th>Progress</th>
                        <th>Quiz Avg</th>
                        <th>Risk</th>
                        <th>Primary Driver</th>
                        <th>Engagement</th>
                        <th>Last Activity</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    students.forEach(student => {
        const riskClass = {
            'HIGH': 'bg-danger',
            'CRITICAL': 'bg-danger',
            'MEDIUM': 'bg-warning',
            'LOW': 'bg-success'
        }[student.risk_level] || 'bg-secondary';
        
        const riskPercent = Math.round((student.risk_score || 0) * 100);
        
        // Determine primary driver
        let primaryDriver = 'N/A';
        let intervention = '';
        const progress = parseFloat(student.progress_percentage || 0);
        const quizAvg = parseFloat(student.average_quiz_score || 0);
        const daysInactive = student.days_since_last_activity || 0;
        
        if (progress < 40) {
            primaryDriver = 'Progress Deficit';
            intervention = 'Agree on catch-up target';
        } else if (quizAvg < 50) {
            primaryDriver = 'Quiz Performance';
            intervention = 'Recommend remediation';
        } else if (daysInactive > 7) {
            primaryDriver = 'Inactivity';
            intervention = 'Send re-engagement message';
        } else {
            primaryDriver = 'On Track';
            intervention = 'Continue monitoring';
        }
        
        // Engagement level
        let engagementLevel = 'Low';
        let engagementClass = 'text-danger';
        const engagementScore = parseFloat(student.engagement_score || 0);
        if (engagementScore > 0.6) {
            engagementLevel = 'High';
            engagementClass = 'text-success';
        } else if (engagementScore > 0.3) {
            engagementLevel = 'Medium';
            engagementClass = 'text-warning';
        }
        
        const lastActivity = student.last_activity 
            ? new Date(student.last_activity).toLocaleDateString()
            : 'Never';
        
        html += `
            <tr>
                <td>
                    <div class="fw-semibold">${student.student_name}</div>
                    <div class="small text-muted">${student.student_email || ''}</div>
                </td>
                <td>${parseFloat(student.progress_percentage || 0).toFixed(1)}%</td>
                <td>${parseFloat(student.average_quiz_score || 0).toFixed(1)}%</td>
                <td>
                    <span class="badge ${riskClass}">${student.risk_level || 'UNKNOWN'}</span>
                    <div class="small text-muted">${riskPercent}%</div>
                </td>
                <td>
                    <div class="small">${primaryDriver}</div>
                    <div class="small text-muted">${intervention}</div>
                </td>
                <td class="${engagementClass}">${engagementLevel}</td>
                <td class="small">${lastActivity}</td>
                <td>
                    <a href="/dashboard/teacher/students/${student.student_id}/?course=${currentCourseId}" 
                       class="btn btn-sm btn-outline-primary">View</a>
                </td>
            </tr>
        `;
    });
    
    html += `</tbody></table></div>`;
    
    $('#studentsList').html(html);
    $('#studentsList').removeClass('grid grid-cols-1 md:grid-cols-2 2xl:grid-cols-3 gap-4');
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

// Store difficulty data for filtering/sorting
let difficultyDataCache = [];
let currentDifficultySort = { column: null, asc: true };

function displayDifficulty(rows) {
    if (!rows || rows.length === 0) {
        $('#difficultyList').html('<tr><td colspan="6" class="text-muted text-center py-3">No lesson difficulty data yet.</td></tr>');
        return;
    }

    // Cache the data for filtering/sorting
    difficultyDataCache = rows;
    
    renderDifficultyTable(rows);
}

function renderDifficultyTable(rows) {
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
        const uniqueStudents = Number(row.unique_students || 0);
        return `
            <tr>
                <td>
                    <div class="d-flex align-items-center">
                        <span class="me-2">${row.lesson_title || 'Untitled Lesson'}</span>
                        <a href="/dashboard/teacher/courses/${currentCourseId}/analytics/?lesson=${row.lesson_id}" 
                           class="text-muted small" title="View detailed analytics for this lesson">
                            <i class="fas fa-external-link-alt"></i> Details
                        </a>
                    </div>
                </td>
                <td>${badge(row.difficulty_level)}</td>
                <td>${failureRate}%</td>
                <td title="Average completed quiz attempts per student, normalized so 3 attempts per student = 100%.">${attemptIntensity}%</td>
                <td title="${uniqueStudents} of ${accessCount} enrolled students accessed this lesson">${accessCoverage}%</td>
                <td>
                    <button class="btn btn-sm btn-outline-secondary" onclick="showLessonStudentsModal('${row.lesson_id}', '${row.lesson_title || 'Lesson'}')">
                        <i class="fas fa-users me-1"></i> Students
                    </button>
                </td>
            </tr>
        `;
    }).join('');

    $('#difficultyList').html(html);
}

// Sort difficulty table by column
function sortDifficultyTable(column) {
    if (currentDifficultySort.column === column) {
        currentDifficultySort.asc = !currentDifficultySort.asc;
    } else {
        currentDifficultySort = { column: column, asc: true };
    }

    const sorted = [...difficultyDataCache].sort((a, b) => {
        let valA, valB;
        switch (column) {
            case 'lesson':
                valA = a.lesson_title || '';
                valB = b.lesson_title || '';
                break;
            case 'difficulty':
                const order = { 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1, 'UNKNOWN': 0 };
                valA = order[(a.difficulty_level || '').toUpperCase()] || 0;
                valB = order[(b.difficulty_level || '').toUpperCase()] || 0;
                break;
            case 'failure':
                valA = a.failure_rate || 0;
                valB = b.failure_rate || 0;
                break;
            case 'intensity':
                valA = a.attempt_intensity || 0;
                valB = b.attempt_intensity || 0;
                break;
            case 'access':
                valA = a.access_coverage_pct || 0;
                valB = b.access_coverage_pct || 0;
                break;
            default:
                return 0;
        }
        
        if (valA < valB) return currentDifficultySort.asc ? -1 : 1;
        if (valA > valB) return currentDifficultySort.asc ? 1 : -1;
        return 0;
    });

    renderDifficultyTable(sorted);
}

// Show modal with students who accessed the lesson
function showLessonStudentsModal(lessonId, lessonTitle) {
    // Load students who accessed this lesson
    $.ajax({
        url: `/api/dashboard/lesson-students/?lesson_id=${lessonId}`,
        method: 'GET',
        success: function(data) {
            const students = data.students || [];
            let html = '';
            
            if (students.length === 0) {
                html = '<p class="text-muted text-center">No students have accessed this lesson yet.</p>';
            } else {
                html = `
                    <table class="table table-sm">
                        <thead>
                            <tr>
                                <th>Student</th>
                                <th>Email</th>
                                <th>Access Count</th>
                                <th>Last Accessed</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${students.map(s => `
                                <tr>
                                    <td>${s.name}</td>
                                    <td>${s.email}</td>
                                    <td>${s.access_count}</td>
                                    <td>${s.last_accessed || 'N/A'}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                `;
            }
            
            $('#lessonStudentsModalTitle').text(`Students: ${lessonTitle}`);
            $('#lessonStudentsList').html(html);
            $('#lessonStudentsModal').removeClass('hidden');
        },
        error: function() {
            $('#lessonStudentsList').html('<p class="text-danger text-center">Failed to load student data.</p>');
        }
    });
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
                        <button class="add-lesson-btn btn btn-sm btn-outline-primary module-inline-action" data-module="${module.id}" title="Add a new lesson to this module">
                            <i class="fas fa-plus mr-1"></i>Add Lesson
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
                            <div class="d-flex align-items-center gap-2">
                                <div class="lesson-meta">
                                    ${lesson.estimated_minutes || 0} min
                                </div>
                                <div class="btn-group btn-group-sm">
                                    <button class="btn btn-outline-primary" onclick="editLesson('${lesson.id}')" title="Edit lesson">
                                        <i class="fas fa-edit"></i>
                                    </button>
                                    <button class="btn btn-outline-danger" onclick="deleteLesson('${lesson.id}')" title="Delete lesson">
                                        <i class="fas fa-trash"></i>
                                    </button>
                                </div>
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

        const questionCount = parseInt(assessment.question_count || assessment.total_questions || 0);
        const isExternal = assessment.quiz_type === 'EXTERNAL' || questionCount === 0;
        const externalBadge = isExternal ? `<span class="badge bg-secondary ms-2" title="External/imported assessment - no online quiz">EXTERNAL</span>` : '';
        
        // Build action buttons - hide for EXTERNAL quizzes
        const actionButtons = isExternal ? '' : `
            <div class="mt-3 d-flex gap-2">
                <a class="btn btn-sm btn-primary" href="/dashboard/teacher/quizzes/${assessment.id}/builder/">
                    <i class="fas fa-edit me-1"></i>Edit
                </a>
                <a class="btn btn-sm btn-outline-secondary" href="/dashboard/teacher/courses/${currentCourseId}/analytics/" target="_blank" rel="noopener" title="View lesson difficulty and performance analytics">
                    <i class="fas fa-chart-bar me-1"></i>Lesson Difficulty
                </a>
            </div>
        `;
        
        const importOnlyIndicator = isExternal ? `<div class="mt-2 text-xs text-warning"><i class="fas fa-info-circle me-1"></i>Import scores only - no online quiz</div>` : '';

        html += `
            <div class="assessment-card ${isExternal ? 'border-secondary bg-light' : ''}">
                <div class="flex justify-between items-start mb-2">
                    <h4 class="font-medium">${assessment.title}${externalBadge}</h4>
                    <span class="assessment-type ${typeClass}">${assessment.quiz_type || 'Quiz'}</span>
                </div>
                <p class="text-sm text-gray-600 mb-3">${assessment.description || 'No description'}</p>
                <div class="text-xs text-gray-500 mb-2">
                    ${assessment.lesson_title || 'Lesson not set'}
                    <span class="mx-2">|</span>
                    ${questionCount} questions
                    <span class="mx-2">|</span>
                    <span title="Number of student submissions"><i class="fas fa-users me-1"></i>${assessment.attempt_count || assessment.submission_count || 0} attempts</span>
                </div>
                <div class="flex justify-between text-xs text-gray-500">
                    <span>${assessment.time_limit_minutes || 0} min</span>
                    <span>${assessment.passing_score || 0}% to pass</span>
                </div>
                ${actionButtons}
                ${importOnlyIndicator}
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
    $('#lessonModal').removeData('editing-lesson-id');
    $('#lessonForm')[0].reset();
    $('#lessonFileName').text('No file selected');
}

function saveLesson() {
    const type = $('#lessonType').val();
    const formData = new FormData();
    formData.append('module', $('#lessonModuleId').val());
    formData.append('title', $('#lessonTitle').val());
    formData.append('content_type', type);
    formData.append('estimated_minutes', $('#lessonMinutes').val() || '15');
    formData.append('is_published', 'true');
    
    if (type === 'VIDEO') {
        formData.append('video_url', $('#lessonUrl').val() || '');
    } else if (type === 'RESOURCE') {
        const file = $('#lessonFile')[0].files[0];
        if (file) {
            formData.append('resource_file', file);
        }
    } else {
        formData.append('content_text', $('#lessonContent').val() || '');
    }
    
    // Check if we're editing or creating
    const editingLessonId = $('#lessonModal').data('editing-lesson-id');
    const url = editingLessonId 
        ? `/api/courses/lessons/${editingLessonId}/`
        : '/api/courses/lessons/';
    const method = editingLessonId ? 'PUT' : 'POST';
    
    $.ajax({
        url: url,
        method: method,
        processData: false,
        contentType: false,
        data: formData,
        success: function() {
            closeLessonModal();
            $('#lessonModal').removeData('editing-lesson-id');
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
    formData.append('is_published', 'true');  // Publish immediately so students can see it

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
    $('#assessmentModalTitle').text('Add Quiz');
    $('#assessmentForm')[0].reset();
    $('#assessmentTimeLimit').val('30');
    $('#assessmentPassingScore').val('70');
    populateAssessmentLessons();
    $('#assessmentModal').removeClass('hidden');
    $('#assessmentTitle').trigger('focus');
}

function closeAssessmentModal() {
    $('#assessmentModal').addClass('hidden');
    $('#saveAssessmentBtn').prop('disabled', false).text('Create Quiz');
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

function saveAssessment() {
    const lessonId = $('#assessmentLesson').val();
    if (!lessonId) {
        alert('Select a lesson for this quiz.');
        return;
    }

    const title = ($('#assessmentTitle').val() || '').trim();
    if (!title) {
        alert('Quiz title is required.');
        $('#assessmentTitle').focus();
        return;
    }

    const quizPayload = {
        lesson: lessonId,
        title: title,
        description: ($('#assessmentDescription').val() || '').trim(),
        quiz_type: 'MCQ',
        passing_score: Number($('#assessmentPassingScore').val() || 70),
        time_limit_minutes: Number($('#assessmentTimeLimit').val() || 30),
        max_attempts: 3,
        is_published: false
    };

    const saveBtn = $('#saveAssessmentBtn');
    saveBtn.prop('disabled', true).text('Creating...');

    // First check if a quiz already exists for this lesson
    $.ajax({
        url: `/api/assessments/quizzes/?lesson=${lessonId}`,
        method: 'GET',
        success: function(listData) {
            const quizzes = Array.isArray(listData) ? listData : (listData.results || []);
            if (quizzes.length > 0) {
                // Update existing quiz
                const existingId = quizzes[0].id;
                $.ajax({
                    url: `/api/assessments/quizzes/${existingId}/`,
                    method: 'PATCH',
                    contentType: 'application/json',
                    data: JSON.stringify(quizPayload),
                    success: function(quiz) {
                        saveBtn.prop('disabled', false).text('Create Quiz');
                        closeAssessmentModal();
                        // Redirect to quiz builder to add questions
                        window.location.href = `/dashboard/teacher/quizzes/${quiz.id}/builder/`;
                    },
                    error: function(xhr) {
                        saveBtn.prop('disabled', false).text('Create Quiz');
                        console.error('Failed to update quiz', xhr.status, xhr.responseText);
                        if (handleAuthError(xhr)) return;
                        alert('Failed to update quiz. Please try again.');
                    }
                });
                return;
            }

            // Create new quiz
            $.ajax({
                url: '/api/assessments/quizzes/',
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify(quizPayload),
                success: function(quiz) {
                    saveBtn.prop('disabled', false).text('Create Quiz');
                    closeAssessmentModal();
                    // Redirect to quiz builder to add questions
                    window.location.href = `/dashboard/teacher/quizzes/${quiz.id}/builder/`;
                },
                error: function(xhr) {
                    saveBtn.prop('disabled', false).text('Create Quiz');
                    console.error('Failed to create quiz', xhr.status, xhr.responseText);
                    if (handleAuthError(xhr)) return;
                    alert('Failed to create quiz. Please try again.');
                }
            });
        },
        error: function(xhr) {
            saveBtn.prop('disabled', false).text('Create Quiz');
            console.error('Failed to check existing quizzes', xhr.status, xhr.responseText);
            if (handleAuthError(xhr)) return;
            alert('Failed to check for existing quizzes. Please try again.');
        }
    });
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

function editLesson(lessonId) {
    // Find the lesson in current modules
    let lesson = null;
    let module = null;
    for (const m of currentModules) {
        if (m.lessons) {
            const found = m.lessons.find(l => String(l.id) === String(lessonId));
            if (found) {
                lesson = found;
                module = m;
                break;
            }
        }
    }
    
    if (!lesson) {
        alert('Lesson not found');
        return;
    }
    
    // Populate and open the edit modal
    $('#lessonModuleId').val(module.id);
    $('#lessonTitle').val(lesson.title || '');
    $('#lessonType').val(lesson.content_type || 'TEXT');
    $('#lessonMinutes').val(lesson.estimated_minutes || 15);
    $('#lessonContent').val(lesson.content_text || '');
    $('#lessonUrl').val(lesson.video_url || lesson.external_url || '');
    $('#lessonFileName').text(lesson.resource_file ? 'Current file: ' + lesson.resource_file.split('/').pop() : 'No file selected');
    
    // Show/hide appropriate fields based on content type
    const type = lesson.content_type || 'TEXT';
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
    
    // Store the lesson ID for the update
    $('#lessonModal').data('editing-lesson-id', lessonId);
    $('#lessonModal').removeClass('hidden');
}

function deleteLesson(lessonId) {
    if (!confirm('Are you sure you want to delete this lesson? This action cannot be undone.')) {
        return;
    }
    
    $.ajax({
        url: `/api/courses/lessons/${lessonId}/`,
        method: 'DELETE',
        headers: { 'X-CSRFToken': getCSRFToken() },
        success: function() {
            loadModules(currentCourseId);
        },
        error: function(xhr) {
            console.error('Failed to delete lesson', xhr.status, xhr.responseText);
            alert('Failed to delete lesson. Please try again.');
        }
    });
}
