/**
 * ISIN helpers, mirroring app/utils/isin.py. The server re-validates;
 * this only lets the form say "wrong" before the round trip.
 */
export function normalizeIsin(value) {
  if (value == null) return '';
  return String(value).trim().toUpperCase();
}

export function isValidIsin(value) {
  if (typeof value !== 'string' || !/^[A-Z]{2}[A-Z0-9]{9}[0-9]$/.test(value)) return false;
  const expanded = value.slice(0, 11).split('')
    .map((ch) => (/[0-9]/.test(ch) ? ch : String(ch.charCodeAt(0) - 55)))
    .join('');
  let total = 0;
  for (let i = 0; i < expanded.length; i += 1) {
    let digit = Number(expanded[expanded.length - 1 - i]);
    if (i % 2 === 0) {
      digit *= 2;
      if (digit > 9) digit -= 9;
    }
    total += digit;
  }
  return (total + Number(value[11])) % 10 === 0;
}

export function invalidIsinMessage(isin) {
  return `"${isin}" is not a valid ISIN. It must be 12 characters with a correct check digit.`;
}
