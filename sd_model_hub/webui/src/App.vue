<script setup lang="ts">
import { useQueryClient } from '@tanstack/vue-query';
import { computed, onBeforeUnmount, onMounted, watch } from 'vue';
import { RouterView } from 'vue-router';
import { useDownloads } from '@/api/queries/downloads';
import { connectSocket, disconnectSocket } from '@/api/socket';
import AuthDialog from '@/components/AuthDialog.vue';
import DownloadsDrawer from '@/components/DownloadsDrawer.vue';
import { useI18n } from '@/i18n';
import { useDownloadsStore } from '@/stores/downloads';
import { usePreferencesStore } from '@/stores/preferences';
import { useUploadsStore } from '@/stores/uploads';
import { applyTheme, watchSystemTheme } from '@/theme/applyTheme';
import { AppShell, IconButton, TRANSITIONS, icons, type NavItem } from '@/ui';

const { t, locale } = useI18n();
const qc = useQueryClient();
const prefs = usePreferencesStore();
const downloadsStore = useDownloadsStore();
const uploads = useUploadsStore();
const jobs = useDownloads();

const themeOptions = () => ({ mode: prefs.prefs.theme, sourceColor: prefs.prefs.sourceColor, contrast: prefs.prefs.contrast });
watch(() => [prefs.prefs.theme, prefs.prefs.sourceColor, prefs.prefs.contrast], () => applyTheme(themeOptions()), { immediate: true });
watch(locale, (l) => (document.documentElement.lang = l), { immediate: true });
const stopTheme = watchSystemTheme(themeOptions);

onMounted(() => {
  connectSocket(qc);
  prefs.loadFromServer();
});
onBeforeUnmount(() => {
  stopTheme();
  disconnectSocket();
});

const activeCount = computed(() => (jobs.data.value ?? []).filter((j) => j.state === 'running' || j.state === 'queued').length + uploads.active);
const nav = computed<NavItem[]>(() => [
  { to: '/browse', label: t('nav.browse'), icon: icons.Search },
  { to: '/hubs', label: t('nav.hubs'), icon: icons.Box },
  { to: '/library', label: t('nav.library'), icon: icons.Library },
  { to: '/settings', label: t('nav.settings'), icon: icons.Settings },
]);
const cycleTheme = () => (prefs.prefs.theme = prefs.prefs.theme === 'light' ? 'dark' : prefs.prefs.theme === 'dark' ? 'system' : 'light');
const themeIcon = computed(() => ({ light: icons.Sun, dark: icons.Moon, system: icons.SunMoon })[prefs.prefs.theme]);
</script>

<template>
  <AppShell :items="nav" :title="t('app.title')">
    <template #rail-top>
      <IconButton :icon="icons.Sparkles" :label="t('app.title')" tonal />
    </template>
    <template #actions>
      <IconButton :icon="themeIcon" :label="`${t('settings.theme')}: ${t(`settings.themes.${prefs.prefs.theme}`)}`" @click="cycleTheme" />
      <IconButton :icon="icons.Download" :label="t('nav.downloads')" :badge="activeCount || null" @click="downloadsStore.drawerOpen = true" />
    </template>
    <RouterView v-slot="{ Component, route }">
      <Transition :name="TRANSITIONS.fadeThrough" mode="out-in">
        <component :is="Component" :key="route.name" />
      </Transition>
    </RouterView>
  </AppShell>
  <DownloadsDrawer />
  <AuthDialog />
</template>
