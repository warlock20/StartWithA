/**
 * Research Companion — selection assist
 * Highlight a phrase in the workspace and, if the user's own knowledge has
 * something to say about it, a small popover offers that evidence. Retrieval
 * only — no LLM, no tokens.
 *
 * The bar for appearing is deliberately high: nobody asked for this, so it has
 * to earn the interruption. It stays silent for short selections, for anything
 * selected inside the companion's own UI, and whenever the server finds nothing
 * above its relevance floor.
 */
(function () {
  const CompanionChat = window.CompanionChat;
  if (!CompanionChat) return;

  const SelectionAssist = {
    // Mirrors MIN_SELECTION_CHARS on the server, to avoid a round-trip we know
    // will come back empty.
    MIN_CHARS: 12,
    popover: null,
    anchorEl: null,      // where the selection lives, so a citation lands there
    lastText: '',

    // The companion's own surfaces are off-limits: offering evidence about the
    // answer it just wrote is noise, not help.
    isOwnUI(node) {
      const el = node && node.nodeType === 3 ? node.parentElement : node;
      return !!(el && el.closest &&
        el.closest('#companionRail, .companion-selection-popover, .modal'));
    },

    // Only the working area. Selecting a nav label or a page heading isn't a
    // research question.
    inWorkspace(node) {
      const el = node && node.nodeType === 3 ? node.parentElement : node;
      return !!(el && el.closest && el.closest('.app-main'));
    },

    async onSelection() {
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed || !sel.rangeCount) return this.hide();

      const text = sel.toString().trim();
      const node = sel.anchorNode;
      if (text.length < this.MIN_CHARS || this.isOwnUI(node) || !this.inWorkspace(node)) {
        return this.hide();
      }
      if (text === this.lastText && this.popover) return;   // same phrase, already shown

      const rect = sel.getRangeAt(0).getBoundingClientRect();
      this.anchorEl = node && node.nodeType === 3 ? node.parentElement : node;

      let evidence;
      try {
        const resp = await fetch(`${CompanionChat.endpointBase}/selection`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, company_id: CompanionChat.focus.company_id }),
        });
        const data = await resp.json();
        if (!data.success) return;
        evidence = data.data.evidence || [];
      } catch (e) {
        return;   // silent: this was never asked for
      }
      if (!evidence.length) return this.hide();

      this.lastText = text;
      this.show(evidence, rect);
    },

    show(evidence, rect) {
      this.hide();
      const pop = document.createElement('div');
      pop.className = 'companion-selection-popover';
      pop.id = 'companionSelectionPopover';

      const head = document.createElement('div');
      head.className = 'csp-head';
      head.innerHTML = `<i class="bi bi-stars"></i> You already know something about this`;
      pop.appendChild(head);

      evidence.forEach((item) => {
        const row = document.createElement('div');
        row.className = 'csp-item';
        row.innerHTML = `
          <div class="csp-item-top">
            <span class="csp-source">${CompanionChat.escapeHtml(item.source_type)}</span>
            <b>${CompanionChat.escapeHtml(item.title || '')}</b>
          </div>
          <p>${CompanionChat.escapeHtml(item.summary || '')}</p>`;

        const insert = document.createElement('button');
        insert.className = 'csp-insert';
        insert.type = 'button';
        insert.textContent = 'Insert citation';
        insert.addEventListener('click', () => this.insertCitation(item));
        row.appendChild(insert);
        pop.appendChild(row);
      });

      document.body.appendChild(pop);
      this.popover = pop;
      this.position(rect);
    },

    // Anchor under the selection, nudged back inside the viewport if it would
    // hang off the right edge or the bottom.
    position(rect) {
      const pop = this.popover;
      const margin = 8;
      const width = pop.offsetWidth;
      let left = rect.left + window.scrollX;
      let top = rect.bottom + window.scrollY + margin;

      const maxLeft = window.scrollX + document.documentElement.clientWidth - width - margin;
      if (left > maxLeft) left = Math.max(margin, maxLeft);

      const overflowsBottom =
        rect.bottom + pop.offsetHeight + margin > document.documentElement.clientHeight;
      if (overflowsBottom) top = rect.top + window.scrollY - pop.offsetHeight - margin;

      pop.style.left = `${left}px`;
      pop.style.top = `${top}px`;
    },

    // Write the evidence where the user was reading. BlockNote exposes its editor
    // globally; a plain textarea takes the text directly. If neither is the
    // target, fall back to the clipboard rather than doing nothing.
    insertCitation(item) {
      const line = `${item.summary || item.title} — ${item.title}`;
      const textarea = this.anchorEl && this.anchorEl.closest
        ? this.anchorEl.closest('textarea')
        : null;

      if (textarea) {
        textarea.value += (textarea.value ? '\n\n' : '') + line;
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
        return this.done('Citation inserted');
      }

      const editor = window.blockNoteEditorInstance;
      if (editor && typeof editor.insertBlocks === 'function') {
        try {
          const doc = editor.document || [];
          editor.insertBlocks(
            [{ type: 'paragraph', content: line }], doc[doc.length - 1], 'after');
          return this.done('Citation inserted');
        } catch (e) { /* editor API drifted — fall through to clipboard */ }
      }

      if (navigator.clipboard) {
        navigator.clipboard.writeText(line).then(
          () => this.done('Citation copied'),
          () => this.done('Could not insert'));
        return;
      }
      this.done('Could not insert');
    },

    done(message) {
      CompanionChat.appendMessage('system', CompanionChat.escapeHtml(message));
      this.hide();
    },

    hide() {
      if (this.popover) {
        this.popover.remove();
        this.popover = null;
      }
      this.lastText = '';
    },
  };

  let selectionTimer = null;
  document.addEventListener('mouseup', () => {
    clearTimeout(selectionTimer);
    // Wait for the selection to settle, and don't fire mid-drag.
    selectionTimer = setTimeout(() => SelectionAssist.onSelection(), 250);
  });

  document.addEventListener('mousedown', (e) => {
    if (!SelectionAssist.popover) return;
    if (!e.target.closest('.companion-selection-popover')) SelectionAssist.hide();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') SelectionAssist.hide();
  });

  window.addEventListener('scroll', () => SelectionAssist.hide(), { passive: true });
})();
