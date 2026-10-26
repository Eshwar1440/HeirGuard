// Aliases over the generated OpenAPI types.
// Regenerate with the backend running: npm run gen:api
import type { components } from './schema';

type S = components['schemas'];

// Fields with a default are optional in the generated schema, but the API always sends them.
type Sent<T, K extends keyof T> = Omit<T, K> & Required<Pick<T, K>>;

export type Beneficiary = S['Beneficiary'];
export type ExtractedField = S['ExtractedField'];
export type Document = Sent<S['Document'], 'fields' | 'needs_review'>;
export type CheckResult = Sent<S['CheckResult'], 'evidence'>;
export type HeirInputs = S['HeirInputs-Input'];
export type ScenarioYear = S['ScenarioYear'];
export type Scenario = Sent<S['Scenario'], 'years'>;
export type GuideText = Sent<S['GuideText'], 'numbers_used' | 'blocked_attempts'>;
export type PrefillField = S['PrefillField'];
export type PrefillHandoff = Sent<S['PrefillHandoff'], 'fields' | 'heir_entered' | 'excluded'>;
export type AuditEntry = Sent<S['AuditEntry'], 'timestamp'>;
export type CaseRecord = Omit<S['CaseState'], 'documents' | 'checks' | 'scenarios' | 'guide' | 'beneficiaries' | 'accounts' | 'prefill'> & {
  documents: Document[];
  checks: CheckResult[];
  scenarios: Scenario[];
  guide: GuideText[];
  beneficiaries: Beneficiary[];
  accounts: S['Account'][];
  prefill: PrefillField[];
};
export type CaseView = Omit<S['CaseView'], 'case' | 'handoff'> & { case: CaseRecord; handoff?: PrefillHandoff | null };
export type BlockedAttempt = S['BlockedAttempt'];
export type Sample = S['Sample'];

export type Choice = 'keep' | 'talk' | 'transfer';
export type FilingStatus = 'single' | 'married_joint' | 'married_separate' | 'head_of_household';

/** Where the flow is paused (M8 interrupt kinds). */
export type Waiting = 'heir_fix' | 'approval' | 'heir_inputs' | 'choice';

// CaseView.simulation, written by the M8 simulate node from M4's SimulationResult.
export interface SimulationRules {
  beneficiary_class: string;
  needs_specialist: boolean;
  deadline_year: number | null;
  annual_rmds_required: boolean;
  died_on_or_after_rbd: boolean;
  required_beginning_date: string;
  year_of_death_rmd_may_be_due: boolean;
  summary: string;
}
export interface DivisorYear { year: number; n: number; beneficiary_factor: string; decedent_factor: string | null; divisor: string }
export interface Simulation {
  beneficiary_id: string;
  balance: string;
  account_type: string;
  rules: SimulationRules;
  factors: DivisorYear[];
  assumptions: string[];
  tax_year: number;
  fill_rate: string;
}

/** The case plus where its flow is paused. Every component receives this. */
export type CaseState = CaseRecord & {
  waiting_for: Waiting | null;
  heir_id: string | null;
  simulation: Simulation | null;
  handoff: PrefillHandoff | null;
  review_note: string | null;
};

export function toCaseState(v: CaseView): CaseState {
  return {
    ...v.case,
    waiting_for: (v.waiting_for as Waiting | null | undefined) ?? null,
    heir_id: v.heir_id ?? null,
    simulation: (v.simulation as Simulation | null | undefined) ?? null,
    handoff: v.handoff ?? null,
    review_note: v.review_note ?? null,
  };
}

// GET /cases/{id}/graph (M3 export_case_graph)
export interface GraphElement {
  data: { id: string; label?: string; type?: string; source?: string; target?: string; status?: string | null; [k: string]: unknown };
}
export interface CaseGraph { nodes: GraphElement[]; edges: GraphElement[] }

// GET /cases/{id}/ai-log
export interface AiLogRecord { timestamp: string; function: string; model: string; latency_ms?: number }
