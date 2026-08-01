/**
 * Research Companion — surfaced insights
 * The user's own history for the company in focus, from the zero-token warnings
 * endpoint. Silent when no company is in focus.
 */
(function () {
  const CompanionChat = window.CompanionChat;
  if (!CompanionChat) return;

  Object.assign(CompanionChat, {
    // Surface what the user's own history already says about this company —
    // pattern warnings, past decisions, logged mistakes. Pure DB on the server,
    // so this costs no tokens and needs no agent turn.
    //
    // Gated on a company focus: warnings are per-company, and an account-wide
    // "surfaced" feed is a different feature. On an unfocused page the section
    // stays empty rather than empty-stated.
    async loadInsights() {
      const companyId = this.focus.company_id;
      const container = document.getElementById('companionInsights');
      if (!container || !companyId) return;

      let warnings;
      try {
        const resp = await fetch(`${this.endpointBase}/warnings?company_id=${companyId}`);
        const data = await resp.json();
        if (!data.success) return;
        warnings = data.data.warnings || [];
      } catch (e) {
        return;   // never block the composer on a background fetch
      }
      if (!warnings.length) return;

      // Mirror the count onto the collapsed strip, so a collapsed rail still says
      // there's something here.
      const light = document.getElementById('companionStatusInsights');
      if (light) {
        document.getElementById('companionInsightCount').textContent = warnings.length;
        light.style.display = '';
      }

      const head = document.createElement('div');
      head.className = 'companion-insights-head';
      head.innerHTML = `<i class="bi bi-lightbulb-fill"></i> Surfaced for you
        <span class="companion-insights-count">${warnings.length}</span>`;
      container.appendChild(head);

      warnings.forEach((w) => container.appendChild(this.insightCard(w)));
    },

    // One card. Everything here is the user's own text from their own rows, but
    // it still goes through escapeHtml — it's user input, not trusted markup.
    insightCard(w) {
      const card = document.createElement('div');
      card.className = `companion-insight companion-insight--${w.severity || 'info'}`;
      const detail = w.detail
        ? `<div class="companion-insight-detail">${this.escapeHtml(w.detail)}</div>` : '';
      card.innerHTML = `
        <div class="companion-insight-top">
          <i class="bi ${w.icon || 'bi-info-circle-fill'}"></i>
          <b>${this.escapeHtml(w.title || '')}</b>
        </div>
        <p>${this.escapeHtml(w.message || '')}</p>
        ${detail}`;

      // Dismiss is view-only for now — nothing is persisted, so a reload brings
      // it back. Persisting dismissals would need a table and a scope decision.
      const dismiss = document.createElement('button');
      dismiss.className = 'companion-insight-dismiss';
      dismiss.type = 'button';
      dismiss.title = 'Dismiss';
      dismiss.innerHTML = '<i class="bi bi-x"></i>';
      dismiss.addEventListener('click', () => card.remove());
      card.appendChild(dismiss);
      return card;
    },
  });
})();
