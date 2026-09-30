import { MODE_LABELS, VERDICT_LABELS, formatDate } from './progress';

const t = (text) => [{ type: 'text', text, styles: {} }];
const para = (text) => ({ type: 'paragraph', content: t(text) });
const bullet = (text) => ({ type: 'bulletListItem', content: t(text) });
const heading = (text, level = 3) => ({ type: 'heading', props: { level }, content: t(text) });

/** BlockNote blocks summarising a completed AI check run, for "Insert into answer". */
export function buildAnswerBlocks(run) {
  const result = run.result || {};
  const blocks = [heading(`AI check · ${formatDate(run.created_at)} · ${MODE_LABELS[run.mode] || run.mode}`)];
  if (result.summary) blocks.push(para(result.summary));
  (result.calculation || []).forEach((line) => {
    const refs = line.evidence && line.evidence.length ? ` [${line.evidence.join(', ')}]` : '';
    const note = line.note ? ` (${line.note})` : '';
    blocks.push(bullet(`${line.label}: ${line.value}${note}${refs}`));
  });
  if (result.suggested_verdict) {
    blocks.push(para(`Suggested verdict: ${VERDICT_LABELS[result.suggested_verdict]}. ${result.verdict_reason || ''}`.trim()));
  }
  (result.gaps || []).forEach((gap) => blocks.push(bullet(`Missing: ${gap}`)));
  if ((run.evidence || []).length) {
    blocks.push(heading('Sources'));
    run.evidence.forEach((e) => {
      const where = e.location ? `${e.source_title}, ${e.location}` : e.source_title;
      blocks.push(bullet(`${e.label} · ${e.metric}: ${e.value} · ${where} · ${e.verified ? 'verified' : 'unverified'}`));
    });
  }
  return blocks;
}

/** Append blocks to the page's BlockNote answer editor. False when no editor is on the page. */
export function insertIntoAnswer(blocks) {
  const editor = window.blockNoteEditorInstance && window.blockNoteEditorInstance.editor;
  if (!editor) return false;
  const doc = editor.document;
  editor.insertBlocks(blocks, doc[doc.length - 1], 'after');
  return true;
}
