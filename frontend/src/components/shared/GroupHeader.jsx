import { colors } from "../../tokens";
import { Icon } from "./Icon";

/**
 * Collapsible group/section header.
 * Usage: <GroupHeader label="PDFs" count={5} collapsed={false} onToggle={fn} />
 */
export function GroupHeader({ label, count, collapsed, onToggle }) {
  return (
    <button
      onClick={onToggle}
      style={{
        width: "100%", textAlign: "left",
        display: "flex", alignItems: "center", gap: 8,
        padding: "10px 18px",
        background: colors.gray50,
        border: "none", borderTop: `1px solid ${colors.border}`,
        cursor: "pointer", fontFamily: "inherit",
      }}>
      <Icon name={collapsed ? "chevron-right" : "chevron-down"} style={{ fontSize: 11, color: colors.gray500 }} />
      <span style={{
        fontSize: 11.5, fontWeight: 700, color: colors.gray700,
        textTransform: "uppercase", letterSpacing: ".05em",
      }}>{label}</span>
      <span style={{
        fontSize: 11, fontWeight: 600, color: colors.gray500,
        padding: "1px 7px", borderRadius: 999, background: colors.gray100,
      }}>{count}</span>
    </button>
  );
}
