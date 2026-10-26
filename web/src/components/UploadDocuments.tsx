import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Box, Button, Card, Chip, Stack, Typography } from '@mui/material';
import type { CaseState } from '../api/types';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import { qk, useCreateCase, useUploadDocuments } from '../api/hooks';
import { toCaseState, type CaseView } from '../api/types';
import ReadingProgress from './ReadingProgress';
import { ErrorCard } from './common';
import { tokens as t } from '../theme';

/**
 * The heir's starting point: drop the documents for the account. With no case open yet, the
 * upload opens a new case first; with an open case waiting for documents, it adds to that case.
 */
export default function UploadDocuments({ caseState, onCase }: { caseState?: CaseState | null; onCase?: (id: string) => void }) {
  const create = useCreateCase();
  const qc = useQueryClient();
  const [opening, setOpening] = useState(false);
  const upload = useUploadDocuments(caseState?.case_id ?? null);
  const [files, setFiles] = useState<File[]>([]);
  const ready = caseState ? caseState.waiting_for === 'heir_fix' : true;
  const owner = caseState?.decedent?.name;
  const people = caseState?.beneficiaries.length ?? 0;

  const onDrop = useCallback((accepted: File[]) => setFiles((f) => [...f, ...accepted]), []);
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop, multiple: true, disabled: !ready,
    accept: { 'application/pdf': ['.pdf'], 'image/png': ['.png'], 'image/jpeg': ['.jpg', '.jpeg'] },
  });

  async function read() {
    if (caseState) {
      await upload.mutateAsync(files);
      setFiles([]);
      return;
    }
    // No case yet: open an empty one, then read the files into it.
    setOpening(true);
    try {
      const id = (await create.mutateAsync(null)).case_id;
      const c = toCaseState(await api.upload<CaseView>(`/cases/${id}/documents`, files));
      qc.setQueryData(qk.case(id), c);
      onCase?.(id);
    } finally {
      setOpening(false);
    }
  }

  if (upload.isPending || opening) return <ReadingProgress />;

  return (
    <Card sx={{ p: 3 }} data-testid="upload-documents">
      <Typography variant="h3" sx={{ fontSize: 21 }}>Upload your documents</Typography>
      <Typography variant="body2" sx={{ mt: 0.75, maxWidth: 720 }}>
        {caseState
          ? <>Add the documents for {owner ? `${owner}'s` : 'the'} account: the death certificate and an Inherited IRA application
              {people > 1 ? ' for each beneficiary' : ''}. Add letters testamentary or other papers if you have them.</>
          : "Add the documents for the account: the death certificate and an Inherited IRA application for each beneficiary. Or choose a case in the Case menu above."}
      </Typography>

      <Box {...getRootProps()} data-testid="upload-dropzone" sx={{
        mt: 2, border: `1.5px dashed ${isDragActive || files.length ? t.accent : '#B9C4D0'}`, borderRadius: '6px', py: 4, px: 2,
        textAlign: 'center', cursor: ready ? 'pointer' : 'default', color: ready ? t.body : t.disabled,
        bgcolor: isDragActive ? t.accentTint : ready ? '#FAFBFC' : t.panel, '&:hover': ready ? { bgcolor: '#EEF5FC' } : undefined,
      }}>
        <input {...getInputProps()} />
        <Typography sx={{ fontSize: 15, fontWeight: 500 }}>Drag documents here, or click to choose files</Typography>
        <Typography variant="caption">PDF, PNG or JPEG</Typography>
      </Box>

      {files.length > 0 && (
        <Stack direction="row" spacing={0.75} useFlexGap sx={{ flexWrap: 'wrap', mt: 1.5 }}>
          {files.map((f, i) => (
            <Chip key={`${f.name}-${i}`} label={f.name} onDelete={() => setFiles((all) => all.filter((_, j) => j !== i))}
              sx={{ bgcolor: t.accentTint, color: t.accentText, fontWeight: 500 }} />
          ))}
        </Stack>
      )}

      <Stack direction="row" sx={{ mt: 2, justifyContent: 'flex-end' }}>
        <Button variant="contained" disabled={!ready || !files.length || upload.isPending} data-testid="upload-submit"
          onClick={read}>
          {upload.isPending ? 'Reading…' : `Read ${files.length || ''} document${files.length === 1 ? '' : 's'}`.replace('  ', ' ')}
        </Button>
      </Stack>
      {upload.isError && <Box sx={{ mt: 1.5 }}><ErrorCard title="We couldn't read your documents" message={(upload.error as Error).message} /></Box>}
    </Card>
  );
}
