<script setup lang="ts">
import { useQueryClient } from '@tanstack/vue-query';
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { previewUrl } from '@/api/client';
import { keys } from '@/api/queries/keys';
import { useEntries, useLibraryMutations, useRoots, useTree } from '@/api/queries/library';
import { useMeta } from '@/api/queries/app';
import type { FolderEntry, ModelEntry } from '@/api/types';
import FileDropZone, { type DroppedFile } from '@/components/FileDropZone.vue';
import FolderTree from '@/components/FolderTree.vue';
import ModelCard from '@/components/ModelCard.vue';
import ModelGrid from '@/components/ModelGrid.vue';
import ModelInfoDialog from '@/components/ModelInfoDialog.vue';
import MoveDialog from '@/components/MoveDialog.vue';
import RenameDialog from '@/components/RenameDialog.vue';
import RootDialog from '@/components/RootDialog.vue';
import { formatBytes, pathSegments } from '@/format';
import { useI18n } from '@/i18n';
import { useDownloadsStore } from '@/stores/downloads';
import { usePreferencesStore } from '@/stores/preferences';
import { useUploadsStore } from '@/stores/uploads';
import { useSettings } from '@/api/queries/app';
import {
  AppButton,
  AppDialog,
  AppIcon,
  AppMenu,
  Breadcrumbs,
  Checkbox,
  ConfirmDialog,
  EmptyState,
  IconButton,
  PathField,
  SegmentedButton,
  SelectField,
  Skeleton,
  TextField,
  icons,
  type MenuItem,
  useSnackbar,
} from '@/ui';

const { t, kindLabel } = useI18n();
const route = useRoute();
const router = useRouter();
const qc = useQueryClient();
const prefs = usePreferencesStore();
const uploads = useUploadsStore();
const downloadsStore = useDownloadsStore();
const snackbar = useSnackbar();
const settings = useSettings();
const meta = useMeta();
const roots = useRoots();
const m = useLibraryMutations();

const str = (v: unknown) => (typeof v === 'string' ? v : null);
const rootId = ref<string | null>(str(route.query.root) ?? prefs.prefs.lastRoot);
const path = ref(str(route.query.path) ?? '');
const kind = ref<string | null>(null);
const direction = ref(1);

watch(
  () => roots.data.value,
  (list) => {
    if (!list) return;
    if (!list.some((r) => r.id === rootId.value)) {
      rootId.value = list[0]?.id ?? null;
      path.value = '';
    }
  },
  { immediate: true },
);
watch([rootId, path], ([r, p]) => {
  if (r) prefs.prefs.lastRoot = r;
  router.replace({ query: { root: r ?? undefined, path: p || undefined } });
  selection.value = new Set();
});
// A link pasted while this view is already open must move it, not only fill it on first load.
watch(
  () => [route.query.root, route.query.path],
  ([r, p]) => {
    const nextRoot = str(r) ?? rootId.value;
    const nextPath = str(p) ?? '';
    if (nextRoot !== rootId.value) rootId.value = nextRoot;
    if (nextPath !== path.value) path.value = nextPath;
  },
);

const entries = useEntries(rootId, path, kind);
const tree = useTree(rootId);
const root = computed(() => roots.data.value?.find((r) => r.id === rootId.value) ?? null);
const listing = computed(() => entries.data.value);
const rootOptions = computed(() => (roots.data.value ?? []).map((r) => ({ value: r.id, label: r.name })));
const kindOptions = computed(() => [{ value: '', label: t('browse.allKinds') }, ...(meta.data.value?.kinds ?? []).map((k) => ({ value: k, label: kindLabel(k) }))]);
const crumbs = computed(() => [{ label: root.value?.name ?? '', value: '' }, ...pathSegments(path.value).map((s) => ({ label: s.name, value: s.path }))]);

function navigate(to: string) {
  direction.value = to.length >= path.value.length ? 1 : -1;
  path.value = to;
}

