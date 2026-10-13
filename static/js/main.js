/**
 * Home page — loads dashboard stats from the backend.
 * Uses the shared authenticatedFetch helper for consistent auth handling
 * (401 redirect, timeout) and animates the stat values once they arrive.
 */
document.addEventListener('DOMContentLoaded', async () => {
    const el = (id) => document.getElementById(id);

    const values = {
        binaries: el('stat-binaries'),
        models: el('stat-models'),
        predictions: el('stat-predictions'),
    };

    // Mark the stats as loading while the request is in flight
    Object.values(values).forEach(node => {
        if (node) node.classList.add('is-loading');
    });

    // Prefer the shared authenticated fetch helper when available
    const fetchStats = (typeof authenticatedFetch !== 'undefined')
        ? authenticatedFetch('/stats', {}, { redirectOn401: true })
        : fetch('/stats', { credentials: 'same-origin' });

    try {
        const res = await fetchStats;
        if (!res.ok) return;

        const data = await res.json();
        animateStat(values.binaries, data.binaries);
        animateStat(values.models, data.models);
        animateStat(values.predictions, data.predictions);
    } catch {
        /* silently fail — stats stay at "-" */
    } finally {
        Object.values(values).forEach(node => {
            if (node) node.classList.remove('is-loading');
        });
    }
});

/**
 * Animate a stat value counting up from 0 to the target.
 * Falls back to setting the value directly when the value is missing
 * or the user prefers reduced motion.
 */
function animateStat(node, value) {
    if (!node) return;

    if (value === undefined || value === null) {
        node.textContent = '-';
        return;
    }

    const target = Number(value);
    const useAnimation =
        Number.isFinite(target) &&
        target >= 0 &&
        typeof window.matchMedia === 'function' &&
        !window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (!useAnimation) {
        node.textContent = String(value);
        return;
    }

    const duration = 600;
    const start = performance.now();

    function frame(now) {
        const t = Math.min((now - start) / duration, 1);
        const eased = 1 - Math.pow(1 - t, 3); // ease-out cubic
        node.textContent = String(Math.round(eased * target));
        if (t < 1) {
            requestAnimationFrame(frame);
        } else {
            node.textContent = String(target);
        }
    }

    requestAnimationFrame(frame);
}
