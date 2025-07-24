// In app/static/js/task_polling.js

document.addEventListener('DOMContentLoaded', function() {
    const pollingDiv = document.getElementById('task-polling-status');
    const generateBtn = document.getElementById('generate-ai-summary-btn'); 
    // Return early if the polling div doesn't exist on the page
    if (!pollingDiv) return;

    // Get the task_id from the URL (e.g., ?task_id=xyz)
    const urlParams = new URLSearchParams(window.location.search);
    const taskId = urlParams.get('task_id');

    if (taskId) {
        // If a task ID is present, make the status area visible and start polling
        pollingDiv.style.display = 'block';
        pollingDiv.innerHTML = `
            <div class="alert alert-info">
                <div class="spinner-border spinner-border-sm me-2" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                Your request is being processed. This may take a few minutes...
            </div>
        `;
        if (generateBtn) {
            generateBtn.disabled = true;
            generateBtn.innerHTML = `
                <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
                Processing...
            `;
        }
        const interval = setInterval(function() {
            // Poll the task_status route
            fetch(`/research/task_status/${taskId}`)
                .then(response => response.json())
                .then(data => {
                    console.log('Polling status:', data);
                    // Check if the task is finished (either SUCCESS or FAILURE)
                    if (data.state === 'SUCCESS' || data.state === 'FAILURE') {
                        clearInterval(interval); // Stop polling

                        let alertClass = data.state === 'SUCCESS' ? 'alert-success' : 'alert-danger';
                        let finalMessage = data.state === 'SUCCESS' ? 'Task completed successfully!' : 'Task failed.';

                        // Display the final status message
                        pollingDiv.innerHTML = `
                            <div class="alert ${alertClass}">
                                ${finalMessage} The page will now reload to show the results.
                            </div>
                        `;

                        // Reload the page after a short delay to show the new documents
                        setTimeout(function() {
                                // This reloads the page to its base URL, removing the "?task_id=..." part
                                window.location.href = window.location.pathname;
                            }, 2500);
                    }
                    // If the task is still PENDING or in another state, the interval will just continue.
                })
                .catch(error => {
                    clearInterval(interval);
                    pollingDiv.innerHTML = `<div class="alert alert-danger">Error: Could not check task status.</div>`;
                    console.error('Polling error:', error);

                    if (generateBtn) {
                        generateBtn.disabled = false;
                        generateBtn.innerHTML = '✨ Generate New AI Summary'; // Restore original text
                    }
                });
        }, 5000); // Poll every 5 seconds
    }
});