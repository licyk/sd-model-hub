import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query';
import { computed, type MaybeRefOrGetter, toValue } from 'vue';
import { api, unwrap } from '../client';
import type { S } from '../types';
import { keys } from './keys';

export const useRoots = () => useQuery({ queryKey: keys.roots, queryFn: () => unwrap(api.GET('/api/v1/library/roots')) });

export function useEntries(rootId: MaybeRefOrGetter<string | null>, path: MaybeRefOrGetter<string>, kind: MaybeRefOrGetter<string | null>) {
  return useQuery({
    queryKey: computed(() => keys.entries(toValue(rootId) ?? '', toValue(path), toValue(kind))),
    enabled: computed(() => !!toValue(rootId)),
    queryFn: () =>
      unwrap(
        api.GET('/api/v1/library/roots/{root_id}/entries', {
          params: { path: { root_id: toValue(rootId)! }, query: { path: toValue(path), kind: toValue(kind) ?? undefined } },
        }),
      ),
    placeholderData: (prev) => prev,
  });
}

export function useTree(rootId: MaybeRefOrGetter<string | null>) {
  return useQuery({
    queryKey: computed(() => keys.tree(toValue(rootId) ?? '')),
    enabled: computed(() => !!toValue(rootId)),
    queryFn: () => unwrap(api.GET('/api/v1/library/roots/{root_id}/tree', { params: { path: { root_id: toValue(rootId)! } } })),
  });
}

export function useModelInfo(rootId: MaybeRefOrGetter<string | null>, path: MaybeRefOrGetter<string | null>) {
  return useQuery({
    queryKey: computed(() => keys.modelInfo(toValue(rootId) ?? '', toValue(path) ?? '')),
    enabled: computed(() => !!toValue(rootId) && !!toValue(path)),
    queryFn: () => unwrap(api.GET('/api/v1/library/roots/{root_id}/model', { params: { path: { root_id: toValue(rootId)! }, query: { path: toValue(path)! } } })),
  });
}

export async function fetchModelHash(rootId: string, path: string): Promise<string | null> {
  const info = await unwrap(api.GET('/api/v1/library/roots/{root_id}/model', { params: { path: { root_id: rootId }, query: { path, hash: true } } }));
  return info.sha256 ?? null;
}

/** Mutations for roots and file operations. Each invalidates the library queries it affects. */
export function useLibraryMutations() {
  const qc = useQueryClient();
  const refreshRoot = (rootId?: string) => {
    qc.invalidateQueries({ queryKey: rootId ? keys.entries(rootId) : ['library', 'entries'] });
    qc.invalidateQueries({ queryKey: rootId ? keys.tree(rootId) : ['library', 'tree'] });
  };
  const refreshRoots = () => qc.invalidateQueries({ queryKey: keys.roots });

  return {
    addRoot: useMutation({ mutationFn: (body: S['RootCreate']) => unwrap(api.POST('/api/v1/library/roots', { body })), onSuccess: refreshRoots }),
    updateRoot: useMutation({
      mutationFn: ({ id, body }: { id: string; body: S['RootUpdate'] }) => unwrap(api.PATCH('/api/v1/library/roots/{root_id}', { params: { path: { root_id: id } }, body })),
      onSuccess: (_d, v) => {
        refreshRoots();
        refreshRoot(v.id);
      },
    }),
    removeRoot: useMutation({ mutationFn: (id: string) => unwrap(api.DELETE('/api/v1/library/roots/{root_id}', { params: { path: { root_id: id } } })), onSuccess: refreshRoots }),
    rename: useMutation({ mutationFn: (body: S['RenameRequest']) => unwrap(api.POST('/api/v1/library/rename', { body })), onSuccess: (_d, v) => refreshRoot(v.root_id) }),
    move: useMutation({ mutationFn: (body: S['MoveRequest']) => unwrap(api.POST('/api/v1/library/move', { body })), onSuccess: () => refreshRoot() }),
    remove: useMutation({ mutationFn: (body: S['DeleteRequest']) => unwrap(api.POST('/api/v1/library/delete', { body })), onSuccess: () => refreshRoot() }),
    createFolder: useMutation({ mutationFn: (body: S['FolderCreate']) => unwrap(api.POST('/api/v1/library/folders', { body })), onSuccess: (_d, v) => refreshRoot(v.root_id) }),
    importPaths: useMutation({ mutationFn: (body: S['ImportRequest']) => unwrap(api.POST('/api/v1/library/import', { body })), onSuccess: (_d, v) => refreshRoot(v.root_id) }),
    scan: useMutation({
      mutationFn: ({ rootId, path }: { rootId: string; path: string }) => unwrap(api.POST('/api/v1/library/roots/{root_id}/scan', { params: { path: { root_id: rootId }, query: { path } } })),
    }),
  };
}
