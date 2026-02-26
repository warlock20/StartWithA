/**
 * =============================================================================
 * AI Research Assistant Module
 * =============================================================================
 * Reusable JavaScript module for AI-powered research assistance across platform.
 *
 * Features:
 * - Challenge Mode: Counter-arguments to test reasoning
 * - Elaboration Mode: Follow-up questions to deepen analysis
 * - Fact-Check Mode: Verify claims and request sources
 *
 * Usage:
 * 1. Include this script in your page: <script src="{{ url_for('static', filename='js/ai-research-assistant.js') }}" defer></script>
 * 2. Initialize: window.aiAssistant = new AIResearchAssistant(config);
 * 3. Trigger: aiAssistant.triggerMode('challenge', answerText, context);
 *
 * Configuration:
 * {
 *     apiEndpoint: '/research/workflow/ai_assist',           // Backend API endpoint
 *     feedbackEndpoint: '/research/workflow/ai_assist/feedback',
 *     regenerateEndpoint: '/research/workflow/ai_assist/regenerate',
 *     getAnswerText: () => string,                  // Function to get answer text from editor
 *     context: { analysis_id, item_id, company_name, question_text } // Context data
 * }
 * =============================================================================
 */

class AIResearchAssistant {
    constructor(config = {}) {
        // Configuration
        this.apiEndpoint = config.apiEndpoint || '/research/workflow/ai_assist';
        this.feedbackEndpoint = config.feedbackEndpoint || '/research/workflow/ai_assist/feedback';
        this.regenerateEndpoint = config.regenerateEndpoint || '/research/workflow/ai_assist/regenerate';
        this.getAnswerText = config.getAnswerText || (() => '');
        this.context = config.context || {};

        // State
        this.currentFeedbackId = null;
        this.currentMode = null;

        // Mode configuration
        this.modes = {
            challenge: {
                section: 'aiResponseChallenge',
                text: 'aiResponseChallengeText',
                loadingMsg: 'Analyzing your reasoning and preparing counter-arguments...'
            },
            elaboration: {
                section: 'aiResponseElaboration',
                text: 'aiResponseElaborationText',
                loadingMsg: 'Crafting follow-up questions to deepen your analysis...'
            },
            factcheck: {
                section: 'aiResponseFactcheck',
                text: 'aiResponseFactcheckText',
                loadingMsg: 'Identifying claims that need verification...'
            }
        };
    }

    /**
     * Trigger AI mode (Challenge, Elaboration, Fact-Check)
     * Validates answer exists, then calls AI assistant API
     */
    triggerMode(mode, answerText = null, context = null) {
        // Get answer text if not provided
        if (!answerText) {
            answerText = this.getAnswerText();
        }

        // Validate answer exists
        if (!answerText || answerText.trim().length < 10) {
            alert('Please write something in your answer before using AI assistance.');
            return;
        }

        // Update context if provided
        if (context) {
            this.context = { ...this.context, ...context };
        }

        // Store current mode
        this.currentMode = mode;

        // Call AI assistant
        this.callAIAssistant(mode, answerText);
    }

