// VoteCouncil Service Worker
const CACHE_NAME = 'votecouncil-v1';
const STATIC_CACHE = 'votecouncil-static-v1';

// Static assets to cache
const STATIC_ASSETS = [
    '/static/css/style.css',
    '/static/js/app.js',
    '/static/manifest.json',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js'
];

// Install event - cache static assets
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(cache => {
                console.log('Caching static assets');
                return cache.addAll(STATIC_ASSETS);
            })
            .then(() => self.skipWaiting())
    );
});

// Activate event - clean old caches
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys()
            .then(cacheNames => {
                return Promise.all(
                    cacheNames
                        .filter(name => name !== CACHE_NAME && name !== STATIC_CACHE)
                        .map(name => caches.delete(name))
                );
            })
            .then(() => self.clients.claim())
    );
});

// Fetch event - network first, fallback to cache
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Skip non-GET requests
    if (request.method !== 'GET') {
        return;
    }

    // For API requests, always try network first
    if (url.pathname.startsWith('/api/') ||
        url.pathname.startsWith('/voters') ||
        url.pathname.startsWith('/boxes') ||
        url.pathname.startsWith('/focals') ||
        url.pathname.startsWith('/candidates')) {
        event.respondWith(networkFirst(request));
        return;
    }

    // For static assets, try cache first
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(cacheFirst(request));
        return;
    }

    // For HTML pages, try network first
    event.respondWith(networkFirst(request));
});

// Cache first strategy
async function cacheFirst(request) {
    const cached = await caches.match(request);
    if (cached) {
        return cached;
    }

    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(STATIC_CACHE);
            cache.put(request, response.clone());
        }
        return response;
    } catch (error) {
        console.error('Fetch failed:', error);
        throw error;
    }
}

// Network first strategy
async function networkFirst(request) {
    try {
        const response = await fetch(request);
        if (response.ok && request.method === 'GET') {
            const cache = await caches.open(CACHE_NAME);
            cache.put(request, response.clone());
        }
        return response;
    } catch (error) {
        const cached = await caches.match(request);
        if (cached) {
            return cached;
        }

        // Return offline page for navigation requests
        if (request.mode === 'navigate') {
            return new Response(
                `<!DOCTYPE html>
                <html>
                <head>
                    <title>Offline - VoteCouncil</title>
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <style>
                        body { font-family: system-ui; text-align: center; padding: 50px; }
                        h1 { color: #333; }
                        p { color: #666; }
                        button { padding: 10px 20px; cursor: pointer; }
                    </style>
                </head>
                <body>
                    <h1>You're Offline</h1>
                    <p>Please check your internet connection and try again.</p>
                    <button onclick="location.reload()">Retry</button>
                </body>
                </html>`,
                {
                    headers: { 'Content-Type': 'text/html' }
                }
            );
        }

        throw error;
    }
}

// Background sync for offline actions
self.addEventListener('sync', (event) => {
    if (event.tag === 'sync-vote-status') {
        event.waitUntil(syncVoteStatus());
    }
});

async function syncVoteStatus() {
    // Get pending updates from IndexedDB
    // Send to server when online
    console.log('Syncing vote status updates...');
}

// Push notifications (future feature)
self.addEventListener('push', (event) => {
    if (event.data) {
        const data = event.data.json();
        const options = {
            body: data.body,
            icon: '/static/icons/icon-192.png',
            badge: '/static/icons/icon-72.png',
            vibrate: [100, 50, 100],
            data: {
                url: data.url || '/dashboard'
            }
        };

        event.waitUntil(
            self.registration.showNotification(data.title, options)
        );
    }
});

self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    event.waitUntil(
        clients.openWindow(event.notification.data.url)
    );
});
