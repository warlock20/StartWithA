/**
 * Research Companion — deep dive and citations
 * The last answer beside the sources it was built from.
 */
(function () {
  const CompanionChat = window.CompanionChat;
  if (!CompanionChat) return;

  Object.assign(CompanionChat, {
    // ---- Deep dive -------------------------------------------------------
    // The last answer beside the sources it was built from. The source list is a
    // record of what the executor read, so it is always complete; the [n] markers
    // in the answer are an extra the model may or may not add, and an unmarked
    // sentence is normal rather than unsourced.
    lastAnswer: '',
    lastSources: [],

    rememberAnswer(answer, sources) {
      this.lastAnswer = answer || '';
      this.lastSources = sources || [];
      const toggle = document.getElementById('companionDeepToggle');
      if (toggle) toggle.style.display = this.lastAnswer ? '' : 'none';
    },

    setDeep(on) {
      const deep = document.getElementById('companionDeep');
      const body = document.getElementById('companionRailBody');
      const footer = document.querySelector('.companion-rail-footer');
      if (!deep) return;

      this.root.classList.toggle('deep', on);
      deep.style.display = on ? '' : 'none';
      if (body) body.style.display = on ? 'none' : '';
      if (footer) footer.style.display = on ? 'none' : '';
      if (on) this.renderDeep();
    },

    renderDeep() {
      const deep = document.getElementById('companionDeep');
      deep.innerHTML = `
        <div class="cdeep-split">
          <div class="cdeep-answer" id="companionDeepAnswer">
            ${this.renderMarkdown(this.lastAnswer)}
          </div>
          <div class="cdeep-sources" id="companionDeepSources"></div>
        </div>
        <div class="cdeep-actions">
          <button class="cdeep-btn cdeep-btn--primary" type="button"
                  id="companionDeepInsert">Insert into checklist</button>
          <button class="cdeep-btn" type="button" id="companionDeepExport">Export</button>
          <button class="cdeep-btn" type="button" id="companionDeepClose">Close</button>
        </div>`;

      this.renderSources();
      this.linkCitations();

      document.getElementById('companionDeepInsert')
        .addEventListener('click', () => this.insertAnswer());
      document.getElementById('companionDeepExport')
        .addEventListener('click', () => this.exportAnswer());
      document.getElementById('companionDeepClose')
        .addEventListener('click', () => this.setDeep(false));
    },

    renderSources() {
      const box = document.getElementById('companionDeepSources');
      if (!box) return;
      if (!this.lastSources.length) {
        box.innerHTML = '<div class="cdeep-src-label">No sources read</div>';
        return;
      }
      box.innerHTML = '<div class="cdeep-src-label">Sources read</div>';
      this.lastSources.forEach((s) => {
        const card = document.createElement('div');
        card.className = 'cdeep-src';
        card.id = `companionSource${s.n}`;
        card.innerHTML = `
          <span class="cdeep-src-n">${s.n}</span>
          <div class="cdeep-src-body">
            <b>${this.escapeHtml(s.label || '')}</b>
            <span>${this.escapeHtml(s.source_type || '')}</span>
          </div>`;
        box.appendChild(card);
      });
    },

    // Turn [n] in the rendered answer into a link to its card. Only numbers that
    // have a card become links — the server already stripped the rest.
    linkCitations() {
      const answer = document.getElementById('companionDeepAnswer');
      if (!answer) return;
      const valid = new Set(this.lastSources.map((s) => String(s.n)));

      const walker = document.createTreeWalker(answer, NodeFilter.SHOW_TEXT);
      const targets = [];
      while (walker.nextNode()) {
        if (/\[\d{1,3}\]/.test(walker.currentNode.nodeValue)) targets.push(walker.currentNode);
      }
      targets.forEach((node) => {
        const html = node.nodeValue.replace(/\[(\d{1,3})\]/g, (whole, n) =>
          valid.has(n)
            ? `<a class="cdeep-cite" href="#companionSource${n}">${n}</a>`
            : whole);
        const span = document.createElement('span');
        span.innerHTML = html;
        node.parentNode.replaceChild(span, node);
      });
    },

    // Same targets as a selection citation: the note being edited, then the
    // BlockNote editor, then the clipboard.
    insertAnswer() {
      const editor = window.blockNoteEditorInstance;
      const textarea = document.querySelector('.app-main textarea');

      if (textarea) {
        textarea.value += (textarea.value ? '\n\n' : '') + this.lastAnswer;
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
        return this.deepDone('Inserted into the page');
      }
      if (editor && typeof editor.insertBlocks === 'function') {
        try {
          const doc = editor.document || [];
          editor.insertBlocks(
            [{ type: 'paragraph', content: this.lastAnswer }], doc[doc.length - 1], 'after');
          return this.deepDone('Inserted into the page');
        } catch (e) { /* editor API drifted — fall through */ }
      }
      if (navigator.clipboard) {
        navigator.clipboard.writeText(this.lastAnswer).then(
          () => this.deepDone('Copied'), () => this.deepDone('Could not insert'));
        return;
      }
      this.deepDone('Could not insert');
    },

    // Markdown, with the source list appended so the numbers still resolve once
    // the answer has left the app.
    exportAnswer() {
      const lines = [this.lastAnswer, ''];
      if (this.lastSources.length) {
        lines.push('## Sources', '');
        this.lastSources.forEach(
          (s) => lines.push(`${s.n}. ${s.label} (${s.source_type})`));
      }
      const blob = new Blob([lines.join('\n')], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'companion-answer.md';
      link.click();
      URL.revokeObjectURL(url);
    },

    deepDone(message) {
      this.setDeep(false);
      this.appendMessage('system', this.escapeHtml(message));
    },
  });
})();
