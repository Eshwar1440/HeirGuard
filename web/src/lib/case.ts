import type { Beneficiary, CaseState, CheckResult, Document, GuideText, BlockedAttempt } from '../api/types';

export const STAGES = [
  { label: 'Notice', caption: "We've been told" },
  { label: 'Restriction', caption: 'Account protected' },
  { label: 'Documents', caption: 'Upload and check' },
  { label: 'Tax rules', caption: 'How rules apply' },
  { label: 'Decision', caption: 'Keep, talk, transfer' },
  { label: 'After', caption: 'Yearly minimums' },
];

export function activeStage(c?: CaseState | null): number {
  if (!c) return 2;
  if (c.choice) return 5;
  if (c.scenarios?.length) return 4;
  if (c.approved) return 3;
  return 2;
}

export const checksFor = (c: CaseState, b: Beneficiary): CheckResult[] =>
  (c.checks ?? []).filter((k) => !k.beneficiary_id || k.beneficiary_id === b.id);

export const allPass = (c?: CaseState | null) =>
  !!c && (c.checks?.length ?? 0) > 0 && c.checks!.every((k) => k.status === 'pass');

export const failCount = (c?: CaseState | null) => (c?.checks ?? []).filter((k) => k.status !== 'pass').length;

const norm = (s: unknown) => String(s ?? '').toLowerCase().replace(/\s+/g, ' ').trim();

/** The beneficiary's own application: an inherited_ira_application whose beneficiary_name matches. */
export function applicationFor(c: CaseState, b: Beneficiary): Document | undefined {
  return (c.documents ?? []).find(
    (d) => d.doc_type === 'inherited_ira_application' && d.fields.some((f) => f.name === 'beneficiary_name' && norm(f.value) === norm(b.name)),
  ) ?? (c.documents ?? []).filter((d) => d.doc_type === 'inherited_ira_application')[(c.beneficiaries ?? []).indexOf(b)];
}

const guideList = (c: CaseState): GuideText[] => c.guide ?? [];

/** The beneficiary using the app (the simulation and prefill are for them). */
export const heirOf = (c: CaseState): Beneficiary | undefined =>
  (c.beneficiaries ?? []).find((b) => b.id === c.heir_id) ?? (c.beneficiaries ?? [])[0];

/** The writer's plain-English reason for a failing check (GuideText tagged by M5), else the rule message. */
export function reasonFor(c: CaseState, check: CheckResult): string {
  const issue = guideList(c).find(
    (g) => g.kind === 'issue_reason' && g.rule_id === check.rule_id && (g.beneficiary_id ?? null) === (check.beneficiary_id ?? null),
  );
  return issue?.text ?? check.message;
}

export function optionsSummary(c: CaseState): GuideText | undefined {
  return guideList(c).filter((g) => g.kind === 'options_summary').pop();
}

/** Every safety-check block, with what happened next: one regeneration, then the fixed template. */
export function blockedAttempts(c?: CaseState | null): (BlockedAttempt & { kind: string; outcome: string })[] {
  if (!c) return [];
  return guideList(c).flatMap((g) => {
    const attempts = g.blocked_attempts ?? [];
    return attempts.map((b, i) => ({
      ...b,
      kind: g.kind,
      outcome: i < attempts.length - 1 ? 'Regenerated once; the new text was blocked too.'
        : attempts.length >= 2 ? 'Fell back to the fixed template, which passed the check.'
        : 'Regenerated once; the new text passed the check.',
    }));
  });
}

export const RULE_LABELS: Record<string, string> = {
  required_docs_present: 'Required documents',
  shares_total_100: 'Shares add up to 100%',
  name_match: 'Name matches across documents',
  dod_consistent: 'Date of death agrees',
  certified_copy: 'Certified death certificate',
  field_review: 'Fields read clearly',
};
export const ruleLabel = (id: string) => RULE_LABELS[id] ?? id;
