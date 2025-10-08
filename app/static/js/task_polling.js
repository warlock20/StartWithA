// In app/static/js/task_polling.js

document.addEventListener('DOMContentLoaded', function () {
    const pollingDiv = document.getElementById('task-polling-status');
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
        
        const interval = setInterval(function () {
            // Poll the task_status route
            fetch(`/tasks/task_status/${taskId}`)
                .then(response => response.json())
                .then(data => {
                    console.log('Polling status:', data);
                    // Check if the task is finished (either SUCCESS or FAILURE)
                    if (data.state === 'SUCCESS' || data.state === 'FAILURE') {
                        clearInterval(interval); // Stop polling

                        let alertClass = data.state === 'SUCCESS' ? 'alert-success' : 'alert-danger';
                        let finalMessage = '';

                        if (data.state === 'SUCCESS') {
                            finalMessage = data.message || 'Task completed successfully! Page will now reload.';
                        } else {
                            // Use the specific error message from the backend
                            finalMessage = `Task failed: ${data.message || 'An unknown error occurred.'} The page will reload.`;
                        }

                        // Display the final status message
                        pollingDiv.innerHTML = `
                            <div class="alert ${alertClass}">
                                ${finalMessage}
                            </div>
                        `;

                        // Always reload the page after a delay to show results or clear the polling state
                        setTimeout(function () {
                            // This reloads the page to its base URL, removing the "?task_id=..." part
                            window.location.href = window.location.pathname;
                        }, 4000); // Increased delay for error messages
                    }
                    // If the task is still PENDING or in another state, the interval will just continue.
                })
                .catch(error => {
                    clearInterval(interval);
                    pollingDiv.innerHTML = `<div class="alert alert-danger">Error: Could not check task status. Please manually refresh the page.</div>`;
                    console.error('Polling error:', error);
                });
        }, 5000); // Poll every 5 seconds
    }
});