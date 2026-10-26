import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Box, Card, Chip, List, ListItem, Stack, Typography } from '@mui/material';
import type { Beneficiary, CaseState } from '../api/types';
import { applicationFor, checksFor, reasonFor, ruleLabel } from '../lib/case';
import { formatPercent, plainValue } from '../lib/format';
import { StatusIcon } from './common';
import { tokens as t } from '../theme';

const SHOWN = [
  ['beneficiary_name', 'Full name'],
  ['beneficiary_date_of_birth', 'Date of birth'],
  ['relationship', 'Relationship'],
  ['share_percent', 'Share of the account'],
] as const;

interface Props {
  caseState: CaseState;
  beneficiary: Beneficiary;
  files: File[];
  onFiles: (files: File[]) => void;
  stacked?: boolean;
  /** True while the flow waits for the heir to upload a corrected document. */
  canUpload?: boolean;
}

// Values are shown exactly as read and are never edited here: a wrong value is fixed by
// uploading a corrected document, which the reader then reads like any other upload.
export default function BeneficiaryCard({ caseState, beneficiary: b, files, onFiles, stacked, canUpload }: Props) {
  const checks = checksFor(caseState, b);
  const failing = checks.filter((c) => c.status !== 'pass');
  const ok = checks.length > 0 && failing.length === 0;
  const app = applicationFor(caseState, b);
  const failingFields = new Set(failing.flatMap((c) => (c.evidence ?? []).filter((e) => e.document_id === app?.id).map((e) => e.field_name)));

  const onDrop = useCallback((accepted: File[]) => onFiles([...files, ...accepted]), [files, onFiles]);
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop, disabled: !canUpload, accept: { 'application/pdf': ['.pdf'], 'image/png': ['.png'], 'image/jpeg': ['.jpg', '.jpeg'] },
  });

  return (
    <Card data-testid={`beneficiary-${b.id}`} sx={{ borderTop: `3px solid ${ok ? t.pass : t.fail}`, display: 'flex', flexDirection: 'column' }}>
      <Stack direction="row" sx={{ justifyContent: 'space-between', alignItems: 'center', px: 2.25, py: 1.75, bgcolor: t.panel, borderBottom: `1px solid ${t.rowRule}` }}>
        <Box>
          <Typography sx={{ fontSize: 15.5, fontWeight: 600, color: t.navy }}>{b.name}</Typography>
          <Typography variant="caption">
            {b.relationship.charAt(0).toUpperCase() + b.relationship.slice(1)} · {b.designation === 'contingent' ? 'Contingent' : 'Primary'} beneficiary · {formatPercent(b.share_percent)} share
          </Typography>
        </Box>
        <Chip size="small" label={ok ? 'Ready' : 'Needs a fix'} sx={{ bgcolor: ok ? t.passTint : t.failTint, color: ok ? t.passText : t.failText }} />
      </Stack>

      <List disablePadding sx={{ px: 2.25, display: 'grid', gridTemplateColumns: stacked ? '1fr 1fr' : '1fr', columnGap: 2.75 }}>
        {checks.map((c) => (
          <ListItem key={`${c.rule_id}-${c.beneficiary_id}`} disableGutters alignItems="flex-start" data-testid={`check-${c.rule_id}`} data-status={c.status}
            sx={{ gap: 1.4, py: 1.25, borderBottom: `1px solid ${t.rowRule}` }}>
            <StatusIcon status={c.status} />
            <Box>
              <Typography sx={{ fontSize: 13.5, fontWeight: 600, color: c.status === 'pass' ? t.ink : t.failText }}>{ruleLabel(c.rule_id)}</Typography>
              <Typography sx={{ fontSize: 13, lineHeight: 1.45, color: t.body, textWrap: 'pretty' }}>
                {c.status === 'pass' ? c.message : reasonFor(caseState, c)}
              </Typography>
            </Box>
          </ListItem>
        ))}
      </List>

      {app && (
        <Box sx={{ px: 2.25, pt: 1.5 }}>
          <Typography variant="overline" component="div" sx={{ mb: 1 }}>What we read from the application</Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.25 }}>
            {SHOWN.map(([name, label]) => {
              const f = app.fields.find((x) => x.name === name);
              if (!f) return null;
              const bad = failingFields.has(name);
              return (
                <Box key={name} data-testid={`field-${b.id}-${name}`} data-bad={bad || undefined}
                  sx={{ border: `1px solid ${bad ? t.fail : t.rule}`, bgcolor: bad ? '#FFF7F6' : t.panel, borderRadius: 1, px: 1.25, py: 0.75 }}>
                  <Box sx={{ fontSize: 11.5, color: bad ? t.failText : t.muted }}>{label}</Box>
                  <Box sx={{ fontSize: 14, fontWeight: 500, color: f.value == null ? t.muted : bad ? t.failText : t.ink }}>
                    {f.value == null ? 'Unreadable' : plainValue(name, f.value)}
                  </Box>
                </Box>
              );
            })}
          </Box>
        </Box>
      )}

      <Box sx={{ p: 2.25, pt: 1.75 }}>
        <Box {...getRootProps()} data-testid={`dropzone-${b.id}`} sx={{
          border: `1.5px dashed ${files.length || isDragActive ? t.accent : '#B9C4D0'}`, borderRadius: '6px', p: 1.75, textAlign: 'center',
          fontSize: 13, cursor: canUpload ? 'pointer' : 'default', color: files.length ? t.accentText : t.muted,
          bgcolor: files.length || isDragActive ? t.accentTint : '#FAFBFC', '&:hover': canUpload ? { bgcolor: '#EEF5FC' } : undefined,
        }}>
          <input {...getInputProps()} />
          {files.length ? `${files.map((f) => f.name).join(', ')} added. Re-check to read it.`
            : canUpload ? 'To fix a value, drag a corrected document here, or click to choose a file' : 'Uploads open when a document needs a fix'}
        </Box>
      </Box>
    </Card>
  );
}
