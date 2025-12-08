/**
 * Hashtag Autocomplete Component
 * Shows existing hashtags as user types
 */

class HashtagAutocomplete {
    constructor(inputElement, options = {}) {
        this.input = inputElement;
        this.options = {
            apiUrl: options.apiUrl || '/journal/api/hashtags',
            minChars: options.minChars || 1,
            maxSuggestions: options.maxSuggestions || 10,
            ...options
        };

        this.hashtags = [];
        this.suggestionsContainer = null;
        this.selectedIndex = -1;

        this.init();
    }

    async init() {
        // Create suggestions container
        this.createSuggestionsContainer();

        // Fetch existing hashtags
        await this.fetchHashtags();

        // Setup event listeners
        this.setupEventListeners();
    }

    createSuggestionsContainer() {
        this.suggestionsContainer = document.createElement('div');
        this.suggestionsContainer.className = 'hashtag-suggestions';
        this.suggestionsContainer.style.display = 'none';
        this.input.parentNode.style.position = 'relative';
        this.input.parentNode.appendChild(this.suggestionsContainer);
    }

    async fetchHashtags() {
        try {
            const response = await fetch(this.options.apiUrl);
            const data = await response.json();

            if (data.success && data.hashtags) {
                this.hashtags = data.hashtags;
            }
        } catch (error) {
            console.error('Failed to fetch hashtags:', error);
        }
    }

    setupEventListeners() {
        // Input event for showing suggestions
        this.input.addEventListener('input', (e) => {
            this.handleInput(e);
        });

        // Keyboard navigation
        this.input.addEventListener('keydown', (e) => {
            this.handleKeydown(e);
        });

        // Click outside to close
        document.addEventListener('click', (e) => {
            if (!this.input.contains(e.target) && !this.suggestionsContainer.contains(e.target)) {
                this.hideSuggestions();
            }
        });
    }

    handleInput(e) {
        const value = this.input.value;
        const cursorPos = this.input.selectionStart;

        // Find the current word being typed (after # or space)
        const textBeforeCursor = value.substring(0, cursorPos);
        const words = textBeforeCursor.split(/\s+/);
        const currentWord = words[words.length - 1];

        // Check if typing a hashtag
        if (currentWord.startsWith('#') && currentWord.length >= this.options.minChars + 1) {
            const searchTerm = currentWord.substring(1).toLowerCase();
            this.showSuggestions(searchTerm, currentWord);
        } else {
            this.hideSuggestions();
        }
    }

    showSuggestions(searchTerm, currentWord) {
        // Filter hashtags
        const matches = this.hashtags
            .filter(tag => tag.toLowerCase().includes(searchTerm.toLowerCase()))
            .filter(tag => tag.toLowerCase() !== currentWord.toLowerCase()) // Exclude exact match
            .slice(0, this.options.maxSuggestions);

        if (matches.length === 0) {
            this.hideSuggestions();
            return;
        }

        // Build suggestions HTML
        const html = matches.map((tag, index) => {
            return `<div class="hashtag-suggestion-item" data-index="${index}" data-tag="${tag}">
                ${tag}
            </div>`;
        }).join('');

        this.suggestionsContainer.innerHTML = html;
        this.suggestionsContainer.style.display = 'block';
        this.selectedIndex = -1;

        // Add click listeners to suggestions
        this.suggestionsContainer.querySelectorAll('.hashtag-suggestion-item').forEach(item => {
            item.addEventListener('click', (e) => {
                this.selectHashtag(e.target.dataset.tag);
            });
        });
    }

    hideSuggestions() {
        this.suggestionsContainer.style.display = 'none';
        this.selectedIndex = -1;
    }

    handleKeydown(e) {
        if (this.suggestionsContainer.style.display === 'none') {
            return;
        }

        const suggestions = this.suggestionsContainer.querySelectorAll('.hashtag-suggestion-item');

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.selectedIndex = Math.min(this.selectedIndex + 1, suggestions.length - 1);
                this.highlightSuggestion(suggestions);
                break;

            case 'ArrowUp':
                e.preventDefault();
                this.selectedIndex = Math.max(this.selectedIndex - 1, 0);
                this.highlightSuggestion(suggestions);
                break;

            case 'Enter':
            case 'Tab':
                if (this.selectedIndex >= 0 && suggestions[this.selectedIndex]) {
                    e.preventDefault();
                    const tag = suggestions[this.selectedIndex].dataset.tag;
                    this.selectHashtag(tag);
                }
                break;

            case 'Escape':
                this.hideSuggestions();
                break;
        }
    }

    highlightSuggestion(suggestions) {
        suggestions.forEach((item, index) => {
            if (index === this.selectedIndex) {
                item.classList.add('selected');
            } else {
                item.classList.remove('selected');
            }
        });
    }

    selectHashtag(tag) {
        const value = this.input.value;
        const cursorPos = this.input.selectionStart;

        // Find the start of the current word
        const textBeforeCursor = value.substring(0, cursorPos);
        const lastHashIndex = textBeforeCursor.lastIndexOf('#');

        if (lastHashIndex !== -1) {
            // Replace the partial hashtag with the selected one
            const before = value.substring(0, lastHashIndex);
            const after = value.substring(cursorPos);
            const newValue = before + tag + ' ' + after;

            this.input.value = newValue;

            // Set cursor position after the inserted tag
            const newCursorPos = lastHashIndex + tag.length + 1;
            this.input.setSelectionRange(newCursorPos, newCursorPos);

            // Trigger input event for any listeners
            this.input.dispatchEvent(new Event('input', { bubbles: true }));
        }

        this.hideSuggestions();
        this.input.focus();
    }
}

// Initialize on all hashtag inputs
function initHashtagAutocomplete() {
    document.querySelectorAll('input[name="hashtags"]').forEach(input => {
        new HashtagAutocomplete(input);
    });
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initHashtagAutocomplete);
} else {
    initHashtagAutocomplete();
}

// Export for manual initialization
window.HashtagAutocomplete = HashtagAutocomplete;
window.initHashtagAutocomplete = initHashtagAutocomplete;
