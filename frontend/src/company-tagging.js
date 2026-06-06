import { mountIsland } from './lib/mountIsland';
import { CompanyTaggingModal } from './components/company-tagging/CompanyTaggingModal';

/**
 * Company Tagging — React island entry point.
 *
 * Auto-mounts into #company-tagging-mount on DOMContentLoaded.
 * The component registers window.detectAndSuggestCompanies() on mount.
 *
 * updateLinkedCompaniesDisplay() and unlinkCompany() operate on non-React DOM
 * (note/snippet cards rendered by Jinja2), so they are registered here as
 * plain global functions.
 */

// -------------------------------------------------------------------------
// updateLinkedCompaniesDisplay — inject company tags into Jinja2-rendered cards
// -------------------------------------------------------------------------
window.updateLinkedCompaniesDisplay = function (targetType, targetId, companies) {
  const cardSelector =
    targetType === 'note'
      ? `[data-note-id="${targetId}"]`
      : `[data-snippet-id="${targetId}"]`;

  const card = document.querySelector(cardSelector);
  if (!card) return;

  let container = card.querySelector('.linked-companies-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'linked-companies-container mt-2';

    const cardBody = card.querySelector('.card-body');
    const cardFooter = card.querySelector('.card-footer');
    if (cardFooter) {
      cardBody.insertBefore(container, cardFooter);
    } else if (cardBody) {
      cardBody.appendChild(container);
    }
  }

  container.innerHTML = '';
  if (companies && companies.length > 0) {
    const tagsHTML = companies
      .map(
        (c) => `
      <span class="company-tag" data-company-id="${c.id}">
        <i class="bi bi-building"></i>
        <span class="company-tag-name">${c.name}</span>
        <span class="company-tag-ticker">${c.ticker}</span>
        <button class="company-tag-remove" onclick="unlinkCompany('${targetType}', ${targetId}, ${c.id})" title="Remove link">
          <i class="bi bi-x"></i>
        </button>
      </span>`,
      )
      .join('');

    container.innerHTML = `
      <div class="small text-muted mb-1">
        <i class="bi bi-link-45deg"></i> Linked Companies:
      </div>
      <div class="company-tags-list">${tagsHTML}</div>
    `;
  }
};

// -------------------------------------------------------------------------
// unlinkCompany — remove a company link from a note/snippet
// -------------------------------------------------------------------------
window.unlinkCompany = async function (targetType, targetId, companyId) {
  if (!confirm('Remove this company link?')) return;

  const endpoint =
    targetType === 'note'
      ? `/sectors/note/${targetId}/unlink-company/${companyId}`
      : `/sectors/snippet/${targetId}/unlink-company/${companyId}`;

  if (window.showToast) window.showToast('Removing\u2026', 'loading');

  try {
    const response = await fetch(endpoint, { method: 'POST' });
    const data = await response.json();

    if (data.success) {
      const tag = document.querySelector(`[data-company-id="${companyId}"]`);
      if (tag) {
        tag.remove();

        const cardSelector =
          targetType === 'note'
            ? `[data-note-id="${targetId}"]`
            : `[data-snippet-id="${targetId}"]`;
        const card = document.querySelector(cardSelector);
        const tagsList = card?.querySelector('.company-tags-list');

        if (tagsList && tagsList.children.length === 0) {
          const container = card.querySelector('.linked-companies-container');
          if (container) container.remove();
        }
      }

      if (window.showToast) window.showToast('Removed', 'success');
    } else {
      if (window.showToast) window.showToast(data.error || 'Failed to unlink company', 'danger');
    }
  } catch (err) {
    console.error('Error unlinking company:', err);
    if (window.showToast) window.showToast('Failed to unlink company', 'danger');
  }
};

// -------------------------------------------------------------------------
// Mount the React island
// -------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', function () {
  mountIsland('company-tagging-mount', CompanyTaggingModal);
});
