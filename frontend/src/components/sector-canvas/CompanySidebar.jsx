import { useEffect } from 'react';
import { showToast } from './utils';

/**
 * CompanySidebar — Behavior-only bridge for the Jinja2-rendered
 * companies sidebar accordion in sector analysis pages.
 *
 * Returns null (no DOM output). Attaches event handlers to:
 *   - #addCompanyForm — intercept submit to add company via API
 *   - #companiesList  — delegated click on .btn-remove-company
 *   - #newCompanyBtn  — opens company search modal
 *
 * Props:
 *   sectorName: string (slug, for API URLs)
 */
export function CompanySidebar({ sectorName }) {
  useEffect(function () {
    if (!sectorName) return;

    // ---- helpers ----

    function updateCompanyBadgeCount() {
      var list = document.getElementById('companiesList');
      var accordion = document.getElementById('companiesCollapse');
      var badge = accordion
        ? accordion.closest('.accordion-item').querySelector('.badge')
        : null;
      if (badge && list) {
        badge.textContent = list.querySelectorAll('.tool-item').length;
      }
    }

    function appendCompanyToList(company) {
      var list = document.getElementById('companiesList');
      if (!list) return;
      var emptyMsg = list.querySelector('p.text-muted');
      if (emptyMsg) emptyMsg.remove();

      var item = document.createElement('div');
      item.className = 'tool-item';
      item.dataset.companyId = company.id;
      item.innerHTML =
        '<div class="tool-item-text">' +
          '<strong>' + escapeText(company.name) + '</strong>' +
          '<small class="d-block text-muted">' + escapeText(company.ticker) + '</small>' +
          (company.is_in_portfolio ? '<span class="badge bg-info">Portfolio</span>' : '') +
        '</div>' +
        '<div class="tool-item-actions">' +
          '<a href="' + escapeText(company.dashboard_url) + '" class="btn btn-sm btn-link p-0" title="View company">' +
            '<i class="bi bi-eye"></i>' +
          '</a>' +
          '<button type="button" class="btn btn-sm btn-link p-0 text-danger btn-remove-company" ' +
            'data-company-id="' + company.id + '" data-company-name="' + escapeText(company.name) + '" title="Remove from sector">' +
            '<i class="bi bi-x-circle"></i>' +
          '</button>' +
        '</div>';
      list.appendChild(item);
      updateCompanyBadgeCount();
    }

    function removeCompanyFromList(companyId) {
      var item = document.querySelector('#companiesList .tool-item[data-company-id="' + companyId + '"]');
      if (item) {
        item.style.transition = 'opacity 0.2s, transform 0.2s';
        item.style.opacity = '0';
        item.style.transform = 'translateX(10px)';
        setTimeout(function () {
          item.remove();
          updateCompanyBadgeCount();
          var list = document.getElementById('companiesList');
          if (list && !list.querySelector('.tool-item')) {
            list.innerHTML = '<p class="text-muted small text-center mb-0">No companies tracked</p>';
          }
        }, 200);
      }
    }

    function addOptionToSelect(company) {
      var select = document.getElementById('companySelect');
      if (!select) return;
      var opt = document.createElement('option');
      opt.value = company.id;
      opt.textContent = company.name;
      var options = Array.from(select.options).slice(1);
      var insertBefore = options.find(function (o) {
        return o.textContent.localeCompare(company.name) > 0;
      });
      select.insertBefore(opt, insertBefore || null);
    }

    function removeOptionFromSelect(companyId) {
      var select = document.getElementById('companySelect');
      if (!select) return;
      var opt = select.querySelector('option[value="' + companyId + '"]');
      if (opt) opt.remove();
      select.value = '';
    }

    function escapeText(str) {
      if (!str) return '';
      var div = document.createElement('div');
      div.textContent = str;
      return div.innerHTML;
    }

    // ---- API helpers ----

    function addCompanyToSector(companyId, callback) {
      showToast('Adding\u2026', 'loading');
      fetch('/sectors/' + sectorName + '/add_company/' + companyId, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.success) {
            callback(data.company);
          } else {
            showToast(data.error || 'Failed to add company', 'error');
          }
        })
        .catch(function () { showToast('Network error', 'error'); });
    }

    function removeCompanyFromSector(companyId, callback) {
      showToast('Removing\u2026', 'loading');
      fetch('/sectors/' + sectorName + '/remove_company/' + companyId, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.success) {
            callback(data.company);
          } else {
            showToast(data.error || 'Failed to remove company', 'error');
          }
        })
        .catch(function () { showToast('Network error', 'error'); });
    }

    // ---- event handlers ----

    var addForm = document.getElementById('addCompanyForm');
    function handleAddSubmit(e) {
      e.preventDefault();
      var select = document.getElementById('companySelect');
      var companyId = select ? select.value : '';
      if (!companyId) return;

      var btn = addForm.querySelector('button[type="submit"]');
      btn.disabled = true;
      btn.innerHTML = '<i class="bi bi-hourglass-split"></i>';

      addCompanyToSector(companyId, function (company) {
        appendCompanyToList(company);
        removeOptionFromSelect(companyId);
        showToast(company.name + ' added to sector', 'success');
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-plus"></i>';
      });
    }
    if (addForm) {
      addForm.addEventListener('submit', handleAddSubmit);
    }

    var companiesList = document.getElementById('companiesList');
    function handleRemoveClick(e) {
      var btn = e.target.closest('.btn-remove-company');
      if (!btn) return;
      e.preventDefault();

      var companyId = btn.dataset.companyId;
      var companyName = btn.dataset.companyName;
      if (!confirm('Remove ' + companyName + ' from this sector?')) return;

      btn.disabled = true;
      removeCompanyFromSector(companyId, function (company) {
        removeCompanyFromList(companyId);
        addOptionToSelect(company);
        showToast(company.name + ' removed from sector', 'success');
      });
    }
    if (companiesList) {
      companiesList.addEventListener('click', handleRemoveClick);
    }

    var newCompanyBtn = document.getElementById('newCompanyBtn');
    function handleNewCompany() {
      if (typeof window.openCompanyModal === 'function') {
        window.openCompanyModal(function (company) {
          addCompanyToSector(company.id, function (added) {
            appendCompanyToList(added);
            removeOptionFromSelect(company.id);
            showToast(added.name + ' added to sector', 'success');
          });
        });
      } else {
        console.error('Company search component not loaded');
      }
    }
    if (newCompanyBtn) {
      newCompanyBtn.addEventListener('click', handleNewCompany);
    }

    // ---- cleanup ----
    return function () {
      if (addForm) addForm.removeEventListener('submit', handleAddSubmit);
      if (companiesList) companiesList.removeEventListener('click', handleRemoveClick);
      if (newCompanyBtn) newCompanyBtn.removeEventListener('click', handleNewCompany);
    };
  }, [sectorName]);

  return null;
}
