import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query';
import { api, unwrap } from '../client';
import type { DownloadCreate, DownloadJob } from '../types';
import { keys } from './keys';

export const useDownloads = () => useQuery({ queryKey: keys.downloads, queryFn: () => unwrap(api.GET('/api/v1/downloads')) });

/** Replace or insert one job in the cached list (used by socket events and mutations). */
export function upsertJob(list: DownloadJob[] | undefined, job: DownloadJob): DownloadJob[] {
  const rest = (list ?? []).filter((j) => j.id !== job.id);
  return [job, ...rest].sort((a, b) => b.id - a.id);
}

export function useCreateDownload() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: DownloadCreate) => unwrap(api.POST('/api/v1/downloads', { body })),
    onSuccess: (job) => qc.setQueryData<DownloadJob[]>(keys.downloads, (old) => upsertJob(old, job)),
  });
}

type Action = 'pause' | 'resume' | 'cancel' | 'restart';

export function useJobAction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action }: { id: number; action: Action }) =>
      unwrap(api.POST(`/api/v1/downloads/{job_id}/${action}` as '/api/v1/downloads/{job_id}/pause', { params: { path: { job_id: id } } })),
    onSuccess: (job) => qc.setQueryData<DownloadJob[]>(keys.downloads, (old) => upsertJob(old, job)),
  });
}

export function useRemoveJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => unwrap(api.DELETE('/api/v1/downloads/{job_id}', { params: { path: { job_id: id } } })),
    onSuccess: (_d, id) => qc.setQueryData<DownloadJob[]>(keys.downloads, (old) => (old ?? []).filter((j) => j.id !== id)),
  });
}

export function useClearFinished() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.POST('/api/v1/downloads/clear-finished')),
    onSuccess: (ids) => qc.setQueryData<DownloadJob[]>(keys.downloads, (old) => (old ?? []).filter((j) => !ids.includes(j.id))),
  });
}
