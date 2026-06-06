import { useState } from "react";
import { colors, transitions } from "../../tokens";
import { Icon } from "./Icon";

/**
 * Icon-only button with hover states.
 * Usage: <IconBtn icon="trash" label="Delete" onClick={fn} danger />
 */
export function IconBtn({ icon, label, onClick, danger, color: btnColor }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      title={label}
      aria-label={label}
      style={{
        width: 30, height: 30, borderRadius: 8,
        border: "none",
        background: hover ? (danger ? colors.danger50 : colors.gray100) : "transparent",
        color: hover && danger ? colors.danger500 : (btnColor || colors.gray500),
        cursor: "pointer", display: "inline-flex", alignItems: "center", justifyContent: "center",
        fontSize: 15, transition: transitions.fast,
      }}>
      <Icon name={icon} />
    </button>
  );
}
