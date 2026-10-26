import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Box, Card, Chip, List, ListItem, Stack, TextField, Typography } from '@mui/material';
import type { Beneficiary, CaseState } from '../api/types';
import { applicationFor, checksFor, reasonFor, ruleLabel } from '../lib/case';
import { formatPercent } from '../lib/format';
import { StatusIcon } from './common';
import { tokens as t } from '../theme';

const EDITABLE = [
  ['beneficiary_name', 'Full name'],
  ['beneficiary_date_of_birth', 'Date of birth'],
  ['relationship', 'Relationship'],
  ['share_percent', 'Share of account (%)'],
] as const;

// Names can't be typed over: a misspelled name is fixed by uploading a corrected form (M8 rule).
const NAME_FIELDS = new Set(['beneficiary_name']);

export interface PendingEdit { field: string; document_id: string; value: string }

interface Props {
  caseState: CaseState;
  beneficiary: Beneficiary;
  edits: Record<string, PendingEdit>;
  onEdit: (e: PendingEdit) => void;
  files: File[];
  onFiles: (files: File[]) => void;
  stacked?: boolean;
  /** True while the flow waits for the heir to fix something. */
  editable?: boolean;
}

export default function BeneficiaryCard({ caseState, beneficiary: b, edits, onEdit, files, onFiles, stacked, editable }: Props) {
  const checks = checksFor(caseState, b);
  const failing = checks.filter((c) => c.status !== 'pass');
  const ok = checks.length > 0 && failing.length === 0;
  const app = applicationFor(caseState, b);
  const failingFields = new Set(failing.flatMap((c) => (c.evidence ?? []).filter((e) => e.document_id === app?.id).map((e) => e.field_name)));

  const onDrop = useCallback((accepted: File[]) => onFiles([...files, ...accepted]), [files, onFiles]);
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop, disabled: !editable, accept: { 'application/pdf': ['.pdf'], 'image/png': ['.png'], 'image/jpeg': ['.jpg', '.jpeg'] },
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
          <Typography variant="overline" component="div" sx={{ mb: 1 }}>What we read{editable ? ' · edit to correct' : ''}</Typography>
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.25 }}>
            {EDITABLE.map(([name, label]) => {
              const f = app.fields.find((x) => x.name === name);
              if (!f) return null;
              const key = `${app.id}.${name}`;
              const bad = failingFields.has(name);
              const locked = !editable || NAME_FIELDS.has(name);
              return (
                <TextField key={name} label={label} size="small" error={bad}
                  helperText={editable && NAME_FIELDS.has(name) ? 'To change a name, upload a corrected form' : undefined}
                  slotProps={{ htmlInput: { 'data-testid': `field-${b.id}-${name}`, readOnly: locked } }}
                  value={edits[key]?.value ?? String(f.value ?? '')}
                  onChange={(e) => onEdit({ field: name, document_id: app.id, value: e.target.value })}
                  sx={bad ? { '& .MuiOutlinedInput-root': { bgcolor: '#FFF7F6' } } : undefined} />
              );
            })}
          </Box>
        </Box>
      )}

      <Box sx={{ p: 2.25, pt: 1.75 }}>
        <Box {...getRootProps()} data-testid={`dropzone-${b.id}`} sx={{
          border: `1.5px dashed ${files.length || isDragActive ? t.accent : '#B9C4D0'}`, borderRadius: '6px', p: 1.75, textAlign: 'center',
          fontSize: 13, cursor: 'pointer', color: files.length ? t.accentText : t.muted, bgcolor: files.length || isDragActive ? t.accentTint : '#FAFBFC',
          '&:hover': { bgcolor: '#EEF5FC' },
        }}>
          <input {...getInputProps()} />
          {files.length ? `${files.map((f) => f.name).join(', ')} added. Re-check to read it.`
            : editable ? 'Drag a corrected document here, or click to choose a file' : 'Uploads open when a document needs a fix'}
        </Box>
      </Box>
    </Card>
  );
}
