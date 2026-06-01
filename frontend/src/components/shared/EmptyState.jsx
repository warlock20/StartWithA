import { colors, spacing } from "../../tokens";
import { Icon } from "./Icon";

/**
 * Empty state placeholder with icon, message, and optional CTA.
 *
 * Usage:
 *   <EmptyState icon="inbox" message="No items yet" />
 *   <EmptyState icon="search" message="No results" action="Clear filters" onAction={fn} />
 */
export function EmptyState({ icon, message, action, onAction }) {
  return (
    <div style={{
      display: "flex", flexDirection: "column", alignItems: "center",
      justifyContent: "center", padding: spacing.xl,
      color: colors.textMuted, textAlign: "center",
    }}>
      {icon && (
        <Icon name={icon} style={{ fontSize: 32, marginBottom: 12, opacity: 0.5 }} />
      )}
      <div style={{ fontSize: 13, fontWeight: 500 }}>{message}</div>
      {action && onAction && (
        <button
          onClick={onAction}
          style={{
            marginTop: 12, padding: "6px 14px", borderRadius: 6,
            border: `1px solid ${colors.border}`, background: colors.white,
            color: colors.textSecondary, fontSize: 12, fontWeight: 600,
            cursor: "pointer",
          }}>
          {action}
        </button>
      )}
    </div>
  );
}
