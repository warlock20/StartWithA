import { useState, useEffect, useRef } from 'react';

/**
 * FocusMode — single-company decision view with UP NEXT sidebar.
 *
 * Two-column layout: main decision card (left) and a scrollable
 * queue of upcoming companies (right). Supports keyboard shortcuts
 * I (Inbox), K (Kill), S (Skip).
 *
 * Props:
 *   companies: Array<{ id, company_name, ticker, sector_label, market_cap, exchange, decision }>
 *   onDecide: (companyId, decision) => void
 *   onOpenKill: (companyId, companyName) => void
 *   disabled: boolean — when true, keyboard shortcuts are suppressed (e.g. modal open)
 */
export function FocusMode({ companies, onDecide, onOpenKill, disabled }) {
  var [skippedIds, setSkippedIds] = useState([]);
  var stateRef = useRef({});

  // Pending = companies without a decision
  var pending = companies.filter(function (c) {
    return !c.decision;
  });

  // Available = pending minus temporarily skipped
  var available = pending.filter(function (c) {
    return skippedIds.indexOf(c.id) === -1;
  });

  // Reset skips when all pending have been skipped
  useEffect(function () {
    if (available.length === 0 && pending.length > 0) {
      setSkippedIds([]);
    }
  }, [available.length, pending.length]);

  var current = available[0] || null;
  var currentIndex = current ? companies.indexOf(current) : -1;
  var upNext = available.slice(1, 8);

  // Keep refs current for the stable keyboard handler
  stateRef.current = {
    current: current,
    onDecide: onDecide,
    onOpenKill: onOpenKill,
    disabled: disabled,
  };

  // Keyboard shortcuts (registered once, reads latest state via ref)
  useEffect(function () {
    function handleKeyDown(e) {
      var s = stateRef.current;
      if (s.disabled) return;
      if (
        e.target.tagName === 'INPUT' ||
        e.target.tagName === 'TEXTAREA' ||
        e.target.tagName === 'SELECT'
      )
        return;
      if (!s.current) return;

      var key = e.key.toLowerCase();
      if (key === 'i') {
        e.preventDefault();
        s.onDecide(s.current.id, 'inbox');
      } else if (key === 'k') {
        e.preventDefault();
        s.onOpenKill(s.current.id, s.current.company_name);
      } else if (key === 's') {
        e.preventDefault();
        setSkippedIds(function (prev) {
          return prev.concat([s.current.id]);
        });
      }
    }

    document.addEventListener('keydown', handleKeyDown);
    return function () {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  function handleSkip() {
    if (!current) return;
    setSkippedIds(function (prev) {
      return prev.concat([current.id]);
    });
  }

  // All companies reviewed
  if (pending.length === 0) {
    return (
      <div className="sweep-focus-complete">
        <i className="bi bi-check-circle" />
        <h3>All companies reviewed!</h3>
        <p>
          You've reviewed all {companies.length} companies in this sweep.
          Switch to Table View to review or change decisions.
        </p>
      </div>
    );
  }

  if (!current) return null;

  return (
    <div className="sweep-focus">
      <div className="sweep-focus__layout">
        {/* ── Main decision card ── */}
        <div className="sweep-focus__card">
          <div className="sweep-focus__card-header">
            <span className="sweep-focus__position">
              #{currentIndex + 1} of {companies.length}
            </span>
            <span className="sweep-decision-badge sweep-decision-badge--pending">
              PENDING
            </span>
          </div>

          <div className="sweep-focus__company-info">
            <h2 className="sweep-focus__name">{current.company_name}</h2>
            {current.ticker && (
              <span className="sweep-focus__ticker">{current.ticker}</span>
            )}
          </div>

          <div className="sweep-focus__details">
            <div className="sweep-focus__detail">
              <span className="sweep-focus__detail-label">Sector</span>
              <span className="sweep-focus__detail-value">
                {current.sector_label || '\u2014'}
              </span>
            </div>
            <div className="sweep-focus__detail">
              <span className="sweep-focus__detail-label">Market Cap</span>
              <span className="sweep-focus__detail-value">
                {current.market_cap || '\u2014'}
              </span>
            </div>
            {current.exchange && (
              <div className="sweep-focus__detail">
                <span className="sweep-focus__detail-label">Exchange</span>
                <span className="sweep-focus__detail-value">{current.exchange}</span>
              </div>
            )}
          </div>

          <div className="sweep-focus__actions">
            <button
              className="sweep-focus__action-btn sweep-focus__action-btn--inbox"
              onClick={function () {
                onDecide(current.id, 'inbox');
              }}
            >
              <i className="bi bi-inbox" /> Inbox
              <kbd className="sweep-focus__kbd">I</kbd>
            </button>
            <button
              className="sweep-focus__action-btn sweep-focus__action-btn--kill"
              onClick={function () {
                onOpenKill(current.id, current.company_name);
              }}
            >
              <i className="bi bi-x-lg" /> Kill
              <kbd className="sweep-focus__kbd">K</kbd>
            </button>
            <button
              className="sweep-focus__action-btn sweep-focus__action-btn--skip"
              onClick={handleSkip}
            >
              <i className="bi bi-skip-forward" /> Skip
              <kbd className="sweep-focus__kbd">S</kbd>
            </button>
          </div>
        </div>

        {/* ── UP NEXT sidebar ── */}
        <div className="sweep-focus__sidebar">
          <h4 className="sweep-focus__sidebar-title">UP NEXT</h4>
          <div className="sweep-focus__sidebar-list">
            {/* Current company — highlighted */}
            <div className="sweep-focus__sidebar-item sweep-focus__sidebar-item--current">
              <span className="sweep-focus__sidebar-name">
                {current.company_name}
              </span>
              {current.ticker && (
                <span className="sweep-focus__sidebar-ticker">
                  {current.ticker}
                </span>
              )}
              {current.market_cap && (
                <span className="sweep-focus__sidebar-mcap">
                  {current.market_cap}
                </span>
              )}
            </div>
            {/* Upcoming companies */}
            {upNext.map(function (c) {
              return (
                <div key={c.id} className="sweep-focus__sidebar-item">
                  <span className="sweep-focus__sidebar-name">
                    {c.company_name}
                  </span>
                  {c.ticker && (
                    <span className="sweep-focus__sidebar-ticker">
                      {c.ticker}
                    </span>
                  )}
                  {c.market_cap && (
                    <span className="sweep-focus__sidebar-mcap">
                      {c.market_cap}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
