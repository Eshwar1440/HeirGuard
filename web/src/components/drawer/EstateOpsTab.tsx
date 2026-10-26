import { Button, Stack, Typography } from '@mui/material';
import type { CaseState } from '../../api/types';
import { isReading, useApprove } from '../../api/hooks';
import { allPass, failCount } from '../../lib/case';
import { ErrorCard, KeyValueRows, Mono } from '../common';
import { tokens as t } from '../../theme';

export default function EstateOpsTab({ caseState }: { caseState: CaseState }) {
  const approve = useApprove(caseState.case_id);
  const pass = allPass(caseState);
  const fails = failCount(caseState);
  const reading = isReading(caseState);
  const can = caseState.waiting_for === 'approval' && !reading;
  const note = caseState.approved ? 'Approved. The flow resumed at simulate.'
    : reading ? 'Waiting for checks to finish.'
    : can ? (pass ? `All ${caseState.checks?.length ?? 0} checks passed.` : `The heir sent ${fails} review item${fails > 1 ? 's' : ''} with the packet. Review before approving.`)
    : fails ? `Blocked: ${fails} check${fails > 1 ? 's' : ''} not passing. The heir has to fix ${fails > 1 ? 'them' : 'it'} first.`
    : 'Waiting for checks.';

  return (
    <Stack spacing={1.75} data-testid="tab-ops">
      <Typography variant="body2">
        Stand-in for the human review step. Calls <Mono>POST /cases/{caseState.case_id}/approve</Mono>, which resumes the flow from <Mono>await_approval</Mono>.
      </Typography>
      <KeyValueRows rows={[
        ['Case', <Mono>{caseState.case_id}</Mono>],
        ['Status', <Mono>{String(caseState.status ?? '—')}</Mono>],
        ['Documents', String(caseState.documents?.length ?? 0)],
        ['Checks', <span style={{ color: fails ? t.fail : t.pass }}>{(caseState.checks?.length ?? 0) - fails} pass · {fails} not passing</span>],
        ['Approved', caseState.approved ? 'yes' : 'no'],
      ]} />
      <Button variant="contained" color="secondary" size="large" disabled={!can || approve.isPending} onClick={() => approve.mutate()} data-testid="approve">
        {caseState.approved ? 'Approved' : approve.isPending ? 'Approving…' : 'Approve packet'}
      </Button>
      <Typography variant="caption">{note}</Typography>
      {approve.isError && <ErrorCard title="Approval failed" message={(approve.error as Error).message} />}
    </Stack>
  );
}
