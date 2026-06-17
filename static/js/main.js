/**
 * Home page — loads dashboard stats from the backend.
 */
document.addEventListener('DOMContentLoaded', async () => {
    const el = (id) => document.getElementById(id);

    try {
        const res = await fetch('/stats', { credentials: 'same-origin' });
        if (!res.ok) return;

        const data = await res.json();
        el('stat-binaries').textContent       = data.binaries ?? '-';
        el('stat-models').textContent         = data.models ?? '-';
        el('stat-predictions').textContent    = data.predictions ?? '-';
    } catch {
        /* silently fail — stats stay at "-" */
    }
});
