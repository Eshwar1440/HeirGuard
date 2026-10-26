import { describe, expect, it } from 'vitest';
import { formatConfidence, formatDate, formatMoney, formatPercent, rmdDates, scenarioLabel, toNumber, fieldLabel } from './format';

describe('toNumber', () => {
  it('parses Decimal strings and formatted values', () => {
    expect(toNumber('206000.00')).toBe(206000);
    expect(toNumber('$1,234.50')).toBe(1234.5);
    expect(toNumber('25%')).toBe(25);
    expect(toNumber(7)).toBe(7);
  });
  it('returns null for empty or invalid', () => {
    expect(toNumber(null)).toBeNull();
    expect(toNumber('')).toBeNull();
    expect(toNumber('abc')).toBeNull();
  });
});

describe('formatMoney', () => {
  it('formats whole dollars by default', () => expect(formatMoney('206000.00')).toBe('$206,000'));
  it('keeps cents when asked', () => expect(formatMoney('412000', { cents: true })).toBe('$412,000.00'));
  it('rounds', () => expect(formatMoney(1234.5)).toBe('$1,235'));
  it('handles negatives', () => expect(formatMoney(-50)).toBe('-$50'));
  it('dashes missing values', () => expect(formatMoney(undefined)).toBe('—'));
});

describe('formatPercent', () => {
  it('formats shares', () => {
    expect(formatPercent('50')).toBe('50%');
    expect(formatPercent('49.50')).toBe('49.5%');
  });
  it('formats fractions', () => expect(formatPercent('0.05', { fraction: true })).toBe('5%'));
});

describe('formatConfidence', () => {
  it('two decimals', () => expect(formatConfidence(0.9)).toBe('0.90'));
});

describe('formatDate', () => {
  it('formats ISO dates without timezone drift', () => {
    expect(formatDate('2025-08-03')).toBe('August 3, 2025');
    expect(formatDate('2035-12-31', { short: true })).toBe('Dec 31, 2035');
  });
  it('passes through unknown formats', () => expect(formatDate('soon')).toBe('soon'));
});

describe('rmdDates', () => {
  it('due Dec 31 with Nov 1 and Dec 1 reminders', () => {
    expect(rmdDates(2026)).toEqual({ due: '2026-12-31', reminders: ['2026-11-01', '2026-12-01'] });
  });
});

describe('labels', () => {
  it('maps scenario keys', () => {
    expect(scenarioLabel('even_spread')).toBe('Even spread');
    expect(scenarioLabel('custom_plan')).toBe('custom plan');
  });
  it('humanizes field names', () => expect(fieldLabel('share_percent')).toBe('Share percent'));
});

describe('plain labels and values', () => {
  it('never shows raw field names or codes to the heir', async () => {
    const { plainLabel, plainValue } = await import('./format');
    expect(plainLabel('share_percent')).toBe('Your share');
    expect(plainLabel('account_type')).toBe('Account type');
    expect(plainValue('account_type', 'traditional_ira')).toBe('Traditional IRA');
    expect(plainValue('share_percent', '50')).toBe('50%');
    expect(plainValue('beneficiary_date_of_birth', '1973-05-02')).toBe('May 2, 1973');
    expect(plainValue('relationship', 'child')).toBe('Child');
    expect(plainValue('beneficiary_name', 'Mackenzie Hernandez')).toBe('Mackenzie Hernandez');
    expect(plainValue('share_percent', null)).toBe('—');
  });
});
