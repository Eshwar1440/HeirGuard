import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import { READING_STATUSES } from '../config';
import { toCaseState, type AiLogRecord, type AuditEntry, type CaseGraph, type CaseState, type CaseView, type Choice, type HeirInputs, type Sample } from './types';

export const qk = {
  samples: ['samples'] as const,
  case: (id: string) => ['case', id] as const,
  graph: (id: string) => ['case', id, 'graph'] as const,
  audit: (id: string) => ['case', id, 'audit'] as const,
  aiLog: (id: string) => ['case', id, 'ai-log'] as const,
};

export const isReading = (c?: CaseState | null) => !!c && READING_STATUSES.includes(String(c.status ?? ''));

export function useSamples() {
  return useQuery({ queryKey: qk.samples, queryFn: () => api.get<Sample[]>('/samples') });
}

export function useCase(id: string | null) {
  return useQuery({
    queryKey: qk.case(id ?? ''),
    queryFn: async () => toCaseState(await api.get<CaseView>(`/cases/${id}`)),
    enabled: !!id,
  });
}

export function useGraph(id: string | null, enabled = true) {
  return useQuery({ queryKey: qk.graph(id ?? ''), queryFn: () => api.get<CaseGraph>(`/cases/${id}/graph`), enabled: !!id && enabled });
}

export function useAudit(id: string | null) {
  return useQuery({ queryKey: qk.audit(id ?? ''), queryFn: () => api.get<AuditEntry[]>(`/cases/${id}/audit`), enabled: !!id });
}

export function useAiLog(id: string | null) {
  return useQuery({ queryKey: qk.aiLog(id ?? ''), queryFn: () => api.get<AiLogRecord[]>(`/cases/${id}/ai-log`), enabled: !!id });
}

/** Every case mutation returns the new CaseView: store it, then refresh the under-the-hood views. */
function useCaseMutation<TVars>(id: string | null, fn: (id: string, v: TVars) => Promise<CaseView>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (v: TVars) => toCaseState(await fn(id!, v)),
    onSuccess: (c) => {
      qc.setQueryData(qk.case(c.case_id), c);
      for (const key of [qk.graph(c.case_id), qk.audit(c.case_id), qk.aiLog(c.case_id)]) qc.invalidateQueries({ queryKey: key });
    },
  });
}

export function useCreateCase() {
  const qc = useQueryClient();
  return useMutation({
    // A sample case opens with its records on file and reads its packet; with no sample the case
    // opens empty and waits for the heir's upload.
    mutationFn: async (sample_id: string | null) =>
      toCaseState(await api.post<CaseView>('/cases', { sample_id, with_documents: sample_id !== null })),
    onSuccess: (c) => qc.setQueryData(qk.case(c.case_id), c),
  });
}

export const useUploadDocuments = (id: string | null) =>
  useCaseMutation<File[]>(id, (cid, files) => api.upload<CaseView>(`/cases/${cid}/documents`, files));

/** Demo only (under the hood): read the case's sample packet as if the heir uploaded it. */
export const useLoadSampleDocuments = (id: string | null) =>
  useCaseMutation<void>(id, (cid) => api.post<CaseView>(`/cases/${cid}/sample-documents`));

export const useSubmitForReview = (id: string | null) =>
  useCaseMutation<void>(id, (cid) => api.post<CaseView>(`/cases/${cid}/submit-for-review`));

export const useApprove = (id: string | null) =>
  useCaseMutation<{ approved: boolean; note?: string } | void>(id, (cid, v) => api.post<CaseView>(`/cases/${cid}/approve`, v ?? { approved: true }));

export const useSimulate = (id: string | null) =>
  useCaseMutation<HeirInputs>(id, (cid, inputs) => api.post<CaseView>(`/cases/${cid}/simulate`, inputs));

export const useChoice = (id: string | null) =>
  useCaseMutation<{ choice: Choice; opt_in_rmd_deposit: boolean }>(id, (cid, v) => api.post<CaseView>(`/cases/${cid}/choice`, v));
