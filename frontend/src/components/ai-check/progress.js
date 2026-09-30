export const VERDICT_LABELS = {
  satisfied: 'Satisfied',
  not_satisfied: 'Not satisfied',
  needs_attention: 'Needs attention',
};

export const MODE_LABELS = { documents: 'My documents', web: 'Web research', both: 'Both' };

const ORDER = ['gathering', 'extracting', 'analyzing'];
const STAGES = [
  { key: 'gather', label: 'Gather', status: 'gathering' },
  { key: 'extract', label: 'Extract', status: 'extracting' },
  { key: 'analyze', label: 'Analyze', status: 'analyzing' },
];

export const TERMINAL = ['completed', 'failed', 'cancelled'];

/** Per-stage display state for the tracker. */
export function stageStates(run) {
  const current = run.status === 'failed' ? run.failed_stage
    : run.status === 'queued' ? (run.mode === 'documents' ? 'extracting' : 'gathering')
      : run.status;
  const currentIndex = run.status === 'completed' ? ORDER.length : ORDER.indexOf(current);
  return STAGES.map((stage, index) => {
    let state;
    if (stage.key === 'gather' && run.mode === 'documents') state = 'skipped';
    else if (index < currentIndex) state = 'done';
    else if (index === currentIndex) state = run.status === 'failed' ? 'failed' : 'active';
    else state = 'pending';
    return { key: stage.key, label: stage.label, state };
  });
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** "27 Sep 2026". Fixed month names: Intl en-GB output varies by ICU version ("Sept"). */
export function formatDate(iso) {
  const d = new Date(iso);
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}
