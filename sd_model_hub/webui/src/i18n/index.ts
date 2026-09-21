import { computed } from 'vue';
import en from '@/i18n/en';
import zhCN from '@/i18n/zh-CN';
import { usePreferencesStore, type Locale } from '@/stores/preferences';

const MESSAGES: Record<Locale, typeof en> = { en, 'zh-CN': zhCN };
export const LOCALES: { value: Locale; label: string }[] = [
  { value: 'en', label: 'English' },
  { value: 'zh-CN', label: '简体中文' },
];

function lookup(tree: unknown, key: string): string | undefined {
  let node: unknown = tree;
  for (const part of key.split('.')) {
    if (node && typeof node === 'object' && part in (node as Record<string, unknown>)) node = (node as Record<string, unknown>)[part];
    else return undefined;
  }
  return typeof node === 'string' ? node : undefined;
}

export function translate(locale: Locale, key: string, params?: Record<string, string | number>): string {
  const text = lookup(MESSAGES[locale], key) ?? lookup(MESSAGES.en, key) ?? key;
  return params ? text.replace(/\{(\w+)\}/g, (_, name: string) => String(params[name] ?? `{${name}}`)) : text;
}

/** ``t(key, params)`` in the current locale; reactive to the locale preference. */
export function useI18n() {
  const store = usePreferencesStore();
  const locale = computed(() => store.prefs.locale);
  const t = (key: string, params?: Record<string, string | number>) => translate(locale.value, key, params);
  /** A kind label, falling back to the raw value for kinds without a translation. */
  const kindLabel = (kind: string | null | undefined) => (kind ? (lookup(MESSAGES[locale.value].kinds, kind) ?? kind) : t('common.unknown'));
  return { t, locale, kindLabel };
}
