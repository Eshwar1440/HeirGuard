import { useState } from 'react';
import { Box, Button, Stack } from '@mui/material';
import type { CaseState } from '../api/types';
import { isReading, useSubmitForReview, useUploadDocuments } from '../api/hooks';
import { allPass } from '../lib/case';
import BeneficiaryCard from './BeneficiaryCard';
import ReadingProgress from './ReadingProgress';
import UploadDocuments from './UploadDocuments';
import { Banner, ErrorCard, SectionHeader } from './common';

interface Props {
  caseState: CaseState;
  layout?: 'side' | 'stacked';
}

export default function DocumentsSection({ caseState, layout = 'side' }: Props) {
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

      {/* First visit: nothing uploaded yet, so the upload card is the whole section. */}
      {!caseState.documents.length && !reading && <UploadDocuments caseState={caseState} />}

      {!reading && mutationError && (
        <ErrorCard title="We couldn't finish checking your documents" message={mutationError.message}
          onRetry={hasPending ? recheck : undefined} />
      )}

      {!reading && caseState.documents.length > 0 && (
        <>
          <Box sx={{ display: 'grid', gridTemplateColumns: layout === 'stacked' ? '1fr' : 'repeat(2, minmax(0, 1fr))', gap: 2 }}>
            {(caseState.beneficiaries ?? []).map((b) => (
              <BeneficiaryCard key={b.id} caseState={caseState} beneficiary={b} stacked={layout === 'stacked'} canUpload={fixing}
                files={files[b.id] ?? []} onFiles={(f) => setFiles((s) => ({ ...s, [b.id]: f }))} />
            ))}
          </Box>

          {pass && caseState.waiting_for === 'approval' && (
            // The approval itself happens under the hood (Estate ops tab), not on the heir's page.
            <Banner tone="pass"><strong>All checks passed for {people === 2 ? 'both beneficiaries' : 'every beneficiary'}.</strong></Banner>
          )}
          {caseState.review_note && fixing && (
            <Banner tone="amber" action={!fails ? (
              <Button variant="outlined" onClick={() => submit.mutate()} disabled={submit.isPending} data-testid="resubmit" sx={{ flex: 'none', bgcolor: '#fff' }}>
                Send for review again
              </Button>) : undefined}>
              <strong>Your documents need another look.</strong> {caseState.review_note} Upload a corrected document on the card, then re-check.
            </Banner>
          )}
          {fails > 0 && (
            <Banner tone="fail">
              <strong>{fails === 1 ? 'One issue' : `${fails} issues`} to fix before this can move forward.</strong> Upload a corrected document on the card, then re-check.
            </Banner>
          )}
          {!fails && reviews > 0 && fixing && !caseState.review_note && (
            <Banner tone="amber" action={
              <Button variant="outlined" onClick={() => submit.mutate()} disabled={submit.isPending} data-testid="submit-for-review" sx={{ flex: 'none', bgcolor: '#fff' }}>
                Send for review
              </Button>}>
              <strong>{reviews === 1 ? 'One item needs' : `${reviews} items need`} a second look.</strong> Upload a corrected document, or send it for review with the rest of the packet.
            </Banner>
          )}
          {caseState.approved && (
            <Banner tone="pass"><strong>Your documents are approved.</strong> Your options are below.</Banner>
          )}
        </>
      )}
    </Stack>
  );
}
