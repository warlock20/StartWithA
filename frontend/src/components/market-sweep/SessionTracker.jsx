import { useState, useEffect } from 'react';

/**
 * SessionTracker — client-side session timer and decision stats.
 *
 * Tracks elapsed time since component mount and counts decisions
 * made during the current page session.
 *
 * Props:
 *   sessionStats: { reviewed, inbox, killed } — counts of decisions made this session
 *   totalCompanies: number — total companies in sweep
 *   totalReviewed: number — all-time reviewed count
 */
export function SessionTracker({ sessionStats, totalCompanies, totalReviewed }) {
  var [elapsed, setElapsed] = useState(0);

  useEffect(function () {
    var interval = setInterval(function () {
      setElapsed(function (prev) {
        return prev + 1;
      });
    }, 60000); // update every minute
    return function () {
      clearInterval(interval);
    };
  }, []);

  var minutes = elapsed;
  var timeLabel = minutes < 1 ? '< 1 min' : minutes + ' min';

  var pct = totalCompanies > 0 ? Math.round((totalReviewed / totalCompanies) * 100) : 0;

  return (
    <div className="sweep-session">
      <div className="sweep-session__top">
        <div className="sweep-session__stats">
          <span className="sweep-session__stat">
            <i className="bi bi-clock" /> {timeLabel}
          </span>
          <span className="sweep-session__stat">
            <strong>{sessionStats.reviewed}</strong> reviewed
          </span>
          <span className="sweep-session__stat sweep-session__stat--inbox">
            <strong>{sessionStats.inbox}</strong> <span className="sweep-session__arrow">→</span> inbox
          </span>
          <span className="sweep-session__stat">
            <strong>{sessionStats.killed}</strong> killed
          </span>
        </div>
        <span className="sweep-session__label">Today's session</span>
      </div>
      <div className="sweep-session__bottom">
        <div className="sweep-session__bar">
          <div className="sweep-progress-bar">
            <div className="sweep-progress-fill" style={{ width: pct + '%' }} />
          </div>
        </div>
        <span className="sweep-session__pct">{pct}%</span>
      </div>
    </div>
  );
}
