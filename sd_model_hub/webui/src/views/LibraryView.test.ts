import { flushPromises, shallowMount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import { computed, ref, toValue } from 'vue';
import LibraryView from './LibraryView.vue';
import { SelectField } from '@/ui';

const queries = vi.hoisted(() => ({ entries: vi.fn(), replace: vi.fn() }));
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ replace: queries.replace }),
}));
vi.mock('@tanstack/vue-query', () => ({ useQueryClient: () => ({ invalidateQueries: vi.fn() }) }));
vi.mock('@/api/queries/library', () => ({
  useRoots: () => ({ data: ref([{ id: 'models', name: 'All models', path: '/models', exists: true }]), isSuccess: ref(true) }),
  useEntries: queries.entries,
  useTree: () => ({ data: ref(null) }),
  useLibraryMutations: () => Object.fromEntries(
    ['rename', 'move', 'remove', 'createFolder', 'importPaths', 'addRoot', 'updateRoot', 'removeRoot', 'scan']
      .map((name) => [name, { isPending: ref(false), mutate: vi.fn() }]),
  ),
}));
vi.mock('@/api/queries/app', () => ({
  useMeta: () => ({ data: ref({ roots_locked: true, kinds: ['lora'], base_models: [] }) }),
  useSettings: () => ({ data: ref({ library: { delete_to_trash: true } }) }),
}));
vi.mock('@/stores/preferences', () => ({ usePreferencesStore: () => ({ prefs: { lastRoot: null, libraryView: 'grid' } }) }));
vi.mock('@/stores/uploads', () => ({ useUploadsStore: () => ({ onFinished: () => () => {}, enqueue: vi.fn() }) }));
vi.mock('@/stores/downloads', () => ({ useDownloadsStore: () => ({ drawerOpen: false }) }));
vi.mock('@/i18n', () => ({ useI18n: () => ({ t: (key: string) => key, kindLabel: (kind: string) => kind }) }));

describe('library folder navigation', () => {
  it('keeps folders visible and navigable while a model kind filter is active', async () => {
    queries.entries.mockImplementation((_root, path) => ({
      data: computed(() => ({
        folders: toValue(path) ? [] : [{ name: 'custom-folder', path: 'custom-folder', folder_kind: null }],
        models: [],
        pending_detection: 0,
      })),
      isPending: ref(false),
      isError: ref(false),
    }));
    const wrapper = shallowMount(LibraryView, {
      global: {
        stubs: {
          FileDropZone: { template: '<div><slot /></div>' },
          ModelGrid: { props: ['items'], template: '<div><slot v-for="item in items" :item="item" /></div>' },
        },
      },
    });
    await flushPromises();
    expect(wrapper.find('button.folder').text()).toContain('custom-folder');

    const filter = wrapper.findAllComponents(SelectField).find((field) => field.props('label') === 'library.filterKind')!;
    filter.vm.$emit('update:modelValue', 'lora');
    await flushPromises();
    expect(toValue(queries.entries.mock.calls[0][2])).toBe('lora');
    expect(wrapper.find('button.folder').exists()).toBe(true);

    await wrapper.find('button.folder').trigger('click');
    await flushPromises();
    expect(toValue(queries.entries.mock.calls[0][1])).toBe('custom-folder');
    expect(toValue(queries.entries.mock.calls[0][2])).toBe('lora');
    expect(queries.replace).toHaveBeenLastCalledWith({ query: { root: 'models', path: 'custom-folder' } });
    wrapper.unmount();
  });
});
