/**
 * Research Companion — verb composer
 * A verb sets the stance; the user types the subject. Stance text comes from the
 * prompt YAML and is rendered into the markup, so nothing is duplicated here.
 */
(function () {
  const CompanionChat = window.CompanionChat;
  if (!CompanionChat) return;

  Object.assign(CompanionChat, {
    // A verb sets the stance and hands the composer back to the user, who names
    // the subject. Nothing is sent until they do — the verb is a framing, not a
    // shortcut to a canned question.
    pickVerb(btn) {
      const input = document.getElementById('companionChatInput');
      const stance = btn.dataset.verbStance || '';
      const placeholder = btn.dataset.verbPlaceholder || '';

      document.querySelectorAll('.companion-verb').forEach(
        (el) => el.classList.toggle('active', el === btn));

      input.value = stance + ' ';
      input.placeholder = placeholder;
      this.autoGrow();
      input.focus();
      input.setSelectionRange(input.value.length, input.value.length);
      input.scrollTop = input.scrollHeight;
    },

    // Back to a blank composer once a question has gone (or been abandoned).
    clearVerb() {
      const input = document.getElementById('companionChatInput');
      document.querySelectorAll('.companion-verb').forEach(
        (el) => el.classList.remove('active'));
      if (input) input.placeholder = 'Ask about your research...';
      this.autoGrow();
    },

    // Grow the composer to fit what's in it, up to a ceiling, then scroll.
    // A verb's stance runs to a couple of lines, and the whole point of keeping
    // it as editable text is that the user can read what will actually be sent —
    // which only works if it's visible.
    autoGrow() {
      const input = document.getElementById('companionChatInput');
      if (!input) return;
      input.style.height = 'auto';
      const ceiling = parseInt(
        getComputedStyle(input).getPropertyValue('max-height'), 10) || 140;
      input.style.height = `${Math.min(input.scrollHeight, ceiling)}px`;
    },
  });
})();
