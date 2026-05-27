import { useState } from "react";
import { colors, fontSizes } from "../../tokens";

/**
 * Conclusion & Valuation panel.
 * Displays the session conclusion with inline editing,
 * and shows the intrinsic value badge.
 */
export function ConclusionPanel({
  conclusion,
  intrinsicValue,
  intrinsicUnit,
  saveConclusionUrl,
  saveValuationUrl,
  companyId,
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [text, setText] = useState(conclusion || '');
  const [saving, setSaving] = useState(false);

  const unitLabel = intrinsicUnit === 1000000 ? 'M'
    : intrinsicUnit === 1000000000 ? 'B'
    : intrinsicUnit === 1000000000000 ? 'T'
    : '';

  const handleSave = async () => {
    setSaving(true);
    try {
      const formData = new FormData();
      formData.append('conclusion', text);
      const resp = await fetch(saveConclusionUrl, {
        method: 'POST',
        body: formData,
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      });
      if (resp.ok) {
        setIsEditing(false);
        if (window.showToast) {
          window.showToast('Conclusion saved successfully.', 'success');
        }
      }
    } catch (err) {
      if (window.showToast) {
        window.showToast('Error saving conclusion.', 'error');
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{
      background: '#fff',
      border: `1px solid ${colors.border}`,
      borderRadius: 12,
      overflow: 'hidden',
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '14px 20px',
        borderBottom: `1px solid ${colors.gray100}`,
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          fontSize: fontSizes.sm, fontWeight: 700, color: colors.gray900,
        }}>
          <i className="bi bi-journal-richtext" style={{ color: colors.gray400 }} />
          Conclusion & Valuation
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {intrinsicValue && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '4px 12px',
              background: colors.accent50,
              border: `1px solid ${colors.accent100}`,
              borderRadius: 7,
            }}>
              <i className="bi bi-calculator" style={{ fontSize: fontSizes.xs, color: colors.accent }} />
              <span style={{
                fontFamily: 'var(--font-mono)',
                fontSize: fontSizes.sm, fontWeight: 700, color: colors.accent,
              }}>${intrinsicValue}{unitLabel}</span>
              <span style={{ fontSize: 10, color: colors.gray400, fontWeight: 500 }}>Intrinsic</span>
            </div>
          )}
          <button
            onClick={() => setIsEditing(!isEditing)}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              padding: '5px 10px', borderRadius: 8,
              border: 'none',
              background: 'transparent', color: colors.gray600,
              fontWeight: 600, fontSize: fontSizes.xs,
              cursor: 'pointer',
              transition: 'all .15s',
            }}
          >
            <i className={`bi bi-${isEditing ? 'x' : 'pencil'}`} style={{ fontSize: fontSizes.xs }} />
            {isEditing ? 'Close' : 'Edit'}
          </button>
        </div>
      </div>

      <div style={{ padding: '16px 20px' }}>
        {isEditing ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <textarea
              value={text}
              onChange={e => setText(e.target.value)}
              rows={4}
              style={{
                width: '100%', padding: '12px 14px',
                border: `1px solid ${colors.border}`, borderRadius: 8,
                fontSize: fontSizes.sm, lineHeight: 1.6, resize: 'vertical',
                outline: 'none', fontFamily: 'inherit',
                color: colors.gray700,
              }}
              onFocus={e => e.target.style.borderColor = colors.accent}
              onBlur={e => e.target.style.borderColor = colors.border}
            />
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                onClick={handleSave}
                disabled={saving}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 6,
                  padding: '7px 14px', borderRadius: 8,
                  border: '1px solid transparent',
                  background: colors.accent, color: '#fff',
                  fontWeight: 600, fontSize: fontSizes.sm,
                  cursor: saving ? 'not-allowed' : 'pointer',
                  opacity: saving ? 0.5 : 1,
                  transition: 'all .15s',
                  boxShadow: '0 1px 2px rgba(0,0,0,.1)',
                }}
              >
                <i className="bi bi-save" style={{ fontSize: fontSizes.sm }} />
                {saving ? 'Saving…' : 'Save Conclusion'}
              </button>
            </div>
          </div>
        ) : conclusion ? (
          <div style={{
            fontSize: fontSizes.sm, lineHeight: 1.7, color: colors.gray600,
          }}>{conclusion}</div>
        ) : (
          <div style={{
            fontSize: fontSizes.sm, color: colors.gray400, fontStyle: 'italic',
          }}>No conclusion added yet. Click Edit to add your assessment.</div>
        )}
      </div>
    </div>
  );
}