type Item = { type: 'folder'; folder: FolderEntry } | { type: 'model'; model: ModelEntry };
const items = computed<Item[]>(() => [
  ...(listing.value?.folders ?? []).map((folder) => ({ type: 'folder' as const, folder })),
  ...(listing.value?.models ?? []).map((model) => ({ type: 'model' as const, model })),
]);
const itemKey = (i: Item) => (i.type === 'folder' ? `f:${i.folder.path}` : `m:${i.model.path}`);

// Selection
const selection = ref(new Set<string>());
const toggle = (p: string, on: boolean) => {
  const next = new Set(selection.value);
  if (on) next.add(p);
  else next.delete(p);
  selection.value = next;
};

// Dialogs
const infoOpen = ref(false);
const infoPath = ref<string | null>(null);
const infoRect = ref<DOMRect | null>(null);
function openInfo(model: ModelEntry, rect: DOMRect | null) {
  infoPath.value = model.path;
  infoRect.value = rect;
  infoOpen.value = true;
}

const renameOpen = ref(false);
const renameTarget = ref<{ path: string; name: string; isFile: boolean } | null>(null);
const renameError = ref<string | null>(null);
function startRename(path: string, name: string, isFile: boolean) {
  renameTarget.value = { path, name, isFile };
  renameError.value = null;
  renameOpen.value = true;
}
function doRename(newName: string) {
  if (!rootId.value || !renameTarget.value) return;
  m.rename.mutate(
    { root_id: rootId.value, path: renameTarget.value.path, new_name: newName },
    { onSuccess: () => (renameOpen.value = false), onError: (e) => (renameError.value = (e as Error).message) },
  );
}

const moveOpen = ref(false);
const movePaths = ref<string[]>([]);
function startMove(paths: string[]) {
  movePaths.value = paths;
  moveOpen.value = true;
}
function doMove(dest: { rootId: string; dir: string }) {
  if (!rootId.value) return;
  m.move.mutate(
    { items: movePaths.value.map((p) => ({ root_id: rootId.value!, path: p })), dest_root_id: dest.rootId, dest_dir: dest.dir, on_conflict: 'error' },
    {
      onSuccess: () => {
        moveOpen.value = false;
        selection.value = new Set();
        qc.invalidateQueries({ queryKey: ['library'] });
      },
      onError: (e) => snackbar.error((e as Error).message),
    },
  );
}

const deleteOpen = ref(false);
const deletePaths = ref<string[]>([]);
const permanent = ref(false);
const toTrash = computed(() => settings.data.value?.library.delete_to_trash !== false);
function startDelete(paths: string[]) {
  deletePaths.value = paths;
  permanent.value = !toTrash.value;
  deleteOpen.value = true;
}
function doDelete() {
  if (!rootId.value) return;
  m.remove.mutate(
    { items: deletePaths.value.map((p) => ({ root_id: rootId.value!, path: p })), permanent: permanent.value },
    {
      onSuccess: () => {
        deleteOpen.value = false;
        selection.value = new Set();
        qc.invalidateQueries({ queryKey: ['library'] });
      },
      onError: (e) => snackbar.error((e as Error).message),
    },
  );
}

const folderOpen = ref(false);
const folderName = ref('');
function doCreateFolder() {
  if (!rootId.value || !folderName.value.trim()) return;
  m.createFolder.mutate(
    { root_id: rootId.value, path: path.value, name: folderName.value.trim() },
    {
      onSuccess: () => {
        folderOpen.value = false;
        folderName.value = '';
      },
      onError: (e) => snackbar.error((e as Error).message),
    },
  );
}

const importOpen = ref(false);
const importPath = ref('');
const importMove = ref(false);
function doImport() {
  if (!rootId.value || !importPath.value.trim()) return;
  m.importPaths.mutate(
    { sources: [importPath.value.trim()], root_id: rootId.value, rel_dir: path.value, move: importMove.value, on_conflict: 'error' },
    {
      onSuccess: () => {
        importOpen.value = false;
        importPath.value = '';
      },
      onError: (e) => snackbar.error((e as Error).message),
    },
  );
}

