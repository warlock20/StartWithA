import { useEffect, useRef } from 'react';

/**
 * SecFilingsFetcher — Behavior-only React island (returns null).
 *
 * Attaches a click handler to the existing SEC filings "Fetch" button
 * (#fetch-sec-btn) and manages the polling lifecycle for the background
 * Celery task. Dispatches a `resources-changed` custom event on success
 * so CompanyResourcesManager can re-fetch its list.
 *
 * Props:
 *   companyId: number
 */
export function SecFilingsFetcher({ companyId }) {
  const mountedRef = useRef(false);

  useEffect(() => {
    if (mountedRef.current) return;
    mountedRef.current = true;

    const secBtn = document.getElementById('fetch-sec-btn');
    const secStatus = document.getElementById('sec-fetch-status');
    if (!secBtn || !secStatus) return;

    function pollTaskStatus(taskId, statusDiv, btn, opts) {
      var label = opts.label || 'Task';
      var btnResetHtml = opts.btnResetHtml || btn.innerHTML;
      var onSuccess = opts.onSuccess || null;
      var failCount = 0;
      var maxFails = 5;

      var pollInterval = setInterval(function () {
        fetch('/research/workflow/task_status/' + taskId)
          .then(function (r) { return r.json(); })
          .then(function (data) {
            failCount = 0;
            if (data.state === 'SUCCESS') {
              statusDiv.innerHTML =
                '<i class="bi bi-check-circle text-success me-1"></i>' +
                '<span class="text-success">' + label + ' completed!</span>';
              btn.disabled = false;
              btn.innerHTML = btnResetHtml;
              clearInterval(pollInterval);
              if (onSuccess) onSuccess();
              setTimeout(function () { statusDiv.classList.add('d-none'); }, 5000);
            } else if (data.state === 'FAILURE') {
              statusDiv.innerHTML =
                '<i class="bi bi-x-circle text-danger me-1"></i>' +
                '<span class="text-danger">' + label + ' failed: ' +
                (data.status_message || 'Unknown error') + '</span>';
              btn.disabled = false;
              btn.innerHTML = btnResetHtml;
              clearInterval(pollInterval);
            } else {
              statusDiv.innerHTML =
                '<span class="spinner-border spinner-border-sm me-2"></span>' +
                '<span>' + (data.status_message || label + ' in progress...') + '</span>';
            }
          })
          .catch(function () {
            failCount++;
            if (failCount >= maxFails) {
              statusDiv.innerHTML =
                '<i class="bi bi-exclamation-triangle text-warning me-1"></i>' +
                '<span>Cannot check status. Task continues in background.</span>';
              btn.disabled = false;
              btn.innerHTML = btnResetHtml;
              clearInterval(pollInterval);
            }
          });
      }, 2000);
    }

    secBtn.addEventListener('click', function () {
      var filingType = document.getElementById('sec-filing-type');
      var yearsEl = document.getElementById('sec-filing-years');
      var type = filingType ? filingType.value : '10-K';
      var years = yearsEl ? parseInt(yearsEl.value, 10) : 5;

      secBtn.disabled = true;
      secBtn.innerHTML =
        '<span class="spinner-border spinner-border-sm me-1"></span>Starting...';
      secStatus.classList.remove('d-none');
      secStatus.innerHTML =
        '<span class="spinner-border spinner-border-sm me-2"></span>Submitting request...';

      fetch('/companies/' + companyId + '/fetch_sec_filings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filing_type: type, years: years }),
      })
        .then(function (response) {
          if (!response.ok) throw new Error('HTTP ' + response.status);
          return response.json();
        })
        .then(function (data) {
          if (data.success) {
            secStatus.innerHTML =
              '<span class="spinner-border spinner-border-sm me-2"></span>' +
              '<span>Fetching ' + type + ' filings (' + years +
              ' yrs)&hellip; This may take a moment.</span>';
            secBtn.innerHTML =
              '<i class="bi bi-hourglass-split me-1"></i>Fetching...';
            pollTaskStatus(data.task_id, secStatus, secBtn, {
              label: 'SEC filings fetch',
              btnResetHtml: '<i class="bi bi-cloud-download me-1"></i>Fetch',
              onSuccess: function () {
                document.dispatchEvent(new CustomEvent('resources-changed'));
              },
            });
          } else {
            secStatus.innerHTML =
              '<i class="bi bi-exclamation-circle text-danger me-1"></i>' +
              '<span class="text-danger">' +
              (data.error || 'Failed to start fetch') + '</span>';
            secBtn.disabled = false;
            secBtn.innerHTML =
              '<i class="bi bi-cloud-download me-1"></i>Fetch';
          }
        })
        .catch(function () {
          secStatus.innerHTML =
            '<i class="bi bi-exclamation-circle text-danger me-1"></i>' +
            '<span class="text-danger">Failed to start SEC fetch. Please try again.</span>';
          secBtn.disabled = false;
          secBtn.innerHTML =
            '<i class="bi bi-cloud-download me-1"></i>Fetch';
        });
    });
  }, [companyId]);

  return null;
}
