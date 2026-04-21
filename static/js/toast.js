/**
 * Glyph - Toast Notification System
 * Provides unified notification system for success, error, warning, and info messages
 */

/**
 * Toast notification manager
 */
const ToastManager = {
    container: null,
    toasts: [],
    
    /**
     * Initialize the toast container
     */
    init() {
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.className = 'toast-container';
            this.container.setAttribute('role', 'alert');
            this.container.setAttribute('aria-live', 'polite');
            document.body.appendChild(this.container);
        }
    },
    
    /**
     * Create and show a toast notification
     * @param {string} message - The message to display
     * @param {string} type - The type of toast: 'success', 'error', 'warning', 'info'
     * @param {number} duration - Duration in milliseconds (default: 5000, 0 for persistent)
     * @returns {HTMLDivElement} The created toast element
     */
    show(message, type = 'info', duration = 5000) {
        this.init();
        
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.setAttribute('role', 'alert');
        
        // Create message text
        const messageSpan = document.createElement('span');
        messageSpan.textContent = message;
        toast.appendChild(messageSpan);
        
        // Create close button
        const closeBtn = document.createElement('button');
        closeBtn.className = 'toast-close';
        closeBtn.innerHTML = '&times;';
        closeBtn.setAttribute('aria-label', 'Close notification');
        closeBtn.addEventListener('click', () => this.remove(toast));
        toast.appendChild(closeBtn);
        
        // Add to container
        this.container.appendChild(toast);
        this.toasts.push(toast);
        
        // Auto-dismiss after duration
        if (duration > 0) {
            setTimeout(() => this.remove(toast), duration);
        }
        
        return toast;
    },
    
    /**
     * Show a success toast
     * @param {string} message - The message to display
     * @param {number} duration - Duration in milliseconds
     */
    success(message, duration = 5000) {
        return this.show(message, 'success', duration);
    },
    
    /**
     * Show an error toast
     * @param {string} message - The message to display
     * @param {number} duration - Duration in milliseconds
     */
    error(message, duration = 7000) {
        return this.show(message, 'error', duration);
    },
    
    /**
     * Show a warning toast
     * @param {string} message - The message to display
     * @param {number} duration - Duration in milliseconds
     */
    warning(message, duration = 5000) {
        return this.show(message, 'warning', duration);
    },
    
    /**
     * Show an info toast
     * @param {string} message - The message to display
     * @param {number} duration - Duration in milliseconds
     */
    info(message, duration = 5000) {
        return this.show(message, 'info', duration);
    },
    
    /**
     * Remove a toast with animation
     * @param {HTMLDivElement} toast - The toast element to remove
     */
    remove(toast) {
        if (!toast || !this.container) return;
        
        toast.classList.add('toast-hiding');
        
        toast.addEventListener('animationend', () => {
            toast.remove();
            this.toasts = this.toasts.filter(t => t !== toast);
        }, { once: true });
        
        // Fallback removal if animation doesn't fire
        setTimeout(() => {
            if (toast.parentNode) {
                toast.remove();
                this.toasts = this.toasts.filter(t => t !== toast);
            }
        }, 350);
    },
    
    /**
     * Remove all toasts
     */
    clear() {
        this.toasts.forEach(toast => this.remove(toast));
    }
};

// Expose globally for use in templates
window.Toast = ToastManager;
