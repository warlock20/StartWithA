import { colors } from "../../tokens";
import { Icon } from "./Icon";

export const TYPE_META = {
  pdf:  { color: colors.danger500, bg: colors.danger50,  icon: "file-earmark-pdf-fill",  label: "PDF" },
  txt:  { color: colors.info500,   bg: colors.info50,    icon: "file-earmark-text-fill", label: "TXT" },
  doc:  { color: colors.info500,   bg: colors.info50,    icon: "file-earmark-word-fill", label: "DOC" },
  docx: { color: colors.info500,   bg: colors.info50,    icon: "file-earmark-word-fill", label: "DOCX" },
  xlsx: { color: colors.success500,bg: colors.success50, icon: "file-earmark-excel-fill",label: "XLSX" },
  xls:  { color: colors.success500,bg: colors.success50, icon: "file-earmark-excel-fill",label: "XLS" },
  csv:  { color: colors.success500,bg: colors.success50, icon: "file-earmark-spreadsheet",label: "CSV" },
  html: { color: colors.warning500,bg: colors.warning50, icon: "file-earmark-code-fill", label: "HTML" },
  link: { color: colors.accent,    bg: colors.accent50,  icon: "link-45deg",             label: "LINK" },
};

/**
 * Colored icon circle for file types.
 * Usage: <FileGlyph type="pdf" size={36} />
 */
export function FileGlyph({ type, size = 36 }) {
  const m = TYPE_META[type] || TYPE_META.pdf;
  return (
    <div style={{
      width: size, height: size, borderRadius: 8,
      background: m.bg, color: m.color,
      display: "flex", alignItems: "center", justifyContent: "center",
      fontSize: size * 0.5, flexShrink: 0,
    }}>
      <Icon name={m.icon} />
    </div>
  );
}
