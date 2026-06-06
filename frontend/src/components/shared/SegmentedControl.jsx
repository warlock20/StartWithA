import { colors } from "../../tokens";
import { Icon } from "./Icon";

/**
 * Toggle button group control.
 * Usage: <SegmentedControl options={[{id:'list',label:'List'},{id:'grid',icon:'grid'}]} value="list" onChange={fn} />
 */
export function SegmentedControl({ options, value, onChange }) {
  return (
    <div style={{
      display: "flex", gap: 0,
      border: `1px solid ${colors.border}`, borderRadius: 8,
      padding: 2, background: colors.white,
    }}>
      {options.map((o) => (
        <button
          key={o.id}
          onClick={() => onChange(o.id)}
          style={{
            padding: o.icon ? undefined : "5px 11px",
            width: o.icon ? 28 : undefined,
            height: o.icon ? 26 : undefined,
            borderRadius: 6, border: "none",
            fontSize: o.icon ? 13 : 11.5,
            fontWeight: 600, cursor: "pointer",
            fontFamily: "inherit",
            background: value === o.id ? colors.gray100 : "transparent",
            color: value === o.id ? colors.gray900 : colors.gray500,
            display: "inline-flex", alignItems: "center", justifyContent: "center",
          }}>
          {o.icon ? <Icon name={o.icon} /> : o.label}
        </button>
      ))}
    </div>
  );
}
