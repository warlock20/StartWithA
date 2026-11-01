/*
 * Settings → AI → My companion knowledge.
 *
 * Re-index now queues the user's index run, then polls the status endpoint
 * while it is queued or running and reloads the page when it ends, so the
 * counts and last-run line come from the server. A page opened while a run is
 * in progress polls too.
 */
(function () {
    const panel = document.getElementById('companion-knowledge');
    if (!panel) return;

    const button = panel.querySelector('[data-knowledge-reindex]');
    const message = panel.querySelector('[data-knowledge-message]');
    const chip = panel.querySelector('[data-knowledge-chip]');
    const POLL_MS = 3000;
    const MAX_POLLS = 200;  // 10 minutes
    const LABELS = { pending: 'Queued', running: 'Indexing' };
    let polls = 0;

    function show(text) {
        if (message) message.textContent = text;
    }

    function inProgress(status) {
        return status === 'pending' || status === 'running';
    }

    function setRunning(status) {
        if (button) button.disabled = true;
        if (chip) chip.textContent = LABELS[status];
        show(`${LABELS[status]}…`);
    }

    function poll() {
        fetch(panel.dataset.statusUrl, { headers: { Accept: 'application/json' } })
            .then((response) => (response.ok ? response.json() : Promise.reject(response.status)))
            .then((status) => {
                const run = status.last_run;
                if (!run || !inProgress(run.status)) {
                    window.location.reload();
                } else if (++polls < MAX_POLLS) {
                    setRunning(run.status);
                    setTimeout(poll, POLL_MS);
                } else {
                    show('Still indexing. Check back later.');
                }
            })
            .catch(() => show('Could not load the index status.'));
    }

    function failed(text) {
        show(text);
        if (button) button.disabled = false;
    }

    if (button) {
        button.addEventListener('click', () => {
            setRunning('pending');
            fetch(panel.dataset.reindexUrl, { method: 'POST', headers: { Accept: 'application/json' } })
                .then((response) => {
                    if (response.status === 429) {
                        failed('You can re-index once every 10 minutes.');
                        return null;
                    }
                    return response.json().then((body) => {
                        if (!response.ok) {
                            failed(body.error || 'Could not start re-indexing.');
                            return;
                        }
                        polls = 0;
                        setTimeout(poll, POLL_MS);
                    });
                })
                .catch(() => failed('Could not start re-indexing.'));
        });
    }

    if (inProgress(panel.dataset.runStatus)) {
        setRunning(panel.dataset.runStatus);
        setTimeout(poll, POLL_MS);
    }
})();
