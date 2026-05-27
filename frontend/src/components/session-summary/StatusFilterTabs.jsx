import { useMemo } from "react";
import { STATUS_CONFIG, FILTER_TABS } from "./constants";
import { colors, fontSizes } from "../../tokens";

/**
 * Status filter tabs — filter the question list by satisfaction status.
 */
export function StatusFilterTabs({ questions, activeFilter, onChange }) {
  const counts = useMemo(() => {
    const c = { all: questions.length };
    questions.forEach(q => { c[q.status] = (c[q.status] || 0) + 1; });
    return c;
  }, [questions]);

  return (
    <div style={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
      {FILTER_TABS.map(tab => {
        const count = counts[tab.id] || 0;
        if (tab.id !== 'all' && count === 0) return null;
        const isActive = activeFilter === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            style={{
              display: 'flex', alignItems: 'center', gap: 5,
              padding: '5px 10px',
              borderRadius: 6,
              border: 'none',
              background: isActive
                ? (tab.id === 'all' ? colors.gray800 : tab.color)
                : 'transparent',
              color: isActive ? '#fff' : colors.gray500,
              fontWeight: isActive ? 600 : 500,
              fontSize: fontSizes.xs,
              cursor: 'pointer',
              transition: 'all .12s',
            }}
          >
            {tab.label}
            <span style={{
              fontSize: 10, fontWeight: 700,
              opacity: isActive ? 0.8 : 0.6,
              background: isActive ? 'rgba(255,255,255,.2)' : colors.gray100,
              color: isActive ? '#fff' : colors.gray500,
              padding: '0 5px', borderRadius: 4,
              lineHeight: '18px',
            }}>{count}</span>
          </button>
        );
      })}
    </div>
  );
}
