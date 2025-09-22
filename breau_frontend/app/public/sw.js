/* Breau SW — minimal app-shell cache */
const CACHE_VERSION = 'breau-v1.0.0';
const STATIC_CACHE = `static-${CACHE_VERSION}`;
const STATIC_ASSETS = [
  '/', '/index.html', '/offline.html',
  '/manifest.webmanifest',
  '/icons/icon-192.png', '/icons/icon-512.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(STATIC_CACHE);
    await cache.addAll(STATIC_ASSETS);
    if ('navigationPreload' in self.registration) {
      await self.registration.navigationPreload.enable();
    }
    self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.map(k => (k.startsWith('static-') && k !== STATIC_CACHE) ? caches.delete(k) : undefined));
    self.clients.claim();
  })());
});

async function cacheFirst(req) {
  const cache = await caches.open(STATIC_CACHE);
  const cached = await cache.match(req);
  if (cached) return cached;
  const res = await fetch(req);
  if (res.ok && (req.url.includes('/assets/') || req.url.endsWith('.css') || req.url.endsWith('.js'))) {
    cache.put(req, res.clone());
  }
  return res;
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  if (request.method !== 'GET' || url.origin !== location.origin) return;

  if (request.mode === 'navigate') {
    event.respondWith((async () => {
      try {
        const preloaded = await event.preloadResponse;
        if (preloaded) return preloaded;

        const net = await fetch(request);
        const cache = await caches.open(STATIC_CACHE);
        cache.put('/index.html', net.clone());
        return net;
      } catch {
        const cache = await caches.open(STATIC_CACHE);
        const cachedIndex = await cache.match('/index.html');
        return cachedIndex || (await cache.match('/offline.html'));
      }
    })());
    return;
  }

  if (url.pathname.startsWith('/assets/') || url.pathname.startsWith('/icons/')) {
    event.respondWith(cacheFirst(request));
    return;
  }

  event.respondWith((async () => {
    const cache = await caches.open(STATIC_CACHE);
    const hit = await cache.match(request);
    if (hit) return hit;
    try {
      const res = await fetch(request);
      if (res.ok && (request.destination === 'style' || request.destination === 'script' || request.destination === 'image')) {
        cache.put(request, res.clone());
      }
      return res;
    } catch {
      return new Response('Offline', { status: 503 });
    }
  })());
});