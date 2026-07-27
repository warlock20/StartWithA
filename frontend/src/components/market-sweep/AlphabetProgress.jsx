const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');

/**
 * AlphabetProgress — A-Z letter strip showing per-letter review progress.
 *
 * Props:
 *   companies: Array<{ company_name, decision }> — full company list
 */
export function AlphabetProgress({ companies }) {
  // Group companies by first letter
  var letterMap = {};
  LETTERS.forEach(function (l) {
    letterMap[l] = { total: 0, decided: 0 };
  });

  companies.forEach(function (c) {
    var first = (c.company_name || '').charAt(0).toUpperCase();
    if (letterMap[first]) {
      letterMap[first].total++;
      if (c.decision) letterMap[first].decided++;
    }
  });

  // Find the active letter (first letter with pending companies)
  var activeLetter = null;
  for (var i = 0; i < LETTERS.length; i++) {
    var info = letterMap[LETTERS[i]];
    if (info.total > 0 && info.decided < info.total) {
      activeLetter = LETTERS[i];
      break;
    }
  }

  return (
    <div className="sweep-alpha-progress">
      <div className="sweep-alpha-progress__header">
        <span className="sweep-alpha-progress__title">ALPHABETICAL PROGRESS</span>
        {activeLetter && (
          <span className="sweep-alpha-progress__current">
            — Currently in <strong>{activeLetter}</strong>
          </span>
        )}
      </div>
      <div className="sweep-alpha-progress__strip">
        {LETTERS.map(function (letter) {
          var info = letterMap[letter];
          var state = 'empty';
          if (info.total > 0) {
            if (info.decided >= info.total) {
              state = 'completed';
            } else if (letter === activeLetter) {
              state = 'active';
            } else if (info.decided > 0) {
              state = 'completed';
            } else {
              state = 'pending';
            }
          }

          return (
            <div
              key={letter}
              className={'sweep-alpha-letter sweep-alpha-letter--' + state}
              title={
                info.total > 0
                  ? letter + ': ' + info.decided + '/' + info.total + ' reviewed'
                  : letter + ': no companies'
              }
            >
              <span className="sweep-alpha-letter__char">{letter}</span>
              {state === 'active' && info.total > 0 && (
                <span className="sweep-alpha-letter__count">
                  {info.decided}/{info.total}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
