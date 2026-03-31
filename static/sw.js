// VoteCouncil Service Worker
const CACHE_NAME = 'votecouncil-v5';
const STATIC_CACHE = 'votecouncil-static-v5';

// Static assets to cache
const STATIC_ASSETS = [
    '/static/css/style.css',
    '/static/js/app.js',
    '/static/manifest.json',
    '/voting',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css',
    'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js'
];

// --- IndexedDB wrapper ---
const DB_NAME = 'votecouncil-offline';
const DB_VERSION = 1;
const STORE_NAME = 'pendingVotes';

function openDB() {
    return new Promise((resolve, reject) => {
        const req = indexedDB.open(DB_NAME, DB_VERSION);
        req.onupgradeneeded = () => {
            const db = req.result;
            if (!db.objectStoreNames.contains(STORE_NAME)) {
                db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
            }
        };
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
    });
}

async function addPendingVote(url, body) {
    const db = await openDB();
    return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, 'readwrite');
        tx.objectStore(STORE_NAME).add({ url, body, timestamp: Date.now() });
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
    });
}

async function getAllPendingVotes() {
    const db = await openDB();
    return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, 'readonly');
        const req = tx.objectStore(STORE_NAME).getAll();
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
    });
}

async function deletePendingVote(id) {
    const db = await openDB();
    return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE_NAME, 'readwrite');
        tx.objectStore(STORE_NAME).delete(id);
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
    });
}

// --- Service Worker events ---

// Install event - cache static assets (resilient: skip failures)
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(cache => {
                console.log('Caching static assets');
                return Promise.allSettled(
                    STATIC_ASSETS.map(url =>
                        cache.add(url).catch(err => console.warn('Cache skip:', url, err.message))
                    )
                );
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

// Fetch event
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Handle POST requests to /voting/mark/* - queue offline if fetch fails
    if (request.method === 'POST' && url.pathname.match(/^\/voting\/mark\//)) {
        event.respondWith(handleVoteMark(request));
        return;
    }

    // Skip other non-GET requests
    if (request.method !== 'GET') {
        return;
    }

    // For static assets and CDN resources, use cache-first
    if (url.pathname.startsWith('/static/') ||
        url.hostname === 'cdn.jsdelivr.net') {
        event.respondWith(cacheFirst(request));
        return;
    }

    // For API/data requests, use network-first
    if (url.pathname.startsWith('/api/') ||
        url.pathname.startsWith('/voters') ||
        url.pathname.startsWith('/boxes') ||
        url.pathname.startsWith('/focals') ||
        url.pathname.startsWith('/candidates')) {
        event.respondWith(networkFirst(request));
        return;
    }

    // For HTML pages, use network-first
    event.respondWith(networkFirst(request));
});

// Handle vote mark POST - try network, queue offline on failure
async function handleVoteMark(request) {
    const clonedRequest = request.clone();
    try {
        const response = await fetch(request);
        return response;
    } catch (error) {
        // Offline - store in IndexedDB for later sync
        const body = await clonedRequest.json();
        const url = clonedRequest.url;
        await addPendingVote(url, body);

        // Notify all clients about the pending vote so badges update
        const clients = await self.clients.matchAll();
        clients.forEach(client => {
            client.postMessage({ type: 'vote-queued' });
        });

        // Register for background sync
        if (self.registration.sync) {
            await self.registration.sync.register('sync-vote-status');
        }

        // Return synthetic success so UI doesn't break
        return new Response(
            JSON.stringify({ status: 'queued', message: 'Saved offline - will sync when online' }),
            {
                status: 200,
                headers: { 'Content-Type': 'application/json' }
            }
        );
    }
}

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

// Background sync - replay queued votes
self.addEventListener('sync', (event) => {
    if (event.tag === 'sync-vote-status') {
        event.waitUntil(syncPendingVotes());
    }
});

async function syncPendingVotes() {
    const pendingVotes = await getAllPendingVotes();
    console.log(`Syncing ${pendingVotes.length} pending votes...`);

    for (const vote of pendingVotes) {
        try {
            const response = await fetch(vote.url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(vote.body)
            });

            if (response.ok) {
                await deletePendingVote(vote.id);
                console.log(`Synced vote ${vote.id}`);
            }
        } catch (error) {
            console.error(`Failed to sync vote ${vote.id}:`, error);
            // Stop trying if still offline
            break;
        }
    }

    // Notify clients that sync is done
    const clients = await self.clients.matchAll();
    clients.forEach(client => {
        client.postMessage({ type: 'sync-complete' });
    });
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
