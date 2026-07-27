import { useState } from "react";
import { STATUS_CONFIG } from "./constants";
import { colors } from "../../tokens";

/**
 * Question Map — colored squares representing each question's status.
 * Clicking a square selects that question in the master-detail panel.
 */
export function StatusHeatmap({ questions, selectedId, onSelect }) {
  return (
    <div style={{
      display: 'flex', flexWrap: 'wrap', gap: 3,
    }}>
      {questions.map((q, i) => (
        <HeatmapCell
          key={q.id}
          question={q}
          index={i}
          isSelected={q.id === selectedId}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}

function HeatmapCell({ question, index, isSelected, onSelect }) {
  const [hovered, setHovered] = useState(false);
  const sc = STATUS_CONFIG[question.status] || STATUS_CONFIG.not_answered;

  return (
    <button
      onClick={() => onSelect(question.id)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      title={`Q${index + 1}: ${question.text.slice(0, 60)}…`}
      style={{
        width: 24, height: 24,
        borderRadius: 4,
        border: isSelected ? `2px solid ${sc.rawColor}` : '1px solid transparent',
        background: sc.rawColor,
        opacity: isSelected ? 1 : hovered ? 0.85 : 0.55,
        cursor: 'pointer',
        transition: 'all .15s',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 9, fontWeight: 700, color: '#fff',
        transform: isSelected ? 'scale(1.15)' : 'scale(1)',
        boxShadow: isSelected ? `0 0 0 3px ${sc.rawColor}22` : 'none',
      }}
    >
      {index + 1}
    </button>
  );
}

/**
 * Keyboard shortcut hint display.
 */
export function KeyHint({ keys }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 3,
      fontSize: 10, color: colors.gray400,
    }}>
      {keys.map((k, i) => (
        <kbd key={i} style={{
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          minWidth: 18, height: 18, padding: '0 4px',
          borderRadius: 3,
          border: `1px solid ${colors.gray200}`,
          background: colors.gray50,
          fontSize: 10, fontWeight: 600,
          color: colors.gray500,
          fontFamily: 'inherit',
        }}>{k}</kbd>
      ))}
    </span>
  );
}
