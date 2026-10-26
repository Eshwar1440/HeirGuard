import { Box, Stack, Typography } from '@mui/material';
import { useAudit } from '../../api/hooks';
import { formatTime } from '../../lib/format';
import { ErrorCard } from '../common';
import { tokens as t } from '../../theme';

const dotColor = (action: string, node: string) =>
  /fail|error|block/i.test(action) ? t.fail : /^await_|interrupt|pause/i.test(node) || /pause/i.test(action) ? t.amber : t.accent;

export default function AuditTab({ caseId }: { caseId: string }) {
  const { data, isLoading, error, refetch } = useAudit(caseId);
  if (isLoading) return <Typography variant="body2">Loading audit entries…</Typography>;
  if (error) return <ErrorCard title="Couldn't load the audit log" message={(error as Error).message} onRetry={() => refetch()} />;
  const entries = [...(data ?? [])].sort((a, b) => b.timestamp.localeCompare(a.timestamp));
  if (!entries.length) return <Typography variant="body2">No audit entries yet.</Typography>;
  return (
    <Stack data-testid="tab-audit">
      {entries.map((a, i) => (
        <Box key={`${a.timestamp}-${i}`} sx={{ display: 'grid', gridTemplateColumns: '64px 14px 1fr', gap: 1.25 }}>
          <Box sx={{ fontFamily: t.mono, fontSize: 11, color: t.muted, pt: '2px' }}>{formatTime(a.timestamp)}</Box>
          <Stack sx={{ alignItems: 'center' }}>
            <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: dotColor(a.action, a.node), mt: '4px', flex: 'none' }} />
            <Box sx={{ flex: 1, width: '1px', bgcolor: t.rule }} />
          </Stack>
          <Stack sx={{ pb: 1.75 }} spacing={0.25}>
            <Box sx={{ fontFamily: t.mono, fontSize: 12, fontWeight: 500 }}>{a.node} <span style={{ color: t.muted, fontWeight: 400 }}>· {a.action}</span></Box>
            <Box sx={{ fontSize: 12.5, color: t.body, lineHeight: 1.4 }}>{a.summary}</Box>
          </Stack>
        </Box>
      ))}
    </Stack>
  );
}
