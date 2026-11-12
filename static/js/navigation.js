/**
 * Glyph - Navigation Utilities
 * Handles navigation active state detection, dropdown functionality,
 * mobile menu toggle, and keyboard navigation
 */
'use strict';

(function () {
    /**
     * Initialize mobile menu toggle
     */
    function initMobileMenu() {
        const navToggle = document.getElementById('nav-toggle');
        const navLinks = document.getElementById('nav-links');

        if (!navToggle || !navLinks) return;

        // Mobile menu toggle
        navToggle.addEventListener('click', function() {
            const isExpanded = navToggle.getAttribute('aria-expanded') === 'true';
            navToggle.setAttribute('aria-expanded', !isExpanded);
            navToggle.classList.toggle('is-active');
            navLinks.classList.toggle('is-open');
        });

        // Close mobile menu when clicking outside
        document.addEventListener('click', function(e) {
            if (!navToggle.contains(e.target) && !navLinks.contains(e.target)) {
                navToggle.setAttribute('aria-expanded', 'false');
                navToggle.classList.remove('is-active');
                navLinks.classList.remove('is-open');
            }
        });

        // Close mobile menu on Escape and return focus to the toggle
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && navLinks.classList.contains('is-open')) {
                navToggle.setAttribute('aria-expanded', 'false');
                navToggle.classList.remove('is-active');
                navLinks.classList.remove('is-open');
                navToggle.focus();
            }
        });
    }

    /**
     * Set active navigation link based on current path
     */
    function setActiveNav() {
        const path = window.location.pathname;

        // Handle dropdown menu items
        document.querySelectorAll('.nav-dropdown-menu a').forEach(function (link) {
            const href = link.getAttribute('href');
            if (href && path.startsWith(href) && href !== '/') {
                link.classList.add('nav-active');
                link.setAttribute('aria-current', 'page');

                // Highlight parent dropdown toggle
                const dropdown = link.closest('.nav-dropdown');
                if (dropdown) {
                    const toggle = dropdown.querySelector('.nav-dropdown-toggle');
                    if (toggle) {
                        toggle.classList.add('active');
                    }
                }
            }
        });

        // Clear stale aria-current markers before applying new state
        document.querySelectorAll('.nav-links a[aria-current]').forEach(function (link) {
            link.removeAttribute('aria-current');
        });

        // Handle top-level links (HOME and unauthenticated links)
        document.querySelectorAll('.nav-links > a').forEach(function (link) {
            const href = link.getAttribute('href');
            if (!href) return;
            const isMatch = href === '/' ? path === '/' : path.startsWith(href);
            if (isMatch) {
                link.classList.add('nav-active');
                link.setAttribute('aria-current', 'page');
            }
        });
    }

    /**
     * Initialize dropdown functionality
     */
    function initDropdowns() {
        const dropdowns = document.querySelectorAll('.nav-dropdown');

        dropdowns.forEach(dropdown => {
            const toggle = dropdown.querySelector('.nav-dropdown-toggle');
            const menu = dropdown.querySelector('.nav-dropdown-menu');

            if (toggle && menu) {
                // Hover functionality for desktop
                if (window.innerWidth > 768) {
                    dropdown.addEventListener('mouseenter', function() {
                        toggle.setAttribute('aria-expanded', 'true');
                        menu.classList.add('is-open');
                        toggle.classList.add('active');
                    });

                    dropdown.addEventListener('mouseleave', function() {
                        toggle.setAttribute('aria-expanded', 'false');
                        menu.classList.remove('is-open');
                        toggle.classList.remove('active');
                    });
                }

                // Click functionality for all devices
                toggle.addEventListener('click', function(e) {
                    e.stopPropagation();
                    const isExpanded = toggle.getAttribute('aria-expanded') === 'true';

                    // On mobile, allow multiple dropdowns to be open
                    // On desktop, close other dropdowns
                    if (window.innerWidth > 768) {
                        document.querySelectorAll('.nav-dropdown-menu').forEach(otherMenu => {
                            if (otherMenu !== menu) {
                                otherMenu.classList.remove('is-open');
                                const otherToggle = otherMenu.closest('.nav-dropdown')?.querySelector('.nav-dropdown-toggle');
                                if (otherToggle) {
                                    otherToggle.setAttribute('aria-expanded', 'false');
                                    otherToggle.classList.remove('active');
                                }
                            }
                        });
                    }

                    // Toggle current dropdown
                    toggle.setAttribute('aria-expanded', !isExpanded);
                    menu.classList.toggle('is-open');
                    toggle.classList.toggle('active');
                });
            }
        });
    }

    /**
     * Initialize keyboard navigation for dropdowns
     */
    function initKeyboardNavigation() {
        document.addEventListener('keydown', function(e) {
            // Arrow key navigation within dropdowns
            if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                const activeDropdown = document.querySelector('.nav-dropdown-menu.is-open');
                if (activeDropdown) {
                    e.preventDefault();
                    const links = activeDropdown.querySelectorAll('a');
                    const currentIndex = Array.from(links).indexOf(document.activeElement);
                    let newIndex;

                    if (e.key === 'ArrowDown') {
                        newIndex = (currentIndex + 1) % links.length;
                    } else {
                        newIndex = (currentIndex - 1 + links.length) % links.length;
                    }

                    links[newIndex].focus();
                }
            }

            // Close dropdowns on Escape, returning focus to the toggle that was open
            if (e.key === 'Escape') {
                const openMenu = document.querySelector('.nav-dropdown-menu.is-open');
                const focusTarget = openMenu?.closest('.nav-dropdown')?.querySelector('.nav-dropdown-toggle');

                document.querySelectorAll('.nav-dropdown-menu').forEach(menu => {
                    menu.classList.remove('is-open');
                });
                document.querySelectorAll('.nav-dropdown-toggle').forEach(toggle => {
                    toggle.setAttribute('aria-expanded', 'false');
                    toggle.classList.remove('active');
                });

                if (focusTarget) {
                    focusTarget.focus();
                }
            }
        });
    }

    // Run when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            initMobileMenu();
            setActiveNav();
            initDropdowns();
            initKeyboardNavigation();
        });
    } else {
        initMobileMenu();
        setActiveNav();
        initDropdowns();
        initKeyboardNavigation();
    }
})();
