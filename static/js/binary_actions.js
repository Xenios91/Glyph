/**
 * Binary Actions - canonical per-binary action list (single source of truth).
 *
 * R4: The "what can I do with this binary?" action set is defined ONCE here and
 * consumed by:
 *   - the binary library task modal (templates/binary_library.html)
 *   - the binary detail action row (templates/binary_detail.html)
 *   - the run-task page (thin wrapper over the executable task types)
 *
 * Every action deep-links with the binary pre-filled so the target page
 * starts with this binary already selected.
 */
(function () {
    'use strict';

    /**
     * Canonical per-binary action list.
     *
     * Each entry:
     *   id:          stable identifier (matches data-task-type values)
     *   label:       short display label (uppercase by convention)
     *   description: one-line description shown in pickers
     *   href:        function(binaryId, binaryName) -> deep link with binary pre-filled
     */
    var ACTIONS = [
        {
            id: 'dangerous_functions',
            label: 'DANGEROUS FUNCTIONS SCAN',
            description: 'Scan the binary for dangerous/insecure functions',
            href: function (binaryId) {
                return '/getDangerousFunctions?binary_id=' + binaryId;
            }
        },
        {
            id: 'behavioral_scan',
            label: 'BEHAVIORAL SCAN',
            description: 'Run a behavioral scan on the binary',
            href: function (binaryId) {
                return '/getBehavioralScan?binary_id=' + binaryId;
            }
        },
        {
            id: 'ml_training',
            label: 'CREATE MODEL',
            description: 'Train a new ML model from this binary',
            href: function (binaryId) {
                return '/create-model?binary_id=' + binaryId;
            }
        },
        {
            id: 'ml_prediction',
            label: 'CREATE PREDICTION',
            description: 'Run an ML prediction against this binary',
            href: function (binaryId) {
                return '/create-prediction?binary_id=' + binaryId;
            }
        },
        {
            id: 'similarity',
            label: 'SIMILARITY',
            description: 'Compare this binary against other binaries',
            href: function (binaryId) {
                return '/similarity-dashboard?binary_id=' + binaryId;
            }
        },
        {
            id: 'run_task',
            label: 'RUN TASK',
            description: 'Run an analysis task on this binary',
            href: function (binaryId, binaryName) {
                return '/run-task?binary_id=' + binaryId + '&binary_name=' + encodeURIComponent(binaryName || '');
            }
        }
    ];

    /**
     * Look up an action by id.
     *
     * @param {string} actionId - action id from ACTIONS
     * @returns {object|null} action entry or null for unknown id
     */
    function getAction(actionId) {
        for (var i = 0; i < ACTIONS.length; i += 1) {
            if (ACTIONS[i].id === actionId) {
                return ACTIONS[i];
            }
        }
        return null;
    }

    /**
     * Build the deep link for an action with the binary pre-filled.
     *
     * @param {string} actionId - action id from ACTIONS
     * @param {number} binaryId - binary database id
     * @param {string} binaryName - binary name (only needed by run_task)
     * @returns {string|null} deep link, or null for unknown action id
     */
    function buildHref(actionId, binaryId, binaryName) {
        var action = getAction(actionId);
        if (!action) {
            return null;
        }
        return action.href(binaryId, binaryName);
    }

    window.BinaryActions = {
        actions: ACTIONS,
        getAction: getAction,
        buildHref: buildHref
    };
})();
