/**
 * Glyph - Navigation Utilities
 * Handles navigation active state detection and dropdown functionality
 */

(function () {
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
        
        // Handle top-level links (for unauthenticated users)
        document.querySelectorAll('.nav-links > a').forEach(function (link) {
            const href = link.getAttribute('href');
            if (href && path.startsWith(href) && href !== '/') {
                link.classList.add('nav-active');
            }
        });
        
        // Handle home page active state
        if (path === '/') {
            const homeLink = document.querySelector('.nav-dropdown-menu a[href="/"]');
            if (homeLink) {
                homeLink.classList.add('nav-active');
                const homeDropdown = homeLink.closest('.nav-dropdown');
                if (homeDropdown) {
                    const toggle = homeDropdown.querySelector('.nav-dropdown-toggle');
                    if (toggle) {
                        toggle.classList.add('active');
                    }
                }
            }
        }
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
            
            // Close dropdowns on Escape
            if (e.key === 'Escape') {
                document.querySelectorAll('.nav-dropdown-menu').forEach(menu => {
                    menu.classList.remove('is-open');
                });
                document.querySelectorAll('.nav-dropdown-toggle').forEach(toggle => {
                    toggle.setAttribute('aria-expanded', 'false');
                    toggle.classList.remove('active');
                });
            }
        });
    }

    // Run when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            setActiveNav();
            initDropdowns();
            initKeyboardNavigation();
        });
    } else {
        setActiveNav();
        initDropdowns();
        initKeyboardNavigation();
    }
})();
