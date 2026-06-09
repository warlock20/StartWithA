import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * JournalEntries — React island for the company dashboard Library > Journal section.
 *
 * Replaces the journal entries code from company-dashboard.js (lines 548-625).
 * Paginated AJAX loading, debounced search, sentiment badges, tags, "Load more".
 *
 * Props (via config):
 *   companyId  — numeric company ID
 *   newEntryUrl — URL for creating a new journal entry (from url_for)
 */
export function JournalEntries({ companyId, newEntryUrl }) {
  var [entries, setEntries] = useState([]);
  var [offset, setOffset] = useState(0);
  var [total, setTotal] = useState(0);
  var [hasMore, setHasMore] = useState(false);
  var [search, setSearch] = useState('');
  var [loading, setLoading] = useState(true);
  var searchTimeoutRef = useRef(null);
  var debouncedSearchRef = useRef('');

  var loadEntries = useCallback(
    function (reset, query) {
      var currentOffset = reset ? 0 : offset;
      var url =
        '/portfolio/api/notes/' + companyId + '?offset=' + currentOffset + '&limit=10';
      if (query) url += '&q=' + encodeURIComponent(query);

      fetch(url)
        .then(function (r) {
          return r.json();
        })
        .then(function (data) {
          if (!data.success) return;
          setTotal(data.total);
          setHasMore(data.has_more);
          if (reset) {
            setEntries(data.entries);
            setOffset(data.entries.length);
          } else {
            setEntries(function (prev) {
              return prev.concat(data.entries);
            });
            setOffset(function (prev) {
              return prev + data.entries.length;
            });
          }
        })
        .catch(function (err) {
          console.error('Error loading journal entries:', err);
        })
        .finally(function () {
          setLoading(false);
        });
    },
    [companyId, offset],
  );

  // Initial load
  useEffect(function () {
    loadEntries(true, '');
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  var handleSearchInput = useCallback(function (e) {
    var value = e.target.value;
    setSearch(value);
    clearTimeout(searchTimeoutRef.current);
    searchTimeoutRef.current = setTimeout(function () {
      debouncedSearchRef.current = value.trim();
      setOffset(0);
      setEntries([]);
      setLoading(true);
      // Use a fresh fetch directly to avoid stale closure on offset
      var url = '/portfolio/api/notes/' + companyId + '?offset=0&limit=10';
      if (value.trim()) url += '&q=' + encodeURIComponent(value.trim());
      fetch(url)
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (!data.success) return;
          setTotal(data.total);
          setHasMore(data.has_more);
          setEntries(data.entries);
          setOffset(data.entries.length);
        })
        .finally(function () { setLoading(false); });
    }, 300);
  }, [companyId]);

  var handleLoadMore = useCallback(function () {
    loadEntries(false, debouncedSearchRef.current);
  }, [loadEntries]);

  return (
    <>
      {/* Search + New Entry */}
      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
        <input
          type="text"
          placeholder="Search entries by content or #tags..."
          value={search}
          onChange={handleSearchInput}
          style={{
            flex: 1,
            minWidth: 200,
            padding: '0.5rem 1rem',
            border: '1px solid var(--gray-200)',
            borderRadius: 8,
            fontSize: '0.9375rem',
          }}
        />
        <a href={newEntryUrl} className="action-btn primary">
          <i className="bi bi-plus-circle" /> New Entry
        </a>
      </div>

      {/* Journal Cards */}
      {entries.map(function (entry) {
        return <JournalCard key={entry.id} entry={entry} />;
      })}

      {/* Load More */}
      {hasMore && (
        <button
          className="journey-notes-load-more"
          onClick={handleLoadMore}
          style={{ display: 'block' }}
        >
          Load more ({offset} of {total}) <i className="bi bi-chevron-down" />
        </button>
      )}

      {/* Empty State */}
      {!loading && entries.length === 0 && (
        <div className="journey-empty-state">
          <i className="bi bi-journal-text" />
          <h4>No Journal Entries Yet</h4>
          <p>
            Journal entries are timestamped observations, earnings reactions, and thesis updates.
          </p>
          <div className="journey-empty-actions">
            <a href={newEntryUrl} className="action-btn primary">
              <i className="bi bi-plus-circle" /> Write First Entry
            </a>
          </div>
        </div>
      )}
    </>
  );
}

function JournalCard({ entry }) {
  var contentHtml = entry.content_html || escapeText(entry.content);
  var viewUrl = '/journal/entry/' + entry.id;

  return (
    <div className="journey-note-card">
      <div className="journey-note-card-header">
        <span className="journey-note-card-date">
          <i className="bi bi-calendar3" /> {entry.created_at}
        </span>
        <div className="journey-note-card-actions">
          {entry.sentiment && (
            <span className={'journey-note-sentiment ' + entry.sentiment}>
              {entry.sentiment}
            </span>
          )}
          <a href={viewUrl} className="journey-note-view-btn" title="View full entry">
            <i className="bi bi-box-arrow-up-right" />
          </a>
        </div>
      </div>
      <div
        className="journey-note-card-content blocknote-content"
        dangerouslySetInnerHTML={{ __html: contentHtml }}
      />
      {entry.tags && entry.tags.length > 0 && (
        <div className="journey-note-tags">
          {entry.tags.slice(0, 6).map(function (t, i) {
            return (
              <span key={i} className="journey-note-tag">
                #{t}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}

function escapeText(text) {
  if (!text) return '';
  var div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
