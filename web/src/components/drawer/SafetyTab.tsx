import { Box, Chip, Stack, Typography } from '@mui/material';
import type { CaseState } from '../../api/types';
import { blockedAttempts } from '../../lib/case';
import { Mono } from '../common';
import { tokens as t } from '../../theme';

export default function SafetyTab({ caseState }: { caseState: CaseState }) {
  const blocks = blockedAttempts(caseState);
  return (
    <Stack spacing={1.25} data-testid="tab-safety">
      <Typography variant="caption">Every sentence from the writer passes <Mono>hg.safety.check</Mono> before it reaches the page.</Typography>
      {!blocks.length && <Typography variant="body2" sx={{ py: 2.5 }}>No blocked attempts yet.</Typography>}
      {blocks.map((b, i) => (
        <Box key={i} sx={{ border: `1px solid ${t.rule}`, borderRadius: 1, overflow: 'hidden' }}>
          <Box sx={{ px: 1.5, py: 0.9, bgcolor: t.band, borderBottom: `1px solid ${t.rule}`, fontSize: 11.5, color: t.muted }}><Mono size={11.5}>{b.kind}</Mono></Box>
          <Stack spacing={1} sx={{ px: 1.5, py: 1.25 }}>
            <Box sx={{ fontSize: 13, color: '#5C1A12', textDecoration: 'line-through', textDecorationColor: 'rgba(180,35,24,.5)' }}>“{b.text}”</Box>
            <Stack direction="row" spacing={0.75} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap' }}>
              <Chip size="small" label="blocked" sx={{ bgcolor: t.failTint, color: t.failText }} />
              <Box sx={{ fontSize: 12, color: t.body }}>{b.reason}</Box>
            </Stack>
            <Box sx={{ fontSize: 12, color: t.muted }}>{b.outcome}</Box>
          </Stack>
        </Box>
      ))}
    </Stack>
  );
}
