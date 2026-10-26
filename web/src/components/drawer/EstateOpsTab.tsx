import { useState } from 'react';
import { Button, Stack, TextField, Typography } from '@mui/material';
import type { CaseState } from '../../api/types';
import { isReading, useApprove, useLoadSampleDocuments } from '../../api/hooks';
import { allPass, failCount } from '../../lib/case';
import { ErrorCard, KeyValueRows, Mono } from '../common';
import { tokens as t } from '../../theme';

export default function EstateOpsTab({ caseState }: { caseState: CaseState }) {
  const approve = useApprove(caseState.case_id);
  const [reason, setReason] = useState('');
  const sample = useLoadSampleDocuments(caseState.case_id);
  const noDocuments = !caseState.documents.length && caseState.waiting_for === 'heir_fix';
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
        {caseState.approved ? 'Approved' : approve.isPending ? 'Approving…' : 'Approve case'}
      </Button>
      {can && (
        <Stack spacing={1} sx={{ border: `1px solid ${t.rule}`, borderRadius: 1, p: 1.5 }}>
          <TextField label="Reason" size="small" multiline minRows={2} value={reason}
            onChange={(e) => setReason(e.target.value)} slotProps={{ htmlInput: { 'data-testid': 'return-reason' } }} />
          <Button variant="outlined" color="error" disabled={!reason.trim() || approve.isPending} data-testid="return-to-heir"
            onClick={() => approve.mutate({ approved: false, note: reason.trim() }, { onSuccess: () => setReason('') })}>
            Deny case
          </Button>
        </Stack>
      )}
      <Typography variant="caption">{note}</Typography>
      {approve.isError && <ErrorCard title="Approval failed" message={(approve.error as Error).message} />}
      {noDocuments && (
        <Stack spacing={1} sx={{ borderTop: `1px solid ${t.rule}`, pt: 1.75 }}>
          <Typography variant="body2">Demo shortcut: read this case's sample packet as if the heir had uploaded it.</Typography>
          <Button variant="outlined" onClick={() => sample.mutate()} disabled={sample.isPending} data-testid="load-sample-documents">
            {sample.isPending ? 'Reading the sample packet…' : "Load this case's sample documents"}
          </Button>
          {sample.isError && <ErrorCard title="Couldn't load the sample" message={(sample.error as Error).message} />}
        </Stack>
      )}
    </Stack>
  );
}
