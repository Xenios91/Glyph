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
    
    // Real-time validation for username (min 3 characters)
    setupFieldValidation(usernameInput, value => value.length >= 3);
    
    // Real-time validation for password (min 8 characters)
    setupFieldValidation(passwordInput, value => value.length >= 8);
    
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
                showError('login-error', errorMessage);
                Toast.error(errorMessage);
            }
        } catch (err) {
            console.error('Login error:', err);
            showError('login-error', 'Network error. Please try again.');
            Toast.error('Network error. Please try again.');
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = '[ LOGIN ]';
        }
    });
}

// Initialize when DOM is ready using shared utility
onDomReady(initLoginForm);
