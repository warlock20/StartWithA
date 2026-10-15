// Findings editor (partials/_findings_editor.html): add / delete red flags,
// green flags and must-exit criteria. Each finding has a signal; the signal
// field suggests the user's existing signals and accepts any new one. Long
// details are clamped to a few lines and open in full in the detail card.
(function () {
    var LONG_TEXT_CHARS = 150;
    var LONG_TEXT_LINES = 3;

    // Clamp a long finding and make it open the detail card
    function markLong(textEl) {
        var text = textEl.textContent;
        if (text.length <= LONG_TEXT_CHARS && text.split('\n').length <= LONG_TEXT_LINES) return;
        textEl.classList.add('is-long', 'detail-trigger');
        textEl.dataset.detailId = textEl.closest('li').dataset.findingId;
        textEl.tabIndex = 0;
        textEl.setAttribute('role', 'button');
        textEl.setAttribute('aria-expanded', 'false');
    }

    function notify(message, type) {
        if (window.showToast) window.showToast(message, type);
    }

    // A login redirect or server error page is HTML, not JSON
    function readJson(r, fallback) {
        var isJson = (r.headers.get('Content-Type') || '').indexOf('application/json') !== -1;
        if (!isJson) {
            throw new Error(r.redirected ? 'Your session expired. Reload the page and sign in.' : fallback);
        }
        return r.json();
    }

    function findingItem(finding) {
        var li = document.createElement('li');
        li.dataset.findingId = finding.id;
        var body = document.createElement('div');
        body.className = 'finding-body';
        var meta = document.createElement('div');
        meta.className = 'finding-meta';
        var signal = document.createElement('span');
        signal.className = 'finding-signal';
        signal.textContent = finding.signal;
        var date = document.createElement('span');
        date.className = 'finding-date';
        date.textContent = finding.date;
        meta.append(signal, date);
        var text = document.createElement('span');
        text.className = 'finding-text';
        text.textContent = finding.text;
        body.append(meta, text);
        li.append(body);
        markLong(text);
        var del = document.createElement('button');
        del.type = 'button';
        del.className = 'finding-delete';
        del.title = 'Delete';
        del.setAttribute('aria-label', 'Delete');
        del.innerHTML = '<i class="bi bi-x"></i>';
        li.append(del);
        return li;
    }

    function signalLabel(s) {
        var parts = [];
        if (s.red_flag) parts.push(s.red_flag + ' red');
        if (s.green_flag) parts.push(s.green_flag + ' green');
        if (s.must_exit) parts.push(s.must_exit + ' must exit');
        parts.push(s.companies + (s.companies === 1 ? ' company' : ' companies'));
        return parts.join(' · ');
    }

    function init(grid) {
        var baseUrl = grid.dataset.findingsUrl;
        var datalist = grid.querySelector('#finding-signals');
        var signalsLoaded = false;
        // Stacked sidebars show only the latest few; the link shows the total
        var limit = parseInt(grid.dataset.limit, 10) || 0;
        var totalEl = grid.parentNode.querySelector('.findings-total');

        function addToTotal(delta) {
            if (totalEl) totalEl.textContent = parseInt(totalEl.textContent, 10) + delta;
        }

        grid.querySelectorAll('.finding-text').forEach(markLong);
        if (window.initDetailCard) {
            window.initDetailCard({
                container: grid,
                label: 'Finding',
                lookup: function (id) {
                    var li = grid.querySelector('li[data-finding-id="' + id + '"]');
                    return li && {
                        signal: li.querySelector('.finding-signal').textContent,
                        text: li.querySelector('.finding-text').textContent
                    };
                },
                sections: [
                    { key: 'signal', label: 'Signal' },
                    { key: 'text', label: 'Details' }
                ]
            });
        }

        // All of the user's signals, loaded once; the browser filters as you type
        function loadSignals() {
            if (signalsLoaded) return;
            signalsLoaded = true;
            fetch(grid.dataset.signalsUrl + '?limit=200')
                .then(function (r) { return readJson(r, 'Could not load signals'); })
                .then(function (data) {
                    datalist.replaceChildren.apply(datalist, (data.signals || []).map(function (s) {
                        var option = document.createElement('option');
                        option.value = s.signal;
                        option.label = signalLabel(s);
                        return option;
                    }));
                })
                .catch(function () { signalsLoaded = false; });
        }

        function rememberSignal(name) {
            var known = Array.prototype.some.call(datalist.options, function (o) { return o.value === name; });
            if (known || name === 'Default') return;
            var option = document.createElement('option');
            option.value = name;
            datalist.appendChild(option);
        }

        function openForm(col) {
            var form = col.querySelector('.finding-add-form');
            form.hidden = false;
            loadSignals();
            form.querySelector('.finding-signal-input').focus();
        }

        function closeForm(form) {
            form.reset();
            form.hidden = true;
        }

        grid.addEventListener('click', function (e) {
            var toggle = e.target.closest('.finding-add-toggle');
            if (toggle) {
                var col = toggle.closest('[data-finding-type]');
                var form = col.querySelector('.finding-add-form');
                if (form.hidden) openForm(col); else closeForm(form);
                return;
            }

            var cancel = e.target.closest('.finding-add-cancel');
            if (cancel) {
                closeForm(cancel.closest('.finding-add-form'));
                return;
            }

            var del = e.target.closest('.finding-delete');
            if (!del) return;
            var li = del.closest('li');
            if (!confirm('Delete this finding?')) return;
            fetch(baseUrl + '/' + li.dataset.findingId, { method: 'DELETE' })
                .then(function (r) { return readJson(r, 'Could not delete'); })
                .then(function (data) {
                    if (!data.success) throw new Error(data.error || 'Could not delete');
                    li.remove();
                    addToTotal(-1);
                })
                .catch(function (err) { notify(err.message, 'error'); });
        });

        grid.addEventListener('keydown', function (e) {
            var form = e.target.closest('.finding-add-form');
            if (!form) return;
            if (e.key === 'Escape') closeForm(form);
            // Ctrl/Cmd+Enter saves from the details box
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                form.requestSubmit();
            }
        });

        grid.addEventListener('submit', function (e) {
            var form = e.target.closest('.finding-add-form');
            if (!form) return;
            e.preventDefault();
            var col = form.closest('[data-finding-type]');
            var signal = form.querySelector('.finding-signal-input').value.trim();
            var text = form.querySelector('.finding-add-input').value.trim();
            if (!text) {
                form.querySelector('.finding-add-input').focus();
                return;
            }
            var button = form.querySelector('button[type="submit"]');
            button.disabled = true;
            fetch(baseUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type: col.dataset.findingType, signal: signal, text: text })
            })
                .then(function (r) { return readJson(r, 'Could not save'); })
                .then(function (data) {
                    if (!data.success) throw new Error(data.error || 'Could not save');
                    var list = col.querySelector('.findings-list');
                    list.appendChild(findingItem(data.finding));
                    if (limit && list.children.length > limit) list.firstElementChild.remove();
                    addToTotal(1);
                    rememberSignal(data.finding.signal);
                    closeForm(form);
                })
                .catch(function (err) { notify(err.message, 'error'); })
                .finally(function () { button.disabled = false; });
        });
    }

    document.querySelectorAll('.findings-editable[data-findings-url]').forEach(init);
})();
