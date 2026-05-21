/**
 * DocumentAnnotations — point-pin and text-highlight annotations on PDF pages.
 *
 * Public API:
 *   DocumentAnnotations.init({ resourceId, companyId, companyName })
 *   DocumentAnnotations.toggleSidebar()
 *   DocumentAnnotations.enterAddMode()
 */
const DocumentAnnotations = (() => {
    // ----- State -----
    let annotations = [];
    let resourceId = null;
    let companyId = null;
    let companyName = '';
    let isAddMode = false;
    let sidebarOpen = false;
    let activePopover = null;
    let highlightActionBtn = null;
    let overlays = [];

    // ----- Init -----

    function init(config) {
        resourceId = config.resourceId;
        companyId = config.companyId;
        companyName = config.companyName || '';

        createOverlaysForAllPages();
        loadAnnotations();
        setupTextSelectionListener();

        var addBtn = document.getElementById('btn-add-annotation');
        if (addBtn) addBtn.addEventListener('click', function () {
            if (isAddMode) exitAddMode(); else enterAddMode();
        });
        var sidebarBtn = document.getElementById('btn-toggle-sidebar');
        if (sidebarBtn) sidebarBtn.addEventListener('click', toggleSidebar);

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                if (isAddMode) exitAddMode();
                hidePopover();
                hideHighlightAction();
            }
        });
    }

    // ----- API Layer -----

    function loadAnnotations() {
        fetch('/companies/api/resources/' + resourceId + '/annotations')
            .then(function (r) { return r.json(); })
            .then(function (result) {
                if (result.success) {
                    annotations = result.data.annotations;
                    renderAllAnnotations();
                    renderSidebar();
                    updateBadge();
                }
            })
            .catch(function (err) { console.error('Failed to load annotations:', err); });
    }

    function createAnnotationAPI(payload, cb) {
        fetch('/companies/api/resources/' + resourceId + '/annotations', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        })
            .then(function (r) { return r.json(); })
            .then(function (result) {
                if (result.success) {
                    annotations.push(result.data.annotation);
                    renderAllAnnotations();
                    renderSidebar();
                    updateBadge();
                    if (cb) cb(result.data.annotation);
                }
            })
            .catch(function (err) { console.error('Failed to create annotation:', err); });
    }

    function updateAnnotation(annotationId, content, scope, cb) {
        fetch('/companies/api/annotations/' + annotationId, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: content, scope: scope }),
        })
            .then(function (r) { return r.json(); })
            .then(function (result) {
                if (result.success) {
                    var updated = result.data.annotation;
                    for (var i = 0; i < annotations.length; i++) {
                        if (annotations[i].id === updated.id) { annotations[i] = updated; break; }
                    }
                    renderAllAnnotations();
                    renderSidebar();
                    if (cb) cb(updated);
                }
            })
            .catch(function (err) { console.error('Failed to update annotation:', err); });
    }

    function deleteAnnotation(annotationId, cb) {
        fetch('/companies/api/annotations/' + annotationId, { method: 'DELETE' })
            .then(function (r) { return r.json(); })
            .then(function (result) {
                if (result.success) {
                    annotations = annotations.filter(function (a) { return a.id !== annotationId; });
                    renderAllAnnotations();
                    renderSidebar();
                    updateBadge();
                    if (cb) cb();
                }
            })
            .catch(function (err) { console.error('Failed to delete annotation:', err); });
    }

    function sendToJournal(annotationId, cb) {
        fetch('/companies/api/annotations/' + annotationId + '/send-to-journal', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        })
            .then(function (r) { return r.json(); })
            .then(function (result) { if (cb) cb(result); })
            .catch(function (err) { console.error('Failed to send to journal:', err); });
    }

    // ----- Overlay & Rendering -----

    function createOverlaysForAllPages() {
        overlays = [];
        var wrappers = document.querySelectorAll('.pdf-page-canvas-wrapper');
        wrappers.forEach(function (wrapper) {
            var pageNum = parseInt(wrapper.dataset.pageNumber);
            // No permanent overlay — overlays are only created during add-mode
            // so the text layer remains fully accessible for selection.
            overlays.push({ pageNumber: pageNum, overlayEl: null, wrapperEl: wrapper });
        });
    }

    function renderAllAnnotations() {
        // Clear existing pins from wrappers
        overlays.forEach(function (o) {
            var pins = o.wrapperEl.querySelectorAll('.annotation-pin:not(.annotation-pin--new)');
            pins.forEach(function (p) { p.remove(); });
        });

        // Clear existing highlights
        document.querySelectorAll('.annotation-highlight').forEach(function (el) {
            // Unwrap highlighted spans back to normal text layer spans
            el.classList.remove('annotation-highlight');
            el.removeAttribute('data-annotation-id');
        });

        annotations.forEach(function (ann) {
            if (ann.annotation_type === 'highlight') {
                applyHighlight(ann);
            } else {
                var entry = overlays.find(function (o) { return o.pageNumber === ann.page_number; });
                if (entry && ann.x_percent != null && ann.y_percent != null) {
                    var pin = createPinElement(ann);
                    entry.wrapperEl.appendChild(pin);
                }
            }
        });
    }

    function createPinElement(annotation) {
        var pin = document.createElement('div');
        pin.className = 'annotation-pin';
        pin.dataset.annotationId = annotation.id;
        pin.style.left = annotation.x_percent + '%';
        pin.style.top = annotation.y_percent + '%';
        pin.title = truncate(annotation.content, 60);
        pin.addEventListener('click', function (e) {
            e.stopPropagation();
            showPopover(annotation, pin);
        });
        return pin;
    }

    // ----- Text Highlight -----

    function applyHighlight(annotation) {
        var entry = overlays.find(function (o) { return o.pageNumber === annotation.page_number; });
        if (!entry) return;

        var textLayer = entry.wrapperEl.querySelector('.textLayer');
        if (!textLayer) return;

        var anchorText = annotation.anchor_text;
        if (!anchorText) return;

        // Only use leaf spans (skip markedContent wrappers to avoid double-counting text)
        var allSpans = textLayer.querySelectorAll('span');
        var spans = [];
        allSpans.forEach(function (span) {
            if (!span.querySelector('span')) spans.push(span);
        });

        // Build concatenated text → span index mapping
        var fullText = '';
        var spanMap = []; // { span, startIdx, endIdx }
        spans.forEach(function (span) {
            var start = fullText.length;
            fullText += span.textContent;
            spanMap.push({ span: span, startIdx: start, endIdx: fullText.length });
        });

        // Find the anchor text in the concatenated page text
        var matchIdx = fullText.indexOf(anchorText);
        if (matchIdx === -1) {
            // Try normalized matching (collapse whitespace)
            var normalizedFull = fullText.replace(/\s+/g, ' ');
            var normalizedAnchor = anchorText.replace(/\s+/g, ' ');
            matchIdx = normalizedFull.indexOf(normalizedAnchor);
        }
        if (matchIdx === -1) return;

        var matchEnd = matchIdx + anchorText.length;

        // Mark all spans that overlap with the match
        spanMap.forEach(function (entry) {
            if (entry.endIdx > matchIdx && entry.startIdx < matchEnd) {
                entry.span.classList.add('annotation-highlight');
                entry.span.dataset.annotationId = annotation.id;
                entry.span.addEventListener('click', function (e) {
                    e.stopPropagation();
                    showPopoverForHighlight(annotation, entry.span);
                });
            }
        });
    }

    function setupTextSelectionListener() {
        var viewer = document.getElementById('pdf-viewer');
        if (!viewer) return;

        document.addEventListener('mouseup', function (e) {
            // Small delay to let the selection finalize
            setTimeout(function () { handleTextSelection(e); }, 10);
        });

        // Hide highlight action when clicking elsewhere
        document.addEventListener('mousedown', function (e) {
            if (highlightActionBtn && !highlightActionBtn.contains(e.target)) {
                hideHighlightAction();
            }
        });
    }

    function handleTextSelection() {
        var selection = window.getSelection();
        if (!selection || selection.isCollapsed || !selection.toString().trim()) {
            return;
        }

        var selectedText = selection.toString().trim();
        if (selectedText.length < 2) return;

        // Check if selection is within a text layer inside our viewer
        var anchorNode = selection.anchorNode;
        var textLayer = anchorNode ? anchorNode.parentElement.closest('.textLayer') : null;
        if (!textLayer) return;

        var wrapper = textLayer.closest('.pdf-page-canvas-wrapper');
        if (!wrapper) return;

        var pageNumber = parseInt(wrapper.dataset.pageNumber);

        // Show floating "Add Note" button near the selection
        var range = selection.getRangeAt(0);
        var rect = range.getBoundingClientRect();

        showHighlightAction(selectedText, pageNumber, rect);
    }

    function showHighlightAction(selectedText, pageNumber, selectionRect) {
        hideHighlightAction();

        var viewer = document.getElementById('pdf-viewer');
        var viewerRect = viewer.getBoundingClientRect();

        var btn = document.createElement('div');
        btn.className = 'highlight-action-btn';
        btn.innerHTML = '<i class="bi bi-chat-quote"></i> Add Note';

        var top = selectionRect.bottom - viewerRect.top + viewer.scrollTop + 4;
        var left = selectionRect.left - viewerRect.left + viewer.scrollLeft;

        if (left + 140 > viewer.clientWidth) {
            left = viewer.clientWidth - 150;
        }
        if (left < 8) left = 8;

        btn.style.top = top + 'px';
        btn.style.left = left + 'px';

        btn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            hideHighlightAction();
            showHighlightCreationPopover(selectedText, pageNumber, selectionRect);
            window.getSelection().removeAllRanges();
        });

        viewer.appendChild(btn);
        highlightActionBtn = btn;
    }

    function hideHighlightAction() {
        if (highlightActionBtn) {
            highlightActionBtn.remove();
            highlightActionBtn = null;
        }
    }

    function showHighlightCreationPopover(anchorText, pageNumber, selectionRect) {
        hidePopover();

        var viewer = document.getElementById('pdf-viewer');
        var viewerRect = viewer.getBoundingClientRect();

        var popover = buildPopoverEl({
            content: '',
            scope: 'company',
            isNew: true,
            anchorText: anchorText,
            onSave: function (content, scope) {
                if (!content.trim()) return;
                createAnnotationAPI({
                    annotation_type: 'highlight',
                    page_number: pageNumber,
                    anchor_text: anchorText,
                    content: content.trim(),
                    scope: scope,
                }, function () {
                    hidePopover();
                });
            },
            onCancel: function () {
                hidePopover();
            },
        });

        // Position below the selection
        var top = selectionRect.bottom - viewerRect.top + viewer.scrollTop + 8;
        var left = selectionRect.left - viewerRect.left + viewer.scrollLeft - 10;

        var popoverWidth = 320;
        if (left + popoverWidth > viewer.clientWidth - 16) {
            left = viewer.clientWidth - popoverWidth - 16;
        }
        if (left < 8) left = 8;

        viewer.appendChild(popover);
        popover.style.top = top + 'px';
        popover.style.left = left + 'px';
        activePopover = popover;

        var ta = popover.querySelector('textarea');
        if (ta) setTimeout(function () { ta.focus(); }, 50);
    }

    function showPopoverForHighlight(annotation, spanEl) {
        hidePopover();

        var viewer = document.getElementById('pdf-viewer');
        var viewerRect = viewer.getBoundingClientRect();
        var spanRect = spanEl.getBoundingClientRect();

        var popover = buildPopoverEl({
            content: annotation.content,
            scope: annotation.scope,
            isNew: false,
            anchorText: annotation.anchor_text,
            annotation: annotation,
            onSave: function (content, scope) {
                if (!content.trim()) return;
                updateAnnotation(annotation.id, content.trim(), scope, function () {
                    hidePopover();
                });
            },
            onCancel: function () {
                hidePopover();
            },
            onDelete: function () {
                if (confirm('Delete this note?')) {
                    deleteAnnotation(annotation.id, function () {
                        hidePopover();
                    });
                }
            },
            onSendToJournal: function (statusEl) {
                sendToJournal(annotation.id, function (result) {
                    if (result && result.success) {
                        statusEl.textContent = 'Sent to journal';
                        statusEl.style.color = '#198754';
                    } else {
                        statusEl.textContent = 'Failed to send';
                        statusEl.style.color = '#dc3545';
                    }
                });
            },
        });

        var top = spanRect.bottom - viewerRect.top + viewer.scrollTop + 8;
        var left = spanRect.left - viewerRect.left + viewer.scrollLeft - 10;

        var popoverWidth = 320;
        if (left + popoverWidth > viewer.clientWidth - 16) {
            left = viewer.clientWidth - popoverWidth - 16;
        }
        if (left < 8) left = 8;

        viewer.appendChild(popover);
        popover.style.top = top + 'px';
        popover.style.left = left + 'px';
        activePopover = popover;
    }

    // ----- Add Mode (pin) -----

    function enterAddMode() {
        isAddMode = true;
        // Create temporary overlays on top of each page for click-catching
        overlays.forEach(function (o) {
            var overlay = document.createElement('div');
            overlay.className = 'pdf-page-overlay add-mode';
            overlay.dataset.pageNumber = o.pageNumber;
            overlay.addEventListener('click', function (e) {
                handleOverlayClick(e, o.pageNumber, overlay);
            });
            o.wrapperEl.appendChild(overlay);
            o.overlayEl = overlay;
        });
        var btn = document.getElementById('btn-add-annotation');
        if (btn) btn.classList.add('active');
    }

    function exitAddMode() {
        isAddMode = false;
        // Remove temporary overlays so text layer is fully accessible
        overlays.forEach(function (o) {
            if (o.overlayEl) {
                o.overlayEl.remove();
                o.overlayEl = null;
            }
        });
        var btn = document.getElementById('btn-add-annotation');
        if (btn) btn.classList.remove('active');
        var temp = document.querySelector('.annotation-pin--new');
        if (temp) temp.remove();
    }

    function handleOverlayClick(e, pageNumber, overlayEl) {
        if (!isAddMode) return;

        var rect = overlayEl.getBoundingClientRect();
        var xPercent = ((e.clientX - rect.left) / rect.width) * 100;
        var yPercent = ((e.clientY - rect.top) / rect.height) * 100;

        xPercent = Math.max(0, Math.min(100, xPercent));
        yPercent = Math.max(0, Math.min(100, yPercent));

        // Find the wrapper for this page before exiting add-mode (which removes overlays)
        var entry = overlays.find(function (o) { return o.pageNumber === pageNumber; });
        var wrapperEl = entry ? entry.wrapperEl : overlayEl.parentElement;

        exitAddMode();

        var tempPin = document.createElement('div');
        tempPin.className = 'annotation-pin annotation-pin--new';
        tempPin.style.left = xPercent + '%';
        tempPin.style.top = yPercent + '%';
        wrapperEl.appendChild(tempPin);

        showCreationPopover(pageNumber, xPercent, yPercent, tempPin, wrapperEl);
    }

    // ----- Popover -----

    function showCreationPopover(pageNumber, xPercent, yPercent, tempPin, overlayEl) {
        hidePopover();

        var popover = buildPopoverEl({
            content: '',
            scope: 'company',
            isNew: true,
            onSave: function (content, scope) {
                if (!content.trim()) return;
                createAnnotationAPI({
                    annotation_type: 'pin',
                    page_number: pageNumber,
                    x_percent: xPercent,
                    y_percent: yPercent,
                    content: content.trim(),
                    scope: scope,
                }, function () {
                    tempPin.remove();
                    hidePopover();
                });
            },
            onCancel: function () {
                tempPin.remove();
                hidePopover();
            },
        });

        positionPopover(popover, tempPin, overlayEl);
        activePopover = popover;

        var ta = popover.querySelector('textarea');
        if (ta) setTimeout(function () { ta.focus(); }, 50);
    }

    function showPopover(annotation, pinEl) {
        hidePopover();

        var overlayEl = pinEl.parentElement;
        var popover = buildPopoverEl({
            content: annotation.content,
            scope: annotation.scope,
            isNew: false,
            anchorText: annotation.anchor_text,
            annotation: annotation,
            onSave: function (content, scope) {
                if (!content.trim()) return;
                updateAnnotation(annotation.id, content.trim(), scope, function () {
                    hidePopover();
                });
            },
            onCancel: function () {
                hidePopover();
            },
            onDelete: function () {
                if (confirm('Delete this note?')) {
                    deleteAnnotation(annotation.id, function () {
                        hidePopover();
                    });
                }
            },
            onSendToJournal: function (statusEl) {
                sendToJournal(annotation.id, function (result) {
                    if (result && result.success) {
                        statusEl.textContent = 'Sent to journal';
                        statusEl.style.color = '#198754';
                    } else {
                        statusEl.textContent = 'Failed to send';
                        statusEl.style.color = '#dc3545';
                    }
                });
            },
        });

        positionPopover(popover, pinEl, overlayEl);
        activePopover = popover;

        pinEl.classList.add('active');
    }

    function hidePopover() {
        if (activePopover) {
            activePopover.remove();
            activePopover = null;
        }
        document.querySelectorAll('.annotation-pin.active').forEach(function (p) {
            p.classList.remove('active');
        });
    }

    function buildPopoverEl(opts) {
        var div = document.createElement('div');
        div.className = 'annotation-popover';

        // Show quoted text for highlight annotations
        if (opts.anchorText) {
            var quoteBlock = document.createElement('div');
            quoteBlock.className = 'mb-2';
            quoteBlock.style.cssText = 'font-size:0.8rem;color:#555;border-left:3px solid #fbc02d;padding:0.375rem 0.5rem;background:#fffde7;border-radius:0 0.25rem 0.25rem 0;max-height:80px;overflow-y:auto;';
            quoteBlock.textContent = opts.anchorText.length > 200
                ? opts.anchorText.substring(0, 200) + '...'
                : opts.anchorText;
            div.appendChild(quoteBlock);
        }

        var ta = document.createElement('textarea');
        ta.placeholder = opts.anchorText ? 'Add your comment...' : 'Write your note...';
        ta.value = opts.content || '';
        div.appendChild(ta);

        // Scope dropdown
        var scopeRow = document.createElement('div');
        scopeRow.className = 'd-flex align-items-center gap-2 mt-2';

        var scopeLabel = document.createElement('small');
        scopeLabel.className = 'text-muted';
        scopeLabel.textContent = 'Scope:';
        scopeRow.appendChild(scopeLabel);

        var sel = document.createElement('select');
        sel.className = 'form-select form-select-sm';
        sel.style.width = 'auto';
        var scopeOptions = [
            { value: 'company', label: companyName || 'Company' },
            { value: 'sector', label: 'Sector' },
            { value: 'general', label: 'General' },
        ];
        scopeOptions.forEach(function (o) {
            var opt = document.createElement('option');
            opt.value = o.value;
            opt.textContent = o.label;
            if (o.value === (opts.scope || 'company')) opt.selected = true;
            sel.appendChild(opt);
        });
        scopeRow.appendChild(sel);
        div.appendChild(scopeRow);

        // Actions
        var actions = document.createElement('div');
        actions.className = 'popover-actions';

        var saveBtn = document.createElement('button');
        saveBtn.className = 'btn btn-sm btn-primary';
        saveBtn.textContent = 'Save';
        saveBtn.addEventListener('click', function () {
            opts.onSave(ta.value, sel.value);
        });
        actions.appendChild(saveBtn);

        var cancelBtn = document.createElement('button');
        cancelBtn.className = 'btn btn-sm btn-outline-secondary';
        cancelBtn.textContent = 'Cancel';
        cancelBtn.addEventListener('click', opts.onCancel);
        actions.appendChild(cancelBtn);

        if (!opts.isNew) {
            var rightActions = document.createElement('div');
            rightActions.className = 'popover-actions-right';

            var journalBtn = document.createElement('button');
            journalBtn.className = 'btn btn-sm btn-outline-success';
            journalBtn.innerHTML = '<i class="bi bi-journal-arrow-up me-1"></i>Journal';

            var statusEl = document.createElement('span');
            statusEl.className = 'popover-meta';
            statusEl.style.display = 'inline';

            journalBtn.addEventListener('click', function () {
                journalBtn.disabled = true;
                opts.onSendToJournal(statusEl);
            });
            rightActions.appendChild(journalBtn);

            var delBtn = document.createElement('button');
            delBtn.className = 'btn btn-sm btn-outline-danger';
            delBtn.innerHTML = '<i class="bi bi-trash"></i>';
            delBtn.title = 'Delete note';
            delBtn.addEventListener('click', opts.onDelete);
            rightActions.appendChild(delBtn);

            actions.appendChild(rightActions);
            div.appendChild(actions);
            div.appendChild(statusEl);
        } else {
            div.appendChild(actions);
        }

        ta.addEventListener('keydown', function (e) {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                e.preventDefault();
                opts.onSave(ta.value, sel.value);
            }
        });

        return div;
    }

    function positionPopover(popover, anchorEl, overlayEl) {
        var viewer = document.getElementById('pdf-viewer');
        viewer.appendChild(popover);

        var viewerRect = viewer.getBoundingClientRect();
        var anchorRect = anchorEl.getBoundingClientRect();

        var top = anchorRect.bottom - viewerRect.top + viewer.scrollTop + 8;
        var left = anchorRect.left - viewerRect.left + viewer.scrollLeft - 10;

        var popoverWidth = 320;
        if (left + popoverWidth > viewer.clientWidth - 16) {
            left = viewer.clientWidth - popoverWidth - 16;
        }
        if (left < 8) left = 8;

        popover.style.top = top + 'px';
        popover.style.left = left + 'px';
    }

    // ----- Sidebar -----

    function toggleSidebar() {
        sidebarOpen = !sidebarOpen;
        var sidebar = document.getElementById('annotation-sidebar');
        if (sidebar) sidebar.classList.toggle('open', sidebarOpen);
        var btn = document.getElementById('btn-toggle-sidebar');
        if (btn) btn.classList.toggle('active', sidebarOpen);
    }

    function renderSidebar() {
        var list = document.getElementById('annotation-sidebar-list');
        if (!list) return;

        if (annotations.length === 0) {
            list.innerHTML = '<div class="annotation-sidebar-empty">' +
                '<i class="bi bi-highlighter me-1"></i> No notes yet.<br>' +
                '<small>Select text on the PDF to highlight, or use "Add Note" for pins.</small></div>';
            return;
        }

        var pages = {};
        annotations.forEach(function (a) {
            if (!pages[a.page_number]) pages[a.page_number] = [];
            pages[a.page_number].push(a);
        });

        var html = '';
        var pageNums = Object.keys(pages).sort(function (a, b) { return a - b; });
        pageNums.forEach(function (pn) {
            html += '<div class="annotation-sidebar-group-label">Page ' + pn + '</div>';
            pages[pn].forEach(function (a) {
                var date = a.created_at ? new Date(a.created_at).toLocaleDateString() : '';
                var icon = a.annotation_type === 'highlight'
                    ? '<i class="bi bi-highlighter text-warning me-1"></i>'
                    : '<i class="bi bi-pin-angle text-danger me-1"></i>';
                var preview = a.annotation_type === 'highlight' && a.anchor_text
                    ? '<div class="sidebar-item-quote">' + icon + escapeHtml(truncate(a.anchor_text, 60)) + '</div>'
                    : '';
                html += '<div class="annotation-sidebar-item" data-annotation-id="' + a.id + '" data-page="' + a.page_number + '">' +
                    preview +
                    '<div class="sidebar-item-content">' + (a.annotation_type !== 'highlight' ? icon : '') + escapeHtml(a.content) + '</div>' +
                    '<div class="sidebar-item-meta">' +
                    '<span>' + date + '</span>' +
                    '<span class="badge bg-light text-dark border">' + escapeHtml(a.scope) + '</span>' +
                    '</div></div>';
            });
        });

        list.innerHTML = html;

        list.querySelectorAll('.annotation-sidebar-item').forEach(function (item) {
            item.addEventListener('click', function () {
                var annId = parseInt(this.dataset.annotationId);
                var pageNum = parseInt(this.dataset.page);
                scrollToAnnotation(pageNum, annId);
            });
        });
    }

    function scrollToAnnotation(pageNumber, annotationId) {
        var entry = overlays.find(function (o) { return o.pageNumber === pageNumber; });
        if (!entry) return;

        var scrollTarget = entry.wrapperEl; // fallback to page wrapper

        if (annotationId) {
            // Scroll to the actual pin or highlight element for precision
            var pin = entry.wrapperEl.querySelector('.annotation-pin[data-annotation-id="' + annotationId + '"]');
            if (pin) {
                scrollTarget = pin;
            } else {
                var span = entry.wrapperEl.querySelector('.annotation-highlight[data-annotation-id="' + annotationId + '"]');
                if (span) scrollTarget = span;
            }
        }

        scrollTarget.scrollIntoView({ behavior: 'smooth', block: 'center' });

        // Highlight after a short delay to let smooth scroll settle
        if (annotationId) {
            setTimeout(function () {
                var pin = entry.wrapperEl.querySelector('.annotation-pin[data-annotation-id="' + annotationId + '"]');
                if (pin) {
                    pin.classList.add('highlight');
                    setTimeout(function () { pin.classList.remove('highlight'); }, 1000);
                }

                var spans = entry.wrapperEl.querySelectorAll('.annotation-highlight[data-annotation-id="' + annotationId + '"]');
                spans.forEach(function (s) {
                    s.style.transition = 'background-color 0.3s';
                    s.style.backgroundColor = 'rgba(255, 235, 59, 0.8)';
                    setTimeout(function () { s.style.backgroundColor = ''; }, 1000);
                });
            }, 400);
        }
    }

    function updateBadge() {
        var badge = document.getElementById('annotation-count-badge');
        if (!badge) return;
        if (annotations.length > 0) {
            badge.textContent = annotations.length;
            badge.style.display = 'inline';
        } else {
            badge.style.display = 'none';
        }
    }

    // ----- Utilities -----

    function escapeHtml(text) {
        if (!text) return '';
        var d = document.createElement('div');
        d.textContent = text;
        return d.innerHTML;
    }

    function truncate(text, maxLen) {
        if (!text) return '';
        return text.length > maxLen ? text.substring(0, maxLen) + '...' : text;
    }

    return { init: init, toggleSidebar: toggleSidebar, enterAddMode: enterAddMode };
})();
