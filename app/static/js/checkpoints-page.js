// Checkpoints page (portfolio/checkpoint_reminders.html): resolve a checkpoint
// (Met / Not met), Hold anyway, Still valid, the tab URL sync and the "positions with no
// issues" toggle. Every successful action reloads the page so the server
// stays the single source of truth for what needs action.
(function () {
    var root = document.querySelector('.checkpoints-page');
    if (!root) return;

    function notify(message) {
        if (window.showToast) window.showToast(message, 'error');
    }

    // A login redirect or server error page is HTML, not JSON
    function readJson(r) {
        var isJson = (r.headers.get('Content-Type') || '').indexOf('application/json') !== -1;
        if (!isJson) {
            throw new Error(r.redirected ? 'Your session expired. Reload the page and sign in.' : 'Something went wrong. Try again.');
        }
        return r.json();
    }

    function postJson(url, body) {
        return fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        }).then(readJson).then(function (data) {
            if (!data || data.success === false) {
                throw new Error((data && data.error) || 'Something went wrong. Try again.');
            }
            return data;
        });
    }

    // Run the request(s); reload on success, toast and re-enable on failure
    function act(buttons, request) {
        buttons.forEach(function (b) { b.disabled = true; });
        return request().then(function () {
            window.location.reload();
        }).catch(function (err) {
            notify(err && err.message ? err.message : 'Something went wrong. Try again.');
            buttons.forEach(function (b) { b.disabled = false; });
        });
    }

    // Re-post every rule; reload if any succeeded (re-stamping is harmless)
    function stillValid(button) {
        button.disabled = true;
        var urls;
        try {
            urls = JSON.parse(button.dataset.reviewUrls || '[]');
        } catch (err) {
            notify('Something went wrong. Try again.');
            button.disabled = false;
            return;
        }
        Promise.allSettled(urls.map(function (u) { return postJson(u, {}); })).then(function (results) {
            var failed = results.filter(function (r) { return r.status === 'rejected'; });
            if (failed.length < results.length || !results.length) {
                window.location.reload();
                return;
            }
            notify(failed[0].reason && failed[0].reason.message ? failed[0].reason.message : 'Something went wrong. Try again.');
            button.disabled = false;
        });
    }

    function closeHold(form) {
        form.hidden = true;
        form.reset();
        var opener = root.querySelector('.cp-hold-open[aria-controls="' + form.id + '"]');
        if (opener) {
            opener.setAttribute('aria-expanded', 'false');
            opener.focus();
        }
    }

    function openHold(button) {
        var form = document.getElementById(button.getAttribute('aria-controls'));
        if (!form) return;
        var open = form.hidden;
        form.hidden = !open;
        button.setAttribute('aria-expanded', open ? 'true' : 'false');
        if (open) form.querySelector('.cp-hold-reason').focus();
    }

    function toggleHealthy(button) {
        var panel = document.getElementById(button.getAttribute('aria-controls'));
        if (!panel) return;
        if (!button.dataset.showLabel) button.dataset.showLabel = button.textContent.trim();
        var show = panel.hidden;
        panel.hidden = !show;
        button.setAttribute('aria-expanded', show ? 'true' : 'false');
        button.textContent = show ? 'Hide positions with no issues' : button.dataset.showLabel;
    }

    root.addEventListener('click', function (e) {
        var status = e.target.closest('.cp-status-btn');
        if (status) {
            var siblings = Array.prototype.filter.call(root.querySelectorAll('.cp-status-btn'), function (b) {
                return b.dataset.statusUrl === status.dataset.statusUrl;
            });
            act(siblings, function () {
                return postJson(status.dataset.statusUrl, { status: status.dataset.status });
            });
            return;
        }
        var still = e.target.closest('.cp-still-valid');
        if (still) {
            stillValid(still);
            return;
        }
        var hold = e.target.closest('.cp-hold-open');
        if (hold) { openHold(hold); return; }
        var cancel = e.target.closest('.cp-hold-cancel');
        if (cancel) { closeHold(cancel.closest('.cp-hold-form')); return; }
        var healthy = e.target.closest('.cp-healthy-toggle');
        if (healthy) toggleHealthy(healthy);
    });

    root.addEventListener('submit', function (e) {
        var form = e.target.closest('.cp-hold-form');
        if (!form) return;
        e.preventDefault();
        var textarea = form.querySelector('.cp-hold-reason');
        var reason = textarea.value.trim();
        if (!reason && form.dataset.reasonRequired === 'true') {
            textarea.focus();
            return;
        }
        var controls = Array.prototype.slice.call(form.querySelectorAll('button'));
        act(controls, function () {
            return postJson(form.dataset.holdUrl, { reason: reason });
        });
    });

    // Keep the chosen tab in the URL so a reload or a shared link lands on it
    root.addEventListener('shown.bs.tab', function (e) {
        var tab = e.target.dataset.tab;
        if (!tab) return;
        var params = new URLSearchParams(window.location.search);
        params.set('tab', tab);
        window.history.replaceState(null, '', window.location.pathname + '?' + params.toString() + (window.location.hash || ''));
    });

    root.addEventListener('keydown', function (e) {
        if (e.key !== 'Escape') return;
        var form = e.target.closest('.cp-hold-form');
        if (form) closeHold(form);
    });
})();
