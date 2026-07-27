import { useState } from "react";
import { STATUS_CONFIG } from "./constants";
import { colors, fontSizes } from "../../tokens";

/**
 * A single row in the question list panel.
 * Shows question number, status dot, and truncated text.
 */
export function QuestionRow({ question, index, isSelected, onClick }) {
  const [hov, setHov] = useState(false);
  const sc = STATUS_CONFIG[question.status] || STATUS_CONFIG.not_answered;

  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: 'flex', alignItems: 'center', gap: 10,
        width: '100%',
        padding: '11px 14px',
        border: 'none',
        borderLeft: `3px solid ${isSelected ? sc.rawColor : 'transparent'}`,
        background: isSelected ? sc.bg : hov ? colors.gray50 : 'transparent',
        cursor: 'pointer',
        textAlign: 'left',
        transition: 'all .1s',
        borderBottom: `1px solid ${colors.gray100}`,
        fontFamily: 'inherit',
      }}
    >
      {/* Number */}
      <span style={{
        fontSize: '0.65rem', fontWeight: 600,
        color: isSelected ? sc.rawColor : colors.gray400,
        width: 22, flexShrink: 0, textAlign: 'center',
      }}>{index + 1}</span>

      {/* Status dot */}
      <div style={{
        width: 8, height: 8, borderRadius: '50%',
        background: sc.rawColor,
        flexShrink: 0,
        opacity: isSelected ? 1 : 0.7,
      }} />

      {/* Question text */}
      <span style={{
        flex: 1, minWidth: 0,
        fontSize: fontSizes.sm,
        fontWeight: isSelected ? 600 : 400,
        color: isSelected ? colors.gray900 : colors.gray700,
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        lineHeight: 1.3,
      }}>{question.text}</span>
    </button>
  );
}
