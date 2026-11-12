/**
 * Glyph - Register Form JavaScript
 * Handles registration form validation and submission
 */
'use strict';

/**
 * Validate email format
 * @param {string} email - Email to validate
 * @returns {boolean} True if valid email format
 */
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

/**
 * Initialize register form with validation and submission handling
 */
function initRegisterForm() {
    const form = document.getElementById('registerForm');
    const usernameInput = document.getElementById('username');
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const confirmPasswordInput = document.getElementById('confirm_password');
    const submitBtn = document.getElementById('register-submit-btn');
    const errorDiv = document.getElementById('register-error');

    if (!form) return;

    // Mark form as initialized for testing
    form.setAttribute('data-initialized', 'true');

    // Real-time validation for username (min 3 characters)
    setupFieldValidation(usernameInput, value => value.length >= 3);

    // Real-time validation for email
    setupFieldValidation(emailInput, value => !value || isValidEmail(value));

    // Real-time validation for password (min 8 characters)
    setupFieldValidation(passwordInput, value => value.length >= 8);

    // Real-time validation for confirm password
    confirmPasswordInput.addEventListener('input', function() {
        if (this.value && passwordInput.value !== this.value) {
            this.classList.add('is-error');
            this.setAttribute('aria-invalid', 'true');
        } else if (this.value) {
            this.classList.remove('is-error');
            this.setAttribute('aria-invalid', 'false');
        }
    });

    // Also clear confirm password error when password changes
    passwordInput.addEventListener('input', function() {
        if (confirmPasswordInput.classList.contains('is-error')) {
            confirmPasswordInput.classList.remove('is-error');
            confirmPasswordInput.setAttribute('aria-invalid', 'false');
        }
    });

    // Form submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        // Validate before submission (inline field-level errors only;
        // toasts are reserved for submission/async outcomes)
        if (usernameInput.value.length < 3) {
            usernameInput.classList.add('is-error');
            usernameInput.focus();
            return;
        }

        if (!isValidEmail(emailInput.value)) {
            emailInput.classList.add('is-error');
            emailInput.focus();
            return;
        }

        if (passwordInput.value.length < 8) {
            passwordInput.classList.add('is-error');
            passwordInput.focus();
            return;
        }

        if (passwordInput.value !== confirmPasswordInput.value) {
            confirmPasswordInput.classList.add('is-error');
            confirmPasswordInput.focus();
            return;
        }

        // Set loading state
        submitBtn.disabled = true;
        submitBtn.textContent = 'REGISTER...';

        const formData = new FormData(form);
        const data = {
            username: formData.get('username'),
            email: formData.get('email'),
            full_name: formData.get('full_name') || null,
            password: passwordInput.value
        };

        try {
            const response = await fetch('/auth/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });

            if (response.ok) {
                Toast.success('Registration successful! Redirecting to login...');
                // Redirect to login page
                setTimeout(() => {
                    window.location.href = '/login';
                }, 1000);
            } else {
                const error = await response.json();
                const errorMessage = error?.error?.message || error?.detail || 'Registration failed';
                // Single error surface: submission outcomes go to the toast only
                Toast.error(errorMessage);
            }
        } catch (err) {
            console.error('Registration error:', err);
            // Single error surface: submission outcomes go to the toast only
            Toast.error('Network error. Please try again.');
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = '[ REGISTER ]';
        }
    });
}

// Initialize when DOM is ready using shared utility
onDomReady(initRegisterForm);
