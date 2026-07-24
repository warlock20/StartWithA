/**
 * =============================================================================
 * Research Companion — Floating Chat Widget (extracted from _companion_widget.html)
 * =============================================================================
 * Config is read from the #companion-root dataset so the widget can be mounted
 * on any page:
 *   data-project-id     — project id (research focus) or 0
 *   data-step-index     — current research step index
 *   data-endpoint-base  — API base (default: /research/workflow/companion)
 *
 * Exposes window.CompanionChat with toggle/send/quickAction/saveCapture/runWrapup.
 */
(function () {
  const root = document.getElementById('companion-root');
  if (!root) return;

  const cfg = {
    projectId: parseInt(root.dataset.projectId || '0', 10),
    stepIndex: parseInt(root.dataset.stepIndex || '0', 10),
    endpointBase: root.dataset.endpointBase || '/research/workflow/companion',
  };

  const CompanionChat = {
    projectId: cfg.projectId,
    stepIndex: cfg.stepIndex,
    endpointBase: cfg.endpointBase,
    isOpen: false,
    conversationHistory: [],

    toggle() {
      this.isOpen = !this.isOpen;
      const panel = document.getElementById('companionPanel');
      const fab = document.getElementById('companionFab');
      const icon = document.getElementById('companionFabIcon');

      panel.classList.toggle('open', this.isOpen);
      fab.classList.toggle('active', this.isOpen);
      icon.className = this.isOpen ? 'bi bi-x-lg' : 'bi bi-chat-text';

      if (this.isOpen) {
        document.getElementById('companionFabBadge').style.display = 'none';
        this.scrollToBottom();
        document.getElementById('companionChatInput').focus();
      }
    },

    async send() {
      const input = document.getElementById('companionChatInput');
      const text = input.value.trim();
      if (!text) return;

      // Check GDPR consent before sending data to AI providers
      if (typeof checkAIConsent === 'function') {
        const consented = await checkAIConsent();
        if (!consented) return;
      }

      // Add user message
      this.appendMessage('user', text);
      this.conversationHistory.push({ role: 'user', content: text });
      input.value = '';

      // Show typing indicator
      this.showTyping();

      try {
        const response = await fetch(`${this.endpointBase}/${this.projectId}/ask`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            question: text,
            conversation_history: this.conversationHistory,
            step_index: this.stepIndex
          })
        });

        this.hideTyping();
        const data = await response.json();

        if (data.success) {
          const answer = data.data.answer;
          this.appendMessage('assistant', this.escapeHtml(answer));
          this.conversationHistory.push({ role: 'assistant', content: answer });
        } else {
          this.appendMessage('assistant', `<span class="text-danger">Error: ${this.escapeHtml(data.error || 'Failed to get answer')}</span>`);
        }
      } catch (err) {
        this.hideTyping();
        this.appendMessage('assistant', `<span class="text-danger">Connection error: ${this.escapeHtml(err.message)}</span>`);
      }
    },

    quickAction(type) {
      const input = document.getElementById('companionChatInput');

      if (type === 'gaps') {
        input.value = 'What gaps remain in my research for this step?';
        this.send();
      } else if (type === 'capture') {
        this.openCaptureModal();
      } else if (type === 'wrapup') {
        this.runWrapup();
      }
    },

    openCaptureModal() {
      const modal = new bootstrap.Modal(document.getElementById('companionCaptureModal'));
      document.getElementById('captureText').value = '';
      document.getElementById('captureSourceTitle').value = '';
      document.getElementById('captureUrl').value = '';
      modal.show();
    },

    async saveCapture() {
      const text = document.getElementById('captureText').value.trim();
      const sourceTitle = document.getElementById('captureSourceTitle').value.trim();
      const url = document.getElementById('captureUrl').value.trim();

      if (!text) {
        alert('Please enter text to capture');
        return;
      }

      try {
        const response = await fetch(`${this.endpointBase}/${this.projectId}/capture`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: text,
            source_title: sourceTitle,
            url: url
          })
        });

        const data = await response.json();

        if (data.success) {
          // Close modal
          const modal = bootstrap.Modal.getInstance(document.getElementById('companionCaptureModal'));
          modal.hide();

          // Show success in chat
          this.appendMessage('system',
            `<i class="bi bi-check-circle-fill text-success me-1"></i> Captured to journal (entry #${data.data.entry_id})`
          );
        } else {
          alert('Failed to save capture: ' + (data.error || 'Unknown error'));
        }
      } catch (err) {
        alert('Connection error: ' + err.message);
      }
    },

    async runWrapup() {
      this.appendMessage('system', 'Generating session wrap-up...');
      this.showTyping();

      try {
        const response = await fetch(`${this.endpointBase}/${this.projectId}/wrapup`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            step_index: this.stepIndex,
            session_findings: this.gatherPageText(),
            duration_minutes: 0
          })
        });

        this.hideTyping();
        const data = await response.json();

        if (data.success) {
          this.appendMessage('assistant',
            `<div class="c-msg-wrapup-label"><i class="bi bi-flag-fill me-1"></i> Session Summary</div>${this.escapeHtml(data.data.summary)}`
          );
        } else {
          this.appendMessage('assistant', `<span class="text-danger">Wrap-up failed: ${this.escapeHtml(data.error || 'Unknown error')}</span>`);
        }
      } catch (err) {
        this.hideTyping();
        this.appendMessage('assistant', `<span class="text-danger">Connection error: ${this.escapeHtml(err.message)}</span>`);
      }
    },

    appendMessage(type, html) {
      const msg = document.createElement('div');
      msg.className = `c-msg c-msg--${type}`;
      if (type === 'assistant') {
        html += aiDisclaimer(true);
      }
      msg.innerHTML = html;
      document.getElementById('companionMessages').appendChild(msg);
      this.scrollToBottom();
    },

    showTyping() {
      const msg = document.createElement('div');
      msg.className = 'c-msg c-msg--typing';
      msg.id = 'companionTyping';
      msg.innerHTML = '<div class="typing-dots"><span></span><span></span><span></span></div>';
      document.getElementById('companionMessages').appendChild(msg);
      this.scrollToBottom();
    },

    hideTyping() {
      const el = document.getElementById('companionTyping');
      if (el) el.remove();
    },

    scrollToBottom() {
      const el = document.getElementById('companionMessages');
      el.scrollTop = el.scrollHeight;
    },

    gatherPageText() {
      const sources = [];
      document.querySelectorAll('textarea').forEach(ta => {
        if (ta.value.trim() && ta.id !== 'companionChatInput') sources.push(ta.value);
      });
      document.querySelectorAll('[class*="blocknote"]').forEach(el => {
        if (el.textContent.trim()) sources.push(el.textContent);
      });
      const notes = document.getElementById('notes');
      if (notes && notes.value) sources.push(notes.value);
      return sources.join(' ').substring(0, 500);
    },

    escapeHtml(text) {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }
  };

  window.CompanionChat = CompanionChat;
})();
