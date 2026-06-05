const CACHE_NAME = 'niceeze-sbds-v1';

const PRECACHE_URLS = [
  'tms_set_001.html',
  'ar_measure.html',
  'pwa_qr.html',
  'manifest.json'
];

// Install: pre-cache listed files
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS))
  );
  // Activate immediately without waiting for old clients to close
  self.skipWaiting();
});

// Activate: delete any caches that are not the current cache name
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) =>
      Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      )
    )
  );
  // Take control of all clients immediately
  self.clients.claim();
});

// Fetch: cache-first strategy — serve from cache, fall back to network and update cache
self.addEventListener('fetch', (event) => {
  // Only handle GET requests
  if (event.request.method !== 'GET') return;

  event.respondWith(
    caches.open(CACHE_NAME).then(async (cache) => {
      const cached = await cache.match(event.request);
      if (cached) {
        // Return cached response, refresh cache in background
        event.waitUntil(
          fetch(event.request)
            .then((networkResponse) => {
              if (networkResponse && networkResponse.ok) {
                cache.put(event.request, networkResponse.clone());
              }
            })
            .catch(() => { /* network unavailable — cached version is fine */ })
        );
        return cached;
      }

      // Not in cache — fetch from network and cache the response
      try {
        const networkResponse = await fetch(event.request);
        if (networkResponse && networkResponse.ok) {
          cache.put(event.request, networkResponse.clone());
        }
        return networkResponse;
      } catch (err) {
        // Network failed and no cache — nothing we can do
        return new Response('Offline — resource not cached.', {
          status: 503,
          statusText: 'Service Unavailable'
        });
      }
    })
  );
});
