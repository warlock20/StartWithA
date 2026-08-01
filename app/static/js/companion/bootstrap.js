/**
 * Research Companion — bootstrap
 * Runs last: renders the rail from focus, replays this tab's thread, restores
 * the expanded state, re-attaches to an in-flight answer, and binds the
 * keyboard routes.
 */
(function () {
  const CompanionChat = window.CompanionChat;
  if (!CompanionChat) return;

  // Render the scope indicator and focus-appropriate quick actions.
  CompanionChat.renderScope();
  CompanionChat.renderQuickActions();

  // Surface the user's own history for this company (no-op when unfocused).
  CompanionChat.loadInsights();

  // Restore the rolling thread for this tab and replay it into the rail.
  CompanionChat.loadThread();
  CompanionChat.conversationHistory.forEach((m) => {
    const isUser = m.role === 'user';
    CompanionChat.appendMessage(
      isUser ? 'user' : 'assistant',
      isUser ? CompanionChat.escapeHtml(m.content) : CompanionChat.renderMarkdown(m.content)
    );
  });

  // Restore the rail's expanded state across navigation (tab-global). Markup
  // ships collapsed, so this only ever expands. Don't focus the input on
  // restore — that would steal focus/scroll on every page load.
  if (sessionStorage.getItem(CompanionChat.keys.open)) {
    CompanionChat.setOpen(true);
  }

  // Resume an answer that was still generating when we navigated to this page.
  CompanionChat.resumePending();

  // '/' in an empty composer jumps to the verbs, so the palette is reachable
  // without the mouse. Only when empty — mid-sentence a slash is just a slash.
  const composer = document.getElementById('companionChatInput');
  if (composer) {
    composer.addEventListener('input', () => CompanionChat.autoGrow());

    composer.addEventListener('keydown', (e) => {
      if (e.key !== '/' || composer.value !== '') return;
      const firstVerb = document.querySelector('#companionVerbPalette .companion-verb');
      if (!firstVerb) return;
      e.preventDefault();
      firstVerb.focus();
    });
  }

  // Arrow keys walk the verb row; Escape returns to the composer empty-handed.
  const palette = document.getElementById('companionVerbPalette');
  if (palette) {
    palette.addEventListener('keydown', (e) => {
      const verbs = [...palette.querySelectorAll('.companion-verb')];
      const at = verbs.indexOf(document.activeElement);
      if (at === -1) return;
      if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
        e.preventDefault();
        const next = e.key === 'ArrowRight' ? at + 1 : at - 1;
        verbs[(next + verbs.length) % verbs.length].focus();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        CompanionChat.clearVerb();
        if (composer) composer.focus();
      }
    });
  }

  // ⌘. / Ctrl+. toggles the rail. Ignored while typing in a field, so it can't
  // steal the keystroke from a note or a form the user is filling in.
  document.addEventListener('keydown', (e) => {
    if (!(e.metaKey || e.ctrlKey) || e.key !== '.') return;
    const el = document.activeElement;
    const tag = el ? el.tagName : '';
    if (tag === 'INPUT' || tag === 'TEXTAREA' || (el && el.isContentEditable)) {
      if (el.id !== 'companionChatInput') return;
    }
    e.preventDefault();
    CompanionChat.toggle();
  });
})();
