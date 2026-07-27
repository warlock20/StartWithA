import { useState, useEffect } from 'react';

/**
 * CompanyAnnotationsPanel — React island for Library > Annotations section.
 *
 * Replaces the loadCompanyAnnotations() function from company-dashboard.js.
 * Fetches annotations, groups by resource document, renders clickable items
 * that open the PDF viewer at the annotated page.
 *
 * Props (via config):
 *   companyId — numeric company ID
 */
export function CompanyAnnotationsPanel({ companyId }) {
  var [groups, setGroups] = useState([]);
  var [totalCount, setTotalCount] = useState(0);
  var [loading, setLoading] = useState(true);
  var [error, setError] = useState(null);

  useEffect(
    function () {
      fetch('/companies/api/' + companyId + '/annotations')
        .then(function (r) {
          return r.json();
        })
        .then(function (result) {
          if (!result.success) {
            setError('Failed to load annotations.');
            return;
          }

          var annotations = result.data.annotations;
          setTotalCount(annotations.length);

          // Group by resource
          var groupMap = {};
          var order = [];
          annotations.forEach(function (a) {
            var key = a.resource_id;
            if (!groupMap[key]) {
              groupMap[key] = {
                title: a.resource_title,
                resourceId: a.resource_id,
                items: [],
              };
              order.push(key);
            }
            groupMap[key].items.push(a);
          });

          setGroups(
            order.map(function (key) {
              return groupMap[key];
            }),
          );
        })
        .catch(function (err) {
          console.error('Failed to load company annotations:', err);
          setError('Failed to load annotations.');
        })
        .finally(function () {
          setLoading(false);
        });
    },
    [companyId],
  );

  if (loading) {
    return (
      <div id="company-annotations-panel">
        <AnnotationsHeader count={0} />
        <div className="text-center text-muted py-4">
          <span className="spinner-border spinner-border-sm me-1" /> Loading annotations...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div id="company-annotations-panel">
        <AnnotationsHeader count={0} />
        <div className="text-danger small">{error}</div>
      </div>
    );
  }

  if (totalCount === 0) {
    return (
      <div id="company-annotations-panel">
        <AnnotationsHeader count={0} />
        <div className="text-center text-muted py-4">
          <i className="bi bi-pin-angle" style={{ fontSize: '1.5rem' }} />
          <p className="mt-2 mb-0 small">
            No annotations yet. Open a PDF document and add pins or highlights to get started.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div id="company-annotations-panel">
      <AnnotationsHeader count={totalCount} />
      {groups.map(function (group) {
        return <AnnotationGroup key={group.resourceId} group={group} />;
      })}
    </div>
  );
}

function AnnotationsHeader({ count }) {
  return (
    <div className="d-flex justify-content-between align-items-center mb-3">
      <div>
        <h6 className="mb-0">
          <i className="bi bi-pin-angle me-1" />
          Document Annotations
        </h6>
        <small className="text-muted">All pins and highlights across your documents</small>
      </div>
      {count > 0 && <span className="badge bg-secondary">{count}</span>}
    </div>
  );
}

function AnnotationGroup({ group }) {
  var viewerUrl = '/companies/resources/' + group.resourceId + '/viewer';

  return (
    <div className="company-section-card mb-3">
      <div
        className="company-section-card-header d-flex justify-content-between align-items-center"
        style={{ padding: '0.625rem 1rem' }}
      >
        <h6 className="mb-0" style={{ fontSize: '0.85rem' }}>
          <i className="bi bi-file-earmark-pdf-fill text-danger me-1" />
          {group.title}
          <span
            className="badge bg-light text-dark border ms-1"
            style={{ fontSize: '0.65rem' }}
          >
            {group.items.length}
          </span>
        </h6>
        <a
          href={viewerUrl}
          target="_blank"
          rel="noreferrer"
          className="btn btn-sm btn-outline-secondary border-0"
          title="Open document"
        >
          <i className="bi bi-box-arrow-up-right" />
        </a>
      </div>
      <div style={{ maxHeight: 300, overflowY: 'auto' }}>
        {group.items.map(function (a, i) {
          return <AnnotationItem key={a.id || i} annotation={a} />;
        })}
      </div>
    </div>
  );
}

function AnnotationItem({ annotation }) {
  var a = annotation;
  var isHighlight = a.annotation_type === 'highlight';
  var date = a.created_at ? new Date(a.created_at).toLocaleDateString() : '';
  var truncatedContent =
    a.content.length > 100 ? a.content.substring(0, 100) + '...' : a.content;
  var truncatedAnchor =
    a.anchor_text && a.anchor_text.length > 80
      ? a.anchor_text.substring(0, 80) + '...'
      : a.anchor_text;

  function handleClick() {
    window.open(
      '/companies/resources/' + a.resource_id + '/viewer#page=' + a.page_number,
      '_blank',
    );
  }

  return (
    <div
      className="d-flex align-items-start py-2 px-3 border-bottom annotation-dashboard-item"
      style={{ cursor: 'pointer', transition: 'background 0.15s' }}
      onClick={handleClick}
      onMouseEnter={function (e) {
        e.currentTarget.style.background = '#f8f9fa';
      }}
      onMouseLeave={function (e) {
        e.currentTarget.style.background = '';
      }}
    >
      <div className="flex-grow-1" style={{ minWidth: 0 }}>
        {isHighlight && truncatedAnchor && (
          <div
            style={{
              fontSize: '0.75rem',
              color: '#777',
              borderLeft: '2px solid #fbc02d',
              padding: '0.125rem 0.375rem',
              marginBottom: '0.25rem',
              background: '#fffde7',
              borderRadius: '0 2px 2px 0',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {truncatedAnchor}
          </div>
        )}
        <div className="small">
          {isHighlight ? (
            <i className="bi bi-highlighter text-warning me-1" />
          ) : (
            <i className="bi bi-pin-angle text-danger me-1" />
          )}
          <span style={{ color: 'var(--gray-500)', fontSize: '0.75rem' }}>
            p.{a.page_number}
          </span>{' '}
          {truncatedContent}
        </div>
        <div style={{ fontSize: '0.7rem', color: '#6c757d', marginTop: '0.125rem' }}>
          {date}{' '}
          <span className="badge bg-light text-dark border" style={{ fontSize: '0.6rem' }}>
            {a.scope}
          </span>
        </div>
      </div>
    </div>
  );
}
