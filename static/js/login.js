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
    const toggleBtn = document.querySelector('.password-toggle-btn');
    const iconEye = toggleBtn?.querySelector('.icon-eye');
    const iconEyeOff = toggleBtn?.querySelector('.icon-eye-off');

    if (!form) return;

    // Mark form as initialized for testing
    form.setAttribute('data-initialized', 'true');

    // Password visibility toggle
    if (toggleBtn && passwordInput) {
        toggleBtn.addEventListener('click', () => {
            const isPassword = passwordInput.type === 'password';
            passwordInput.type = isPassword ? 'text' : 'password';
            toggleBtn.setAttribute('aria-label', isPassword ? 'Hide password' : 'Show password');
            if (iconEye) iconEye.classList.toggle('is-hidden', isPassword);
            if (iconEyeOff) iconEyeOff.classList.toggle('is-hidden', !isPassword);
        });
    }

    // Real-time validation for username (min 3 characters)
    setupFieldValidation(usernameInput, value => value.length >= 3);

    // Real-time validation for password (min 8 characters)
    setupFieldValidation(passwordInput, value => value.length >= 8);

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

        if (passwordInput.value.length < 8) {
            passwordInput.classList.add('is-error');
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
                // Honor a same-origin ?redirect= target; fall back to home
                const redirectTo = getLoginRedirectUrl('/');
                setTimeout(() => {
                    window.location.href = redirectTo;
                }, 500);
            } else {
                const error = await response.json();
                const errorMessage = error?.error?.message || error?.detail || 'Login failed';
                // Single error surface: submission outcomes go to the toast only
                Toast.error(errorMessage);
            }
        } catch (err) {
            console.error('Login error:', err);
            // Single error surface: submission outcomes go to the toast only
            Toast.error('Network error. Please try again.');
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = '[ LOGIN ]';
        }
    });
}

/**
 * Resolve the post-login redirect target from the ?redirect= query param.
 * Only same-origin paths are honored; absolute cross-origin URLs and
 * protocol-relative URLs (//evil.com) are rejected in favor of the fallback.
 *
 * @param {string} fallback - URL to use when no valid redirect is present
 * @returns {string} Safe same-origin path (with query/hash preserved) or fallback
 */
function getLoginRedirectUrl(fallback) {
    const params = new URLSearchParams(window.location.search);
    const redirect = params.get('redirect');
    if (!redirect) {
        return fallback;
    }
    try {
        const url = new URL(redirect, window.location.origin);
        if (redirect.startsWith('//') || !/^https?:$/.test(url.protocol)) {
            return fallback;
        }
        if (url.origin !== window.location.origin) {
            return fallback;
        }
        return url.pathname + url.search + url.hash;
    } catch (e) {
        return fallback;
    }
}

// Initialize when DOM is ready using shared utility
onDomReady(initLoginForm);
