// Money arrives from the API as Decimal strings. Never do tax math here; only display.

type Num = string | number | null | undefined;

export function toNumber(v: Num): number | null {
  if (v === null || v === undefined || v === '') return null;
  const n = typeof v === 'number' ? v : Number(String(v).replace(/[$,%\s]/g, ''));
  return Number.isFinite(n) ? n : null;
}

export function formatMoney(v: Num, opts: { cents?: boolean } = {}): string {
  const n = toNumber(v);
  if (n === null) return '—';
  const digits = opts.cents ? 2 : 0;
  const s = Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return `${n < 0 ? '-' : ''}$${s}`;
}

/** 50 -> "50%", "49.50" -> "49.5%", 0.05 with {fraction:true} -> "5%" */
export function formatPercent(v: Num, opts: { fraction?: boolean } = {}): string {
  const n = toNumber(v);
  if (n === null) return '—';
  const pct = opts.fraction ? n * 100 : n;
  return `${Number(pct.toFixed(2))}%`;
}

export function formatConfidence(v: Num): string {
  const n = toNumber(v);
  return n === null ? '—' : n.toFixed(2);
}

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const SHORT = MONTHS.map((m) => m.slice(0, 3));

/** "2025-08-03" -> "August 3, 2025" ({short:true} -> "Aug 3, 2025"). Parses as a calendar date, no timezone shift. */
export function formatDate(iso: string | null | undefined, opts: { short?: boolean } = {}): string {
  if (!iso) return '—';
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  const [, y, mo, d] = m;
  const names = opts.short ? SHORT : MONTHS;
  return `${names[Number(mo) - 1]} ${Number(d)}, ${y}`;
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleTimeString('en-US', { hour12: false });
}

export const SCENARIO_LABELS: Record<string, string> = {
  lump_sum_now: 'Lump sum now',
  minimums_then_balloon: 'Minimums, then balloon',
  even_spread: 'Even spread',
  fill_bracket: 'Fill the bracket',
};
export const scenarioLabel = (name: string) => SCENARIO_LABELS[name] ?? name.replace(/_/g, ' ');

export const FILING_LABELS: Record<string, string> = {
  single: 'Single',
  married_joint: 'Married filing jointly',
  married_separate: 'Married filing separately',
  head_of_household: 'Head of household',
};

/** RMD for a year is due Dec 31; reminders on Nov 1 and Dec 1 of that year. */
export function rmdDates(year: number) {
  return { due: `${year}-12-31`, reminders: [`${year}-11-01`, `${year}-12-01`] };
}

export function fieldLabel(name: string): string {
  const s = name.replace(/_/g, ' ');
  return s.charAt(0).toUpperCase() + s.slice(1);
}
