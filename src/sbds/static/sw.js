const CACHE_NAME = 'niceeze-sbds-v1';

const PRECACHE_URLS = [
  'tms_set_001.html',
  'ar_measure.html',
  'pwa_qr.html',
  'manifest.json'
];

// Install: precache listed assets
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(PRECACHE_URLS))
  );
  self.skipWaiting();
});

// Activate: remove old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames =>
      Promise.all(
        cacheNames
          .filter(name => name !== CACHE_NAME)
          .map(name => caches.delete(name))
      )
    )
  );
  self.clients.claim();
});

// Fetch: cache-first, fall back to network and update cache
self.addEventListener('fetch', event => {
  // Only handle GET requests
  if (event.request.method !== 'GET') return;

  event.respondWith(
    caches.open(CACHE_NAME).then(async cache => {
      const cached = await cache.match(event.request);
      if (cached) {
        // Serve from cache, then update cache in background
        event.waitUntil(
          fetch(event.request)
            .then(networkResponse => {
              if (networkResponse && networkResponse.status === 200) {
                cache.put(event.request, networkResponse.clone());
              }
            })
            .catch(() => { /* network unavailable, that's OK */ })
        );
        return cached;
      }
      // Not in cache: fetch from network and cache it
      try {
        const networkResponse = await fetch(event.request);
        if (networkResponse && networkResponse.status === 200) {
          cache.put(event.request, networkResponse.clone());
        }
        return networkResponse;
      } catch (err) {
        // Network failed and no cache — nothing to return
        return new Response('Offline — resource not cached.', {
          status: 503,
          headers: { 'Content-Type': 'text/plain' }
        });
      }
    })
  );
});
