import { useState, useMemo, useEffect, useRef } from "react";
import { colors, fontSizes } from "../../tokens";
import { STATUS_CONFIG } from "./constants";
import { StatusHeatmap, KeyHint } from "./StatusHeatmap";
import { StatusFilterTabs } from "./StatusFilterTabs";
import { QuestionRow } from "./QuestionRow";
import { AnswerDetail } from "./AnswerDetail";
import { ConclusionPanel } from "./ConclusionPanel";

/**
 * SessionSummary — React Island root component.
 *
 * Renders the interactive portion of the session summary page:
 * Question Map, Conclusion Panel, and Master-Detail split panel.
 */
export function SessionSummary({ config }) {
  const {
    session,
    company,
    questions,
    intrinsicValue,
    intrinsicUnit,
    urls,
  } = config;

  const [selectedId, setSelectedId] = useState(questions[0]?.id || null);
  const [filter, setFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [searchFocused, setSearchFocused] = useState(false);
  const listRef = useRef(null);

  // Filtered questions
  const filtered = useMemo(() => {
    let qs = questions;
    if (filter !== 'all') qs = qs.filter(q => q.status === filter);
    if (search.trim()) {
      const s = search.toLowerCase();
      qs = qs.filter(q =>
        q.text.toLowerCase().includes(s) ||
        (q.answerHtml || '').toLowerCase().includes(s)
      );
    }
    return qs;
  }, [questions, filter, search]);

  // Auto-select first when filter changes and current selection is not in filtered list
  useEffect(() => {
    if (filtered.length > 0 && !filtered.find(q => q.id === selectedId)) {
      setSelectedId(filtered[0].id);
    }
  }, [filtered, selectedId]);

  // Keyboard navigation
  useEffect(() => {
    const handler = (e) => {
      if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;
      const idx = filtered.findIndex(q => q.id === selectedId);
      if (e.key === 'ArrowDown' || e.key === 'j') {
        e.preventDefault();
        if (idx < filtered.length - 1) setSelectedId(filtered[idx + 1].id);
      } else if (e.key === 'ArrowUp' || e.key === 'k') {
        e.preventDefault();
        if (idx > 0) setSelectedId(filtered[idx - 1].id);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [filtered, selectedId]);

  // Scroll selected row into view
  useEffect(() => {
    if (!listRef.current) return;
    const row = listRef.current.querySelector(`[data-qid="${selectedId}"]`);
    if (row) row.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [selectedId]);

  const selectedQuestion = questions.find(q => q.id === selectedId);
  const selectedIndex = questions.findIndex(q => q.id === selectedId);

  // Handle heatmap click — jump to question, reset filters
  const handleHeatmapSelect = (id) => {
    setSelectedId(id);
    setFilter('all');
    setSearch('');
  };

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: 16,
    }}>
      {/* ── Question Map ── */}
      <div style={{
        display: 'flex', flexDirection: 'column', justifyContent: 'center',
        gap: 6,
        padding: '10px 16px',
        background: '#fff',
        border: `1px solid ${colors.border}`,
        borderRadius: 8,
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <span style={{ fontSize: fontSizes.xs, fontWeight: 600, color: colors.gray500 }}>
            Question Map
          </span>
          <KeyHint keys={['↑', '↓']} />
        </div>
        <StatusHeatmap
          questions={questions}
          selectedId={selectedId}
          onSelect={handleHeatmapSelect}
        />
      </div>

      {/* ── Conclusion ── */}
      <ConclusionPanel
        conclusion={session.conclusion}
        intrinsicValue={intrinsicValue}
        intrinsicUnit={intrinsicUnit}
        saveConclusionUrl={urls.saveConclusion}
        saveValuationUrl={urls.saveIntrinsicValue}
        companyId={company.id}
      />

      {/* ── Master-Detail Split Panel ── */}
      <div style={{
        display: 'flex',
        background: '#fff',
        border: `1px solid ${colors.border}`,
        borderRadius: 12,
        overflow: 'hidden',
        height: 520,
      }}>
        {/* Left: question list */}
        <div style={{
          width: 420,
          flexShrink: 0,
          display: 'flex', flexDirection: 'column',
          borderRight: `1px solid ${colors.border}`,
          background: colors.gray50,
        }}>
          {/* List header: search + filters */}
          <div style={{
            padding: '12px 14px',
            borderBottom: `1px solid ${colors.gray100}`,
            display: 'flex', flexDirection: 'column', gap: 8,
          }}>
            {/* Search */}
            <div style={{ position: 'relative' }}>
              <i className="bi bi-search" style={{
                position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)',
                fontSize: fontSizes.xs, color: searchFocused ? colors.gray600 : colors.gray400,
                transition: 'color .15s',
              }} />
              <input
                type="text"
                placeholder="Search questions..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                onFocus={() => setSearchFocused(true)}
                onBlur={() => setSearchFocused(false)}
                style={{
                  width: '100%',
                  padding: '7px 10px 7px 30px',
                  border: `1px solid ${searchFocused ? colors.accent : colors.gray200}`,
                  borderRadius: 7,
                  fontSize: fontSizes.xs,
                  color: colors.gray800,
                  background: '#fff',
                  outline: 'none',
                  transition: 'border-color .15s, box-shadow .15s',
                  boxShadow: searchFocused ? '0 0 0 3px rgba(45,106,79,.08)' : 'none',
                  fontFamily: 'inherit',
                }}
              />
            </div>
            {/* Filters */}
            <StatusFilterTabs
              questions={questions}
              activeFilter={filter}
              onChange={setFilter}
            />
          </div>

          {/* Question list */}
          <div ref={listRef} style={{
            flex: 1, overflow: 'auto',
          }}>
            {filtered.length === 0 ? (
              <div style={{
                padding: '32px 20px', textAlign: 'center',
                color: colors.gray400, fontSize: fontSizes.sm,
              }}>
                <i className="bi bi-search" style={{ fontSize: fontSizes.xxl, marginBottom: 8, display: 'block', opacity: 0.4 }} />
                No questions match this filter.
              </div>
            ) : (
              filtered.map((q) => {
                const globalIdx = questions.findIndex(qq => qq.id === q.id);
                return (
                  <div key={q.id} data-qid={q.id}>
                    <QuestionRow
                      question={q}
                      index={globalIdx}
                      isSelected={q.id === selectedId}
                      onClick={() => setSelectedId(q.id)}
                    />
                  </div>
                );
              })
            )}
          </div>

          {/* List footer */}
          <div style={{
            padding: '8px 14px',
            borderTop: `1px solid ${colors.gray100}`,
            fontSize: fontSizes.xs, color: colors.gray400,
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <span>{filtered.length} of {questions.length} questions</span>
            <KeyHint keys={['↑', '↓', 'j', 'k']} />
          </div>
        </div>

        {/* Right: detail panel */}
        <div style={{
          flex: 1, minWidth: 0,
          display: 'flex', flexDirection: 'column',
          background: '#fff',
        }}>
          {selectedQuestion ? (
            <AnswerDetail
              question={selectedQuestion}
              index={selectedIndex}
              editAnswerUrl={urls.editAnswer}
            />
          ) : (
            <div style={{
              flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: colors.gray400,
            }}>
              <div style={{ textAlign: 'center' }}>
                <i className="bi bi-clipboard-data" style={{ fontSize: 40, marginBottom: 12, opacity: 0.3 }} />
                <div style={{ fontSize: fontSizes.sm, fontWeight: 600 }}>Select a question</div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
