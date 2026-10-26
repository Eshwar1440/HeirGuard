import type { ReactNode } from 'react';
import { Box, Button, Card, Chip, Stack, Typography } from '@mui/material';
import { tokens as t } from '../theme';

export function SectionHeader({ n, title, action }: { n: string; title: string; action?: ReactNode }) {
  return (
    <Stack direction="row" sx={{ alignItems: 'baseline', justifyContent: 'space-between' }}>
      <Stack direction="row" spacing={1.5} sx={{ alignItems: 'baseline' }}>
        <Box component="span" sx={{ fontFamily: t.mono, fontSize: 12, fontWeight: 500, color: t.accent }}>{n}</Box>
        <Typography variant="h2" component="h2">{title}</Typography>
      </Stack>
      {action}
    </Stack>
  );
}

export function HypotheticalChip({ small }: { small?: boolean }) {
  return (
    <Chip size="small" label="hypothetical"
      sx={{ bgcolor: t.amberTint, color: t.amberText, height: small ? 18 : 20, fontSize: small ? 10.5 : 11, '& .MuiChip-label': { px: 0.9 } }} />
  );
}

export function StatusIcon({ status }: { status: string }) {
  const pass = status === 'pass';
  const review = status === 'needs_review';
  return (
    <Box aria-label={status} sx={{
      flex: 'none', width: 20, height: 20, borderRadius: '50%', mt: '1px', display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: 12, fontWeight: 700, color: '#fff', bgcolor: pass ? t.pass : review ? t.amber : t.fail,
    }}>{pass ? '✓' : review ? '?' : '!'}</Box>
  );
}

export function StatusChip({ status, label }: { status: 'pass' | 'fail' | 'needs_review' | string; label?: string }) {
  const map: Record<string, [string, string]> = { pass: [t.passTint, t.passText], fail: [t.failTint, t.failText], needs_review: [t.amberTint, t.amberText] };
  const [bg, fg] = map[status] ?? [t.rowRule, t.body];
  return <Chip size="small" label={label ?? status} sx={{ bgcolor: bg, color: fg }} />;
}

export function MonoStatus({ status }: { status: string }) {
  const bg = status === 'pass' ? t.pass : status === 'fail' ? t.fail : t.amber;
  return <Box component="span" sx={{ fontFamily: t.mono, fontSize: 11, fontWeight: 600, px: 1, py: '2px', borderRadius: 10, bgcolor: bg, color: '#fff' }}>{status}</Box>;
}

export function Placeholder({ children, dashed }: { children: ReactNode; dashed?: boolean }) {
  return (
    <Card sx={{ px: 2.75, py: 2.25, borderStyle: dashed ? 'dashed' : 'solid' }}>
      <Typography variant="body2" sx={{ color: t.muted }}>{children}</Typography>
    </Card>
  );
}

export function Banner({ tone, children, action }: { tone: 'pass' | 'fail' | 'info' | 'amber'; children: ReactNode; action?: ReactNode }) {
  const map = {
    pass: [t.passTint, '#B9DCC5', t.passText],
    fail: [t.failTint, t.failBorder, '#5C1A12'],
    info: [t.accentTint, t.accentBorder, t.accentText],
    amber: [t.callout, t.calloutBorder, t.amberText],
  }[tone];
  return (
    <Box role="status" sx={{ bgcolor: map[0], border: `1px solid ${map[1]}`, color: map[2], borderRadius: '6px', px: 2.25, py: 1.75,
      display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2, fontSize: 14, lineHeight: 1.5 }}>
      <Box>{children}</Box>
      {action}
    </Box>
  );
}

export function ErrorCard({ title, message, onRetry }: { title: string; message?: string; onRetry?: () => void }) {
  return (
    <Banner tone="fail" action={onRetry && <Button variant="outlined" color="error" onClick={onRetry} sx={{ bgcolor: '#fff', flex: 'none' }}>Try again</Button>}>
      <Box sx={{ fontWeight: 600, color: t.failText }}>{title}</Box>
      {message && <Box sx={{ fontSize: 13.5 }}>{message}</Box>}
    </Banner>
  );
}

export function Mono({ children, size = 12 }: { children: ReactNode; size?: number }) {
  return <Box component="span" sx={{ fontFamily: t.mono, fontSize: size }}>{children}</Box>;
}

export function KeyValueRows({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <Box sx={{ border: `1px solid ${t.rule}`, borderRadius: 1, fontSize: 13 }}>
      {rows.map(([k, v]) => (
        <Stack key={k} direction="row" sx={{ justifyContent: 'space-between', px: 1.5, py: 1, borderBottom: `1px solid ${t.rowRule}`, '&:last-of-type': { borderBottom: 0 } }}>
          <Box sx={{ color: t.muted }}>{k}</Box><Box sx={{ fontWeight: 500 }}>{v}</Box>
        </Stack>
      ))}
    </Box>
  );
}
