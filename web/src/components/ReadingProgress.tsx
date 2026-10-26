import { useEffect, useState } from 'react';
import { Box, Card, LinearProgress, Stack, Typography } from '@mui/material';
import type { Document } from '../api/types';
import { tokens as t } from '../theme';

const DOC_LABELS: Record<string, string> = {
  death_certificate: 'Death certificate',
  inherited_ira_application: 'Inherited IRA application',
  letters_testamentary: 'Letters testamentary',
  affidavit_of_domicile: 'Affidavit of domicile',
  trust_certification: 'Trust certification',
  will: 'Will',
  unknown: 'Document',
};

/** Document reading takes several seconds. The API exposes no per-file progress, so bars are indeterminate. */
export default function ReadingProgress({ documents }: { documents?: Document[] }) {
  const [secs, setSecs] = useState(0);
  useEffect(() => {
    const i = setInterval(() => setSecs((s) => s + 1), 1000);
    return () => clearInterval(i);
  }, []);
  const rows = documents?.length
    ? documents.map((d) => ({ key: d.id, label: DOC_LABELS[d.doc_type] ?? d.doc_type, done: d.fields.length > 0 }))
    : [{ key: 'pending', label: 'Your documents', done: false }];
  return (
    <Card sx={{ px: 2.75, py: 2.5 }} data-testid="reading-progress" aria-busy="true">
      <Stack spacing={1.75}>
        <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'baseline' }}>
          <Typography variant="subtitle1">Reading your documents</Typography>
          <Typography variant="caption">This usually takes 5 to 10 seconds · {secs}s</Typography>
        </Stack>
        {rows.map((r) => (
          <Box key={r.key} sx={{ display: 'grid', gridTemplateColumns: '260px 1fr 70px', alignItems: 'center', gap: 1.75, fontSize: 13.5 }}>
            <span>{r.label}</span>
            <LinearProgress variant={r.done ? 'determinate' : 'indeterminate'} value={100} color="secondary" />
            <Box sx={{ fontSize: 12.5, textAlign: 'right', color: r.done ? t.pass : t.muted }}>{r.done ? 'Done' : 'Reading…'}</Box>
          </Box>
        ))}
      </Stack>
    </Card>
  );
}
