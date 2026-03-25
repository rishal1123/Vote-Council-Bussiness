// VoteCouncil Application JavaScript

// Toast notification system
function showToast(message, type = 'info') {
    // Create toast container if it doesn't exist
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    // Create toast element
    const toastId = 'toast-' + Date.now();
    const bgClass = {
        'success': 'bg-success',
        'danger': 'bg-danger',
        'warning': 'bg-warning',
        'info': 'bg-info'
    }[type] || 'bg-info';

    const textClass = type === 'warning' ? 'text-dark' : 'text-white';

    const toastHtml = `
        <div id="${toastId}" class="toast ${bgClass} ${textClass}" role="alert">
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;

    container.insertAdjacentHTML('beforeend', toastHtml);

    const toastEl = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastEl, { delay: 3000 });
    toast.show();

    // Remove element after hidden
    toastEl.addEventListener('hidden.bs.toast', () => {
        toastEl.remove();
    });
}

// Format date
function formatDate(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleDateString();
}

// Format datetime
function formatDateTime(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleString();
}

// Confirm action
function confirmAction(message) {
    return confirm(message);
}

// PWA Install Prompt
let deferredPrompt;

window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    showInstallPrompt();
});

function showInstallPrompt() {
    // Don't show if already installed or dismissed
    if (localStorage.getItem('pwaInstallDismissed')) return;

    const promptHtml = `
        <div id="installPrompt" class="alert alert-primary alert-dismissible fade show" role="alert">
            <i class="bi bi-download me-2"></i>
            <strong>Install VoteCouncil</strong> for quick access!
            <button type="button" class="btn btn-sm btn-primary ms-2" onclick="installPWA()">Install</button>
            <button type="button" class="btn-close" onclick="dismissInstall()"></button>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', promptHtml);
}

async function installPWA() {
    const prompt = document.getElementById('installPrompt');
    if (prompt) prompt.remove();

    if (deferredPrompt) {
        deferredPrompt.prompt();
        const { outcome } = await deferredPrompt.userChoice;
        deferredPrompt = null;

        if (outcome === 'accepted') {
            showToast('App installed successfully!', 'success');
        }
    }
}

function dismissInstall() {
    const prompt = document.getElementById('installPrompt');
    if (prompt) prompt.remove();
    localStorage.setItem('pwaInstallDismissed', 'true');
}

// Service Worker Registration
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/sw.js')
            .then(registration => {
                console.log('ServiceWorker registered:', registration.scope);
            })
            .catch(error => {
                console.log('ServiceWorker registration failed:', error);
            });
    });
}

// Online/Offline status
window.addEventListener('online', () => {
    showToast('You are back online', 'success');
});

window.addEventListener('offline', () => {
    showToast('You are offline. Some features may not work.', 'warning');
});

// API helper
async function apiCall(url, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json'
        }
    };

    const response = await fetch(url, { ...defaultOptions, ...options });

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Request failed' }));
        throw new Error(error.detail || 'Request failed');
    }

    return response.json();
}

// Debounce function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Format numbers
function formatNumber(num) {
    return new Intl.NumberFormat().format(num);
}

// Copy to clipboard
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showToast('Copied to clipboard', 'success');
    } catch (err) {
        showToast('Failed to copy', 'danger');
    }
}

// Initialize tooltips
document.addEventListener('DOMContentLoaded', () => {
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltipTriggerList.forEach(el => new bootstrap.Tooltip(el));
});

// Auto-refresh indicator
let refreshInterval;

function startAutoRefresh(callback, interval = 30000) {
    if (refreshInterval) clearInterval(refreshInterval);
    refreshInterval = setInterval(callback, interval);
}

function stopAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
}

// Page visibility API - pause refresh when page is hidden
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        stopAutoRefresh();
    }
});
