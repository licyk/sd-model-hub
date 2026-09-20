<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useMeta, useSettings } from '@/api/queries/app';
import { useRoots, useTree } from '@/api/queries/library';
import { useI18n } from '@/i18n';
import { usePreferencesStore } from '@/stores/preferences';
import { AppButton, AppDialog, Checkbox, PathField, SelectField, TextField } from '@/ui';

export interface Destination {
  root_id?: string | null;
  rel_dir?: string | null;
  dest_dir?: string | null;
  overwrite: boolean;
}

/** Root and folder chooser, defaulting to the layout's folder for the model's kind. */
const props = defineProps<{ kind?: string | null; fileLabel?: string | null; loading?: boolean; defaultSubfolder?: string | null }>();
const open = defineModel<boolean>('open', { default: false });
const emit = defineEmits<{ confirm: [Destination] }>();
const { t } = useI18n();
const prefs = usePreferencesStore();
const roots = useRoots();
const meta = useMeta();
const settings = useSettings();

const rootId = ref<string | null>(null);
const relDir = ref('');
const absolute = ref('');
const overwrite = ref(false);
const tree = useTree(rootId);

const rootOptions = computed(() => [...(roots.data.value ?? []).map((r) => ({ value: r.id, label: r.name })), { value: '__abs__', label: t('dest.absolute') }]);
const root = computed(() => roots.data.value?.find((r) => r.id === rootId.value));

/** The first folder of the layout that maps to the kind, preferring one that exists. */
const suggested = computed(() => {
  const kind = props.kind;
  const layout = root.value?.layout;
  if (!kind || !layout) return '';
  const configured = settings.data.value?.downloads.kind_folders?.[kind];
  if (configured) return configured;
  const mapping = meta.data.value?.layouts[layout] ?? {};
  const candidates = Object.entries(mapping).filter(([, k]) => k === kind).map(([folder]) => folder);
  const existing = new Set<string>();
  const walk = (node: { path: string; children?: { path: string; children?: unknown[] }[] }, depth: number) => {
    existing.add(node.path);
    if (depth < 2) for (const c of node.children ?? []) walk(c as never, depth + 1);
  };
  if (tree.data.value) walk(tree.data.value as never, 0);
  return candidates.find((c) => existing.has(c)) ?? candidates.find((c) => !c.startsWith('models/')) ?? candidates[0] ?? '';
});

watch(open, (v) => {
  if (!v) return;
  const list = roots.data.value ?? [];
  const preferred = settings.data.value?.downloads.default_root ?? prefs.prefs.lastRoot;
  rootId.value = list.find((r) => r.id === preferred)?.id ?? list[0]?.id ?? '__abs__';
  overwrite.value = false;
});
watch([suggested, open], () => {
  if (open.value) relDir.value = [suggested.value, props.defaultSubfolder].filter(Boolean).join('/');
});

function confirm() {
  if (rootId.value === '__abs__') emit('confirm', { dest_dir: absolute.value.trim(), overwrite: overwrite.value });
  else emit('confirm', { root_id: rootId.value, rel_dir: relDir.value.trim(), overwrite: overwrite.value });
}
</script>

<template>
  <AppDialog v-model:open="open" :title="t('dest.title')" width="small">
    <div class="form">
      <p v-if="fileLabel" class="type-body-medium muted file">{{ t('dest.fileName') }}: {{ fileLabel }}</p>
      <p v-if="!roots.data.value?.length" class="type-body-medium muted">{{ t('dest.noRoots') }}</p>
      <SelectField v-model="rootId" :label="t('dest.root')" :options="rootOptions" />
      <PathField v-if="rootId === '__abs__'" v-model="absolute" :label="t('dest.absolute')" />
      <TextField v-else v-model="relDir" :label="t('dest.folder')" :supporting-text="t('dest.folderHelp')" @enter="confirm" />
      <Checkbox v-model="overwrite" :label="t('dest.overwrite')" />
      <slot />
    </div>
    <template #actions>
      <AppButton variant="text" @click="open = false">{{ t('common.cancel') }}</AppButton>
      <AppButton :loading="loading" :disabled="rootId === '__abs__' && !absolute.trim()" @click="confirm">{{ t('dest.queue') }}</AppButton>
    </template>
  </AppDialog>
</template>

<style scoped>
.form { display: flex; flex-direction: column; gap: var(--app-space-3); }
.file { margin: 0; word-break: break-all; }
</style>
