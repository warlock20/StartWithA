/**
 * Research Companion — rail UI
 * Scope indicator, quick actions, the verb composer, capture and wrap-up.
 * Extends window.CompanionChat (see core.js).
 */
(function () {
  const CompanionChat = window.CompanionChat;
  if (!CompanionChat) return;

  // Human label for the current scope, shown in the rail header so a shared
  // 'general' thread across unfocused pages reads as intentional, not a glitch.
  // Generic (scope type only) — no per-page wiring.
  const scopeLabel = (f) => {
    if (f.project_id) return { icon: 'bi-search', text: 'This research session' };
    if (f.company_id) return { icon: 'bi-building', text: 'Focused on this company' };
    if (f.type === 'portfolio') return { icon: 'bi-pie-chart', text: 'Across your portfolio' };
    return { icon: 'bi-globe', text: 'Across your whole account' };
  };

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

  Object.assign(CompanionChat, {
    renderScope() {
      const el = document.getElementById('companionScope');
      if (!el) return;
      const s = scopeLabel(this.focus);
      el.innerHTML = `<i class="bi ${s.icon}"></i> ${this.escapeHtml(s.text)}`;
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
            `<div class="c-msg-wrapup-label"><i class="bi bi-flag-fill me-1"></i> Session Summary</div>${this.renderMarkdown(data.data.summary)}`
          );
        } else {
          this.appendMessage('assistant', `<span class="text-danger">Wrap-up failed: ${this.escapeHtml(data.error || 'Unknown error')}</span>`);
        }
      } catch (err) {
        this.hideTyping();
        this.appendMessage('assistant', `<span class="text-danger">Connection error: ${this.escapeHtml(err.message)}</span>`);
      }
    },
  });
})();
