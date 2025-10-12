/**
 * AI-Powered Summary Generation
 *
 * Handles AI summary generation for sector research Key Takeaways.
 */

/**
 * Generate AI summary of sector research
 */
async function generateAISummary() {
    const button = document.getElementById('generateAISummaryBtn');

    if (!button) return;

    // Get sector name from page (assuming it's in the URL or data attribute)
    const pathParts = window.location.pathname.split('/');
    const sectorName = pathParts[pathParts.indexOf('sectors') + 1];

    if (!sectorName) {
        alert('Could not determine sector name');
        return;
    }

    // Check if takeaways editor exists
    if (!window.takeawaysQuill) {
        alert('Takeaways editor not initialized');
        return;
    }

    // Disable button and show loading state
    const originalHTML = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Generating...';

    try {
        // sectorName is already URL-encoded from the pathname, so don't encode it again
        const response = await fetch(`/sectors/${sectorName}/generate-ai-summary`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                bullet_count: 7,
                focus: 'balanced'  // Can be: balanced, insights, risks, opportunities
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || `HTTP error! status: ${response.status}`);
        }

        if (data.success) {
            // Insert the generated summary into the Quill editor
            // Option 1: Replace content
            // window.takeawaysQuill.root.innerHTML = data.summary_html;

            // Option 2: Append to existing content (better UX)
            const currentLength = window.takeawaysQuill.getLength();

            // If editor is empty or just has newline, replace
            if (currentLength <= 1) {
                window.takeawaysQuill.root.innerHTML = data.summary_html;
            } else {
                // Otherwise, add separator and append
                window.takeawaysQuill.insertText(currentLength - 1, '\n\n');
                window.takeawaysQuill.clipboard.dangerouslyPasteHTML(currentLength + 1, data.summary_html);
            }

            // Trigger auto-save
            if (typeof saveTakeaways === 'function') {
                saveTakeaways();
            }

            // Show success message
            showSuccessToast(`AI summary generated successfully (${data.bullet_points.length} key takeaways)`);

            // Optional: Log token usage
            if (data.token_count) {
                console.log(`AI tokens used: ${data.token_count}`);
            }
        } else {
            throw new Error(data.error || 'Failed to generate summary');
        }

    } catch (error) {
        console.error('Error generating AI summary:', error);
        alert(`Failed to generate AI summary: ${error.message}`);
    } finally {
        // Re-enable button
        button.disabled = false;
        button.innerHTML = originalHTML;
    }
}

/**
 * Show success toast notification
 */
function showSuccessToast(message) {
    // Check if Bootstrap toast is available
    if (typeof bootstrap !== 'undefined' && bootstrap.Toast) {
        // Create toast element
        const toastHTML = `
            <div class="toast align-items-center text-white bg-success border-0" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="d-flex">
                    <div class="toast-body">
                        <i class="bi bi-check-circle me-2"></i>${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;

        // Add to toast container or create one
        let container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container position-fixed top-0 end-0 p-3';
            document.body.appendChild(container);
        }

        container.insertAdjacentHTML('beforeend', toastHTML);
        const toastElement = container.lastElementChild;
        const toast = new bootstrap.Toast(toastElement, { delay: 3000 });
        toast.show();

        // Remove from DOM after hidden
        toastElement.addEventListener('hidden.bs.toast', () => {
            toastElement.remove();
        });
    } else {
        // Fallback to console
        console.log(message);
    }
}