const rootDialogOpen = ref(false);
const editingRoot = ref(false);
const rootError = ref<string | null>(null);
function openRootDialog(edit: boolean) {
  editingRoot.value = edit;
  rootError.value = null;
  rootDialogOpen.value = true;
}
function saveRoot(form: { name: string | null; path: string; layout: 'comfyui' | 'sd-webui' | 'custom'; kind: string | null }) {
  const onError = (e: unknown) => (rootError.value = (e as Error).message);
  if (editingRoot.value && rootId.value) {
    m.updateRoot.mutate({ id: rootId.value, body: form }, { onSuccess: () => (rootDialogOpen.value = false), onError });
  } else {
    m.addRoot.mutate(form, {
      onSuccess: (r) => {
        rootDialogOpen.value = false;
        rootId.value = r.id;
        path.value = '';
      },
      onError,
    });
  }
}
const removeRootOpen = ref(false);
function doRemoveRoot() {
  if (!rootId.value) return;
  m.removeRoot.mutate(rootId.value, { onSuccess: () => (removeRootOpen.value = false) });
}

// A host application can fix the model folders; the actions that would change them are then gone.
const rootsLocked = computed(() => meta.data.value?.roots_locked ?? false);
const rootMenu = computed<MenuItem[]>(() =>
  rootsLocked.value
    ? []
    : [
        { id: 'add', label: t('library.addRoot'), icon: icons.Plus },
        { id: 'edit', label: t('library.editRoot'), icon: icons.Pencil, disabled: !root.value },
        { id: 'remove', label: t('library.removeRoot'), icon: icons.Trash2, danger: true, disabled: !root.value },
      ],
);
function onRootMenu(id: string) {
  if (id === 'add') openRootDialog(false);
  if (id === 'edit') openRootDialog(true);
  if (id === 'remove') removeRootOpen.value = true;
}

const modelMenu = computed<MenuItem[]>(() => [
  { id: 'info', label: t('common.info'), icon: icons.Info },
  { id: 'rename', label: t('common.rename'), icon: icons.Pencil },
  { id: 'move', label: t('common.move'), icon: icons.Move },
  { id: 'delete', label: t('common.delete'), icon: icons.Trash2, danger: true },
]);
function onModelMenu(id: string, model: ModelEntry) {
  if (id === 'info') openInfo(model, null);
  if (id === 'rename') startRename(model.path, model.name, !model.is_dir);
  if (id === 'move') startMove([model.path]);
  if (id === 'delete') startDelete([model.path]);
}
const folderMenu = computed<MenuItem[]>(() => [
  { id: 'rename', label: t('common.rename'), icon: icons.Pencil },
  { id: 'move', label: t('common.move'), icon: icons.Move },
  { id: 'delete', label: t('common.delete'), icon: icons.Trash2, danger: true },
]);
function onFolderMenu(id: string, folder: FolderEntry) {
  if (id === 'rename') startRename(folder.path, folder.name, false);
  if (id === 'move') startMove([folder.path]);
  if (id === 'delete') startDelete([folder.path]);
}

function rescan() {
  if (!rootId.value) return;
  m.scan.mutate({ rootId: rootId.value, path: path.value }, { onSuccess: () => snackbar.show(t('library.scanStarted')) });
}

// Drag and drop: files land in the folder on screen.
function onDrop(files: DroppedFile[]) {
  if (!rootId.value) return;
  uploads.enqueue(rootId.value, path.value, files);
  snackbar.show(t('library.uploadStarted', { n: files.length }), { actionLabel: t('browse.openDownloads'), action: () => (downloadsStore.drawerOpen = true) });
}
const stopListening = uploads.onFinished((item) => {
  if (item.state === 'failed') snackbar.error(t('library.uploadFailed', { name: item.name, error: item.error ?? '' }));
  qc.invalidateQueries({ queryKey: keys.entries(item.rootId) });
  qc.invalidateQueries({ queryKey: keys.tree(item.rootId) });
});
onBeforeUnmount(stopListening);

