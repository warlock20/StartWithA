/*
 * Suggest kill criterion: Mistake Log panel.
 *
 * Asks the server (Celery task) for a kill-checklist question that would have
 * caught a logged mistake, lets the user edit it, and adds it to a checklist.
 * Every piece of model or user text is written with textContent/value only.
 */
(function () {
    'use strict';

    var root = document.getElementById('mistake-log-root');
    if (!root) return;

    var POLL_MS = 2000;
    var GIVE_UP_MS = 90000;
    var THRESHOLD_LABELS = { numerical: 'Numerical threshold', qualitative: 'Qualitative' };
    var CONFIDENCE_LABELS = { high: 'High confidence', medium: 'Medium confidence', low: 'Low confidence' };

    // The server sends confidence as a 0 to 1 number.
    function confidenceLevel(n) {
        var value = typeof n === 'number' ? n : parseFloat(n);
        if (isNaN(value)) return null;
        if (value >= 0.75) return 'high';
        if (value >= 0.5) return 'medium';
        return 'low';
    }

    function fillConfidence(slot, n) {
        slot.textContent = '';
        var level = confidenceLevel(n);
        if (level) slot.appendChild(el('span', 'criterion-pill' + (level === 'high' ? ' criterion-pill--high' : ''), CONFIDENCE_LABELS[level]));
    }

    function parseAttr(name, fallback) {
        try {
            var value = JSON.parse(root.getAttribute(name));
            return value === null || value === undefined ? fallback : value;
        } catch (e) {
            return fallback;
        }
    }

    var checklists = parseAttr('data-kill-checklists', []);
    var defaultChecklistId = parseAttr('data-default-checklist-id', null);
    var manageUrl = root.getAttribute('data-manage-url');
    var usageUrl = root.getAttribute('data-usage-url');

    // One entry per mistake: { token, checklistId, timer }. A new token invalidates older polls.
    var runs = {};
    var nextToken = 1;

    // ---------------------------------------------------------------- DOM helpers

    function el(tag, className, text) {
        var node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined && text !== null) node.textContent = text;
        return node;
    }

    function icon(name) {
        var i = el('i', 'bi bi-' + name);
        i.setAttribute('aria-hidden', 'true');
        return i;
    }

    function button(label, className, onClick, iconName) {
        var b = el('button', className);
        b.type = 'button';
        if (iconName) b.appendChild(icon(iconName));
        b.appendChild(document.createTextNode((iconName ? ' ' : '') + label));
        b.addEventListener('click', onClick);
        return b;
    }

    function link(label, href, className) {
        var a = el('a', className, label);
        a.href = href;
        return a;
    }

    function safeInternalUrl(url, fallback) {
        return typeof url === 'string' && url.charAt(0) === '/' && url.charAt(1) !== '/' ? url : fallback;
    }

    function checklistById(id) {
        for (var i = 0; i < checklists.length; i++) {
            if (checklists[i].id === id) return checklists[i];
        }
        return null;
    }

    function panelFor(mistakeId) {
        return document.getElementById('criterion-panel-' + mistakeId);
    }

    function suggestButtons(mistakeId) {
        return document.querySelectorAll('.js-suggest-criterion[data-mistake-id="' + mistakeId + '"]');
    }

    function setBusy(mistakeId, busy) {
        var buttons = suggestButtons(mistakeId);
        for (var i = 0; i < buttons.length; i++) buttons[i].disabled = busy;
    }

    // Renders node into the mistake's live-region slot, then moves focus to the new panel's
    // heading (or to focusSelector). Pass focusSelector === false to leave focus alone.
    function show(mistakeId, node, focusSelector) {
        var panel = panelFor(mistakeId);
        if (!panel) return null;
        panel.textContent = '';
        panel.appendChild(node);
        if (focusSelector !== false) {
            var target = node.querySelector(focusSelector || '.criterion-panel-title, .criterion-success-title');
            if (target) target.focus();
        }
        return panel;
    }

    function focusSuggestButton(mistakeId) {
        var buttons = suggestButtons(mistakeId);
        for (var i = 0; i < buttons.length; i++) {
            if (buttons[i].offsetParent !== null) { buttons[i].focus(); return; }
        }
        if (buttons.length) buttons[0].focus();
    }

    function cancelRun(mistakeId) {
        var run = runs[mistakeId];
        if (run && run.timer) clearTimeout(run.timer);
        delete runs[mistakeId];
    }

    function dismiss(mistakeId) {
        cancelRun(mistakeId);
        var panel = panelFor(mistakeId);
        if (panel) panel.textContent = '';
        setBusy(mistakeId, false);
        focusSuggestButton(mistakeId);
    }

    // ---------------------------------------------------------------- panel shell

    function shell(modifier) {
        return el('section', 'criterion-panel' + (modifier ? ' criterion-panel--' + modifier : ''));
    }

    function header(title, subtitle, iconName, confidence) {
        var head = el('header', 'criterion-panel-header');
        var left = el('div', 'criterion-panel-heading');
        var iconWrap = el('span', 'criterion-panel-icon');
        iconWrap.appendChild(icon(iconName || 'lightbulb'));
        var text = el('div');
        var heading = el('h4', 'criterion-panel-title', title);
        heading.tabIndex = -1;
        text.appendChild(heading);
        if (subtitle) text.appendChild(el('p', 'criterion-panel-sub', subtitle));
        left.appendChild(iconWrap);
        left.appendChild(text);
        head.appendChild(left);
        if (confidence !== undefined) {
            var slot = el('span', 'criterion-pill-slot');
            fillConfidence(slot, confidence);
            head.appendChild(slot);
        }
        return head;
    }

    // ---------------------------------------------------------------- states

    function showAnalysing(mistakeId, checklistId) {
        var cl = checklistById(checklistId) || checklistById(defaultChecklistId);
        var box = shell('muted');
        var status = el('div', 'criterion-panel-status');
        status.setAttribute('role', 'status');
        var spinner = el('span', 'spinner-border spinner-border-sm');
        spinner.setAttribute('aria-hidden', 'true');
        status.appendChild(spinner);
        status.appendChild(el('p', null, 'Reading this mistake and your ' + (cl ? cl.name : 'kill checklist') + ' criteria…'));
        box.appendChild(status);
        box.appendChild(el('p', 'criterion-panel-hint', 'Usually 5 to 15 seconds.'));
        show(mistakeId, box, false);
    }

    function showFailed(mistakeId, message, checklistId) {
        setBusy(mistakeId, false);
        var box = shell('error');
        box.appendChild(header("Couldn't get a suggestion", null, 'exclamation-triangle'));
        box.appendChild(el('p', 'criterion-panel-message', message || 'The AI call failed or returned nothing usable.'));
        var row = el('div', 'criterion-panel-buttons');
        row.appendChild(button('Try again', 'action-btn primary', function () { start(mistakeId, checklistId); }, 'arrow-repeat'));
        row.appendChild(button('Close', 'action-btn', function () { dismiss(mistakeId); }));
        box.appendChild(row);
        show(mistakeId, box);
    }

    function showNoChecklist(mistakeId) {
        setBusy(mistakeId, false);
        var box = shell('muted');
        box.appendChild(header('Create a kill checklist first', null, 'list-check'));
        box.appendChild(el('p', 'criterion-panel-message',
            'A suggestion needs a checklist to compare with and to add to. With no default set, your first checklist is used.'));
        var row = el('div', 'criterion-panel-buttons');
        row.appendChild(link('Create a kill checklist', manageUrl || '#', 'action-btn primary'));
        row.appendChild(button('Close', 'action-btn', function () { dismiss(mistakeId); }));
        box.appendChild(row);
        show(mistakeId, box);
    }

    function showTokenLimit(mistakeId, message) {
        setBusy(mistakeId, false);
        var box = shell('muted');
        box.appendChild(header('Not enough AI tokens left this month', null, 'speedometer2'));
        box.appendChild(el('p', 'criterion-panel-message', message || 'Nothing was sent to the AI.'));
        var row = el('div', 'criterion-panel-buttons');
        row.appendChild(link('Settings › AI usage', usageUrl || '#', 'action-btn primary'));
        row.appendChild(button('Close', 'action-btn', function () { dismiss(mistakeId); }));
        box.appendChild(row);
        show(mistakeId, box);
    }

    function overlapText(overlap) {
        var number = overlap.position !== undefined ? overlap.position : overlap.order + 1;
        return '#' + number + ' “' + overlap.question + '”';
    }

    function showAlreadyCovered(mistakeId, result) {
        setBusy(mistakeId, false);
        var box = shell('muted');
        box.appendChild(header('Your checklist already asks this', null, 'check2-circle'));
        var message = el('p', 'criterion-panel-message');
        var overlap = result.overlap;
        if (overlap) {
            message.appendChild(el('strong', null, overlapText(overlap)));
            message.appendChild(document.createTextNode(' covers the same failure.' +
                (overlap.explanation ? ' ' + overlap.explanation : '')));
        } else {
            message.textContent = 'An existing criterion already covers the same failure.';
        }
        box.appendChild(message);
        var row = el('div', 'criterion-panel-buttons');
        var hasOptions = (result.suggestions || []).length > 0;
        row.appendChild(button(hasOptions ? 'Show other options' : 'Write my own', 'action-btn primary',
            function () { showReady(mistakeId, result, true); }));
        row.appendChild(button('Close', 'action-btn', function () { dismiss(mistakeId); }));
        box.appendChild(row);
        show(mistakeId, box);
    }

    function thresholdPills(container, suggestion) {
        container.textContent = '';
        var label = THRESHOLD_LABELS[suggestion.threshold_type];
        if (label) container.appendChild(el('span', 'criterion-pill', label));
    }

    function optionLabel(c) {
        return c.name + (c.is_default ? ' (default)' : '') + ' · ' + c.criteria_count + ' criteria';
    }

    function showReady(mistakeId, result, skipCoveredCheck, prefill) {
        if (result.already_covered && !skipCoveredCheck) {
            showAlreadyCovered(mistakeId, result);
            return;
        }
        setBusy(mistakeId, false);

        var suggestions = result.suggestions || [];
        var usedChecklist = result.checklist || {};
        var selectedIndex = prefill && prefill.index !== undefined ? prefill.index : 0;
        var current = suggestions[selectedIndex] || suggestions[0] || { question: '' };
        if (prefill) {
            current = Object.assign({}, current, {
                question: prefill.question, help_text: prefill.help_text, failure_reason: prefill.failure_reason,
            });
        }
        var uid = 'crit-' + mistakeId;

        var box = shell();
        box.appendChild(header('Suggested kill criterion',
            "From this mistake's root cause and lesson, checked against your " + (usedChecklist.name || 'kill') + ' criteria.',
            'lightbulb', current.confidence === undefined ? null : current.confidence));
        var pillSlot = box.firstChild.querySelector('.criterion-pill-slot');

        // Editable question
        var questionField = el('div', 'criterion-field');
        var qLabel = el('label', 'criterion-field-label', 'Criterion question');
        qLabel.htmlFor = uid + '-q';
        var textarea = el('textarea', 'form-control');
        textarea.id = uid + '-q';
        textarea.rows = 2;
        textarea.maxLength = 500;
        textarea.value = current.question || '';
        var pills = el('div', 'criterion-pills');
        thresholdPills(pills, current);
        var failureLine = el('p', 'criterion-failure');
        function renderFailure() {
            failureLine.textContent = '';
            failureLine.hidden = !current.failure_reason;
            if (current.failure_reason) {
                failureLine.appendChild(el('strong', null, 'Kills the idea when: '));
                failureLine.appendChild(document.createTextNode(current.failure_reason));
            }
        }
        renderFailure();
        questionField.appendChild(qLabel);
        questionField.appendChild(textarea);
        questionField.appendChild(failureLine);
        questionField.appendChild(pills);
        box.appendChild(questionField);

        // Why + overlap
        var grid = el('div', 'criterion-insight-grid');
        var why = el('div', 'criterion-insight');
        why.appendChild(el('h5', null, 'Why this would have caught it'));
        var whyText = el('p', null, current.why_it_catches || (suggestions.length ? '' : 'No suggestion to show. Write your own question above.'));
        why.appendChild(whyText);
        var overlapBox = el('div', 'criterion-insight');
        overlapBox.appendChild(el('h5', null, 'Overlap with your checklist'));
        var overlapP = el('p');
        if (result.overlap) {
            overlapP.appendChild(document.createTextNode('Closest existing criterion: '));
            overlapP.appendChild(el('strong', null, overlapText(result.overlap)));
            overlapP.appendChild(document.createTextNode(result.overlap.explanation ? ' ' + result.overlap.explanation : ''));
        } else {
            overlapP.textContent = 'Nothing similar on ' + (usedChecklist.name || 'your checklist') + '.';
        }
        overlapBox.appendChild(overlapP);
        var overlapNote = el('p', 'criterion-panel-hint');
        overlapNote.style.marginTop = '0.5rem';
        overlapBox.appendChild(overlapNote);
        grid.appendChild(why);
        grid.appendChild(overlapBox);
        box.appendChild(grid);

        // Other options
        if (suggestions.length > 1) {
            var fieldset = el('fieldset', 'criterion-options');
            fieldset.appendChild(el('legend', 'criterion-field-label', 'Other options'));
            suggestions.forEach(function (s, index) {
                var row = el('label', 'criterion-option');
                var radio = document.createElement('input');
                radio.type = 'radio';
                radio.name = uid + '-alt';
                radio.checked = index === selectedIndex;
                radio.addEventListener('change', function () {
                    current = s;
                    selectedIndex = index;
                    textarea.value = s.question || '';
                    whyText.textContent = s.why_it_catches || '';
                    thresholdPills(pills, s);
                    renderFailure();
                    fillConfidence(pillSlot, s.confidence);
                });
                var text = el('span', 'criterion-option-text');
                text.appendChild(document.createTextNode(s.question || ''));
                text.appendChild(el('span', 'criterion-option-meta', THRESHOLD_LABELS[s.threshold_type] || ''));
                row.appendChild(radio);
                row.appendChild(text);
                fieldset.appendChild(row);
            });
            fieldset.appendChild(el('p', 'criterion-panel-hint', 'Picking an option copies it into the question above, where you can still edit it.'));
            box.appendChild(fieldset);
        }

        // Target checklist + position
        var selects = el('div', 'criterion-select-grid');
        var targetField = el('div', 'criterion-field');
        var targetLabel = el('label', 'criterion-field-label', 'Add to');
        targetLabel.htmlFor = uid + '-target';
        var target = el('select', 'form-select');
        target.id = uid + '-target';
        checklists.forEach(function (c) {
            var opt = document.createElement('option');
            opt.value = String(c.id);
            opt.textContent = optionLabel(c);
            target.appendChild(opt);
        });
        if (usedChecklist.id !== undefined) target.value = String(usedChecklist.id);
        if (prefill && checklistById(prefill.checklist_id)) target.value = String(prefill.checklist_id);
        target.addEventListener('change', function () {
            var differs = Number(target.value) !== usedChecklist.id;
            var chosen = checklistById(Number(target.value));
            overlapNote.textContent = differs && chosen ? 'Overlap was checked against ' + (usedChecklist.name || 'the first checklist') + '.' : '';
        });
        targetField.appendChild(targetLabel);
        targetField.appendChild(target);

        var positionField = el('div', 'criterion-field');
        var posLabel = el('label', 'criterion-field-label', 'Position');
        posLabel.htmlFor = uid + '-pos';
        var position = el('select', 'form-select');
        position.id = uid + '-pos';
        [['last', 'Last'], ['first', 'First (checked earliest)']].forEach(function (pair) {
            var opt = document.createElement('option');
            opt.value = pair[0];
            opt.textContent = pair[1];
            position.appendChild(opt);
        });
        position.value = prefill && prefill.position === 'first' ? 'first' : 'last';
        positionField.appendChild(posLabel);
        positionField.appendChild(position);
        selects.appendChild(targetField);
        selects.appendChild(positionField);
        box.appendChild(selects);

        var errorLine = el('p', 'criterion-panel-message text-danger');
        errorLine.hidden = true;
        errorLine.setAttribute('role', 'alert');
        box.appendChild(errorLine);

        // Footer
        var footer = el('footer', 'criterion-panel-footer');
        footer.appendChild(el('span', 'criterion-panel-tokens',
            result.tokens_used ? 'Used about ' + formatTokens(result.tokens_used) + ' AI tokens' : ''));
        var buttons = el('div', 'criterion-panel-buttons');
        var dismissBtn = button('Dismiss', 'action-btn', function () { dismiss(mistakeId); });
        buttons.appendChild(dismissBtn);
        var addBtn = button('Add to checklist', 'action-btn primary', function () {
            var question = textarea.value.trim();
            if (!question) {
                errorLine.textContent = 'Write the question first.';
                errorLine.hidden = false;
                return;
            }
            errorLine.hidden = true;
            var payload = {
                checklist_id: Number(target.value),
                question: question,
                help_text: current.help_text || '',
                failure_reason: current.failure_reason || '',
                position: position.value,
            };
            var snapshot = Object.assign({ index: selectedIndex }, payload);
            addBtn.disabled = true;
            dismissBtn.disabled = true;
            addCriterion(mistakeId, payload, snapshot, function (message) {
                addBtn.disabled = false;
                dismissBtn.disabled = false;
                errorLine.textContent = message;
                errorLine.hidden = false;
            }, result);
        }, 'check2');
        buttons.appendChild(addBtn);
        footer.appendChild(buttons);
        box.appendChild(footer);

        show(mistakeId, box, 'textarea');
    }

    function formatTokens(n) {
        return n >= 1000 ? (Math.round(n / 100) / 10) + 'k' : String(n);
    }

    function showAdded(mistakeId, added, prefill, result) {
        var question = prefill.question;
        setBusy(mistakeId, false);
        var box = el('div', 'criterion-success');
        box.setAttribute('role', 'status');
        var text = el('div');
        text.appendChild(el('p', 'criterion-success-title',
            'Added to ' + added.checklist_name + ' as criterion #' + (added.position !== undefined ? added.position : added.order + 1)));
        text.firstChild.tabIndex = -1;
        text.appendChild(el('p', 'criterion-success-quote', '“' + question + '”'));
        var undoError = el('p', 'criterion-panel-message text-danger');
        undoError.setAttribute('role', 'alert');
        undoError.hidden = true;
        text.appendChild(undoError);
        var row = el('div', 'criterion-panel-buttons');
        var undo = button('Undo', 'action-btn', function () {
            undo.disabled = true;
            undoCriterion(mistakeId, added, prefill, result, function (message) {
                undo.disabled = false;
                undoError.textContent = message;
                undoError.hidden = false;
            });
        });
        row.appendChild(undo);
        row.appendChild(link('View checklist', safeInternalUrl(added.checklist_url, manageUrl || '#'), 'action-btn primary'));
        box.appendChild(text);
        box.appendChild(row);
        show(mistakeId, box);
    }

    // ---------------------------------------------------------------- chip

    function ensureChip(mistakeId) {
        if (document.getElementById('added-chip-' + mistakeId)) return;
        var panel = panelFor(mistakeId);
        var item = panel && panel.closest('.mistake-accordion-item');
        var badges = item && item.querySelector('.mistake-badges');
        if (!badges) return;
        var chip = el('span', 'mistake-criterion-chip');
        chip.id = 'added-chip-' + mistakeId;
        chip.dataset.createdHere = '1';
        chip.appendChild(icon('check-circle-fill'));
        chip.appendChild(document.createTextNode(' Kill criterion added'));
        badges.appendChild(chip);
    }

    function removeChipIfCreatedHere(mistakeId) {
        var chip = document.getElementById('added-chip-' + mistakeId);
        if (chip && chip.dataset.createdHere === '1') chip.remove();
    }

    // ---------------------------------------------------------------- network

    function requestJson(method, url, body) {
        var options = { method: method, headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin' };
        if (body !== undefined) options.body = JSON.stringify(body);
        return fetch(url, options).then(function (response) {
            if (response.status === 204) return { status: 204, data: {} };
            return response.json().catch(function () { return {}; }).then(function (data) {
                return { status: response.status, data: data || {} };
            });
        });
    }

    function start(mistakeId, checklistId) {
        cancelRun(mistakeId);
        var chosen = checklistId === undefined || checklistId === null ? defaultChecklistId : checklistId;
        var run = { token: nextToken++, checklistId: chosen, timer: null };
        runs[mistakeId] = run;
        setBusy(mistakeId, true);
        showAnalysing(mistakeId, chosen);

        requestJson('POST', '/learning/mistakes/' + mistakeId + '/suggest-criterion', { checklist_id: chosen })
            .then(function (res) {
                if (runs[mistakeId] !== run) return;
                if (res.status === 202 && res.data.task_id) {
                    run.startedAt = Date.now();
                    poll(mistakeId, run, res.data.task_id);
                } else if (res.status === 400 && res.data.error === 'no_checklist') {
                    cancelRun(mistakeId);
                    showNoChecklist(mistakeId);
                } else if (res.status === 429) {
                    cancelRun(mistakeId);
                    showTokenLimit(mistakeId, res.data.error);
                } else {
                    cancelRun(mistakeId);
                    showFailed(mistakeId, typeof res.data.error === 'string' ? res.data.error : null, chosen);
                }
            })
            .catch(function () {
                if (runs[mistakeId] !== run) return;
                cancelRun(mistakeId);
                showFailed(mistakeId, 'Network error. Check your connection and try again.', chosen);
            });
    }

    function poll(mistakeId, run, taskId) {
        run.timer = setTimeout(function () {
            if (runs[mistakeId] !== run) return;
            if (Date.now() - run.startedAt > GIVE_UP_MS) {
                cancelRun(mistakeId);
                showFailed(mistakeId, 'This is taking longer than expected. Try again in a moment.', run.checklistId);
                return;
            }
            requestJson('GET', '/learning/mistakes/suggest-criterion/' + encodeURIComponent(taskId))
                .then(function (res) {
                    if (runs[mistakeId] !== run) return;
                    var state = res.data.state;
                    if (res.status === 200 && state === 'COMPLETED' && res.data.result) {
                        cancelRun(mistakeId);
                        showReady(mistakeId, res.data.result);
                    } else if (res.status === 200 && state === 'FAILED') {
                        cancelRun(mistakeId);
                        showFailed(mistakeId, res.data.error, run.checklistId);
                    } else if (res.status === 404) {
                        cancelRun(mistakeId);
                        showFailed(mistakeId, null, run.checklistId);
                    } else {
                        poll(mistakeId, run, taskId);
                    }
                })
                .catch(function () {
                    if (runs[mistakeId] === run) poll(mistakeId, run, taskId);
                });
        }, POLL_MS);
    }

    // Add and Undo hold the mistake's run slot, so Suggest stays disabled and a response that
    // arrives after the run was replaced is dropped.
    function beginAction(mistakeId) {
        cancelRun(mistakeId);
        var run = { token: nextToken++, checklistId: null, timer: null };
        runs[mistakeId] = run;
        setBusy(mistakeId, true);
        return run;
    }

    function endAction(mistakeId, run) {
        if (runs[mistakeId] !== run) return false;
        cancelRun(mistakeId);
        setBusy(mistakeId, false);
        return true;
    }

    function adjustCount(checklistId, delta) {
        var cl = checklistById(checklistId);
        if (cl) cl.criteria_count = Math.max(0, (cl.criteria_count || 0) + delta);
    }

    function addCriterion(mistakeId, payload, prefill, onError, result) {
        var run = beginAction(mistakeId);
        requestJson('POST', '/learning/mistakes/' + mistakeId + '/criteria', payload)
            .then(function (res) {
                if (!endAction(mistakeId, run)) return;
                if (res.status === 201) {
                    adjustCount(payload.checklist_id, 1);
                    ensureChip(mistakeId);
                    showAdded(mistakeId, res.data, prefill, result);
                } else {
                    onError(typeof res.data.error === 'string' ? res.data.error : 'Could not add the criterion. Try again.');
                }
            })
            .catch(function () {
                if (endAction(mistakeId, run)) onError('Network error. Try again.');
            });
    }

    function undoCriterion(mistakeId, added, prefill, result, onError) {
        var run = beginAction(mistakeId);
        requestJson('DELETE', '/learning/mistakes/' + mistakeId + '/criteria/' + added.criterion_id)
            .then(function (res) {
                if (!endAction(mistakeId, run)) return;
                if (res.status === 204) {
                    adjustCount(added.checklist_id, -1);
                    removeChipIfCreatedHere(mistakeId);
                    showReady(mistakeId, result, true, prefill);
                } else {
                    onError(typeof res.data.error === 'string' ? res.data.error : 'Could not undo. Try again.');
                }
            })
            .catch(function () {
                if (endAction(mistakeId, run)) onError('Network error. Try again.');
            });
    }

    // ---------------------------------------------------------------- wiring

    document.addEventListener('click', function (event) {
        var btn = event.target.closest('.js-suggest-criterion');
        if (!btn || btn.disabled) return;
        if (runs[Number(btn.getAttribute('data-mistake-id'))]) return;
        start(Number(btn.getAttribute('data-mistake-id')), defaultChecklistId);
    });

    // Drop ?suggest_for so a reload does not bring the banner back.
    function clearSuggestParam() {
        try {
            var url = new URL(window.location.href);
            if (!url.searchParams.has('suggest_for')) return;
            url.searchParams.delete('suggest_for');
            window.history.replaceState(window.history.state, '', url.pathname + url.search + url.hash);
        } catch (e) { /* history API unavailable: nothing to clean */ }
    }

    var bannerDismiss = document.getElementById('mistake-banner-dismiss');
    var bannerSuggest = document.getElementById('mistake-banner-suggest');
    var banner = document.getElementById('mistake-suggest-banner');
    if (bannerDismiss && banner) {
        bannerDismiss.addEventListener('click', function () {
            banner.hidden = true;
            clearSuggestParam();
        });
    }
    if (bannerSuggest && banner) {
        bannerSuggest.addEventListener('click', function () {
            var id = Number(bannerSuggest.getAttribute('data-mistake-id'));
            banner.hidden = true;
            clearSuggestParam();
            if (runs[id]) return;
            openMistake(id);
            start(id, defaultChecklistId);
        });
    }

    function openMistake(mistakeId) {
        var collapse = document.getElementById('mistake-' + mistakeId);
        if (!collapse) return;
        if (window.bootstrap && window.bootstrap.Collapse) {
            window.bootstrap.Collapse.getOrCreateInstance(collapse, { toggle: false }).show();
        } else {
            collapse.classList.add('show');
        }
        collapse.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }

})();
