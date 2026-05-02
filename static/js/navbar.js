/**
 * Glyph - Navbar JavaScript
 * Mobile navigation toggle and dropdown functionality
 */
(function() {
    function initNavbar() {
        const navToggle = document.getElementById('nav-toggle');
        const navLinks = document.getElementById('nav-links');
        
        // Mobile menu toggle
        if (navToggle && navLinks) {
            navToggle.addEventListener('click', function() {
                const isExpanded = navToggle.getAttribute('aria-expanded') === 'true';
                navToggle.setAttribute('aria-expanded', !isExpanded);
                navToggle.classList.toggle('is-active');
                navLinks.classList.toggle('is-open');
            });
        }
        
        // Dropdown functionality
        const dropdowns = document.querySelectorAll('.nav-dropdown');
        
        dropdowns.forEach(dropdown => {
            const toggle = dropdown.querySelector('.nav-dropdown-toggle');
            const menu = dropdown.querySelector('.nav-dropdown-menu');
            
            if (toggle && menu) {
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
        
        // Close mobile menu when clicking outside
        document.addEventListener('click', function(e) {
            if (navToggle && navLinks && !navToggle.contains(e.target) && !navLinks.contains(e.target)) {
                navToggle.setAttribute('aria-expanded', 'false');
                navToggle.classList.remove('is-active');
                navLinks.classList.remove('is-open');
            }
        });
        
        // Close dropdowns when clicking outside (desktop)
        document.addEventListener('click', function(e) {
            if (window.innerWidth > 768 && !e.target.closest('.nav-dropdown')) {
                document.querySelectorAll('.nav-dropdown-menu').forEach(menu => {
                    menu.classList.remove('is-open');
                });
                document.querySelectorAll('.nav-dropdown-toggle').forEach(toggle => {
                    toggle.setAttribute('aria-expanded', 'false');
                    toggle.classList.remove('active');
                });
            }
        });
        
        // Keyboard navigation
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                // Close mobile menu
                if (navToggle) {
                    navToggle.setAttribute('aria-expanded', 'false');
                    navToggle.classList.remove('is-active');
                    navLinks.classList.remove('is-open');
                }
                // Close all dropdowns
                document.querySelectorAll('.nav-dropdown-menu').forEach(menu => {
                    menu.classList.remove('is-open');
                });
                document.querySelectorAll('.nav-dropdown-toggle').forEach(toggle => {
                    toggle.setAttribute('aria-expanded', 'false');
                    toggle.classList.remove('active');
                });
            }
            
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
        });
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initNavbar);
    } else {
        initNavbar();
    }
})();
