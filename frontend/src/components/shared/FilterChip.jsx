import { useState } from "react";
import { colors, transitions } from "../../tokens";

/**
 * Filter chip with count badge.
 * Usage: <FilterChip active={true} onClick={fn} label="Documents" count={12} />
 */
export function FilterChip({ active, onClick, label, count }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: "inline-flex", alignItems: "center", gap: 6,
        padding: "6px 11px", borderRadius: 999,
        border: `1px solid ${active ? colors.accent : colors.border}`,
        background: active ? colors.accent : (hover ? colors.gray50 : colors.white),
        color: active ? colors.white : colors.gray700,
        fontSize: 12, fontWeight: 600, cursor: "pointer",
        whiteSpace: "nowrap", transition: transitions.fast,
        fontFamily: "inherit",
      }}>
      <span>{label}</span>
      <span style={{
        fontSize: 10.5, fontWeight: 700,
        padding: "1px 6px", borderRadius: 999,
        background: active ? "rgba(255,255,255,.22)" : colors.gray100,
        color: active ? colors.white : colors.gray600,
      }}>{count}</span>
    </button>
  );
}
