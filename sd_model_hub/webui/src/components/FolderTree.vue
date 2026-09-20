<script setup lang="ts">
import { ref, watch } from 'vue';
import type { TreeNode } from '@/api/types';
import { AppIcon, collapseHooks, icons } from '@/ui';

defineOptions({ name: 'FolderTree' });

/** Library navigation. Nodes on the path to the selected folder open automatically. */
const props = withDefaults(defineProps<{ node: TreeNode; selected: string; depth?: number }>(), { depth: 0 });
const emit = defineEmits<{ select: [string] }>();
const isAncestor = (path: string) => path === '' || props.selected === path || props.selected.startsWith(`${path}/`);
const expanded = ref(props.depth === 0 || isAncestor(props.node.path));
watch(
  () => props.selected,
  () => {
    if (isAncestor(props.node.path)) expanded.value = true;
  },
);
</script>

<template>
  <div class="tree-node" role="treeitem" :aria-expanded="node.children.length ? expanded : undefined" :aria-selected="selected === node.path">
    <div class="row state-layer" :class="{ active: selected === node.path }" :style="{ paddingInlineStart: `${depth * 12 + 4}px` }" @click="emit('select', node.path)">
      <button v-if="node.children.length" type="button" class="toggle" :aria-label="expanded ? 'Collapse' : 'Expand'" @click.stop="expanded = !expanded">
        <AppIcon :icon="icons.ChevronRight" :size="18" class="chevron" :class="{ open: expanded }" />
      </button>
      <span v-else class="toggle" />
      <AppIcon :icon="selected === node.path ? icons.FolderOpen : icons.Folder" :size="18" />
      <span class="type-label-large name" :title="node.name">{{ node.name }}</span>
    </div>
    <Transition name="collapse" v-bind="collapseHooks">
      <div v-if="expanded && node.children.length" role="group">
        <FolderTree v-for="child in node.children" :key="child.path" :node="child" :selected="selected" :depth="depth + 1" @select="emit('select', $event)" />
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.row {
  display: flex; align-items: center; gap: var(--app-space-1); height: 36px; padding-right: var(--app-space-2);
  border-radius: var(--md-sys-shape-corner-full); cursor: pointer; color: var(--md-sys-color-on-surface-variant);
}
.row.active { background: var(--md-sys-color-secondary-container); color: var(--md-sys-color-on-secondary-container); }
.toggle { display: grid; place-items: center; width: 24px; height: 24px; flex: none; border: 0; padding: 0; background: transparent; color: inherit; cursor: pointer; border-radius: 50%; }
.chevron { transition: transform var(--md-sys-motion-duration-short4) var(--md-sys-motion-easing-standard); }
.chevron.open { transform: rotate(90deg); }
.name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
