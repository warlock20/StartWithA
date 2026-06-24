import { useState } from "react";
import { colors, transitions } from "../../tokens";
import { Icon } from "./Icon";

/**
 * Button with primary/secondary/ghost variants.
 * Usage: <Btn icon="plus" kind="primary" onClick={fn}>Add Item</Btn>
 */
export function Btn({ icon, children, kind = "secondary", onClick, size = "md" }) {
  const [hover, setHover] = useState(false);
  const styles = {
    primary: {
      background: hover ? colors.accent700 : colors.accent,
      color: colors.white, border: "1px solid transparent",
    },
    secondary: {
      background: hover ? colors.gray50 : colors.white,
      color: colors.gray700, border: `1px solid ${colors.border}`,
    },
    ghost: {
      background: hover ? colors.gray100 : "transparent",
      color: colors.gray700, border: "1px solid transparent",
    },
  };
  const pad = size === "sm" ? "6px 10px" : "8px 14px";
  const fs = size === "sm" ? 12.5 : 13;
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: "inline-flex", alignItems: "center", gap: 6,
        padding: pad, borderRadius: 10,
        fontWeight: 600, fontSize: fs, cursor: "pointer",
        transition: transitions.fast, whiteSpace: "nowrap",
        fontFamily: "inherit",
        ...styles[kind],
      }}>
      {icon && <Icon name={icon} />}
      <span>{children}</span>
    </button>
  );
}
