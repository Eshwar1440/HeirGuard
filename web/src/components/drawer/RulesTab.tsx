import { Box, Stack, Typography } from '@mui/material';
import type { CaseState } from '../../api/types';
import { reasonFor } from '../../lib/case';
import { MonoStatus } from '../common';
import { tokens as t } from '../../theme';

export default function RulesTab({ caseState }: { caseState: CaseState }) {
  const checks = [...(caseState.checks ?? [])].sort((a, b) => Number(b.status !== 'pass') - Number(a.status !== 'pass'));
  const names = Object.fromEntries((caseState.beneficiaries ?? []).map((b) => [b.id, b.name.split(' ')[0]]));
  const failing = checks.filter((c) => c.status !== 'pass').length;
  if (!checks.length) return <Typography variant="body2">No checks have run yet.</Typography>;
  return (
    <Stack spacing={1} data-testid="tab-rules">
      <Typography variant="caption">{checks.length} results · grouped per beneficiary · {failing ? `${failing} not passing` : 'all passing'}</Typography>
      {checks.map((c, i) => {
        const fail = c.status !== 'pass';
        return (
          <Box key={`${c.rule_id}-${c.beneficiary_id}-${i}`} data-testid={`rule-${c.rule_id}`} data-status={c.status}
            sx={{ border: `1px solid ${fail ? t.failBorder : t.rowRule}`, bgcolor: fail ? '#FFF7F6' : '#fff', borderRadius: 1, px: 1.5, py: 1.25, display: 'flex', flexDirection: 'column', gap: 0.6 }}>
            <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center' }}>
              <Box sx={{ fontFamily: t.mono, fontSize: 12.5, fontWeight: 500 }}>{c.rule_id}</Box>
              <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
                <Box sx={{ fontSize: 12, color: t.muted }}>{c.beneficiary_id ? names[c.beneficiary_id] ?? c.beneficiary_id : 'case'}</Box>
                <MonoStatus status={c.status} />
              </Stack>
            </Stack>
            <Box sx={{ fontFamily: t.mono, fontSize: 11.5, color: t.body, lineHeight: 1.45 }}>{c.message}</Box>
            {fail && (
              <Box sx={{ fontSize: 12.5, color: '#5C1A12', lineHeight: 1.45, borderTop: `1px solid ${t.failBorder}`, pt: 0.75 }} data-testid="writer-reason">
                <strong>Writer reason:</strong> {reasonFor(caseState, c)}
              </Box>
            )}
            {!!c.evidence?.length && (
              <Box sx={{ fontSize: 11, color: t.muted }}>evidence: {c.evidence.map((e) => `${e.document_id}.${e.field_name}`).join(', ')}</Box>
            )}
          </Box>
        );
      })}
    </Stack>
  );
}
