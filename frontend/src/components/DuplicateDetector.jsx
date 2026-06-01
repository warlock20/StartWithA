import { useState, useEffect, useRef, useCallback } from "react";
import { useDebounce } from "../hooks/useDebounce";
import { apiPost } from "../lib/api";

/**
 * Real-time duplicate detection for companies and ideas.
 *
 * Bridge pattern: mounts into #duplicate-alerts and observes external form
 * inputs (name, ticker) owned by the Jinja2 template. Renders Bootstrap-
 * compatible alerts and controls the external submit button.
 *
 * Props (passed via mountIsland from template init script):
 *   entityType      — 'company' | 'idea'
 *   nameInputId     — DOM id of the name input to observe
 *   tickerInputId   — DOM id of the ticker input to observe
 *   submitSelector  — CSS selector for the submit button to enable/disable
 */

const ALERT_ICONS = {
  danger: "\u{1F6AB}",   // 🚫
  warning: "\u26A0\uFE0F", // ⚠️
  info: "\u2139\uFE0F",    // ℹ️
  success: "\u2705",       // ✅
};

export function DuplicateDetector({
  entityType = "company",
  nameInputId,
  tickerInputId,
  submitSelector,
}) {
  const [nameValue, setNameValue] = useState("");
  const [tickerValue, setTickerValue] = useState("");
  const [alerts, setAlerts] = useState([]);
  const [isDuplicate, setIsDuplicate] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);

  const lastCheckRef = useRef({ name: "", ticker: "" });
  const successTimerRef = useRef(null);

  const debouncedName = useDebounce(nameValue, 500);
  const debouncedTicker = useDebounce(tickerValue, 500);

  // ---------------------------------------------------------------------------
  // Bridge: observe external form inputs
  // ---------------------------------------------------------------------------
  useEffect(() => {
    const nameEl = nameInputId ? document.getElementById(nameInputId) : null;
    const tickerEl = tickerInputId ? document.getElementById(tickerInputId) : null;

    // Seed from current values (inputs may already have content)
    if (nameEl) setNameValue(nameEl.value);
    if (tickerEl) setTickerValue(tickerEl.value);

    const onName = (e) => setNameValue(e.target.value);
    const onTicker = (e) => setTickerValue(e.target.value);

    if (nameEl) nameEl.addEventListener("input", onName);
    if (tickerEl) tickerEl.addEventListener("input", onTicker);

    return () => {
      if (nameEl) nameEl.removeEventListener("input", onName);
      if (tickerEl) tickerEl.removeEventListener("input", onTicker);
    };
  }, [nameInputId, tickerInputId]);

  // ---------------------------------------------------------------------------
  // Bridge: enable/disable external submit button
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (!submitSelector) return;
    const btn = document.querySelector(submitSelector);
    if (!btn) return;

    if (isDuplicate) {
      btn.disabled = true;
      btn.classList.add("btn-secondary");
      btn.classList.remove("btn-primary");
    } else {
      btn.disabled = false;
      btn.classList.remove("btn-secondary");
      btn.classList.add("btn-primary");
    }
  }, [isDuplicate, submitSelector]);

  // ---------------------------------------------------------------------------
  // API check on debounced value changes
  // ---------------------------------------------------------------------------
  useEffect(() => {
    const name = debouncedName.trim();
    const ticker = debouncedTicker.trim();

    // Skip if unchanged
    if (
      name === lastCheckRef.current.name &&
      ticker === lastCheckRef.current.ticker
    ) {
      return;
    }

    // Skip if both empty
    if (!name && !ticker) {
      setAlerts([]);
      setIsDuplicate(false);
      setShowSuccess(false);
      return;
    }

    lastCheckRef.current = { name, ticker };

    let cancelled = false;

    (async () => {
      try {
        const result = await apiPost("/api/check-duplicates", {
          name,
          ticker_symbol: ticker,
          entity_type: entityType,
        });

        if (cancelled) return;

        if (
          !result.is_duplicate &&
          !result.suggestions?.length &&
          !result.similar_matches?.length
        ) {
          setAlerts([]);
          setIsDuplicate(false);
          setShowSuccess(true);

          // Auto-hide success after 3s
          clearTimeout(successTimerRef.current);
          successTimerRef.current = setTimeout(
            () => setShowSuccess(false),
            3000
          );
          return;
        }

        setShowSuccess(false);
        setIsDuplicate(!!result.is_duplicate);

        const newAlerts = [];
        (result.exact_matches || []).forEach((match) => {
          newAlerts.push({ level: "danger", message: match.message, data: match });
        });
        (result.similar_matches || []).forEach((match) => {
          const pct = Math.round(match.similarity * 100);
          newAlerts.push({
            level: "warning",
            message: `${match.message} (${pct}% similar)`,
            data: match,
          });
        });
        (result.suggestions || []).forEach((sug) => {
          newAlerts.push({ level: "info", message: sug.message, data: sug });
        });

        setAlerts(newAlerts);
      } catch (err) {
        if (!cancelled) console.error("Duplicate check failed:", err);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [debouncedName, debouncedTicker, entityType]);

  // Cleanup success timer on unmount
  useEffect(() => {
    return () => clearTimeout(successTimerRef.current);
  }, []);

  // ---------------------------------------------------------------------------
  // Actions
  // ---------------------------------------------------------------------------
  const resurrectIdea = useCallback(async (ideaId) => {
    if (!confirm("Are you sure you want to resurrect this previously killed idea?")) {
      return;
    }
    try {
      if (window.showToast) window.showToast("Resurrecting\u2026", "loading");
      const data = await apiPost(`/ideas/${ideaId}/resurrect`);
      if (data.success) {
        if (window.showToast) window.showToast("Resurrected", "success");
        window.location.href = `/ideas/${ideaId}`;
      } else {
        if (window.showToast)
          window.showToast(
            "Failed to resurrect idea: " + (data.error || "Unknown error"),
            "danger"
          );
      }
    } catch (err) {
      console.error("Error:", err);
      if (window.showToast)
        window.showToast("Failed to resurrect idea", "danger");
    }
  }, []);

  const dismissAlert = useCallback((index) => {
    setAlerts((prev) => prev.filter((_, i) => i !== index));
  }, []);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <>
      {showSuccess && (
        <div className="alert alert-success fade show">
          <small>{ALERT_ICONS.success} No duplicates found</small>
        </div>
      )}

      {alerts.map((alert, i) => (
        <Alert
          key={i}
          level={alert.level}
          message={alert.message}
          data={alert.data}
          onDismiss={() => dismissAlert(i)}
          onResurrect={resurrectIdea}
        />
      ))}
    </>
  );
}

// ---------------------------------------------------------------------------
// Alert sub-component
// ---------------------------------------------------------------------------
function Alert({ level, message, data, onDismiss, onResurrect }) {
  return (
    <div className={`alert alert-${level} alert-dismissible fade show`}>
      <div className="d-flex align-items-start">
        <div className="flex-grow-1">
          <strong>{ALERT_ICONS[level]}</strong> {message}
          <ActionButtons data={data} onResurrect={onResurrect} />
        </div>
        <button
          type="button"
          className="btn-close"
          onClick={onDismiss}
          aria-label="Close"
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Action buttons per match type
// ---------------------------------------------------------------------------
function ActionButtons({ data, onResurrect }) {
  if (!data?.type) return null;

  if (data.type === "ticker_conflict" && data.company) {
    return (
      <div className="mt-2">
        <a
          href={`/companies/${data.company.id}/edit`}
          className="btn btn-sm btn-outline-primary"
        >
          Update Existing Company
        </a>
      </div>
    );
  }

  if (data.type === "exact_duplicate" && data.company) {
    return (
      <div className="mt-2">
        <a
          href={`/companies/${data.company.id}`}
          className="btn btn-sm btn-outline-primary"
        >
          View Existing Company
        </a>
      </div>
    );
  }

  if (data.type === "killed_idea_exists" && data.idea) {
    return (
      <div className="mt-2">
        <button
          type="button"
          className="btn btn-sm btn-outline-secondary"
          onClick={() => onResurrect(data.idea.id)}
        >
          Resurrect Previous Idea
        </button>
        <small className="text-muted d-block mt-1">
          Previously killed: {data.idea.kill_reason || "No reason provided"}
        </small>
      </div>
    );
  }

  if (data.type === "promote_existing_company" && data.company) {
    return (
      <div className="mt-2">
        <a
          href={`/research/workflow/intelligent-routing?company_id=${data.company.id}&source=duplicate_detection`}
          className="btn btn-sm btn-outline-success"
        >
          <i className="bi bi-rocket-takeoff" /> Start Research
        </a>
        <a
          href={`/companies/${data.company.id}`}
          className="btn btn-sm btn-outline-secondary ms-2"
        >
          <i className="bi bi-building" /> View Company
        </a>
      </div>
    );
  }

  return null;
}
