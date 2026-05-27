import { STATUS_CONFIG } from "./constants";
import { colors, fontSizes } from "../../tokens";

/**
 * Detail panel showing the selected question's answer.
 * Answer HTML is pre-rendered server-side via blocknote_to_html.
 */
export function AnswerDetail({ question, index, editAnswerUrl }) {
  const sc = STATUS_CONFIG[question.status] || STATUS_CONFIG.not_answered;

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%',
    }}>
      {/* Question header */}
      <div style={{
        padding: '20px 24px 16px',
        borderBottom: `1px solid ${colors.gray100}`,
        background: '#fff',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          marginBottom: 10,
        }}>
          <span style={{
            fontFamily: 'var(--font-mono)',
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            width: 28, height: 28, borderRadius: 7,
            background: sc.rawColor, color: '#fff',
            fontSize: fontSizes.xs, fontWeight: 700,
          }}>{index + 1}</span>
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 4,
            padding: '3px 10px',
            borderRadius: 6,
            fontSize: fontSizes.xs, fontWeight: 600,
            color: sc.rawColor,
            background: sc.bg,
            border: `1px solid ${sc.border}`,
            lineHeight: 1.5, whiteSpace: 'nowrap',
          }}>
            <i className={`bi bi-${sc.icon}`} style={{ fontSize: fontSizes.xs }} />
            {sc.label}
          </span>
        </div>
        <h3 style={{
          fontSize: fontSizes.base, fontWeight: 700, color: colors.gray900,
          lineHeight: 1.4, letterSpacing: '-0.01em',
          margin: 0,
        }}>{question.text}</h3>
        {question.parent && (
          <div style={{
            marginTop: 6, fontSize: fontSizes.xs, color: colors.gray400,
          }}>
            Sub-item of: {question.parent}
          </div>
        )}
      </div>

      {/* Answer body */}
      <div style={{
        flex: 1, overflow: 'auto',
        padding: '20px 24px 24px',
      }}>
        {question.answerHtml ? (
          <div
            className="answer-text"
            style={{
              fontSize: fontSizes.sm, lineHeight: 1.75, color: colors.gray700,
            }}
            dangerouslySetInnerHTML={{ __html: question.answerHtml }}
          />
        ) : (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center',
            justifyContent: 'center', height: '100%',
            color: colors.gray400, textAlign: 'center',
          }}>
            <i className="bi bi-chat-left-text" style={{ fontSize: 36, marginBottom: 12, opacity: 0.5 }} />
            <div style={{ fontSize: fontSizes.sm, fontWeight: 600, color: colors.gray500, marginBottom: 4 }}>
              No answer yet
            </div>
            <div style={{ fontSize: fontSizes.sm }}>
              Click "Edit Answer" to add your analysis.
            </div>
          </div>
        )}
      </div>

      {/* Footer actions */}
      <div style={{
        padding: '12px 24px',
        borderTop: `1px solid ${colors.gray100}`,
        display: 'flex', justifyContent: 'flex-end', gap: 8,
        background: '#fff',
      }}>
        <a
          href={editAnswerUrl.replace('{itemId}', question.id)}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            padding: '5px 10px', borderRadius: 8,
            border: `1px solid ${colors.border}`,
            background: '#fff', color: colors.gray700,
            fontWeight: 600, fontSize: fontSizes.xs,
            cursor: 'pointer', textDecoration: 'none',
            transition: 'all .15s',
          }}
        >
          <i className="bi bi-pencil" style={{ fontSize: fontSizes.xs }} />
          <span>Edit Answer</span>
        </a>
      </div>
    </div>
  );
}
