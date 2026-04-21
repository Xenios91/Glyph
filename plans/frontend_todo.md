# Frontend Improvements - Remaining Tasks

This document tracks the remaining frontend improvements identified during the review of `frontend_improvements.md`.

---

## Not Implemented (Gaps)

### 1. Build Process (7.3)
**Priority:** Long-term
**Issue:** No build process for frontend assets
**Recommendations:**
- Add webpack or vite for bundling
- Add CSS preprocessing (Sass/Less)
- Add minification and source maps
**Files:** Project root

### 2. Frontend Unit Tests (8.1)
**Priority:** Long-term
**Issue:** No frontend unit tests
**Recommendations:**
- Add Jest or Vitest for JS testing
- Test utility functions
- Test form validation
**Files:** `tests/`

### 3. E2E Tests (8.2)
**Priority:** Long-term
**Issue:** No end-to-end tests
**Recommendations:**
- Add Playwright or Cypress tests
- Test critical user flows
- Test responsive layouts
**Files:** `tests/`

### 4. Accessibility Tests (8.3)
**Priority:** Long-term
**Issue:** No automated a11y testing
**Recommendations:**
- Add axe-core for accessibility testing
- Run tests in CI/CD
**Files:** `tests/`

### 5. CSS Minification/Bundling (4.1)
**Priority:** Medium
**Issue:** CSS files not minified or bundled
**Recommendations:**
- Minify CSS files
- Consider CSS bundling
- Remove unused CSS
**Files:** All `static/css/*.css`

---

## Implementation Notes

### Current Status
- **Fully Implemented:** 24 of 29 items (83%)
- **Partially Implemented:** 1 item (CSS optimization)
- **Not Implemented:** 4 items (all testing-related + build process)

### Dependencies to Consider
- Current dependencies: nes.css, jQuery (for some legacy code), Google Fonts
- Design system: Cyberpunk/retro aesthetic with dark theme

### Suggested Implementation Order
1. **CSS Minification** - Quick win, can be done independently
2. **Build Process** - Foundation for other improvements
3. **Frontend Unit Tests** - Can be added alongside build process
4. **E2E Tests** - Requires stable build process
5. **Accessibility Tests** - Can be integrated into CI/CD pipeline

---

## References
- Original plan: `plans/frontend_improvements.md`
- Review date: 2026-04-21
