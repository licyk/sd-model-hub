import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query';
import { createPinia } from 'pinia';
import { createApp } from 'vue';
import App from '@/App.vue';
import { ApiError } from '@/api/client';
import { router } from '@/router';
import '@/theme/tokens.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      // Client errors (bad input, not found, needs a token) are not worth retrying.
      retry: (count, error) => !(error instanceof ApiError && error.status >= 400 && error.status < 500) && count < 2,
    },
  },
});

createApp(App).use(createPinia()).use(router).use(VueQueryPlugin, { queryClient }).mount('#app');

// The starting screen in index.html fades out once the interface is on the page.
const boot = document.getElementById('boot');
if (boot) {
  requestAnimationFrame(() => boot.classList.add('boot-done'));
  boot.addEventListener('transitionend', () => boot.remove(), { once: true });
  // A browser that skips the transition, or a tab in the background, must not keep the overlay.
  setTimeout(() => boot.remove(), 1500);
}
