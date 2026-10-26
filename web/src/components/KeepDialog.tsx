import { useState } from 'react';
import { Box, Button, Checkbox, Chip, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel, Typography } from '@mui/material';
import type { CaseState } from '../api/types';
import { useChoice } from '../api/hooks';
import { plainLabel, plainValue } from '../lib/format';
import { ErrorCard } from './common';
import { tokens as t } from '../theme';

const OPT_IN_FIELD = 'rmd_deposit_opt_in';

/** "the death certificate" or "Daniel's application", for a source chip. */
function sourceName(caseState: CaseState, documentId?: string | null): string {
  const doc = (caseState.documents ?? []).find((d) => d.id === documentId);
  if (!doc) return 'your documents';
  if (doc.doc_type === 'death_certificate') return 'the death certificate';
  const who = doc.fields.find((f) => f.name === 'beneficiary_name')?.value;
  return who ? `${who.split(' ')[0]}'s application` : 'the application';
}

export default function KeepDialog({ caseState, open, onClose }: { caseState: CaseState; open: boolean; onClose: () => void }) {
  const choice = useChoice(caseState.case_id);
  const stored = (caseState.prefill ?? []).find((f) => f.name === OPT_IN_FIELD)?.value === 'yes';
  const [optIn, setOptIn] = useState(false);
  const prefill = (caseState.prefill ?? []).filter((f) => f.name !== OPT_IN_FIELD);
  const built = caseState.choice === 'keep' && prefill.length > 0;
  const heirEntered = caseState.handoff?.heir_entered ?? {};
  const excluded = built ? caseState.handoff?.excluded ?? [] : [];

  return (
    <Dialog open={open} onClose={onClose} maxWidth={false} slotProps={{ paper: { sx: { width: 680 } } }} data-testid="keep-dialog">
      <DialogTitle sx={{ pb: 0.5 }}>
        <Typography variant="h3" component="div" sx={{ fontSize: 21 }}>Inherited IRA application</Typography>
        <Typography variant="body2" sx={{ color: t.muted, mt: 0.5 }}>
          Proposed handoff to digital onboarding, prefilled from verified documents. Not a real submission.
        </Typography>
      </DialogTitle>
      <DialogContent dividers sx={{ px: 3, py: 1 }}>
        {built ? (
          prefill.map((f) => {
            const sourced = !!f.source_document_id;
            return (
              <Box key={f.name} data-testid="prefill-row" sx={{ display: 'grid', gridTemplateColumns: '170px 1fr auto', gap: 1.5, alignItems: 'center', py: 1.25, borderBottom: `1px solid ${t.rowRule}` }}>
                <Box sx={{ fontSize: 12.5, color: t.muted }}>{plainLabel(f.name)}</Box>
                <Box sx={{ fontSize: 14, fontWeight: sourced ? 500 : 400, color: sourced ? t.ink : t.muted }}>{sourced ? plainValue(f.name, f.value) : heirEntered[f.name] ?? 'Entered by heir at signing'}</Box>
                <Chip size="small" data-testid="source-chip"
                  label={sourced ? `From ${sourceName(caseState, f.source_document_id)}` : 'You enter this'}
                  sx={{ fontWeight: 500, fontSize: 11, bgcolor: sourced ? t.accentTint : t.rowRule, color: sourced ? t.accentText : t.muted }} />
              </Box>
            );
          })
        ) : (
          <Typography variant="body2" sx={{ py: 2 }}>
            We'll fill the application from the documents that passed every check. You'll review each field and its source before anything is sent.
          </Typography>
        )}
        <FormControlLabel sx={{ alignItems: 'flex-start', py: 2, m: 0, gap: 1 }}
          control={<Checkbox checked={built ? stored : optIn} onChange={(e) => setOptIn(e.target.checked)} disabled={built} sx={{ p: 0, mt: '2px' }} slotProps={{ input: { 'aria-label': 'Opt in to RMD deposit' } }} />}
          label={
            <Box>
              <Box sx={{ fontSize: 14, fontWeight: 500 }}>Deposit each year's required minimum into my linked brokerage account</Box>
              <Box sx={{ fontSize: 12.5, color: t.muted }}>Optional. Leave unchecked to receive reminders only. You can change this later.</Box>
            </Box>
          } />
        {excluded.length > 0 && (
          <Box sx={{ pb: 2, fontSize: 12.5, color: t.amberText }} data-testid="prefill-excluded">
            <strong>Left out, for you to enter at signing:</strong>{' '}
            {excluded.map((e) => plainLabel(e.name)).join(', ')}. The reasons are under the hood.
          </Box>
        )}
        {choice.isError && <Box sx={{ pb: 2 }}><ErrorCard title="We couldn't prefill the application" message={(choice.error as Error).message} /></Box>}
      </DialogContent>
      <DialogActions sx={{ px: 3, py: 1.75, bgcolor: t.panel }}>
        <Button variant="outlined" onClick={onClose} sx={{ borderColor: t.inputBorder, borderWidth: 1 }}>{built ? 'Close' : 'Cancel'}</Button>
        {!built && (
          <Button variant="contained" data-testid="prefill-application" disabled={choice.isPending}
            onClick={() => choice.mutate({ choice: 'keep', opt_in_rmd_deposit: optIn })}>
            {choice.isPending ? 'Preparing…' : 'Prefill my application'}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
