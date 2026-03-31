
/**
 * TeachLink Main JavaScript
 * Global utilities and functions
 */

// Global configuration
const TeachLink = {
    // API Base URL
    API_BASE: '/api',
    
    // Show loading spinner
    showLoading: function() {
        let spinner = document.getElementById('global-spinner');
        if (!spinner) {
            spinner = document.createElement('div');
            spinner.id = 'global-spinner';
            spinner.className = 'spinner-overlay';
            spinner.innerHTML = '<div class="spinner-border text-primary" style="width: 3rem; height: 3rem;"></div>';
            document.body.appendChild(spinner);
        }
        spinner.classList.add('show');
    },
    
    // Hide loading spinner
    hideLoading: function() {
        const spinner = document.getElementById('global-spinner');
        if (spinner) {
            spinner.classList.remove('show');
        }
    },
    
    // Show toast notification
    showToast: function(message, type = 'info') {
        const toastContainer = document.getElementById('toast-container') || (() => {
            const container = document.createElement('div');
            container.id = 'toast-container';
            container.style.position = 'fixed';
            container.style.top = '20px';
            container.style.right = '20px';
            container.style.zIndex = '9999';
            document.body.appendChild(container);
            return container;
        })();
        
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type} border-0 fade-in`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <i class="fas ${
                        type === 'success' ? 'fa-check-circle' :
                        type === 'danger' ? 'fa-exclamation-circle' :
                        type === 'warning' ? 'fa-exclamation-triangle' :
                        'fa-info-circle'
                    } me-2"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        
        toastContainer.appendChild(toast);
        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();
        
        setTimeout(() => {
            toast.remove();
        }, 5000);
    },
    
    // Format date
    formatDate: function(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    },
    
    // Time ago
    timeAgo: function(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const seconds = Math.floor((now - date) / 1000);
        
        const intervals = {
            year: 31536000,
            month: 2592000,
            week: 604800,
            day: 86400,
            hour: 3600,
            minute: 60
        };
        
        for (const [unit, secondsInUnit] of Object.entries(intervals)) {
            const interval = Math.floor(seconds / secondsInUnit);
            if (interval >= 1) {
                return interval === 1 ? `1 ${unit} ago` : `${interval} ${unit}s ago`;
            }
        }
        
        return 'just now';
    },
    
    // Confirm dialog
    confirm: function(message, callback) {
        if (confirm(message)) {
            callback();
        }
    },
    
    // AJAX wrapper with error handling
    ajax: function(options) {
        this.showLoading();
        
        return $.ajax({
            url: options.url,
            method: options.method || 'GET',
            data: options.data,
            contentType: options.contentType || 'application/json',
            headers: options.headers || {},
            success: function(response) {
                TeachLink.hideLoading();
                if (options.success) options.success(response);
            },
            error: function(xhr, status, error) {
                TeachLink.hideLoading();
                
                let errorMessage = 'An error occurred';
                if (xhr.responseJSON && xhr.responseJSON.message) {
                    errorMessage = xhr.responseJSON.message;
                } else if (xhr.responseJSON && xhr.responseJSON.error) {
                    errorMessage = xhr.responseJSON.error;
                } else if (error) {
                    errorMessage = error;
                }
                
                TeachLink.showToast(errorMessage, 'danger');
                
                if (options.error) options.error(xhr, status, error);
            }
        });
    },
    
    // Get risk color
    getRiskColor: function(level) {
        const colors = {
            'LOW': '#198754',
            'MEDIUM': '#ffc107',
            'HIGH': '#dc3545',
            'CRITICAL': '#7f1d1d'
        };
        return colors[level] || '#6c757d';
    },
    
    // Get risk badge class
    getRiskClass: function(level) {
        const classes = {
            'LOW': 'risk-low',
            'MEDIUM': 'risk-medium',
            'HIGH': 'risk-high',
            'CRITICAL': 'risk-critical'
        };
        return classes[level] || '';
    }
};

// Initialize on document ready
$(document).ready(function() {
    console.log('TeachLink initialized');
    
    // Auto-dismiss alerts after 5 seconds
    setTimeout(function() {
        $('.alert-dismissible').alert('close');
    }, 5000);
    
    // Enable all tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Enable all popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
});

// Export for use in other files
window.TeachLink = TeachLink;