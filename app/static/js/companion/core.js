/**
 * =============================================================================
 * Research Companion — core
 * =============================================================================
 * Config, per-context state, and the ask/poll transport. Creates
 * window.CompanionChat; every other companion module extends that object and
 * must load after this one (deferred scripts run in document order).
 *
 * Config is read from the #companionRail dataset so the rail can be mounted on
 * any page. Focus is a page hint: {type, company_id?, project_id?, step?}.
 *   data-endpoint-base       — global companion API base (default: /companion)
 *   data-focus-type          — 'company' | 'research' | 'portfolio' | ''
 *   data-focus-company-id    — company id (or empty)
 *   data-focus-project-id    — research project id (or empty)
 *   data-focus-step          — research step index (or empty)
 *
 * History is one rolling thread per browser tab, kept in sessionStorage.
 */
(function () {
  const root = document.getElementById('companionRail');
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

  const cfg = {
    endpointBase: root.dataset.endpointBase || '/companion',
    researchBase: '/research/workflow/companion',
    focus: {
      type: root.dataset.focusType || '',
      company_id: toInt(root.dataset.focusCompanyId),
      project_id: toInt(root.dataset.focusProjectId),
      step: toInt(root.dataset.focusStep),
      // Which page the user is actually on, so the agent can answer "what is this
      // page?" instead of guessing from the account-wide map.
      path: window.location.pathname,
      title: document.title,
    },
  };

  // sessionStorage keys are scoped to the focus context (and per browser tab), so
  // switching pages loads the right conversation and tabs never collide.
  const CTX_KEY = focusKey(cfg.focus);
  const THREAD_KEY = 'companion.thread:' + CTX_KEY;
  const OPEN_KEY = 'companion.open';   // tab-global: whether the rail is expanded
  const PENDING_KEY = 'companion.pending:' + CTX_KEY;  // in-flight task for this context

  const CompanionChat = {
    root: root,
    // sessionStorage keys, shared with the modules that load after this one.
    keys: { thread: THREAD_KEY, open: OPEN_KEY, pending: PENDING_KEY },

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
        this.conversationHistory = JSON.parse(sessionStorage.getItem(this.keys.thread) || '[]');
      } catch (e) {
        this.conversationHistory = [];
      }
    },
    saveThread() {
      try {
        sessionStorage.setItem(this.keys.thread, JSON.stringify(this.conversationHistory));
      } catch (e) { /* storage full / disabled — non-fatal */ }
    },

    // Apply + persist expanded/collapsed. Shared by toggle() and the on-load
    // restore so the rail keeps its width across navigations (tab-global).
    setOpen(open) {
      this.isOpen = open;
      // Collapsing leaves the deep dive: a 44px strip has nowhere to put an
      // answer beside its sources, and re-expanding into a stale split is worse
      // than landing back in the conversation.
      if (!open && this.isDeep && typeof this.setDeep === 'function') {
        this.setDeep(false);
      }
      this.root.classList.toggle('collapsed', !open);
      // Drives the mobile scrim and the background scroll lock. Set at every
      // width — the CSS that reads it is scoped to the mobile breakpoint, so a
      // docked rail is unaffected and a resize needs no re-sync.
      document.body.classList.toggle('companion-open', open);
      try {
        sessionStorage.setItem(this.keys.open, open ? '1' : '');
      } catch (e) { /* storage disabled — non-fatal */ }
      if (open) {
        document.getElementById('companionRailBadge').style.display = 'none';
        this.scrollToBottom();
      }
    },

    toggle() {
      this.setOpen(!this.isOpen);
      if (this.isOpen) document.getElementById('companionChatInput').focus();
    },

    // A question is in flight. Shown on the collapsed strip (spinner) and on the
    // orb (a slow pulse), so leaving the rail collapsed still tells you it's busy.
    setRunning(running) {
      const spinner = document.getElementById('companionStatusRunning');
      if (spinner) spinner.style.display = running ? '' : 'none';
      const orb = document.getElementById('companionRailOrb');
      if (orb) orb.classList.toggle('is-running', running);
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
      this.clearVerb();

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
          sessionStorage.setItem(this.keys.pending, JSON.stringify({
            taskId: data.data.task_id, startedAt: Date.now(),
          }));
        } catch (e) { /* storage disabled — resume is best-effort */ }

        const result = await this.pollAnswer(data.data.task_id);
        sessionStorage.removeItem(this.keys.pending);
        this.hideTyping();
        if (result !== null) {
          this.appendMessage('assistant', this.renderMarkdown(result.answer));
          this.conversationHistory.push({ role: 'assistant', content: result.answer });
          this.saveThread();
          this.rememberAnswer(result.answer, result.sources);
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
          const payload = data.data.result || {};
          return {
            answer: payload.answer || '(no answer)',
            sources: payload.sources || [],
          };
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
      try { p = JSON.parse(sessionStorage.getItem(this.keys.pending) || 'null'); }
      catch (e) { p = null; }
      if (!p || !p.taskId) return;

      // Always allow one status check (a finished task returns instantly), but
      // bound the polling loop to ~3 min from when it started so a lost worker
      // can't spin forever.
      const AGE_CAP = 3 * 60 * 1000;
      const remaining = Math.max(2000, AGE_CAP - (Date.now() - (p.startedAt || 0)));

      this.showTyping();
      this.pollAnswer(p.taskId, 1200, remaining).then((result) => {
        this.hideTyping();
        sessionStorage.removeItem(this.keys.pending);
        if (result !== null) {
          this.appendMessage('assistant', this.renderMarkdown(result.answer));
          this.conversationHistory.push({ role: 'assistant', content: result.answer });
          this.saveThread();
          this.rememberAnswer(result.answer, result.sources);
          if (!this.isOpen) {
            document.getElementById('companionRailBadge').style.display = 'block';
          }
        }
      });
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

    // showTyping/hideTyping bracket every run (ask, resume, wrap-up), so the
    // collapsed strip's running light rides along with them.
    showTyping() {
      const msg = document.createElement('div');
      msg.className = 'c-msg c-msg--typing';
      msg.id = 'companionTyping';
      msg.innerHTML = '<div class="typing-dots"><span></span><span></span><span></span></div>';
      document.getElementById('companionMessages').appendChild(msg);
      this.setRunning(true);
      this.scrollToBottom();
    },

    hideTyping() {
      const el = document.getElementById('companionTyping');
      if (el) el.remove();
      this.setRunning(false);
    },

    // The scroll region is the whole body (insights + messages), not the message
    // list alone.
    scrollToBottom() {
      const el = document.getElementById('companionRailBody');
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
})();
