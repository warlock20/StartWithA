/*
 * Research Companion — Quick Capture Bookmarklet
 *
 * Usage: Drag the bookmarklet link to your browser toolbar.
 * Click it on any page to capture selected text + URL.
 *
 * This file is the SOURCE. The actual bookmarklet is minified into a
 * javascript: URL. See the Research Clipboard page for the drag-and-drop link.
 *
 * The bookmarklet reads the active project ID from localStorage
 * (set when the user opens a research project in the app).
 */
(function() {
    var selectedText = window.getSelection().toString().trim();
    var pageTitle = document.title;
    var pageUrl = window.location.href;

    if (!selectedText) {
        selectedText = prompt('No text selected. Paste or type your finding:');
        if (!selectedText) return;
    }

    var projectId = localStorage.getItem('research_companion_project_id');
    if (!projectId) {
        alert('No active research project. Open a project in the app first.');
        return;
    }

    // Show a small confirmation popup
    var popup = document.createElement('div');
    popup.style.cssText = 'position:fixed;top:20px;right:20px;z-index:999999;background:#1a1a2e;color:#e0e0e0;padding:16px 20px;border-radius:8px;font-family:system-ui;font-size:14px;box-shadow:0 4px 12px rgba(0,0,0,0.3);max-width:400px;';
    popup.innerHTML = '<div style="font-weight:600;margin-bottom:8px;">Saving to Research...</div>' +
        '<div style="font-size:12px;color:#a0a0a0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' +
        selectedText.substring(0, 100) + (selectedText.length > 100 ? '...' : '') + '</div>';
    document.body.appendChild(popup);

    // Send to capture API
    var API_BASE = localStorage.getItem('research_companion_api_base') || '';
    fetch(API_BASE + '/research/workflow/companion/' + projectId + '/capture', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
            text: selectedText,
            url: pageUrl,
            source_title: pageTitle
        })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            popup.innerHTML = '<div style="color:#4ade80;font-weight:600;">Captured!</div>' +
                '<div style="font-size:12px;color:#a0a0a0;margin-top:4px;">Saved to Research Journal</div>';
        } else {
            popup.innerHTML = '<div style="color:#f87171;font-weight:600;">Error</div>' +
                '<div style="font-size:12px;">' + (data.error || 'Unknown error') + '</div>';
        }
        setTimeout(function() { popup.remove(); }, 2000);
    })
    .catch(function(err) {
        popup.innerHTML = '<div style="color:#f87171;font-weight:600;">Error</div>' +
            '<div style="font-size:12px;">Could not reach server. Are you logged in?</div>';
        setTimeout(function() { popup.remove(); }, 3000);
    });
})();
