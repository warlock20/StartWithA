/**
 * Sector research time tracker.
 *
 * Accumulates *active* research time on the sector analysis page and flushes it
 * to the server periodically. "Active" means the tab is visible AND the user has
 * interacted within the idle window — so leaving the tab open in the background
 * or walking away does not inflate the recorded research time.
 *
 * Requires an element with id="sector-time-tracker" carrying a
 * data-analysis-id attribute, rendered by the sector analysis template.
 */
(function () {
  'use strict';

  var el = document.getElementById('sector-time-tracker');
  if (!el) return;

  var analysisId = el.getAttribute('data-analysis-id');
  if (!analysisId) return;

  var endpoint = '/api/sectors/analysis/' + analysisId + '/track-time';

  var IDLE_LIMIT_MS = 60 * 1000; // treat user as idle after 60s of no interaction
  var FLUSH_INTERVAL_MS = 30 * 1000; // push accumulated time to server every 30s
  var TICK_MS = 1000;

  var lastActivity = Date.now();
  var lastTick = Date.now();
  var pendingSeconds = 0; // active seconds accumulated but not yet flushed

  var activityEvents = ['mousemove', 'keydown', 'scroll', 'click', 'touchstart'];
  activityEvents.forEach(function (evt) {
    document.addEventListener(evt, function () {
      lastActivity = Date.now();
    }, { passive: true });
  });

  // Accumulate elapsed wall-clock time, but only count it while the page is
  // visible and the user has been active recently.
  setInterval(function () {
    var now = Date.now();
    var deltaSeconds = (now - lastTick) / 1000;
    lastTick = now;

    var isVisible = document.visibilityState === 'visible';
    var isActive = (now - lastActivity) < IDLE_LIMIT_MS;

    if (isVisible && isActive) {
      pendingSeconds += deltaSeconds;
    }
  }, TICK_MS);

  function flush(useBeacon) {
    var seconds = Math.round(pendingSeconds);
    if (seconds <= 0) return;

    pendingSeconds -= seconds;
    var payload = JSON.stringify({ seconds: seconds });

    if (useBeacon && navigator.sendBeacon) {
      var blob = new Blob([payload], { type: 'application/json' });
      var ok = navigator.sendBeacon(endpoint, blob);
      if (!ok) pendingSeconds += seconds; // re-queue if the beacon was rejected
      return;
    }

    fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
      body: payload,
      keepalive: true,
    }).catch(function () {
      pendingSeconds += seconds; // re-queue on network failure
    });
  }

  setInterval(function () { flush(false); }, FLUSH_INTERVAL_MS);

  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden') flush(true);
  });

  window.addEventListener('beforeunload', function () { flush(true); });
})();