    /**
     * Call AI Assistant API
     * Makes AJAX POST request to backend
     */
    callAIAssistant(mode, answerText) {
        // Show loading state
        this.showLoading(mode);

        // Prepare request data
        const requestData = {
            mode: mode,
            question_text: this.context.question_text,
            answer_text: answerText,
            analysis_id: this.context.analysis_id,
            item_id: this.context.item_id,
            company_name: this.context.company_name
        };

        // Make AJAX POST request
        fetch(this.apiEndpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
        })
        .then(response => {
            // Check for token limit error (429)
            if (response.status === 429) {
                return response.json().then(data => {
                    this.hideLoading();
                    this.showTokenLimitError(data);
                    throw new Error('Token limit exceeded'); // Stop further processing
                });
            }
            return response.json();
        })
        .then(data => {
            this.hideLoading();

            if (data.success) {
                // Display AI response
                this.displayResponse(mode, data.response, data.feedback_id);
                this.currentFeedbackId = data.feedback_id;

                // Log success
                console.log(`AI ${mode} success: ${data.tokens_used} tokens used`);
            } else {
                // Show error
                alert('AI Assistant Error: ' + (data.error || 'Unknown error occurred'));
                console.error('AI assist error:', data.error);
            }
        })
        .catch(error => {
            // Only show network error if not token limit error
            if (error.message !== 'Token limit exceeded') {
                this.hideLoading();
                alert('Network error. Please check your connection and try again.');
                console.error('AI assist network error:', error);
            }
        });
    }

    /**
     * Show token limit error message
     * Displays user-friendly error when token limit is exceeded (429)
     */
    showTokenLimitError(data) {
        const responseArea = document.getElementById('aiResponseArea');
        const loadingSpinner = document.getElementById('aiLoadingSpinner');

        // Hide loading spinner
        if (loadingSpinner) {
            loadingSpinner.style.display = 'none';
        }

        // Hide all response sections
        Object.values(this.modes).forEach(modeConfig => {
            const section = document.getElementById(modeConfig.section);
            if (section) section.style.display = 'none';
        });

        // Format reset date if available
        let resetDateText = 'unknown date';
        if (data.reset_date) {
            const resetDate = new Date(data.reset_date);
            resetDateText = resetDate.toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric'
            });
        }

        // Create error message HTML
        const errorHtml = `
            <div class="alert alert-warning" role="alert">
                <div class="d-flex align-items-start">
                    <i class="bi bi-exclamation-triangle-fill me-3 fs-4"></i>
                    <div class="flex-grow-1">
                        <h6 class="alert-heading mb-2">
                            <strong>AI Token Limit Reached</strong>
                        </h6>
                        <p class="mb-2">
                            You've used <strong>${data.tokens_used?.toLocaleString() || 'all'}</strong> of your
                            <strong>${data.tokens_limit?.toLocaleString() || 'monthly'}</strong> AI tokens.
                        </p>
                        <p class="mb-2 small">
                            Your token limit will reset on <strong>${resetDateText}</strong>.
                        </p>
                        <hr class="my-2">
                        <p class="mb-0 small">
                            <a href="/settings/profile/" class="alert-link">
                                <i class="bi bi-graph-up me-1"></i>View your token usage and subscription details
                            </a>
                        </p>
                    </div>
                </div>
            </div>
        `;

        // Show error in response area
        if (responseArea) {
            responseArea.innerHTML = errorHtml;
            responseArea.style.display = 'block';
        }

        console.warn('Token limit exceeded:', data);
    }

    /**
     * Show AI loading spinner with mode-specific message
     */
    showLoading(mode) {
        const responseArea = document.getElementById('aiResponseArea');
        const loadingSpinner = document.getElementById('aiLoadingSpinner');

        // Hide all response sections
        Object.values(this.modes).forEach(modeConfig => {
            const section = document.getElementById(modeConfig.section);
            if (section) section.style.display = 'none';
        });

        // Update loading message based on mode
        const loadingText = loadingSpinner.querySelector('p');
        if (loadingText && this.modes[mode]) {
            loadingText.textContent = this.modes[mode].loadingMsg;
        }

        // Show loading spinner and response area
        loadingSpinner.style.display = 'flex';
        responseArea.style.display = 'block';
    }

    /**
     * Hide AI loading spinner
     */
    hideLoading() {
        const loadingSpinner = document.getElementById('aiLoadingSpinner');
        if (loadingSpinner) {
            loadingSpinner.style.display = 'none';
        }
    }

    /**
     * Display AI response in appropriate section
     */
    displayResponse(mode, responseText, feedbackId) {
        const modeConfig = this.modes[mode];
        if (!modeConfig) {
            console.error('Invalid mode:', mode);
            return;
        }

        const responseSection = document.getElementById(modeConfig.section);
        const contentDiv = document.getElementById(modeConfig.text);

        if (!responseSection || !contentDiv) {
            console.error('Could not find response containers for mode:', mode);
            return;
        }

        // Format and display response
        contentDiv.innerHTML = this.formatResponse(responseText);

        // Add feedback buttons dynamically
        const feedbackContainer = responseSection.querySelector('.ai-feedback-buttons');
        if (feedbackContainer) {
            feedbackContainer.innerHTML = this.createFeedbackButtons();
        }

        // Show response section
        responseSection.style.display = 'block';

        // Store feedback_id in data attribute for feedback buttons
        responseSection.setAttribute('data-feedback-id', feedbackId);
    }

    /**
     * Format AI response text (simple markdown-style formatting)
     * Converts line breaks, bold text, and lists to HTML
     */
    formatResponse(text) {
        // Escape HTML first
        let formatted = text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        // Convert **bold** to <strong>
        formatted = formatted.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

        // Convert line breaks to paragraphs
        const paragraphs = formatted.split('\n\n');
        formatted = paragraphs.map(p => {
            // Check if paragraph is a list
            if (p.includes('\n- ') || p.includes('\n* ') || p.match(/^\d+\./m)) {
                // Convert bullet lists
                let listContent = p.replace(/^- /gm, '<li>').replace(/^\* /gm, '<li>');
                // Convert numbered lists
                listContent = listContent.replace(/^\d+\. /gm, '<li>');

                // Wrap in ul or ol
                if (p.match(/^\d+\./m)) {
                    return '<ol>' + listContent.split('\n').map(line => line.startsWith('<li>') ? line + '</li>' : line).join('') + '</ol>';
                } else {
                    return '<ul>' + listContent.split('\n').map(line => line.startsWith('<li>') ? line + '</li>' : line).join('') + '</ul>';
                }
            } else {
                return '<p>' + p.replace(/\n/g, '<br>') + '</p>';
            }
        }).join('');

        return formatted;
    }

    /**
     * Create reusable AI feedback buttons
     * Generates HTML for feedback buttons (Helpful, Not Helpful, Regenerate, Copy, Dismiss)
     * Can be reused across platform (research, decision journal, portfolio notes, etc.)
     */
    createFeedbackButtons() {
        return `
            <div class="d-flex flex-wrap gap-2 justify-content-between align-items-center mt-3 pt-2 border-top">
                <div class="d-flex gap-2">
                    <button type="button" class="btn btn-sm btn-outline-success" onclick="window.aiAssistant.submitFeedback('helpful')" title="Mark this response as helpful">
                        <i class="bi bi-hand-thumbs-up me-1"></i> Helpful
                    </button>
                    <button type="button" class="btn btn-sm btn-outline-danger" onclick="window.aiAssistant.submitFeedback('not_helpful')" title="Mark this response as not helpful">
                        <i class="bi bi-hand-thumbs-down me-1"></i> Not Helpful
                    </button>
                </div>
                <div class="d-flex gap-2">
                    <button type="button" class="btn btn-sm btn-outline-primary" onclick="window.aiAssistant.regenerate()" title="Generate a new response">
                        <i class="bi bi-arrow-clockwise me-1"></i> Regenerate
                    </button>
                    <button type="button" class="btn btn-sm btn-outline-secondary" onclick="window.aiAssistant.copyToClipboard()" title="Copy response to clipboard">
                        <i class="bi bi-clipboard me-1"></i> Copy
                    </button>
                    <button type="button" class="btn btn-sm btn-outline-secondary" onclick="window.aiAssistant.dismiss()" title="Close this response">
                        <i class="bi bi-x-lg me-1"></i> Dismiss
                    </button>
                </div>
            </div>
        `;
    }

    /**
     * Submit feedback for AI response
     */
    submitFeedback(feedbackValue) {
        if (!this.currentFeedbackId) {
            console.error('No feedback_id available');
            return;
        }

        // Disable feedback buttons
        const feedbackButtons = document.querySelectorAll('.ai-feedback-buttons .btn');
        feedbackButtons.forEach(btn => btn.disabled = true);

        // Make AJAX POST request
        fetch(this.feedbackEndpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                feedback_id: this.currentFeedbackId,
                feedback: feedbackValue
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('Feedback recorded:', feedbackValue);

                // Show brief confirmation
                const confirmationMsg = feedbackValue === 'helpful'
                    ? 'Thank you for your feedback!'
                    : 'Feedback recorded. We\'ll improve our responses.';

                console.log(confirmationMsg);

                // If not helpful, could enable regenerate functionality here
                if (feedbackValue === 'not_helpful') {
                    console.log('User can regenerate response');
                }
            } else {
                console.error('Feedback error:', data.error);
                // Re-enable buttons on error
                feedbackButtons.forEach(btn => btn.disabled = false);
            }
        })
        .catch(error => {
            console.error('Feedback network error:', error);
            // Re-enable buttons on error
            feedbackButtons.forEach(btn => btn.disabled = false);
        });
    }

    /**
     * Regenerate AI response
     */
    regenerate() {
        if (!this.currentFeedbackId) {
            console.error('No feedback_id available for regeneration');
            return;
        }

        // Show loading
        this.showLoading(this.currentMode || 'regenerating');

        // Make AJAX POST request
        fetch(this.regenerateEndpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                feedback_id: this.currentFeedbackId
            })
        })
        .then(response => {
            // Check for token limit error (429)
            if (response.status === 429) {
                return response.json().then(data => {
                    this.hideLoading();
                    this.showTokenLimitError(data);
                    throw new Error('Token limit exceeded');
                });
            }
            return response.json();
        })
        .then(data => {
            this.hideLoading();

            if (data.success) {
                // Display new AI response
                this.displayResponse(data.mode, data.response, data.feedback_id);
                this.currentFeedbackId = data.feedback_id;

                console.log('Response regenerated:', data.tokens_used, 'tokens used');
            } else {
                alert('Regeneration Error: ' + (data.error || 'Unknown error occurred'));
                console.error('Regeneration error:', data.error);
            }
        })
        .catch(error => {
            // Only show network error if not token limit error
            if (error.message !== 'Token limit exceeded') {
                this.hideLoading();
                alert('Network error. Please check your connection and try again.');
                console.error('Regeneration network error:', error);
            }
        });
    }

    /**
     * Dismiss AI response area
     */
    dismiss() {
        // Submit dismissed feedback
        if (this.currentFeedbackId) {
            this.submitFeedback('dismissed');
        }

        // Hide response area
        const responseArea = document.getElementById('aiResponseArea');
        if (responseArea) {
            responseArea.style.display = 'none';
        }

        // Hide all response sections
        Object.values(this.modes).forEach(modeConfig => {
            const section = document.getElementById(modeConfig.section);
            if (section) section.style.display = 'none';
        });

        // Reset state
        this.currentFeedbackId = null;
        this.currentMode = null;
    }

    /**
     * Copy current AI response to clipboard
     */
    copyToClipboard() {
        if (!this.currentMode) {
            console.error('No current mode set');
            return;
        }

        const modeConfig = this.modes[this.currentMode];
        if (!modeConfig) {
            console.error('Invalid mode:', this.currentMode);
            return;
        }

        const contentDiv = document.getElementById(modeConfig.text);
        if (!contentDiv) {
            console.error('Could not find response content');
            return;
        }

        // Get text content (strip HTML)
        const textContent = contentDiv.innerText || contentDiv.textContent;

        // Copy to clipboard
        navigator.clipboard.writeText(textContent).then(() => {
            // Show brief success feedback
            const copyBtn = document.querySelector('.ai-feedback-buttons .btn-outline-secondary[onclick*="copyToClipboard"]');
            if (copyBtn) {
                const originalHTML = copyBtn.innerHTML;
                copyBtn.innerHTML = '<i class="bi bi-check me-1"></i> Copied!';
                copyBtn.classList.remove('btn-outline-secondary');
                copyBtn.classList.add('btn-success');

                setTimeout(() => {
                    copyBtn.innerHTML = originalHTML;
                    copyBtn.classList.remove('btn-success');
                    copyBtn.classList.add('btn-outline-secondary');
                }, 2000);
            }
            console.log('Response copied to clipboard');
        }).catch(err => {
            console.error('Failed to copy to clipboard:', err);
            alert('Failed to copy to clipboard. Please try selecting and copying manually.');
        });
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AIResearchAssistant;
}
