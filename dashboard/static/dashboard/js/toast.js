// Toast notification system for success feedback
// Add this to dashboard/static/dashboard/js/main.js or a new file

function showSuccessToast(message, title = "Success") {
    const toastHtml = `
    <div class="toast align-items-center text-white bg-success border-0" role="alert" aria-live="assertive" aria-atomic="true">
        <div class="d-flex">
            <div class="toast-body">
                <strong>${title}</strong>
                <small class="ms-2">${message}</small>
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    </div>
    `;
    addToastToContainer(toastHtml);
}

function showErrorToast(message, title = "Error") {
    const toastHtml = `
    <div class="toast align-items-center text-white bg-danger border-0" role="alert" aria-live="assertive" aria-atomic="true">
        <div class="d-flex">
            <div class="toast-body">
                <strong>${title}</strong>
                <small class="ms-2">${message}</small>
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    </div>
    `;
    addToastToContainer(toastHtml);
}

function showWarningToast(message, title = "Warning") {
    const toastHtml = `
    <div class="toast align-items-center text-dark bg-warning border-0" role="alert" aria-live="assertive" aria-atomic="true">
        <div class="d-flex">
            <div class="toast-body">
                <strong>${title}</strong>
                <small class="ms-2">${message}</small>
            </div>
            <button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    </div>
    `;
    addToastToContainer(toastHtml);
}

function addToastToContainer(toastHtml) {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            min-width: 300px;
        `;
        document.body.appendChild(container);
    }
    
    const wrapper = document.createElement('div');
    wrapper.style.marginBottom = '10px';
    wrapper.innerHTML = toastHtml;
    
    container.appendChild(wrapper);
    
    const toast = new bootstrap.Toast(wrapper.querySelector('.toast'));
    toast.show();
    
    // Auto-remove after toast is hidden
    wrapper.addEventListener('hidden.bs.toast', function() {
        wrapper.remove();
    });
}

// Auto-wire form submissions to show success toast
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('form[data-success-message]').forEach(form => {
        form.addEventListener('submit', function(e) {
            const message = this.getAttribute('data-success-message') || 'Saved successfully';
            // Note: This will fire before actual submission - use AJAX for real feedback
            // Or add a hidden input that gets set to success by backend redirect
        });
    });
});

// Manual trigger for form submissions (use after AJAX success):
// showSuccessToast("Course saved successfully", "Success!");
// showErrorToast("Failed to save. Please try again.", "Error");
