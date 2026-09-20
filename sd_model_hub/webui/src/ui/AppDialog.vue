<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue';
import IconButton from './IconButton.vue';
import { X } from './icons';
import { containerFrom } from './motion/transitions';

/**
 * A modal dialog built from the tokens. With ``fromRect`` it grows from that rectangle (the
 * ``container`` transition); otherwise it fades and scales.
 */
const props = withDefaults(defineProps<{ title?: string; fromRect?: DOMRect | null; width?: 'small' | 'medium' | 'large'; closeLabel?: string }>(), { width: 'medium', closeLabel: 'Close' });
const open = defineModel<boolean>('open', { default: false });
const emit = defineEmits<{ closed: [] }>();
const panel = ref<HTMLElement | null>(null);
const motionStyle = ref<Record<string, string>>({});
let previousFocus: HTMLElement | null = null;

function onKey(event: KeyboardEvent) {
  if (event.key === 'Escape') open.value = false;
  if (event.key === 'Tab' && panel.value) {
    const focusable = panel.value.querySelectorAll<HTMLElement>('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"]), md-filled-button, md-outlined-button, md-text-button, md-filled-tonal-button, md-icon-button');
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      last.focus();
      event.preventDefault();
    } else if (!event.shiftKey && document.activeElement === last) {
      first.focus();
      event.preventDefault();
    }
  }
}

watch(
  open,
  async (value) => {
    if (value) {
      previousFocus = document.activeElement as HTMLElement | null;
      document.addEventListener('keydown', onKey);
      motionStyle.value = {};
      await nextTick();
      // Offsets ignore the enter transform already applied, unlike getBoundingClientRect().
      const p = panel.value;
      motionStyle.value = p ? containerFrom(props.fromRect, new DOMRect(p.offsetLeft, p.offsetTop, p.offsetWidth, p.offsetHeight)) : {};
      panel.value?.focus();
    } else {
      document.removeEventListener('keydown', onKey);
      previousFocus?.focus?.();
    }
  },
  { immediate: true },
);
onBeforeUnmount(() => document.removeEventListener('keydown', onKey));
</script>

<template>
  <Teleport to="body">
    <Transition name="scrim">
      <div v-if="open" class="scrim" @click="open = false" />
    </Transition>
    <Transition name="container" @after-leave="emit('closed')">
      <div v-if="open" class="layer" @click.self="open = false">
        <section ref="panel" class="dialog" :class="width" role="dialog" aria-modal="true" :aria-label="title" tabindex="-1" :style="motionStyle">
          <header v-if="title || $slots.header" class="head">
            <slot name="header"><h2 class="type-headline-small title">{{ title }}</h2></slot>
            <IconButton :icon="X" :label="closeLabel" @click="open = false" />
          </header>
          <div class="body"><slot /></div>
          <footer v-if="$slots.actions" class="actions"><slot name="actions" /></footer>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.scrim { position: fixed; inset: 0; background: color-mix(in srgb, var(--md-sys-color-scrim) 32%, transparent); z-index: 40; }
.layer { position: fixed; inset: 0; display: grid; place-items: center; padding: var(--app-space-4); z-index: 41; }
.dialog {
  display: flex; flex-direction: column; max-height: calc(100vh - 32px); width: 100%; outline: none;
  background: var(--md-sys-color-surface-container-high); color: var(--md-sys-color-on-surface);
  border-radius: var(--md-sys-shape-corner-extra-large); box-shadow: var(--app-elevation-3);
}
.small { max-width: 400px; }
.medium { max-width: 640px; }
.large { max-width: 1040px; }
.head { display: flex; align-items: center; justify-content: space-between; gap: var(--app-space-2); padding: var(--app-space-4) var(--app-space-4) 0 var(--app-space-6); }
.title { margin: 0; overflow: hidden; text-overflow: ellipsis; }
.body { padding: var(--app-space-4) var(--app-space-6); overflow: auto; flex: 1; }
.actions { display: flex; justify-content: flex-end; flex-wrap: wrap; gap: var(--app-space-2); padding: 0 var(--app-space-6) var(--app-space-6); }
@media (max-width: 599px) {
  .layer { padding: 0; align-items: end; }
  .dialog { max-height: 92vh; border-radius: var(--md-sys-shape-corner-extra-large) var(--md-sys-shape-corner-extra-large) 0 0; }
}
</style>
