/* TeachLink Main JavaScript */

// Utility Functions
var TeachLink = window.TeachLink || {
    
    // Format date to readable string
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
    
    // Format relative time (e.g., "2 days ago")
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
    
    // Get color for risk level
    getRiskColor: function(riskLevel) {
        const colors = {
            'LOW': '#10b981',
            'MEDIUM': '#f59e0b',
            'HIGH': '#ef4444',
            'CRITICAL': '#7f1d1d',
            'UNKNOWN': '#6b7280'
        };
        return colors[riskLevel] || colors.UNKNOWN;
    },
    
    // Get CSS class for risk level
    getRiskClass: function(riskLevel) {
        const classes = {
            'LOW': 'risk-badge-low',
            'MEDIUM': 'risk-badge-medium',
            'HIGH': 'risk-badge-high',
            'CRITICAL': 'risk-badge-critical',
            'UNKNOWN': 'bg-gray-100 text-gray-800'
        };
        return classes[riskLevel] || classes.UNKNOWN;
    },
    
    // Show toast notification
    showToast: function(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `fixed bottom-4 right-4 px-4 py-2 rounded-lg shadow-lg text-white ${
            type === 'success' ? 'bg-green-500' :
            type === 'error' ? 'bg-red-500' :
            type === 'warning' ? 'bg-yellow-500' :
            'bg-blue-500'
        } z-50 animate-fade-in-up`;
        
        toast.innerHTML = `
            <div class="flex items-center">
                <i class="fas ${
                    type === 'success' ? 'fa-check-circle' :
                    type === 'error' ? 'fa-exclamation-circle' :
                    type === 'warning' ? 'fa-exclamation-triangle' :
                    'fa-info-circle'
                } mr-2"></i>
                <span>${message}</span>
            </div>
        `;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 3000);
    },
    
    // Confirm dialog
    confirm: function(message, callback) {
        if (window.confirm(message)) {
            callback();
        }
    },
    
    // Debounce function for search inputs
    debounce: function(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },
    
    // Format percentage
    formatPercent: function(value) {
        return Math.round(value * 100) + '%';
    },
    
    // Download data as CSV
    downloadCSV: function(data, filename) {
        const csv = this.convertToCSV(data);
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        window.URL.revokeObjectURL(url);
    },
    
    // Convert array to CSV
    convertToCSV: function(data) {
        if (!data || data.length === 0) return '';
        
        const headers = Object.keys(data[0]);
        const csv = [
            headers.join(','),
            ...data.map(row => headers.map(field => JSON.stringify(row[field])).join(','))
        ].join('\n');
        
        return csv;
    }
};

// Authentication token handling
$(document).ready(function() {
    // Store token from login response
    const token = localStorage.getItem('auth_token');
    if (token) {
        $.ajaxSetup({
            headers: {
                'Authorization': 'Bearer ' + token
            }
        });
    }
    
    // Handle logout
    $('form[action*="logout"]').on('submit', function(e) {
        localStorage.removeItem('auth_token');
    });
});

// Chart default configurations
if (window.Chart) {
    Chart.defaults.font.family = "'Inter', system-ui, -apple-system, sans-serif";
    Chart.defaults.plugins.tooltip.backgroundColor = '#1f2937';
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
}

// Global error handler
window.onerror = function(msg, url, lineNo, columnNo, error) {
    console.error('Error: ' + msg + '\nURL: ' + url + '\nLine: ' + lineNo);
    return false;
};

// Export for use in other files
window.TeachLink = TeachLink;
