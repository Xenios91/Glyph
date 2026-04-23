# Navbar Dropdown Redesign Plan

## Overview
Transform the current flat navbar into a categorical dropdown navigation system to accommodate future menu items and improve organization.

## Current Structure
The navbar currently displays all links horizontally:
- **Authenticated**: HOME, VIEW MODELS, PREDICTIONS, UPLOAD, CONFIG, PROFILE, LOGOUT
- **Unauthenticated**: LOGIN, REGISTER

## New Categorical Structure

### Authenticated User Menu
```
┌─────────────────────────────────────────────────────────┐
│  GLYPH    [ANALYSIS ▼]  [SYSTEM ▼]  [USERNAME ▼]       │
└─────────────────────────────────────────────────────────┘

ANALYSIS dropdown:
  - HOME (/)
  - UPLOAD (/uploadBinary)
  - VIEW MODELS (/getModels)
  - PREDICTIONS (/getPredictions)

SYSTEM dropdown:
  - CONFIG (/config)

USER dropdown:
  - PROFILE (/profile)
  - LOGOUT (/auth/logout)
```

### Unauthenticated User Menu
```
┌─────────────────────────────────────────────────────────┐
│  GLYPH                          [LOGIN]  [REGISTER]     │
└─────────────────────────────────────────────────────────┘
```

## HTML Structure Design

```html
<nav class="navbar" role="navigation" aria-label="Main navigation">
    <a href="/" class="nav-logo" aria-label="Glyph home">
        <h1>GLYPH</h1>
    </a>
    
    <!-- Mobile hamburger menu toggle -->
    <button class="nav-toggle" id="nav-toggle" aria-label="Toggle navigation menu" aria-expanded="false" aria-controls="nav-links">
        <span></span>
        <span></span>
        <span></span>
    </button>
    
    <div class="nav-links" id="nav-links">
        {% if user and user.username %}
        <!-- Authenticated user menu with dropdowns -->
        
        <!-- ANALYSIS Dropdown -->
        <div class="nav-dropdown">
            <button class="nav-dropdown-toggle" aria-expanded="false" aria-haspopup="true" aria-controls="analysis-menu">
                ANALYSIS
                <svg class="dropdown-arrow" aria-hidden="true" viewBox="0 0 10 6">
                    <path d="M1 1L5 5L9 1" fill="none" stroke="currentColor" stroke-width="1.5"/>
                </svg>
            </button>
            <ul class="nav-dropdown-menu" id="analysis-menu" role="menu">
                <li role="none"><a href="/" role="menuitem" aria-label="Home">HOME</a></li>
                <li role="none"><a href="/uploadBinary" role="menuitem" aria-label="Upload Binary">UPLOAD</a></li>
                <li role="none"><a href="/getModels" role="menuitem" aria-label="View Models">VIEW MODELS</a></li>
                <li role="none"><a href="/getPredictions" role="menuitem" aria-label="View Predictions">PREDICTIONS</a></li>
            </ul>
        </div>
        
        <!-- SYSTEM Dropdown -->
        <div class="nav-dropdown">
            <button class="nav-dropdown-toggle" aria-expanded="false" aria-haspopup="true" aria-controls="system-menu">
                SYSTEM
                <svg class="dropdown-arrow" aria-hidden="true" viewBox="0 0 10 6">
                    <path d="M1 1L5 5L9 1" fill="none" stroke="currentColor" stroke-width="1.5"/>
                </svg>
            </button>
            <ul class="nav-dropdown-menu" id="system-menu" role="menu">
                <li role="none"><a href="/config" role="menuitem" aria-label="Configuration">CONFIG</a></li>
            </ul>
        </div>
        
        <!-- USER Dropdown -->
        <div class="nav-dropdown">
            <button class="nav-dropdown-toggle" aria-expanded="false" aria-haspopup="true" aria-controls="user-menu">
                {{ user.username | upper }}
                <svg class="dropdown-arrow" aria-hidden="true" viewBox="0 0 10 6">
                    <path d="M1 1L5 5L9 1" fill="none" stroke="currentColor" stroke-width="1.5"/>
                </svg>
            </button>
            <ul class="nav-dropdown-menu" id="user-menu" role="menu">
                <li role="none"><a href="/profile" role="menuitem" aria-label="View Profile">PROFILE</a></li>
                <li role="none"><a href="/auth/logout" role="menuitem" aria-label="Logout">LOGOUT</a></li>
            </ul>
        </div>
        
        {% else %}
        <!-- Unauthenticated user menu -->
        <a href="/login" aria-label="Login">LOGIN</a>
        <a href="/register" aria-label="Register">REGISTER</a>
        {% endif %}
    </div>
</nav>
```

## CSS Styles Required

### Dropdown Container
```css
.nav-dropdown {
    position: relative;
    display: inline-block;
}
```

### Dropdown Toggle Button
```css
.nav-dropdown-toggle {
    font-family: var(--font-display);
    font-size: var(--text-xs);
    letter-spacing: 0.05em;
    color: var(--magenta);
    background: transparent;
    border: none;
    padding: 0.5rem 0.75rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    transition: color 0.1s;
}

.nav-dropdown-toggle:hover {
    color: var(--yellow);
}

.nav-dropdown-toggle.active {
    color: var(--cyan-bright);
}

.dropdown-arrow {
    width: 10px;
    height: 6px;
    transition: transform 0.15s;
}

.nav-dropdown-toggle.active .dropdown-arrow {
    transform: rotate(180deg);
}
```

