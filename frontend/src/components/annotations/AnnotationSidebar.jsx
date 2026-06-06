import { useMemo } from 'react';

/**
 * Annotation sidebar list — grouped by page number.
 * Rendered via React Portal into #annotation-sidebar-list.
 */
export function AnnotationSidebar({ annotations, onScrollTo }) {
  const groupedByPage = useMemo(() => {
    const pages = {};
    annotations.forEach((a) => {
      if (!pages[a.page_number]) pages[a.page_number] = [];
      pages[a.page_number].push(a);
    });
    return Object.entries(pages).sort(([a], [b]) => a - b);
  }, [annotations]);

  if (annotations.length === 0) {
    return (
      <div className="annotation-sidebar-empty">
        <i className="bi bi-highlighter me-1" /> No notes yet.
        <br />
        <small>Select text on the PDF to highlight, or use &ldquo;Drop Pin&rdquo; for pins.</small>
      </div>
    );
  }

  return (
    <>
      {groupedByPage.map(([pageNum, items]) => (
        <div key={pageNum}>
          <div className="annotation-sidebar-group-label">Page {pageNum}</div>
          {items.map((a) => (
            <div
              key={a.id}
              className="annotation-sidebar-item"
              onClick={() => onScrollTo(parseInt(pageNum), a.id)}
            >
              {a.annotation_type === 'highlight' && a.anchor_text && (
                <div className="sidebar-item-quote">
                  <i className="bi bi-highlighter text-warning me-1" />
                  {truncate(a.anchor_text, 60)}
                </div>
              )}
              <div className="sidebar-item-content">
                {a.annotation_type !== 'highlight' && (
                  <i className="bi bi-pin-angle text-danger me-1" />
                )}
                {a.content}
              </div>
              <div className="sidebar-item-meta">
                <span>{a.created_at ? new Date(a.created_at).toLocaleDateString() : ''}</span>
                <span className="badge bg-light text-dark border">{a.scope}</span>
              </div>
            </div>
          ))}
        </div>
      ))}
    </>
  );
}

function truncate(text, maxLen) {
  if (!text) return '';
  return text.length > maxLen ? text.substring(0, maxLen) + '...' : text;
}
