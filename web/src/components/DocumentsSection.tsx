import { useState } from 'react';
import { Box, Button, Stack } from '@mui/material';
import type { CaseState } from '../api/types';
import { isReading, useSubmitForReview, useUploadDocuments } from '../api/hooks';
import { allPass } from '../lib/case';
import BeneficiaryCard from './BeneficiaryCard';
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
  const submit = useSubmitForReview(id);
  const [files, setFiles] = useState<Record<string, File[]>>({});

  const reading = isReading(caseState) || upload.isPending;
  const fixing = caseState.waiting_for === 'heir_fix';
  const pass = allPass(caseState);
  const checks = caseState.checks ?? [];
  const fails = checks.filter((k) => k.status === 'fail').length;
  const reviews = checks.filter((k) => k.status === 'needs_review').length;
  const pendingFiles = Object.values(files).flat();
  const hasPending = pendingFiles.length > 0;
  const mutationError = (upload.error ?? submit.error) as Error | null;
  const people = (caseState.beneficiaries ?? []).length;

  // Values are never edited: the corrected documents are read and every check runs again.
  async function recheck() {
    await upload.mutateAsync(pendingFiles);
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
              <BeneficiaryCard key={b.id} caseState={caseState} beneficiary={b} stacked={layout === 'stacked'} canUpload={fixing}
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
              <strong>{fails === 1 ? 'One issue' : `${fails} issues`} to fix before this can move forward.</strong> Upload a corrected document on the card, then re-check.
            </Banner>
          )}
          {!fails && reviews > 0 && fixing && (
            <Banner tone="amber" action={
              <Button variant="outlined" onClick={() => submit.mutate()} disabled={submit.isPending} data-testid="submit-for-review" sx={{ flex: 'none', bgcolor: '#fff' }}>
                Send to estate operations
              </Button>}>
              <strong>{reviews === 1 ? 'One item needs' : `${reviews} items need`} a second look.</strong> Upload a corrected document, or send it to estate operations to review with the packet.
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
