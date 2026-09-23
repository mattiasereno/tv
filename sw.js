// Service worker: serve a far APRIRE l'app senza rete.
//
// Strategia: rete per prima, cache come ripiego. Non il contrario.
// Il contrario e' come si costruisce un'app che resta indietro per
// sempre e non si capisce perche': con rete vedi sempre l'ultima
// versione, senza rete vedi l'ultima che avevi.
//
// Tocca SOLO i file nostri. Le chiamate a TMDB e SmartThings non
// passano da qui: hanno bisogno di dati freschi, e una risposta
// vecchia in cache sarebbe peggio di un errore.
//
// versione.json non viene mai messo in cache, altrimenti il
// controllo di versione confronterebbe due copie vecchie fra loro.

const DEPOSITO = "tv-1";
const ESSENZIALI = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./icona-180.png",
  "./icona-192.png",
  "./icona-512.png",
];

self.addEventListener("install", e => {
  e.waitUntil(
    caches.open(DEPOSITO)
      .then(c => c.addAll(ESSENZIALI))
      .catch(() => {})            // se un file manca, non blocco l'installazione
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys()
      .then(nomi => Promise.all(nomi.filter(n => n !== DEPOSITO).map(n => caches.delete(n))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  const r = e.request;
  if (r.method !== "GET") return;

  const url = new URL(r.url);
  if (url.origin !== self.location.origin) return;   // TMDB, SmartThings, immagini
  if (url.pathname.endsWith("versione.json")) return; // deve essere sempre fresco

  e.respondWith(
    fetch(r)
      .then(risposta => {
        if (risposta && risposta.ok) {
          const copia = risposta.clone();
          caches.open(DEPOSITO).then(c => c.put(r, copia)).catch(() => {});
        }
        return risposta;
      })
      .catch(() =>
        caches.match(r)
          .then(c => c || caches.match("./index.html"))
          // Se anche la cache e' vuota devo restituire una Response
          // comunque: respondWith(undefined) fa fallire la richiesta
          // con un errore di rete generico e indecifrabile.
          .then(c => c || new Response(
            "Sei senza rete e non ho ancora una copia di questa pagina.",
            { status: 503, headers: { "Content-Type": "text/plain; charset=utf-8" } }))
      )
  );
});