### Dropdown Menu
```css
.nav-dropdown-menu {
    position: absolute;
    top: 100%;
    left: 0;
    min-width: 180px;
    background: var(--nav-bg);
    border: 2px solid var(--cyan-dim);
    border-top: none;
    margin: 0;
    padding: 0;
    list-style: none;
    opacity: 0;
    visibility: hidden;
    transform: translateY(-10px);
    transition: all 0.15s ease;
    z-index: 1000;
    box-shadow: 0 4px 24px rgba(125, 216, 216, 0.07);
}

.nav-dropdown-menu.is-open {
    opacity: 1;
    visibility: visible;
    transform: translateY(0);
}

.nav-dropdown-menu li {
    border-bottom: 1px solid rgba(125, 216, 216, 0.1);
}

.nav-dropdown-menu li:last-child {
    border-bottom: none;
}

.nav-dropdown-menu a {
    display: block;
    padding: 0.75rem 1rem;
    color: var(--text-primary);
    text-decoration: none;
    font-family: var(--font-display);
    font-size: var(--text-xs);
    transition: background 0.1s, color 0.1s;
}

.nav-dropdown-menu a:hover {
    background: rgba(125, 216, 216, 0.1);
    color: var(--cyan);
}

.nav-dropdown-menu a.nav-active {
    color: var(--cyan-bright);
    background: rgba(125, 216, 216, 0.05);
}
```

### Mobile Responsive
```css
@media (max-width: 768px) {
    .nav-dropdown {
        display: block;
        width: 100%;
        border-bottom: 1px solid rgba(125, 216, 216, 0.1);
    }
    
    .nav-dropdown-toggle {
        width: 100%;
        justify-content: space-between;
        padding: 1.25rem 1rem;
        min-height: 56px;
    }
    
    .nav-dropdown-menu {
        position: static;
        opacity: 1;
        visibility: visible;
        transform: none;
        display: none;
        background: rgba(13, 13, 26, 0.5);
        border: none;
        box-shadow: none;
    }
    
    .nav-dropdown-menu.is-open {
        display: block;
        animation: dropdown-slide-down 0.2s ease;
    }
    
    .nav-dropdown-menu a {
        padding-left: 2rem;
        font-size: var(--text-sm);
    }
}

@keyframes dropdown-slide-down {
    from {
        opacity: 0;
        transform: translateY(-10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}
```

## JavaScript Functionality

### Dropdown Toggle Handler
```javascript
function initDropdowns() {
    const dropdowns = document.querySelectorAll('.nav-dropdown');
    
    dropdowns.forEach(dropdown => {
        const toggle = dropdown.querySelector('.nav-dropdown-toggle');
        const menu = dropdown.querySelector('.nav-dropdown-menu');
        
        if (toggle && menu) {
            toggle.addEventListener('click', (e) => {
                e.stopPropagation();
                const isExpanded = toggle.getAttribute('aria-expanded') === 'true';
                
                // Close all other dropdowns
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
                
                // Toggle current dropdown
                toggle.setAttribute('aria-expanded', !isExpanded);
                menu.classList.toggle('is-open');
                toggle.classList.toggle('active');
            });
        }
    });
    
    // Close dropdowns when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.nav-dropdown')) {
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
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.nav-dropdown-menu').forEach(menu => {
                menu.classList.remove('is-open');
            });
            document.querySelectorAll('.nav-dropdown-toggle').forEach(toggle => {
                toggle.setAttribute('aria-expanded', 'false');
                toggle.classList.remove('active');
                toggle.focus();
            });
        }
    });
}
```

### Active State Detection Update
```javascript
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
}
```

## Accessibility Features

1. **ARIA Labels**: All interactive elements have appropriate ARIA labels
2. **ARIA Expanded**: Dropdown toggles use `aria-expanded` to indicate state
3. **ARIA Has Popup**: Dropdown toggles use `aria-haspopup="true"`
4. **ARIA Controls**: Dropdown toggles reference their menu with `aria-controls`
5. **Role Menu**: Dropdown menus use `role="menu"` and items use `role="menuitem"`
6. **Keyboard Navigation**: 
   - Enter/Space to open/close dropdowns
   - Escape to close dropdowns
   - Tab to navigate between elements
7. **Focus Management**: Focus returns to toggle when dropdown closes

## Files to Modify

1. **templates/components/navbar.html** - Update HTML structure
2. **static/css/style.css** - Add dropdown styles
3. **static/js/navigation.js** - Update dropdown functionality and active state detection

## Testing Checklist

- [ ] Desktop dropdown hover/click behavior
- [ ] Mobile dropdown accordion behavior
- [ ] Active state highlighting on current page
- [ ] Keyboard navigation (Tab, Enter, Escape)
- [ ] Screen reader compatibility
- [ ] Click outside to close dropdowns
- [ ] Only one dropdown open at a time (desktop)
- [ ] Mobile menu integration with dropdowns
- [ ] Unauthenticated user links still work

## Future Extensibility

The dropdown structure allows easy addition of new menu items:
- Add new `<li>` elements to existing dropdowns
- Create new dropdown categories by copying the `.nav-dropdown` structure
- Mobile menu automatically adapts to new items
