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

  // Thread identity: one conversation per focus context. Most-specific wins, so a
  // research project (which belongs to a company) keeps its own thread, distinct
  // from the company page and the portfolio. Unfocused pages share 'general'.
  const focusKey = (f) => {
    if (f.project_id) return 'project:' + f.project_id;
    if (f.company_id) return 'company:' + f.company_id;
    if (f.type === 'portfolio') return 'portfolio';
    return 'general';
  };

  // Human label for the current scope, shown in the panel header so a shared
  // 'general' thread across unfocused pages reads as intentional, not a glitch.
  // Generic (scope type only) — no per-page wiring.
  const scopeLabel = (f) => {
    if (f.project_id) return { icon: 'bi-search', text: 'This research session' };
    if (f.company_id) return { icon: 'bi-building', text: 'Focused on this company' };
    if (f.type === 'portfolio') return { icon: 'bi-pie-chart', text: 'Across your portfolio' };
    return { icon: 'bi-globe', text: 'Across your whole account' };
  };

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

  // sessionStorage keys are scoped to the focus context (and per browser tab), so
  // switching pages loads the right conversation and tabs never collide.
  const CTX_KEY = focusKey(cfg.focus);
  const THREAD_KEY = 'companion.thread:' + CTX_KEY;
  const OPEN_KEY = 'companion.open';   // tab-global: whether the panel is open
  const PENDING_KEY = 'companion.pending:' + CTX_KEY;  // in-flight task for this context

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

    // Apply + persist open/closed. Shared by toggle() and the on-load restore so
    // the panel stays open across navigations (tab-global preference).
    setOpen(open) {
      this.isOpen = open;
      document.getElementById('companionPanel').classList.toggle('open', open);
      document.getElementById('companionFab').classList.toggle('active', open);
      document.getElementById('companionFabIcon').className =
        open ? 'bi bi-x-lg' : 'bi bi-chat-text';
      try {
        sessionStorage.setItem(OPEN_KEY, open ? '1' : '');
      } catch (e) { /* storage disabled — non-fatal */ }
      if (open) {
        document.getElementById('companionFabBadge').style.display = 'none';
        this.scrollToBottom();
      }
    },

    toggle() {
      this.setOpen(!this.isOpen);
      if (this.isOpen) document.getElementById('companionChatInput').focus();
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
        // Kick off the background task, then poll for the answer.
        const response = await fetch(`${this.endpointBase}/ask`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            question: text,
            history: this.conversationHistory,
            focus: this.focus
          })
        });
        const data = await response.json();
        if (!data.success) {
          this.hideTyping();
          this.appendMessage('assistant', `<span class="text-danger">Error: ${this.escapeHtml(data.error || 'Failed to start')}</span>`);
          return;
        }
        // Record the in-flight task so the answer can be recovered if the user
        // navigates away before it finishes (the Celery task keeps running).
        try {
          sessionStorage.setItem(PENDING_KEY, JSON.stringify({
            taskId: data.data.task_id, startedAt: Date.now(),
          }));
        } catch (e) { /* storage disabled — resume is best-effort */ }

        const answer = await this.pollAnswer(data.data.task_id);
        sessionStorage.removeItem(PENDING_KEY);
        this.hideTyping();
        if (answer !== null) {
          this.appendMessage('assistant', this.renderMarkdown(answer));
          this.conversationHistory.push({ role: 'assistant', content: answer });
          this.saveThread();
        }
      } catch (err) {
        this.hideTyping();
        this.appendMessage('assistant', `<span class="text-danger">Connection error: ${this.escapeHtml(err.message)}</span>`);
      }
    },

    // Poll the companion task until completed/failed. Returns the answer or null.
    async pollAnswer(taskId, intervalMs = 1200, timeoutMs = 90000) {
      const deadline = Date.now() + timeoutMs;
      while (Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, intervalMs));
        let data;
        try {
          const resp = await fetch(`${this.endpointBase}/ask/status/${taskId}`);
          data = await resp.json();
        } catch (e) {
          continue; // transient — keep polling
        }
        const status = data && data.data ? data.data.status : null;
        if (status === 'completed') {
          return (data.data.result && data.data.result.answer) || '(no answer)';
        }
        if (status === 'failed') {
          this.appendMessage('assistant', `<span class="text-danger">Failed: ${this.escapeHtml((data.data && data.data.error) || 'unknown error')}</span>`);
          return null;
        }
      }
      this.appendMessage('assistant', '<span class="text-danger">Timed out waiting for the companion.</span>');
      return null;
    },

    // Re-attach to a task that was still running when the user navigated here.
    // Only this context's pending task is resumed; a task started elsewhere stays
    // put and resolves when the user returns to that context.
    resumePending() {
      let p;
      try { p = JSON.parse(sessionStorage.getItem(PENDING_KEY) || 'null'); }
      catch (e) { p = null; }
      if (!p || !p.taskId) return;

      // Always allow one status check (a finished task returns instantly), but
      // bound the polling loop to ~3 min from when it started so a lost worker
      // can't spin forever.
      const AGE_CAP = 3 * 60 * 1000;
      const remaining = Math.max(2000, AGE_CAP - (Date.now() - (p.startedAt || 0)));

      this.showTyping();
      this.pollAnswer(p.taskId, 1200, remaining).then((answer) => {
        this.hideTyping();
        sessionStorage.removeItem(PENDING_KEY);
        if (answer !== null) {
          this.appendMessage('assistant', this.renderMarkdown(answer));
          this.conversationHistory.push({ role: 'assistant', content: answer });
          this.saveThread();
          if (!this.isOpen) {
            document.getElementById('companionFabBadge').style.display = 'block';
          }
        }
      });
    },

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
    },

    // Render the agent's markdown answer to sanitized HTML. `marked` does the
    // markdown → HTML; `DOMPurify` strips anything unsafe (answers are LLM output,
    // so this must be sanitized). Falls back to escaped plain text if the vendored
    // libs somehow didn't load.
    renderMarkdown(text) {
      const raw = String(text == null ? '' : text);
      if (window.marked && window.DOMPurify) {
        return window.DOMPurify.sanitize(window.marked.parse(raw, { breaks: true }));
      }
      return this.escapeHtml(raw);
    }
  };

  window.CompanionChat = CompanionChat;

  // Render the scope indicator and focus-appropriate quick actions.
  CompanionChat.renderScope();
  CompanionChat.renderQuickActions();

  // Restore the rolling thread for this tab and replay it into the panel.
  CompanionChat.loadThread();
  CompanionChat.conversationHistory.forEach((m) => {
    const isUser = m.role === 'user';
    CompanionChat.appendMessage(
      isUser ? 'user' : 'assistant',
      isUser ? CompanionChat.escapeHtml(m.content) : CompanionChat.renderMarkdown(m.content)
    );
  });

  // Restore panel open/closed state across navigation (tab-global). Don't focus
  // the input on restore — that would steal focus/scroll on every page load.
  if (sessionStorage.getItem(OPEN_KEY)) {
    CompanionChat.setOpen(true);
  }

  // Resume an answer that was still generating when we navigated to this page.
  CompanionChat.resumePending();
})();