const warningFor = (model: ModelEntry) => (model.mismatch ? t('library.mismatchText') : null);
const baseFor = (model: ModelEntry) => {
  const b = model.detection?.base_model ?? model.sidecar?.base_model;
  return b ? (meta.data.value?.base_models.find((x) => x.value === b)?.label ?? b) : null;
};
const kindFor = (model: ModelEntry) => {
  const k = model.detection?.kind && model.detection.kind !== 'unknown' ? model.detection.kind : (model.sidecar?.kind ?? model.folder_kind ?? 'unknown');
  return kindLabel(k);
};
</script>

<template>
  <div class="library">
    <EmptyState
      v-if="roots.isSuccess.value && !roots.data.value?.length"
      :icon="icons.HardDrive"
      :title="t('library.noRootsTitle')"
      :text="rootsLocked ? t('library.rootsLocked') : t('library.noRootsText')"
      class="no-roots"
    >
      <AppButton v-if="!rootsLocked" :icon="icons.FolderPlus" @click="openRootDialog(false)">{{ t('library.addRoot') }}</AppButton>
    </EmptyState>

    <template v-else>
      <aside class="side">
        <div class="root-row">
          <SelectField v-model="rootId" :label="t('library.root')" :options="rootOptions" class="root-select" @update:model-value="path = ''" />
          <AppMenu v-if="rootMenu.length" :items="rootMenu" @select="onRootMenu">
            <template #default="{ toggle }"><IconButton :icon="icons.MoreVertical" :label="t('common.more')" @click="toggle" /></template>
          </AppMenu>
        </div>
        <p v-if="root" class="type-body-small muted root-path" :title="root.path">{{ root.path }}</p>
        <p v-if="root && !root.exists" class="type-body-small error">{{ t('library.missing') }}</p>
        <div class="tree" role="tree">
          <FolderTree v-if="tree.data.value" :node="tree.data.value" :selected="path" @select="navigate" />
          <div v-else class="tree-skeleton"><Skeleton v-for="i in 6" :key="i" height="28px" shape="full" /></div>
        </div>
      </aside>

      <section class="main">
        <FileDropZone :label="t('library.dropHere', { folder: path || root?.name || '/' })" :disabled="!rootId" @files="onDrop">
          <div class="head">
            <Breadcrumbs :crumbs="crumbs" @navigate="navigate" />
            <div class="toolbar">
              <template v-if="selection.size">
                <span class="type-label-large">{{ t('library.selected', { n: selection.size }) }}</span>
                <IconButton :icon="icons.Move" :label="t('common.move')" @click="startMove([...selection])" />
                <IconButton :icon="icons.Trash2" :label="t('common.delete')" @click="startDelete([...selection])" />
                <IconButton :icon="icons.X" :label="t('library.clearSelection')" @click="selection = new Set()" />
              </template>
              <template v-else>
                <AppButton variant="tonal" :icon="icons.FolderInput" @click="importOpen = true">{{ t('library.import') }}</AppButton>
                <IconButton :icon="icons.FolderPlus" :label="t('library.newFolder')" @click="folderOpen = true" />
                <IconButton :icon="icons.RefreshCw" :label="t('library.rescan')" :spin="m.scan.isPending.value" @click="rescan" />
                <SelectField :model-value="kind ?? ''" :label="t('library.filterKind')" :options="kindOptions" class="kind" @update:model-value="kind = $event || null" />
                <SegmentedButton
                  v-model="prefs.prefs.libraryView"
                  :options="[
                    { value: 'grid', icon: icons.LayoutGrid, ariaLabel: t('library.grid') },
                    { value: 'list', icon: icons.LayoutList, ariaLabel: t('library.list') },
                  ]"
                />
              </template>
            </div>
          </div>

          <Transition name="shared-axis-x" mode="out-in">
            <div :key="`${rootId}:${path}:${kind}`" class="content" :style="{ '--axis-dir': direction }">
              <div v-if="entries.isPending.value" class="skeletons">
                <div v-for="i in 10" :key="i" class="skeleton-card"><Skeleton height="200px" shape="medium" /><Skeleton width="70%" /></div>
              </div>
              <EmptyState v-else-if="entries.isError.value" :icon="icons.AlertTriangle" :title="t('common.error')" :text="(entries.error.value as Error)?.message" />
              <EmptyState v-else-if="!items.length" :icon="icons.FolderOpen" :title="t('library.emptyTitle')" :text="t('library.emptyText')">
                <AppButton variant="tonal" :icon="icons.FolderInput" @click="importOpen = true">{{ t('library.import') }}</AppButton>
              </EmptyState>
              <ModelGrid v-else :items="items" :item-key="itemKey" :layout="prefs.prefs.libraryView">
                <template #default="{ item }">
                  <button v-if="item.type === 'folder'" type="button" class="folder state-layer" :class="`folder-${prefs.prefs.libraryView}`" @click="navigate(item.folder.path)">
                    <span class="folder-icon"><AppIcon :icon="icons.Folder" :size="24" /></span>
                    <span class="folder-text">
                      <span class="type-title-small folder-name">{{ item.folder.name }}</span>
                      <span v-if="item.folder.folder_kind" class="type-body-small muted">{{ kindLabel(item.folder.folder_kind) }}</span>
                    </span>
                    <AppMenu :items="folderMenu" @select="onFolderMenu($event, item.folder)">
                      <template #default="{ toggle }"><IconButton :icon="icons.MoreVertical" :label="t('common.more')" @click.stop="toggle" /></template>
                    </AppMenu>
                  </button>
                  <ModelCard
                    v-else
                    :layout="prefs.prefs.libraryView"
                    :title="item.model.name"
                    :subtitle="formatBytes(item.model.size)"
                    :preview="item.model.preview && rootId ? previewUrl(rootId, item.model.preview, prefs.prefs.libraryView === 'list' ? 128 : 384) : null"
                    :kind="kindFor(item.model)"
                    :base="baseFor(item.model)"
                    :warning="warningFor(item.model)"
                    :pending="!item.model.detection && (listing?.pending_detection ?? 0) > 0"
                    :selected="selection.has(item.model.path)"
                    @activate="openInfo(item.model, $event)"
                  >
                    <template #select>
                      <Checkbox
                        :model-value="selection.has(item.model.path)"
                        :dense="prefs.prefs.libraryView === 'list'"
                        :class="prefs.prefs.libraryView === 'list' ? '' : 'select-box'"
                        @update:model-value="toggle(item.model.path, $event)"
                      />
                    </template>
                    <template #actions>
                      <AppMenu :items="modelMenu" @select="onModelMenu($event, item.model)">
                        <template #default="{ toggle: open }"><IconButton :icon="icons.MoreVertical" :label="t('common.more')" @click="open" /></template>
                      </AppMenu>
                    </template>
                  </ModelCard>
                </template>
              </ModelGrid>
            </div>
          </Transition>
        </FileDropZone>
      </section>
    </template>

    <ModelInfoDialog v-model:open="infoOpen" :root-id="rootId" :path="infoPath" :from-rect="infoRect" />
    <RenameDialog v-model:open="renameOpen" :name="renameTarget?.name ?? ''" :is-file="renameTarget?.isFile" :loading="m.rename.isPending.value" :error="renameError" @confirm="doRename" />
    <MoveDialog v-model:open="moveOpen" :count="movePaths.length" :root-id="rootId" :loading="m.move.isPending.value" @confirm="doMove" />
    <ConfirmDialog
      v-model:open="deleteOpen"
      :title="t('library.deleteTitle', { n: deletePaths.length })"
      :message="permanent ? t('library.deletePermanent') : t('library.deleteTrash')"
      :confirm-label="t('common.delete')"
      :cancel-label="t('common.cancel')"
      :loading="m.remove.isPending.value"
      danger
      @confirm="doDelete"
    >
      <Checkbox v-if="toTrash" v-model="permanent" :label="t('library.permanent')" />
    </ConfirmDialog>
    <AppDialog v-model:open="folderOpen" :title="t('library.newFolder')" width="small">
      <TextField v-model="folderName" :label="t('library.folderName')" @enter="doCreateFolder" />
      <template #actions>
        <AppButton variant="text" @click="folderOpen = false">{{ t('common.cancel') }}</AppButton>
        <AppButton :disabled="!folderName.trim()" :loading="m.createFolder.isPending.value" @click="doCreateFolder">{{ t('common.save') }}</AppButton>
      </template>
    </AppDialog>
    <AppDialog v-model:open="importOpen" :title="t('library.import')" width="small">
      <div class="form">
        <PathField v-model="importPath" :label="t('library.importPath')" :supporting-text="t('library.importHelp')" placeholder="/path/to/model.safetensors" @enter="doImport" />
        <Checkbox v-model="importMove" :label="t('library.importMove')" />
      </div>
      <template #actions>
        <AppButton variant="text" @click="importOpen = false">{{ t('common.cancel') }}</AppButton>
        <AppButton :disabled="!importPath.trim()" :loading="m.importPaths.isPending.value" @click="doImport">{{ t('library.import') }}</AppButton>
      </template>
    </AppDialog>
    <RootDialog v-model:open="rootDialogOpen" :root="editingRoot ? root : null" :loading="m.addRoot.isPending.value || m.updateRoot.isPending.value" :error="rootError" @confirm="saveRoot" />
    <ConfirmDialog
      v-model:open="removeRootOpen"
      :title="t('library.removeRoot')"
      :message="t('library.removeRootText')"
      :confirm-label="t('library.removeRoot')"
      :cancel-label="t('common.cancel')"
      @confirm="doRemoveRoot"
    />
  </div>
