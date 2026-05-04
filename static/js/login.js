/**
 * Glyph - Login Form JavaScript
 * Handles login form validation and submission
 */
'use strict';

/**
 * Initialize login form with validation and submission handling
 */
function initLoginForm() {
    const form = document.getElementById('loginForm');
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const submitBtn = document.getElementById('login-submit-btn');
    const errorDiv = document.getElementById('login-error');
    
    if (!form) return;
    
    // Real-time validation for username
    usernameInput.addEventListener('blur', function() {
        if (this.value.length < 3) {
            this.classList.add('is-error');
            this.setAttribute('aria-invalid', 'true');
        } else {
            this.classList.remove('is-error');
            this.setAttribute('aria-invalid', 'false');
        }
    });
    
    usernameInput.addEventListener('input', function() {
        if (this.classList.contains('is-error')) {
            this.classList.remove('is-error');
            this.setAttribute('aria-invalid', 'false');
        }
    });
    
    // Real-time validation for password
    passwordInput.addEventListener('blur', function() {
        if (this.value.length < 8) {
            this.classList.add('is-error');
            this.setAttribute('aria-invalid', 'true');
        } else {
            this.classList.remove('is-error');
            this.setAttribute('aria-invalid', 'false');
        }
    });
    
    passwordInput.addEventListener('input', function() {
        if (this.classList.contains('is-error')) {
            this.classList.remove('is-error');
            this.setAttribute('aria-invalid', 'false');
        }
    });
    
    // Form submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Validate before submission
        if (usernameInput.value.length < 3) {
            usernameInput.classList.add('is-error');
            Toast.error('Username must be at least 3 characters');
            usernameInput.focus();
            return;
        }
        
        if (passwordInput.value.length < 8) {
            passwordInput.classList.add('is-error');
            Toast.error('Password must be at least 8 characters');
            passwordInput.focus();
            return;
        }
        
        // Set loading state
        submitBtn.disabled = true;
        submitBtn.textContent = 'LOGIN...';
        
        const formData = new FormData(form);
        
        try {
            const response = await fetch('/auth/token', {
                method: 'POST',
                body: formData
            });
            
            if (response.ok) {
                Toast.success('Login successful! Redirecting...');
                // Redirect to home page
                setTimeout(() => {
                    window.location.href = '/';
                }, 500);
            } else {
                const error = await response.json();
                const errorMessage = error.detail || 'Login failed';
                showError(errorMessage);
                Toast.error(errorMessage);
            }
        } catch (err) {
            console.error('Login error:', err);
            showError('Network error. Please try again.');
            Toast.error('Network error. Please try again.');
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = '[ LOGIN ]';
        }
    });
    
    function showError(message) {
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
        setTimeout(() => {
            errorDiv.style.display = 'none';
        }, 5000);
    }
}

// Initialize when DOM is ready using shared utility
onDomReady(initLoginForm);
