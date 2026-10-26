import { useState } from 'react';
import { Box, Button, Stack } from '@mui/material';
import type { CaseState } from '../api/types';
import { isReading, usePatchField, useSubmitForReview, useUploadDocuments } from '../api/hooks';
import { allPass } from '../lib/case';
import BeneficiaryCard, { type PendingEdit } from './BeneficiaryCard';
import ReadingProgress from './ReadingProgress';
import { Banner, ErrorCard, SectionHeader } from './common';

interface Props {
  caseState: CaseState;
  onOpenOps: () => void;
  layout?: 'side' | 'stacked';
}

export default function DocumentsSection({ caseState, onOpenOps, layout = 'side' }: Props) {
  const id = caseState.case_id;
  const upload = useUploadDocuments(id);
  const patch = usePatchField(id);
  const submit = useSubmitForReview(id);
  const [edits, setEdits] = useState<Record<string, PendingEdit>>({});
  const [files, setFiles] = useState<Record<string, File[]>>({});

  const reading = isReading(caseState) || upload.isPending || patch.isPending;
  const fixing = caseState.waiting_for === 'heir_fix';
  const pass = allPass(caseState);
  const checks = caseState.checks ?? [];
  const fails = checks.filter((k) => k.status === 'fail').length;
  const reviews = checks.filter((k) => k.status === 'needs_review').length;
  const pendingFiles = Object.values(files).flat();
  const changed = Object.values(edits).filter((e) => {
    const doc = caseState.documents.find((d) => d.id === e.document_id);
    return String(doc?.fields.find((f) => f.name === e.field)?.value ?? '') !== e.value.trim();
  });
  const hasPending = pendingFiles.length > 0 || changed.length > 0;
  const mutationError = (upload.error ?? patch.error ?? submit.error) as Error | null;
  const people = (caseState.beneficiaries ?? []).length;

  // Each correction resumes the flow and re-runs the checks, so send them one at a time
  // while the case still waits for a fix, then any uploads.
  async function recheck() {
    let current = caseState;
    for (const e of changed) {
      if (current.waiting_for !== 'heir_fix') break;
      current = await patch.mutateAsync({ ...e, value: e.value.trim() });
    }
    if (pendingFiles.length && current.waiting_for === 'heir_fix') await upload.mutateAsync(pendingFiles);
    setEdits({});
    setFiles({});
  }

  return (
    <Stack component="section" spacing={1.75} data-testid="documents-section">
      <SectionHeader n="01" title="Documents" action={
        <Button variant="outlined" onClick={recheck} disabled={reading || !fixing || !hasPending} data-testid="recheck">
          Re-check documents
        </Button>
      } />

      {reading && <ReadingProgress documents={caseState.documents} />}

      {!reading && mutationError && (
        <ErrorCard title="We couldn't finish checking your documents" message={mutationError.message}
          onRetry={hasPending ? recheck : undefined} />
      )}

      {!reading && (
        <>
          <Box sx={{ display: 'grid', gridTemplateColumns: layout === 'stacked' ? '1fr' : 'repeat(2, minmax(0, 1fr))', gap: 2 }}>
            {(caseState.beneficiaries ?? []).map((b) => (
              <BeneficiaryCard key={b.id} caseState={caseState} beneficiary={b} stacked={layout === 'stacked'} editable={fixing}
                edits={edits} onEdit={(e) => setEdits((s) => ({ ...s, [`${e.document_id}.${e.field}`]: e }))}
                files={files[b.id] ?? []} onFiles={(f) => setFiles((s) => ({ ...s, [b.id]: f }))} />
            ))}
          </Box>

          {pass && caseState.waiting_for === 'approval' && (
            <Banner tone="info" action={<Button variant="contained" color="secondary" onClick={onOpenOps} sx={{ flex: 'none' }}>Open Estate ops</Button>}>
              <strong>All checks passed for {people === 2 ? 'both beneficiaries' : 'every beneficiary'}.</strong> Estate operations reviews the packet before options open.
            </Banner>
          )}
          {fails > 0 && (
            <Banner tone="fail">
              <strong>{fails === 1 ? 'One issue' : `${fails} issues`} to fix before this can move forward.</strong> Correct the field on the card or upload an updated document, then re-check.
            </Banner>
          )}
          {!fails && reviews > 0 && fixing && (
            <Banner tone="amber" action={
              <Button variant="outlined" onClick={() => submit.mutate()} disabled={submit.isPending} data-testid="submit-for-review" sx={{ flex: 'none', bgcolor: '#fff' }}>
                Send to estate operations
              </Button>}>
              <strong>{reviews === 1 ? 'One item needs' : `${reviews} items need`} a second look.</strong> Fix it here, or send it to estate operations to review with the packet.
            </Banner>
          )}
          {caseState.approved && (
            <Banner tone="pass"><strong>Approved by estate operations.</strong> Your options are below.</Banner>
          )}
        </>
      )}
    </Stack>
  );
}
