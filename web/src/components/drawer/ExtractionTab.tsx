import { useState } from 'react';
import { Document as PdfDocument, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import { Box, Chip, LinearProgress, Stack, Typography } from '@mui/material';
import type { CaseState } from '../../api/types';
import { API_URL, CONFIDENCE_THRESHOLD } from '../../config';
import { formatConfidence } from '../../lib/format';
import { tokens as t } from '../../theme';

pdfjs.GlobalWorkerOptions.workerSrc = new URL('pdfjs-dist/build/pdf.worker.min.mjs', import.meta.url).toString();

const DOC_NAMES: Record<string, string> = { death_certificate: 'Death certificate', inherited_ira_application: 'Application' };

// file_ref is a Supabase Storage path; the browser never talks to Supabase directly (AGENTS.md).
// Expects the backend to serve the file. TODO: confirm the route with M8 (not in the current endpoint list).
const fileUrl = (caseId: string, docId: string, ref: string) =>
  /^https?:/.test(ref) ? ref : `${API_URL}/cases/${caseId}/documents/${docId}/file`;

export default function ExtractionTab({ caseState }: { caseState: CaseState }) {
  const docs = caseState.documents ?? [];
  const [docId, setDocId] = useState(docs[docs.length - 1]?.id);
  const [pdfFailed, setPdfFailed] = useState(false);
  const doc = docs.find((d) => d.id === docId) ?? docs[0];
  if (!doc) return <Typography variant="body2">No documents read yet.</Typography>;
  const failingFields = new Set((caseState.checks ?? []).filter((c) => c.status !== 'pass').flatMap((c) => (c.evidence ?? []).filter((e) => e.document_id === doc.id).map((e) => e.field_name)));

  return (
    <Stack spacing={1.75} data-testid="tab-extraction">
      <Stack direction="row" spacing={0.75} useFlexGap sx={{ flexWrap: 'wrap' }}>
        {docs.map((d) => {
          const on = d.id === doc.id;
          const who = d.fields.find((f) => f.name === 'beneficiary_name')?.value;
          return <Chip key={d.id} onClick={() => { setDocId(d.id); setPdfFailed(false); }} label={`${DOC_NAMES[d.doc_type] ?? d.doc_type}${who ? ` · ${String(who).split(' ')[0]}` : ''}`}
            sx={{ fontWeight: 500, bgcolor: on ? t.navy : '#fff', color: on ? '#fff' : t.body, border: `1px solid ${on ? t.navy : t.inputBorder}` }} />;
        })}
      </Stack>
      <Box sx={{ display: 'grid', gridTemplateColumns: '170px 1fr', gap: 2, alignItems: 'start' }}>
        <Box sx={{ border: `1px solid ${t.inputBorder}`, boxShadow: '0 2px 6px rgba(15,39,66,.12)', bgcolor: '#fff', minHeight: 220, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          {pdfFailed ? (
            <Typography variant="caption" sx={{ p: 1.5, textAlign: 'center' }}>Preview unavailable</Typography>
          ) : (
            <PdfDocument file={fileUrl(caseState.case_id, doc.id, doc.file_ref)} onLoadError={() => setPdfFailed(true)}
              loading={<Typography variant="caption">Loading page…</Typography>}>
              <Page pageNumber={1} width={168} renderAnnotationLayer={false} renderTextLayer={false} />
            </PdfDocument>
          )}
        </Box>
        <Box>
          <Stack direction="row" sx={{ justifyContent: 'space-between', fontSize: 11.5, color: t.muted, pb: 0.75, borderBottom: `1px solid ${t.rule}` }}>
            <span>Field · value</span><span>Confidence (threshold {CONFIDENCE_THRESHOLD}, hypothetical)</span>
          </Stack>
          {doc.fields.map((f) => {
            const low = f.confidence < CONFIDENCE_THRESHOLD;
            const bad = failingFields.has(f.name);
            return (
              <Box key={f.name} sx={{ py: 1, borderBottom: `1px solid ${t.rowRule}` }} data-testid={`ext-${f.name}`}>
                <Stack direction="row" spacing={1} sx={{ justifyContent: 'space-between' }}>
                  <Box sx={{ fontFamily: t.mono, fontSize: 11.5, color: t.muted }}>{f.name} <span style={{ color: t.disabled }}>p.{f.page}</span></Box>
                  <Box sx={{ fontSize: 13, fontWeight: 600, color: bad ? t.fail : f.value == null ? t.muted : t.ink, bgcolor: bad ? t.failTint : 'transparent', px: bad ? 0.5 : 0 }}>{f.value == null ? 'unreadable' : String(f.value)}</Box>
                </Stack>
                <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mt: 0.6 }}>
                  <Box sx={{ position: 'relative', flex: 1 }}>
                    <LinearProgress variant="determinate" value={f.confidence * 100} sx={{ height: 5, '& .MuiLinearProgress-bar': { bgcolor: low ? t.amber : t.accent } }} />
                    <Box sx={{ position: 'absolute', left: `${CONFIDENCE_THRESHOLD * 100}%`, top: -3, width: '1px', height: 11, bgcolor: t.ink }} />
                  </Box>
                  <Box sx={{ fontSize: 11.5, width: 30, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{formatConfidence(f.confidence)}</Box>
                </Stack>
              </Box>
            );
          })}
          {doc.needs_review && <Typography variant="caption" sx={{ color: t.amberText, display: 'block', mt: 1 }}>Needs review: a field is below the threshold.</Typography>}
        </Box>
      </Box>
    </Stack>
  );
}