</template>

<style scoped>
.library { display: grid; grid-template-columns: 280px minmax(0, 1fr); height: 100%; }
.no-roots { grid-column: 1 / -1; align-self: center; }
.side { display: flex; flex-direction: column; gap: var(--app-space-2); padding: var(--app-space-4); border-right: 1px solid var(--md-sys-color-outline-variant); min-height: 0; }
.root-row { display: flex; align-items: center; gap: var(--app-space-1); }
.root-select { flex: 1; min-width: 0; }
.root-path { margin: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; direction: rtl; text-align: left; }
.error { color: var(--md-sys-color-error); margin: 0; }
.tree { flex: 1; overflow: auto; margin: 0 calc(-1 * var(--app-space-2)); }
.tree-skeleton { display: flex; flex-direction: column; gap: var(--app-space-2); padding: var(--app-space-2); }
.main { min-width: 0; overflow: auto; }
.head { position: sticky; top: 0; z-index: 5; display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--app-space-2); padding: var(--app-space-3) var(--app-space-4); background: var(--md-sys-color-surface-container-low); }
.toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: var(--app-space-2); }
.kind { min-width: 150px; }
.content { position: relative; padding: 0 var(--app-space-4) var(--app-space-6); }
.skeletons { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: var(--app-space-3); }
.skeleton-card { display: flex; flex-direction: column; gap: var(--app-space-2); }
.folder {
  display: flex; align-items: center; gap: var(--app-space-3); width: 100%; padding: var(--app-space-2) var(--app-space-1) var(--app-space-2) var(--app-space-3);
  border: 0; border-radius: var(--md-sys-shape-corner-medium); background: var(--md-sys-color-surface-container); color: var(--md-sys-color-on-surface); cursor: pointer; text-align: left; font: inherit;
}
.folder-grid { min-height: 64px; }
.folder-list { min-height: 56px; }
.folder-icon { display: grid; place-items: center; width: 40px; height: 40px; border-radius: var(--md-sys-shape-corner-small); background: var(--md-sys-color-secondary-container); color: var(--md-sys-color-on-secondary-container); flex: none; }
.folder-text { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.folder-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.select-box { padding: 2px; border-radius: var(--md-sys-shape-corner-small); background: color-mix(in srgb, var(--md-sys-color-surface) 70%, transparent); }
.form { display: flex; flex-direction: column; gap: var(--app-space-3); }
@media (max-width: 839px) {
  .library { grid-template-columns: minmax(0, 1fr); grid-template-rows: auto 1fr; }
  .side { border-right: 0; border-bottom: 1px solid var(--md-sys-color-outline-variant); }
  .tree { max-height: 160px; }
}
</style>
