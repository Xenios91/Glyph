/**
 * Glyph — Call Graph Visualization
 * Custom force-directed graph renderer using Canvas API
 */
'use strict';

(function () {
    'use strict';

    // ============================================================
    // Constants
    // ============================================================

    var COLORS = {
        entry: '#d4c87a',
        normal: '#7dd8d8',
        selected: '#c87ab8',
        dimmed: 'rgba(224, 224, 224, 0.25)',
        edge: 'rgba(125, 216, 216, 0.2)',
        edgeHighlight: 'rgba(200, 122, 184, 0.6)',
        edgeDimmed: 'rgba(125, 216, 216, 0.05)',
        text: '#e0e0e0',
        textDimmed: 'rgba(224, 224, 224, 0.3)',
        arrow: 'rgba(125, 216, 216, 0.4)',
        arrowHighlight: 'rgba(200, 122, 184, 0.8)',
    };

    var NODE_RADIUS = 18;
    var NODE_RADIUS_HOVER = 22;
    var NODE_RADIUS_ENTRY = 24;
    var MIN_ZOOM = 0.1;
    var MAX_ZOOM = 5;
    var ZOOM_SENSITIVITY = 0.001;
    var DRAG_THRESHOLD = 3;

    // Force simulation parameters
    var REPULSION = 800;
    var ATTRACTION = 0.005;
    var CENTER_GRAVITY = 0.005;
    var DAMPING = 0.85;
    var MAX_VELOCITY = 8;
    var IDEAL_EDGE_LENGTH = 120;
    var CONVERGENCE_THRESHOLD = 0.1;

    // ============================================================
    // State
    // ============================================================

    var graphData = null;
    var nodes = [];
    var edges = [];
    var nodeMap = {};
    var selectedNode = null;
    var hoveredNode = null;
    var draggedNode = null;
    var dragOffset = { x: 0, y: 0 };
    var dragStartPos = { x: 0, y: 0 };
    var isDragging = false;
    var isPanning = false;
    var panStart = { x: 0, y: 0 };
    var camera = { x: 0, y: 0, zoom: 1 };
    var animationId = null;
    var simulationRunning = false;
    var simulationAlpha = 1.0;
    var canvas = null;
    var ctx = null;
    var tooltipEl = null;
    var canvasWidth = 0;
    var canvasHeight = 0;

    // ============================================================
    // Initialization
    // ============================================================

    document.addEventListener('DOMContentLoaded', function () {
        initCallGraph();
    });

    function initCallGraph() {
        canvas = document.getElementById('graph-canvas');
        tooltipEl = document.getElementById('graph-tooltip');

        if (!canvas) return;

        ctx = canvas.getContext('2d');

        // Button handlers
        var loadBtn = document.getElementById('btn-load-graph');
        var resetBtn = document.getElementById('btn-reset-view');
        var exportBtn = document.getElementById('btn-export-svg');

        if (loadBtn) loadBtn.addEventListener('click', loadCallGraph);
        if (resetBtn) resetBtn.addEventListener('click', resetView);
        if (exportBtn) exportBtn.addEventListener('click', exportToSvg);

        // Canvas events
        canvas.addEventListener('mousedown', onMouseDown);
        canvas.addEventListener('mousemove', onMouseMove);
        canvas.addEventListener('mouseup', onMouseUp);
        canvas.addEventListener('mouseleave', onMouseLeave);
        canvas.addEventListener('wheel', onWheel, { passive: false });
        canvas.addEventListener('dblclick', onDblClick);

        // Touch support
        canvas.addEventListener('touchstart', onTouchStart, { passive: false });
        canvas.addEventListener('touchmove', onTouchMove, { passive: false });
        canvas.addEventListener('touchend', onTouchEnd);

        // Resize handling
        window.addEventListener('resize', onResize);
        onResize();
    }

    // ============================================================
    // Data Loading
    // ============================================================

    async function loadCallGraph() {
        var binaryId = getBinaryId();
        if (!binaryId) return;

        var loadBtn = document.getElementById('btn-load-graph');
        var loadingEl = document.getElementById('graph-loading');
        var containerEl = document.getElementById('graph-container');
        var errorEl = document.getElementById('graph-error');
        var emptyEl = document.getElementById('graph-empty');

        if (loadBtn) loadBtn.disabled = true;
        if (loadingEl) loadingEl.style.display = 'flex';
        if (containerEl) containerEl.style.display = 'none';
        if (errorEl) errorEl.style.display = 'none';
        if (emptyEl) emptyEl.style.display = 'none';

        try {
            var response = await authenticatedFetch(
                '/api/v1/call-graph/' + binaryId + '/graph',
                { headers: { 'Accept': 'application/json' } }
            );

            var data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to load call graph');
            }

            graphData = data.data;
            buildGraph(graphData);

            if (nodes.length === 0) {
                if (emptyEl) emptyEl.style.display = 'block';
                if (loadingEl) loadingEl.style.display = 'none';
                if (loadBtn) loadBtn.disabled = false;
                return;
            }

            updateStats(graphData);
            enableControls(true);

            if (loadingEl) loadingEl.style.display = 'none';
            if (containerEl) containerEl.style.display = 'block';

            // Resize canvas now that container is visible and reposition nodes
            onResize();
            initPositions();

            // Center camera and start simulation
            centerCamera();
            startSimulation();

        } catch (error) {
            console.error('Load call graph error:', error);
            if (loadingEl) loadingEl.style.display = 'none';
            if (errorEl) {
                errorEl.style.display = 'block';
                var msgEl = document.getElementById('graph-error-message');
                if (msgEl) msgEl.textContent = error.message;
            }
            if (loadBtn) loadBtn.disabled = false;
        }
    }

    function buildGraph(data) {
        nodes = [];
        edges = [];
        nodeMap = {};

        var entrySet = new Set(data.entry_points || []);

        // Build nodes
        if (data.nodes) {
            data.nodes.forEach(function (node, i) {
                var isEntry = entrySet.has(node.name);
                var graphNode = {
                    id: i,
                    name: node.name,
                    entrypoint: node.entrypoint,
                    callers: node.callers || [],
                    callees: node.callees || [],
                    isEntry: isEntry,
                    x: 0,
                    y: 0,
                    vx: 0,
                    vy: 0,
                    radius: isEntry ? NODE_RADIUS_ENTRY : NODE_RADIUS,
                    pinned: false,
                };
                nodes.push(graphNode);
                nodeMap[node.name] = graphNode;
            });
        }

        // Build edges
        if (data.edges) {
            data.edges.forEach(function (edge) {
                var source = nodeMap[edge.caller];
                var target = nodeMap[edge.callee];
                if (source && target) {
                    edges.push({
                        source: source.id,
                        target: target.id,
                        callCount: edge.call_count || 1,
                    });
                }
            });
        }

        // Initialize positions in a circle
        initPositions();
    }

    function initPositions() {
        var count = nodes.length;
        if (count === 0) return;

        var radius = Math.min(canvasWidth, canvasHeight) * 0.3;
        var centerX = canvasWidth / 2;
        var centerY = canvasHeight / 2;

        nodes.forEach(function (node, i) {
            var angle = (2 * Math.PI * i) / count - Math.PI / 2;
            node.x = centerX + radius * Math.cos(angle);
            node.y = centerY + radius * Math.sin(angle);
            node.vx = 0;
            node.vy = 0;
        });
    }

    // ============================================================
    // Force Simulation
    // ============================================================

    function startSimulation() {
        simulationAlpha = 1.0;
        simulationRunning = true;
        if (animationId) cancelAnimationFrame(animationId);
        tick();
    }

    function stopSimulation() {
        simulationRunning = false;
        if (animationId) {
            cancelAnimationFrame(animationId);
            animationId = null;
        }
    }

    function tick() {
        if (!simulationRunning) return;

        applyForces();
        render();

        simulationAlpha *= DAMPING;

        if (simulationAlpha > CONVERGENCE_THRESHOLD / 100) {
            animationId = requestAnimationFrame(tick);
        } else {
            // Final render
            render();
            simulationRunning = false;
        }
    }

    function applyForces() {
        var n = nodes.length;
        if (n === 0) return;

        // Repulsion (charge) between all nodes
        for (var i = 0; i < n; i++) {
            var a = nodes[i];
            if (a.pinned) continue;

            for (var j = i + 1; j < n; j++) {
                var b = nodes[j];
                var dx = a.x - b.x;
                var dy = a.y - b.y;
                var distSq = dx * dx + dy * dy + 1;
                var force = REPULSION / distSq;
                var fx = (dx / Math.sqrt(distSq)) * force;
                var fy = (dy / Math.sqrt(distSq)) * force;

                a.vx += fx;
                a.vy += fy;
                if (!b.pinned) {
                    b.vx -= fx;
                    b.vy -= fy;
                }
            }
        }

        // Attraction along edges
        for (var e = 0; e < edges.length; e++) {
            var edge = edges[e];
            var source = nodes[edge.source];
            var target = nodes[edge.target];
            var dx = target.x - source.x;
            var dy = target.y - source.y;
            var dist = Math.sqrt(dx * dx + dy * dy) || 1;
            var force = (dist - IDEAL_EDGE_LENGTH) * ATTRACTION;
            var fx = (dx / dist) * force;
            var fy = (dy / dist) * force;

            if (!source.pinned) {
                source.vx += fx;
                source.vy += fy;
            }
            if (!target.pinned) {
                target.vx -= fx;
                target.vy -= fy;
            }
        }

        // Center gravity
        var cx = canvasWidth / 2;
        var cy = canvasHeight / 2;
        for (var k = 0; k < n; k++) {
            var node = nodes[k];
            if (node.pinned) continue;
            node.vx += (cx - node.x) * CENTER_GRAVITY;
            node.vy += (cy - node.y) * CENTER_GRAVITY;
        }

        // Apply velocities with damping and clamping
        for (var m = 0; m < n; m++) {
            var nd = nodes[m];
            if (nd.pinned) continue;

            nd.vx = Math.max(-MAX_VELOCITY, Math.min(MAX_VELOCITY, nd.vx));
            nd.vy = Math.max(-MAX_VELOCITY, Math.min(MAX_VELOCITY, nd.vy));

            nd.x += nd.vx * simulationAlpha;
            nd.y += nd.vy * simulationAlpha;

            // Keep within bounds
            nd.x = Math.max(nd.radius, Math.min(canvasWidth - nd.radius, nd.x));
            nd.y = Math.max(nd.radius, Math.min(canvasHeight - nd.radius, nd.y));
        }
    }

    // ============================================================
    // Rendering
    // ============================================================

    function render() {
        if (!ctx) return;

        ctx.clearRect(0, 0, canvasWidth, canvasHeight);
        ctx.save();

        // Apply camera transform
        ctx.translate(camera.x, camera.y);
        ctx.scale(camera.zoom, camera.zoom);

        // Determine highlighted nodes
        var highlighted = new Set();
        var highlightedEdges = new Set();

        if (selectedNode !== null || hoveredNode !== null) {
            var focus = selectedNode !== null ? selectedNode : hoveredNode;
            highlighted.add(focus);

            edges.forEach(function (edge, idx) {
                if (edge.source === focus || edge.target === focus) {
                    highlightedEdges.add(idx);
                    highlighted.add(edge.source);
                    highlighted.add(edge.target);
                }
            });
        }

        // Draw edges
        edges.forEach(function (edge, idx) {
            var source = nodes[edge.source];
            var target = nodes[edge.target];
            var isHighlighted = highlightedEdges.has(idx);
            var isDimmed = highlighted.size > 0 && !isHighlighted;

            ctx.beginPath();
            ctx.moveTo(source.x, source.y);
            ctx.lineTo(target.x, target.y);

            if (isHighlighted) {
                ctx.strokeStyle = COLORS.edgeHighlight;
                ctx.lineWidth = 2;
            } else if (isDimmed) {
                ctx.strokeStyle = COLORS.edgeDimmed;
                ctx.lineWidth = 0.5;
            } else {
                ctx.strokeStyle = COLORS.edge;
                ctx.lineWidth = 1;
            }
            ctx.stroke();

            // Draw arrow
            drawArrow(source, target, isHighlighted, isDimmed);

            // Draw call count badge
            if (edge.callCount > 1 && !isDimmed) {
                drawCallCountBadge(edge, isHighlighted);
            }
        });

        // Draw nodes
        nodes.forEach(function (node) {
            var isSelected = (node.id === selectedNode);
            var isHovered = (node.id === hoveredNode);
            var isHighlighted = highlighted.has(node.id);
            var isDimmed = highlighted.size > 0 && !isHighlighted;

            var r = node.radius;
            if (isHovered) r = NODE_RADIUS_HOVER;

            // Glow effect
            if (isSelected || isHovered) {
                ctx.beginPath();
                ctx.arc(node.x, node.y, r + 6, 0, Math.PI * 2);
                var glowColor = isSelected ? COLORS.selected : COLORS.entry;
                ctx.fillStyle = glowColor.replace(')', ', 0.2)').replace('rgb', 'rgba');
                ctx.fill();
            }

            // Node circle
            ctx.beginPath();
            ctx.arc(node.x, node.y, r, 0, Math.PI * 2);

            if (isDimmed) {
                ctx.fillStyle = COLORS.dimmed;
            } else if (isSelected) {
                ctx.fillStyle = COLORS.selected;
            } else if (node.isEntry) {
                ctx.fillStyle = COLORS.entry;
            } else {
                ctx.fillStyle = COLORS.normal;
            }
            ctx.fill();

            // Node border
            ctx.strokeStyle = isDimmed ? 'rgba(224, 224, 224, 0.1)' : 'rgba(13, 13, 26, 0.6)';
            ctx.lineWidth = 2;
            ctx.stroke();

            // Node label
            if (!isDimmed) {
                var labelColor = isSelected ? COLORS.selected : (node.isEntry ? COLORS.entry : COLORS.normal);
                ctx.fillStyle = labelColor;
                ctx.font = "11px 'Source Code Pro', monospace";
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';

                var shortName = truncateName(node.name, 20);
                ctx.fillText(shortName, node.x, node.y + r + 14);
            }
        });

        ctx.restore();
    }

    function drawArrow(source, target, highlighted, dimmed) {
        var dx = target.x - source.x;
        var dy = target.y - source.y;
        var dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 1) return;

        var nx = dx / dist;
        var ny = dy / dist;

        // Arrow position near target
        var arrowDist = dist - target.radius - 4;
        var ax = source.x + nx * arrowDist;
        var ay = source.y + ny * arrowDist;

        var arrowSize = highlighted ? 7 : 5;

        ctx.beginPath();
        ctx.moveTo(ax, ay);
        ctx.lineTo(
            ax - arrowSize * nx + arrowSize * 0.4 * ny,
            ay - arrowSize * ny - arrowSize * 0.4 * nx
        );
        ctx.lineTo(
            ax - arrowSize * nx - arrowSize * 0.4 * ny,
            ay - arrowSize * ny + arrowSize * 0.4 * nx
        );
        ctx.closePath();

        if (highlighted) {
            ctx.fillStyle = COLORS.arrowHighlight;
        } else if (dimmed) {
            ctx.fillStyle = COLORS.edgeDimmed;
        } else {
            ctx.fillStyle = COLORS.arrow;
        }
        ctx.fill();
    }

    function drawCallCountBadge(edge, highlighted) {
        var source = nodes[edge.source];
        var target = nodes[edge.target];
        var mx = (source.x + target.x) / 2;
        var my = (source.y + target.y) / 2;

        var text = String(edge.callCount);
        ctx.font = "10px 'Source Code Pro', monospace";
        var textWidth = ctx.measureText(text).width;
        var pad = 4;

        var bg = highlighted ? 'rgba(200, 122, 184, 0.8)' : 'rgba(13, 13, 26, 0.85)';
        var color = highlighted ? '#ffffff' : COLORS.normal;

        ctx.fillStyle = bg;
        ctx.fillRect(mx - textWidth / 2 - pad, my - 8, textWidth + pad * 2, 16);

        ctx.fillStyle = color;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(text, mx, my);
    }

    function truncateName(name, maxLen) {
        if (!name || name.length <= maxLen) return name;
        return name.substring(0, maxLen - 2) + '\u2026';
    }

    // ============================================================
    // Interaction
    // ============================================================

    function getMousePos(e) {
        var rect = canvas.getBoundingClientRect();
        return {
            x: e.clientX - rect.left,
            y: e.clientY - rect.top,
        };
    }

    function screenToWorld(sx, sy) {
        return {
            x: (sx - camera.x) / camera.zoom,
            y: (sy - camera.y) / camera.zoom,
        };
    }

    function findNodeAt(wx, wy) {
        for (var i = nodes.length - 1; i >= 0; i--) {
            var node = nodes[i];
            var dx = wx - node.x;
            var dy = wy - node.y;
            var hitRadius = Math.max(node.radius, NODE_RADIUS_HOVER) + 4;
            if (dx * dx + dy * dy <= hitRadius * hitRadius) {
                return node;
            }
        }
        return null;
    }

    function onMouseDown(e) {
        var pos = getMousePos(e);
        var world = screenToWorld(pos.x, pos.y);
        var node = findNodeAt(world.x, world.y);

        if (node) {
            draggedNode = node;
            dragOffset.x = world.x - node.x;
            dragOffset.y = world.y - node.y;
            dragStartPos = { x: pos.x, y: pos.y };
            isDragging = false;
        } else {
            isPanning = true;
            panStart = { x: pos.x - camera.x, y: pos.y - camera.y };
        }
    }

    function onMouseMove(e) {
        var pos = getMousePos(e);
        var world = screenToWorld(pos.x, pos.y);

        if (draggedNode) {
            var dx = pos.x - dragStartPos.x;
            var dy = pos.y - dragStartPos.y;
            if (Math.abs(dx) > DRAG_THRESHOLD || Math.abs(dy) > DRAG_THRESHOLD) {
                isDragging = true;
            }

            if (isDragging) {
                draggedNode.x = world.x - dragOffset.x;
                draggedNode.y = world.y - dragOffset.y;
                draggedNode.pinned = true;

                // Restart simulation briefly to settle
                if (!simulationRunning) {
                    simulationAlpha = 0.3;
                    startSimulation();
                }
            }
        } else if (isPanning) {
            camera.x = pos.x - panStart.x;
            camera.y = pos.y - panStart.y;
            render();
        } else {
            // Hover detection
            var node = findNodeAt(world.x, world.y);
            var prevHovered = hoveredNode;
            hoveredNode = node ? node.id : null;

            if (prevHovered !== hoveredNode) {
                render();
                showTooltip(node, pos);
            } else if (node) {
                positionTooltip(pos);
            }
        }
    }

    function onMouseUp(e) {
        if (draggedNode && !isDragging) {
            // It was a click
            selectedNode = selectedNode === draggedNode.id ? null : draggedNode.id;
            render();
        }

        if (draggedNode) {
            // Unpin after drag so simulation can settle
            draggedNode.pinned = false;
        }

        draggedNode = null;
        isDragging = false;
        isPanning = false;
    }

    function onMouseLeave() {
        hoveredNode = null;
        hideTooltip();
        if (!draggedNode) {
            isPanning = false;
        }
        render();
    }

    function onWheel(e) {
        e.preventDefault();
        var pos = getMousePos(e);
        var delta = -e.deltaY * ZOOM_SENSITIVITY;
        var newZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, camera.zoom + delta));

        // Zoom toward cursor
        var ratio = newZoom / camera.zoom;
        camera.x = pos.x - (pos.x - camera.x) * ratio;
        camera.y = pos.y - (pos.y - camera.y) * ratio;
        camera.zoom = newZoom;

        render();
    }

    function onDblClick(e) {
        var pos = getMousePos(e);
        var world = screenToWorld(pos.x, pos.y);
        var node = findNodeAt(world.x, world.y);

        if (node) {
            // Zoom to node
            var targetZoom = Math.min(MAX_ZOOM, camera.zoom * 1.5);
            var rect = canvas.getBoundingClientRect();
            var cx = rect.width / 2;
            var cy = rect.height / 2;

            camera.x = cx - node.x * targetZoom;
            camera.y = cy - node.y * targetZoom;
            camera.zoom = targetZoom;

            render();
        } else {
            resetView();
        }
    }

    // Touch support
    var lastTouchDist = 0;
    var lastTouchCenter = null;

    function onTouchStart(e) {
        if (e.touches.length === 1) {
            var touch = e.touches[0];
            var fakeEvent = { clientX: touch.clientX, clientY: touch.clientY };
            onMouseDown(fakeEvent);
        } else if (e.touches.length === 2) {
            e.preventDefault();
            var t1 = e.touches[0];
            var t2 = e.touches[1];
            lastTouchDist = Math.hypot(t2.clientX - t1.clientX, t2.clientY - t1.clientY);
            lastTouchCenter = {
                x: (t1.clientX + t2.clientX) / 2,
                y: (t1.clientY + t2.clientY) / 2,
            };
        }
    }

    function onTouchMove(e) {
        if (e.touches.length === 1) {
            var touch = e.touches[0];
            var fakeEvent = { clientX: touch.clientX, clientY: touch.clientY };
            onMouseMove(fakeEvent);
        } else if (e.touches.length === 2) {
            e.preventDefault();
            var t1 = e.touches[0];
            var t2 = e.touches[1];
            var dist = Math.hypot(t2.clientX - t1.clientX, t2.clientY - t1.clientY);
            var center = {
                x: (t1.clientX + t2.clientX) / 2,
                y: (t1.clientY + t2.clientY) / 2,
            };

            if (lastTouchDist > 0) {
                var scale = dist / lastTouchDist;
                var newZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, camera.zoom * scale));
                var rect = canvas.getBoundingClientRect();
                var px = center.x - rect.left;
                var py = center.y - rect.top;
                var ratio = newZoom / camera.zoom;
                camera.x = px - (px - camera.x) * ratio;
                camera.y = py - (py - camera.y) * ratio;
                camera.zoom = newZoom;
                render();
            }

            if (lastTouchCenter) {
                var dx = center.x - lastTouchCenter.x;
                var dy = center.y - lastTouchCenter.y;
                camera.x += dx;
                camera.y += dy;
                render();
            }

            lastTouchDist = dist;
            lastTouchCenter = center;
        }
    }

    function onTouchEnd(e) {
        var fakeEvent = {};
        if (e.changedTouches.length === 1) {
            var touch = e.changedTouches[0];
            fakeEvent.clientX = touch.clientX;
            fakeEvent.clientY = touch.clientY;
            onMouseUp(fakeEvent);
        }
        lastTouchDist = 0;
        lastTouchCenter = null;
    }

    // ============================================================
    // Tooltip
    // ============================================================

    function showTooltip(node, pos) {
        if (!node || !tooltipEl) {
            hideTooltip();
            return;
        }

        var html =
            '<div class="tooltip-name">' + escapeHtml(node.name) + '</div>' +
            '<div class="tooltip-detail">Address: ' + escapeHtml(node.entrypoint || 'N/A') + '</div>' +
            '<div class="tooltip-detail">Callers: ' + node.callers.length + '</div>' +
            '<div class="tooltip-detail">Callees: ' + node.callees.length + '</div>';

        if (node.isEntry) {
            html += '<div class="tooltip-detail" style="color: ' + COLORS.entry + ';">Entry Point</div>';
        }

        tooltipEl.innerHTML = html;
        tooltipEl.style.display = 'block';
        positionTooltip(pos);
    }

    function positionTooltip(pos) {
        if (!tooltipEl) return;
        var rect = canvas.getBoundingClientRect();
        var tx = pos.x + 16;
        var ty = pos.y - 10;

        // Keep tooltip within canvas bounds
        var tw = tooltipEl.offsetWidth;
        var th = tooltipEl.offsetHeight;
        if (tx + tw > rect.width - 10) tx = pos.x - tw - 16;
        if (ty + th > rect.height - 10) ty = pos.y - th - 10;
        if (ty < 10) ty = 10;

        tooltipEl.style.left = tx + 'px';
        tooltipEl.style.top = ty + 'px';
    }

    function hideTooltip() {
        if (tooltipEl) tooltipEl.style.display = 'none';
    }

    // ============================================================
    // Controls
    // ============================================================

    function resetView() {
        centerCamera();
        selectedNode = null;
        render();
    }

    function centerCamera() {
        if (nodes.length === 0) {
            camera = { x: 0, y: 0, zoom: 1 };
            return;
        }

        // Calculate bounding box
        var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        nodes.forEach(function (node) {
            if (node.x < minX) minX = node.x;
            if (node.y < minY) minY = node.y;
            if (node.x > maxX) maxX = node.x;
            if (node.y > maxY) maxY = node.y;
        });

        var graphW = maxX - minX + NODE_RADIUS * 4;
        var graphH = maxY - minY + NODE_RADIUS * 4;
        var cx = (minX + maxX) / 2;
        var cy = (minY + maxY) / 2;

        var scaleX = canvasWidth / graphW;
        var scaleY = canvasHeight / graphH;
        camera.zoom = Math.min(scaleX, scaleY, 1.5) * 0.9;
        camera.x = canvasWidth / 2 - cx * camera.zoom;
        camera.y = canvasHeight / 2 - cy * camera.zoom;
    }

    function enableControls(enabled) {
        var resetBtn = document.getElementById('btn-reset-view');
        var exportBtn = document.getElementById('btn-export-svg');
        if (resetBtn) resetBtn.disabled = !enabled;
        if (exportBtn) exportBtn.disabled = !enabled;
    }

    function updateStats(data) {
        var nodesEl = document.getElementById('stat-nodes');
        var edgesEl = document.getElementById('stat-edges');
        var entryEl = document.getElementById('stat-entry-points');

        if (nodesEl) nodesEl.textContent = data.total_nodes || 0;
        if (edgesEl) edgesEl.textContent = data.total_edges || 0;
        if (entryEl) entryEl.textContent = (data.entry_points || []).length;
    }

    // ============================================================
    // Export
    // ============================================================

    function exportToSvg() {
        if (nodes.length === 0) return;

        var width = canvasWidth / camera.zoom;
        var height = canvasHeight / camera.zoom;

        var svg = '<?xml version="1.0" encoding="UTF-8"?>\n';
        svg += '<svg xmlns="http://www.w3.org/2000/svg" width="' + Math.ceil(width) + '" height="' + Math.ceil(height) + '" viewBox="0 0 ' + width + ' ' + height + '">\n';

        // Styles
        svg += '<style>\n';
        svg += '  .node { stroke-width: 2px; }\n';
        svg += '  .edge { stroke: ' + COLORS.edge + '; stroke-width: 1px; fill: none; }\n';
        svg += '  .label { font-family: "Source Code Pro", monospace; font-size: 11px; fill: ' + COLORS.text + '; text-anchor: middle; }\n';
        svg += '</style>\n';

        // Edges
        edges.forEach(function (edge) {
            var source = nodes[edge.source];
            var target = nodes[edge.target];
            svg += '<line class="edge" x1="' + source.x + '" y1="' + source.y + '" x2="' + target.x + '" y2="' + target.y + '"/>\n';
        });

        // Nodes
        nodes.forEach(function (node) {
            var fill = node.isEntry ? COLORS.entry : COLORS.normal;
            svg += '<circle class="node" cx="' + node.x + '" cy="' + node.y + '" r="' + node.radius + '" fill="' + fill + '"/>\n';
            svg += '<text class="label" x="' + node.x + '" y="' + (node.y + node.radius + 14) + '">' + escapeXml(node.name) + '</text>\n';
        });

        svg += '</svg>';

        // Download
        var blob = new Blob([svg], { type: 'image/svg+xml' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = 'call_graph_' + getBinaryId() + '.svg';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    // ============================================================
    // Utility
    // ============================================================

    function getBinaryId() {
        var id = parseInt(window.location.pathname.split('/').pop(), 10);
        return isNaN(id) ? null : id;
    }

    function onResize() {
        if (!canvas) return;
        var rect = canvas.parentElement.getBoundingClientRect();
        canvasWidth = Math.floor(rect.width * window.devicePixelRatio);
        canvasHeight = Math.floor(rect.height * window.devicePixelRatio);
        canvas.width = canvasWidth;
        canvas.height = canvasHeight;
        ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
        // Adjust for HiDPI in world space
        canvasWidth = rect.width;
        canvasHeight = rect.height;

        if (nodes.length > 0) {
            render();
        }
    }

    function escapeHtml(str) {
        if (!str) return '';
        var div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    }

    function escapeXml(str) {
        if (!str) return '';
        return str.replace(/&/g, '&').replace(/</g, '<').replace(/>/g, '>').replace(/"/g, '"');
    }

})();
