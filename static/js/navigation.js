/**
 * Glyph - Navigation Utilities
 * Handles navigation active state detection
 */

(function () {
    /**
     * Set active navigation link based on current path
     */
    function setActiveNav() {
        const path = window.location.pathname;
        document.querySelectorAll('.nav-links a').forEach(function (link) {
            const href = link.getAttribute('href');
            if (href && path.startsWith(href) && href !== '/') {
                link.classList.add('nav-active');
            }
        });
    }

    // Run when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setActiveNav);
    } else {
        setActiveNav();
    }
})();
