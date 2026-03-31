/**
 * Glyph Background Effects
 * Handles stars, city lights, particles, and clouds animations
 */

(function() {
    'use strict';

    /**
     * Create starfield effect
     */
    function createStarfield() {
        const sf = document.getElementById('starfield');
        if (!sf) return;

        const colors = ['#e0e0ff', '#00ffff', '#ff00ff', '#ffffff'];

        for (let i = 0; i < 120; i++) {
            const s = document.createElement('div');
            s.className = 'px-star';
            const sz = Math.random() < 0.2 ? 2 : 1;
            const col = colors[Math.floor(Math.random() * colors.length)];
            const blink = Math.random() < 0.4;
            s.style.cssText = `width:${sz}px;height:${sz}px;top:${Math.random() * 75}%;left:${Math.random() * 100}%;background:${col};${blink ? `animation:px-blink ${0.8 + Math.random() * 2.4}s ${Math.random() * 3}s step-end infinite;` : ''}`;
            sf.appendChild(s);
        }
    }

    /**
     * Create city window lights effect
     */
    function createCityLights() {
        const city = document.getElementById('cityline');
        if (!city) return;

        const winColors = ['#ffff00', '#00ffff', '#ff00ff', '#ff4400', '#ffffff'];

        for (let i = 0; i < 80; i++) {
            const w = document.createElement('div');
            w.className = 'win';
            const col = winColors[Math.floor(Math.random() * winColors.length)];
            const blink = Math.random() < 0.35;
            w.style.cssText = `left:${Math.random() * 100}%;top:${20 + Math.random() * 70}%;background:${col};box-shadow:0 0 4px ${col};${blink ? `animation:px-blink ${0.5 + Math.random() * 3}s ${Math.random() * 4}s step-end infinite;` : ''}`;
            city.appendChild(w);
        }
    }

    /**
     * Create falling data particles effect
     */
    function createParticles() {
        const ptcl = document.getElementById('particles');
        if (!ptcl) return;

        const chars = '01 アイウエオカキクケコサシスセソ#@%&';
        const bitColors = ['#00ffff', '#ff00ff', '#00ff41', '#ffff00'];

        for (let i = 0; i < 30; i++) {
            const b = document.createElement('div');
            b.className = 'data-bit';
            const col = bitColors[Math.floor(Math.random() * bitColors.length)];
            const ch = chars[Math.floor(Math.random() * chars.length)];
            const dur = 3 + Math.random() * 7;
            const delay = Math.random() * 5;
            b.style.cssText = `left:${Math.random() * 100}%;top:-20px;color:${col};animation:fall ${dur}s ${delay}s linear infinite;`;
            b.textContent = ch;
            ptcl.appendChild(b);
        }
    }

    /**
     * Create cloud drift effect
     */
    function createClouds() {
        const cl = document.getElementById('clouds');
        if (!cl) return;

        for (let i = 0; i < 8; i++) {
            const c = document.createElement('div');
            c.className = 'cloud';
            const dur = 20 + Math.random() * 40;
            const delay = Math.random() * 20;
            c.style.cssText = `left:-15%;top:${10 + Math.random() * 35}%;animation:cloud-drift ${dur}s ${delay}s linear infinite;`;
            cl.appendChild(c);
        }
    }

    /**
     * Initialize all background effects
     */
    function initEffects() {
        createStarfield();
        createCityLights();
        createParticles();
        createClouds();
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initEffects);
    } else {
        initEffects();
    }
})();
