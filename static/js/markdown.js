/**
 * Glyph - Minimal, safe Markdown renderer
 *
 * Renders the Markdown used by LLM analysis results into HTML without any
 * external dependencies. The application's strict Content Security Policy
 * (script-src 'self') forbids loading third-party libraries such as
 * marked.js or DOMPurify, so this self-contained renderer escapes every
 * piece of source text and only emits a fixed set of safe elements.
 * Raw HTML contained in the source is never passed through — it is
 * escaped and displayed as literal text.
 *
 * Supported syntax:
 *   - Fenced code blocks (``` / ~~~) with optional language tag
 *   - ATX headings (# through ######)
 *   - Bold (**text** / __text__), italic (*text* / _text__), strikethrough (~~text~~)
 *   - Inline code (`code`)
 *   - Links [text](url) — only http/https/mailto/relative URLs are kept
 *   - Images ![alt](url) — rendered as links (remote images are CSP-blocked)
 *   - Unordered (-, *, +) and ordered (1., 1)) lists with continuation lines
 *   - Blockquotes (>), horizontal rules (---, ***, ___)
 *   - Tables with optional column alignment (:---, ---:, :---:)
 *   - Paragraphs with hard line breaks (two trailing spaces)
 */
(function (global) {
    'use strict';

    /**
     * Escape a value for safe inclusion in HTML text or attribute content.
     * @param {string} text - Value to escape.
     * @returns {string} Escaped text.
     */
    function escapeHtml(text) {
        return String(text)
            .replace(/&/g, '\u0026amp;')
            .replace(/</g, '\u0026lt;')
            .replace(/>/g, '\u0026gt;')
            .replace(/"/g, '\u0026quot;')
            .replace(/'/g, '\u0026#39;');
    }

    /**
     * True when a URL is safe to render as an href.
     * Only http(s) and mailto links, plus scheme-less relative URLs, are
     * allowed; anything else (javascript:, data:, vbscript:, ...) is dropped.
     * @param {string} url - URL from the Markdown source.
     * @returns {boolean} Whether the URL may be used in an anchor.
     */
    function isSafeUrl(url) {
        const trimmed = String(url).trim();
        if (!trimmed) return false;
        const schemeMatch = /^([a-z][a-z0-9+.-]*):/i.exec(trimmed);
        if (schemeMatch) {
            const scheme = schemeMatch[1].toLowerCase() + ':';
            return scheme === 'http:' || scheme === 'https:' || scheme === 'mailto:';
        }
        // No scheme: relative URL. Reject whitespace and control characters.
        return !/[\s\x00-\x1f]/.test(trimmed);
    }

    /**
     * Render inline Markdown (code spans, emphasis, links) on already-
     * paragraph-sized text. All source text is escaped before markup is
     * applied, so no raw HTML from the source can execute.
     * @param {string} text - Inline Markdown source.
     * @returns {string} HTML string.
     */
    function renderInline(text) {
        // Split out code spans first so their contents are not processed
        // as emphasis or links.
        const segments = [];
        let lastIndex = 0;
        let match;
        const codeRe = /`([^`\n]+)`/g;
        while ((match = codeRe.exec(text)) !== null) {
            if (match.index > lastIndex) {
                segments.push({ type: 'text', value: text.slice(lastIndex, match.index) });
            }
            segments.push({ type: 'code', value: match[1] });
            lastIndex = match.index + match[0].length;
        }
        if (lastIndex < text.length) {
            segments.push({ type: 'text', value: text.slice(lastIndex) });
        }

        let html = '';
        for (const segment of segments) {
            if (segment.type === 'code') {
                html += `<code>${escapeHtml(segment.value)}</code>`;
            } else {
                html += renderEmphasis(escapeHtml(segment.value));
            }
        }
        return html;
    }

    /**
     * Apply emphasis and link markup to already-escaped text.
     * @param {string} escaped - HTML-escaped inline text.
     * @returns {string} HTML string.
     */
    function renderEmphasis(escaped) {
        let out = escaped;

        // Images first: render as links because the CSP blocks remote images.
        out = out.replace(/!\[([^\]]*)\]\(([^)\s]+)\)/g, (full, alt, url) => {
            if (!isSafeUrl(url)) return alt;
            const label = alt || 'image';
            return `<a href="${url}" target="_blank" rel="noopener noreferrer">${label}</a>`;
        });

        // Links: only safe URLs are kept; unsafe ones keep their label text.
        out = out.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (full, label, url) => {
            if (!isSafeUrl(url)) return label;
            return `<a href="${url}" target="_blank" rel="noopener noreferrer">${label}</a>`;
        });

        // Bold, then italic, then strikethrough.
        out = out.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        out = out.replace(/__([^_]+)__/g, '<strong>$1</strong>');
        out = out.replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, '$1<em>$2</em>');
        out = out.replace(/(^|[^_\w])_([^_\n]+)_(?!\w)/g, '$1<em>$2</em>');
        out = out.replace(/~~([^~]+)~~/g, '<del>$1</del>');

        return out;
    }

    /**
     * Parse a table row into trimmed cells, stripping outer pipes.
     * @param {string} row - Raw table row.
     * @returns {string[]} Cell contents.
     */
    function parseTableRow(row) {
        let r = row.trim();
        if (r.startsWith('|')) r = r.slice(1);
        if (r.endsWith('|')) r = r.slice(0, -1);
        return r.split('|').map((cell) => cell.trim());
    }

    /**
     * Render a list of lines as block-level Markdown.
     * @param {string[]} lines - Source lines (no trailing newlines).
     * @returns {string} HTML string.
     */
    function renderBlocks(lines) {
        let html = '';
        let i = 0;
        const n = lines.length;
        let paragraph = [];

        const flushParagraph = () => {
            if (paragraph.length === 0) return;
            const parts = paragraph.map((line, idx) => {
                const hardBreak = idx < paragraph.length - 1 && / {2,}$/.test(line);
                const inline = renderInline(line.trimEnd());
                return hardBreak ? `${inline}<br>` : inline;
            });
            html += `<p>${parts.join(' ')}</p>\n`;
            paragraph = [];
        };

        while (i < n) {
            const line = lines[i];

            // Blank line ends the current paragraph.
            if (/^\s*$/.test(line)) {
                flushParagraph();
                i += 1;
                continue;
            }

            // Fenced code block.
            const fence = /^ {0,3}(`{3,}|~{3,})\s*([^\s`~]*)\s*$/.exec(line);
            if (fence) {
                flushParagraph();
                const marker = fence[1][0];
                const minLen = fence[1].length;
                const lang = fence[2];
                const closeRe =
                    marker === '`'
                        ? new RegExp('^ {0,3}\\`{' + minLen + ',}\\s*$')
                        : new RegExp('^ {0,3}~{' + minLen + ',}\\s*$');
                const body = [];
                i += 1;
                while (i < n && !closeRe.test(lines[i])) {
                    body.push(lines[i]);
                    i += 1;
                }
                i += 1; // skip the closing fence (or run past the end)
                const cls = lang ? ` class="language-${escapeHtml(lang)}"` : '';
                html += `<pre><code${cls}>${escapeHtml(body.join('\n'))}</code></pre>\n`;
                continue;
            }

            // ATX heading.
            const heading = /^(#{1,6})\s+(.*?)\s*#*\s*$/.exec(line);
            if (heading) {
                flushParagraph();
                const level = heading[1].length;
                html += `<h${level}>${renderInline(heading[2])}</h${level}>\n`;
                i += 1;
                continue;
            }

            // Horizontal rule.
            if (/^ {0,3}(-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
                flushParagraph();
                html += '<hr>\n';
                i += 1;
                continue;
            }

            // Blockquote: collect consecutive quoted lines and render them
            // recursively so nested structure is preserved.
            if (/^ {0,3}>/.test(line)) {
                flushParagraph();
                const quoteLines = [];
                while (i < n && /^ {0,3}>/.test(lines[i])) {
                    quoteLines.push(lines[i].replace(/^ {0,3}>\s?/, ''));
                    i += 1;
                }
                html += `<blockquote>\n${renderBlocks(quoteLines)}</blockquote>\n`;
                continue;
            }

            // Lists (unordered or ordered) with indented continuation lines.
            const ulItem = /^ {0,3}([-*+])\s+(.*)$/.exec(line);
            const olItem = /^ {0,3}(\d{1,9})[.)]\s+(.*)$/.exec(line);
            if (ulItem || olItem) {
                flushParagraph();
                const isOl = !!olItem;
                const itemRe = isOl
                    ? /^ {0,3}(\d{1,9})[.)]\s+(.*)$/
                    : /^ {0,3}([-*+])\s+(.*)$/;
                const items = [];
                while (i < n) {
                    const m = itemRe.exec(lines[i]);
                    if (m) {
                        items.push(m[2]);
                        i += 1;
                    } else if (items.length > 0 && /^ {2,}\S/.test(lines[i])) {
                        // Indented continuation of the current item.
                        items[items.length - 1] += ` ${lines[i].trim()}`;
                        i += 1;
                    } else {
                        break;
                    }
                }
                const tag = isOl ? 'ol' : 'ul';
                const lis = items.map((item) => `<li>${renderInline(item)}</li>`).join('');
                html += `<${tag}>${lis}</${tag}>\n`;
                continue;
            }

            // Table: a row containing '|' followed by a separator row.
            if (
                line.includes('|') &&
                i + 1 < n &&
                /^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)*\|?\s*$/.test(lines[i + 1])
            ) {
                flushParagraph();
                const headers = parseTableRow(line);
                const sepCells = parseTableRow(lines[i + 1]);
                const aligns = sepCells.map((cell) => {
                    const left = cell.startsWith(':');
                    const right = cell.endsWith(':');
                    if (left && right) return 'center';
                    if (right) return 'right';
                    if (left) return 'left';
                    return '';
                });
                i += 2;
                const rows = [];
                while (i < n && lines[i].includes('|') && !/^\s*$/.test(lines[i])) {
                    rows.push(parseTableRow(lines[i]));
                    i += 1;
                }
                const alignAttr = (idx) =>
                    aligns[idx] ? ` style="text-align:${aligns[idx]}"` : '';
                let table = '<table>\n<thead>\n<tr>';
                headers.forEach((header, idx) => {
                    table += `<th${alignAttr(idx)}>${renderInline(header)}</th>`;
                });
                table += '</tr>\n</thead>\n';
                if (rows.length > 0) {
                    table += '<tbody>\n';
                    rows.forEach((row) => {
                        table += '<tr>';
                        headers.forEach((_, idx) => {
                            table += `<td${alignAttr(idx)}>${renderInline(row[idx] || '')}</td>`;
                        });
                        table += '</tr>\n';
                    });
                    table += '</tbody>\n';
                }
                table += '</table>\n';
                html += table;
                continue;
            }

            // Anything else accumulates into a paragraph.
            paragraph.push(line);
            i += 1;
        }

        flushParagraph();
        return html;
    }

    /**
     * Render a Markdown document to safe HTML.
     * @param {string} source - Markdown source text.
     * @returns {string} HTML string (empty string for empty input).
     */
    function renderMarkdown(source) {
        if (source === null || source === undefined) return '';
        const text = String(source).replace(/\r\n?/g, '\n');
        if (text.trim() === '') return '';
        return renderBlocks(text.split('\n'));
    }

    global.renderMarkdown = renderMarkdown;
    global.GlyphMarkdown = { render: renderMarkdown };
})(typeof window !== 'undefined' ? window : this);
