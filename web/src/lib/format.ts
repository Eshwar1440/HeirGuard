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

/** Plain labels for fields the heir sees (the under-the-hood views keep the raw names). */
export const FIELD_LABELS: Record<string, string> = {
  beneficiary_name: 'Your name',
  beneficiary_date_of_birth: 'Date of birth',
  relationship: 'Relationship to the owner',
  decedent_name: 'Account owner',
  decedent_date_of_death: 'Date of death',
  date_of_death: 'Date of death',
  account_type: 'Account type',
  share_percent: 'Your share',
  beneficiary_ssn: 'Social Security number',
  linked_brokerage_account_number: 'Linked brokerage account number',
};
export const plainLabel = (name: string) => FIELD_LABELS[name] ?? fieldLabel(name);

export const ACCOUNT_TYPE_LABELS: Record<string, string> = {
  traditional_ira: 'Traditional IRA',
  roth_ira: 'Roth IRA',
  tod_brokerage: 'Transfer-on-death brokerage',
  joint: 'Joint',
  individual: 'Individual',
  trust_owned: 'Trust-owned',
};

/** A stored value as the heir should read it: dates in words, shares as percents, words capitalized. */
export function plainValue(name: string, value: string | null | undefined): string {
  if (value == null || value === '') return '—';
  if (name.includes('date')) return formatDate(value);
  if (name === 'share_percent') return formatPercent(value);
  if (name === 'account_type') return ACCOUNT_TYPE_LABELS[value] ?? value.replace(/_/g, ' ');
  if (name === 'relationship' || name === 'designation') return value.charAt(0).toUpperCase() + value.slice(1);
  return value;
}
