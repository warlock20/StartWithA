/**
 * =============================================================================
 * Research Companion — Floating Chat Widget (extracted from _companion_widget.html)
 * =============================================================================
 * Config is read from the #companion-root dataset so the widget can be mounted
 * on any page. Focus is a page hint: {type, company_id?, project_id?, step?}.
 *   data-endpoint-base       — global companion API base (default: /companion)
 *   data-focus-type          — 'company' | 'research' | 'portfolio' | ''
 *   data-focus-company-id    — company id (or empty)
 *   data-focus-project-id    — research project id (or empty)
 *   data-focus-step          — research step index (or empty)
 *
 * Chat + capture go to the global /companion endpoint; wrap-up stays on the
 * research route (research-only feature). History is one rolling thread per
 * browser tab, kept in sessionStorage.
 *
 * Exposes window.CompanionChat with toggle/send/quickAction/saveCapture/runWrapup.
 */
(function () {
  const root = document.getElementById('companion-root');
  if (!root) return;

  const toInt = (v) => (v ? parseInt(v, 10) : null);
  const cfg = {
    endpointBase: root.dataset.endpointBase || '/companion',
    researchBase: '/research/workflow/companion',
    focus: {
      type: root.dataset.focusType || '',
      company_id: toInt(root.dataset.focusCompanyId),
      project_id: toInt(root.dataset.focusProjectId),
      step: toInt(root.dataset.focusStep),
    },
  };

  const THREAD_KEY = 'companion.thread';

  // Quick actions per focus type. `prefill` sends a question through the agent;
  // `action` runs a widget function. "Capture" is universal. Labels stay factual
  // (the companion surfaces facts, not opinions — e.g. concentration, not "risk").
  const QUICK_ACTIONS = {
    company: [
      { label: 'What did I miss?', icon: 'bi-search',
        prefill: 'What did I miss on this company — which research steps, flags, or checkpoints are still open?' },
      { label: 'Past mistakes here?', icon: 'bi-exclamation-triangle',
        prefill: 'What past mistakes or behavioural patterns of mine are relevant to this company?' },
      { label: 'Capture', icon: 'bi-bookmark-plus', action: 'capture' },
    ],
    portfolio: [
      { label: 'Where am I concentrated?', icon: 'bi-pie-chart',
        prefill: 'Where is my portfolio most concentrated — by position and by sector?' },
      { label: 'Checkpoints due?', icon: 'bi-calendar-check',
        prefill: 'Which of my holdings have checkpoints or thesis reviews due?' },
      { label: 'Capture', icon: 'bi-bookmark-plus', action: 'capture' },
    ],
    research: [
      { label: 'Gaps?', icon: 'bi-search',
        prefill: 'What gaps remain in my research for this step?' },
      { label: 'Wrap Up', icon: 'bi-flag', action: 'wrapup' },
      { label: 'Capture', icon: 'bi-bookmark-plus', action: 'capture' },
    ],
    default: [
      { label: 'Capture', icon: 'bi-bookmark-plus', action: 'capture' },
    ],
  };

  const CompanionChat = {
    endpointBase: cfg.endpointBase,
    researchBase: cfg.researchBase,
    focus: cfg.focus,
    projectId: cfg.focus.project_id,   // research-only helpers (wrap-up)
    stepIndex: cfg.focus.step || 0,
    isOpen: false,
    conversationHistory: [],

    // One rolling thread per tab.
    loadThread() {
      try {
        this.conversationHistory = JSON.parse(sessionStorage.getItem(THREAD_KEY) || '[]');
      } catch (e) {
        this.conversationHistory = [];
      }
    },
    saveThread() {
      try {
        sessionStorage.setItem(THREAD_KEY, JSON.stringify(this.conversationHistory));
      } catch (e) { /* storage full / disabled — non-fatal */ }
    },

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
      this.saveThread();
      input.value = '';

      // Show typing indicator
      this.showTyping();

      try {
        const response = await fetch(`${this.endpointBase}/ask`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            question: text,
            history: this.conversationHistory,
            focus: this.focus
          })
        });

        this.hideTyping();
        const data = await response.json();

        if (data.success) {
          const answer = data.data.answer;
          this.appendMessage('assistant', this.escapeHtml(answer));
          this.conversationHistory.push({ role: 'assistant', content: answer });
          this.saveThread();
        } else {
          this.appendMessage('assistant', `<span class="text-danger">Error: ${this.escapeHtml(data.error || 'Failed to get answer')}</span>`);
        }
      } catch (err) {
        this.hideTyping();
        this.appendMessage('assistant', `<span class="text-danger">Connection error: ${this.escapeHtml(err.message)}</span>`);
      }
    },

    renderQuickActions() {
      const container = document.getElementById('companionQuickActions');
      if (!container) return;
      const actions = QUICK_ACTIONS[this.focus.type] || QUICK_ACTIONS.default;
      container.innerHTML = '';
      actions.forEach((a) => {
        const btn = document.createElement('button');
        btn.className = 'cqa-btn';
        btn.type = 'button';
        btn.innerHTML = `<i class="bi ${a.icon}"></i> ${a.label}`;
        btn.addEventListener('click', () => {
          if (a.action === 'capture') {
            this.openCaptureModal();
          } else if (a.action === 'wrapup') {
            this.runWrapup();
          } else if (a.prefill) {
            document.getElementById('companionChatInput').value = a.prefill;
            this.send();
          }
        });
        container.appendChild(btn);
      });
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
        const response = await fetch(`${this.endpointBase}/capture`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: text,
            source_title: sourceTitle,
            url: url,
            focus: this.focus
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
      // Wrap-up is a research-only feature; keep it on the research route.
      if (!this.projectId) return;
      this.appendMessage('system', 'Generating session wrap-up...');
      this.showTyping();

      try {
        const response = await fetch(`${this.researchBase}/${this.projectId}/wrapup`, {
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

  // Render focus-appropriate quick actions.
  CompanionChat.renderQuickActions();

  // Restore the rolling thread for this tab and replay it into the panel.
  CompanionChat.loadThread();
  CompanionChat.conversationHistory.forEach((m) => {
    CompanionChat.appendMessage(
      m.role === 'user' ? 'user' : 'assistant',
      CompanionChat.escapeHtml(m.content)
    );
  });
})();
