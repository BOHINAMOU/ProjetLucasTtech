// Service worker minimal : permet à Chrome/Android de proposer l'installation de l'application (aucune mise en cache hors ligne).
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', () => {});
