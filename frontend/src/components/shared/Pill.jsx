import { colors } from "../../tokens";

/**
 * Inline badge/tag component.
 * Usage: <Pill color={colors.info500} bg={colors.info50}>Draft</Pill>
 */
export function Pill({ children, color: pillColor, bg, strong = false }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      padding: "2px 8px", borderRadius: 999,
      background: bg || colors.gray100, color: pillColor || colors.gray600,
      fontSize: 11, fontWeight: strong ? 600 : 500,
      whiteSpace: "nowrap",
    }}>{children}</span>
  );
}
