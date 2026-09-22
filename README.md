# TV

Dice se un film o una serie è **già compreso** negli abbonamenti che paghi,
e apre l'app giusta sulla TV Samsung. Un file, nessuna dipendenza,
nessun server.

## Come funziona

Il telefono parla diretto a due servizi:

- **TMDB** per la ricerca, i generi, le schede e i trailer
- **cloud SmartThings** per lanciare le app sulla TV e per il telecomando

Non c'è niente in mezzo: nessun server da tenere accesso, nessuna
funzione serverless. Funziona anche da rete mobile.

Il filtro "solo ciò che pago" lo fa TMDB, con `with_watch_providers` +
`watch_region`: quello che non hai in abbonamento non arriva nemmeno
al telefono.

## Non contiene segreti

Le due chiavi le inserisci tu in Impostazioni al primo avvio, e restano
in `localStorage`, sul tuo telefono. Non sono in questo codice e non
passano da nessun server. Per questo il repository può essere pubblico.

- **Chiave TMDB**: themoviedb.org → il tuo profilo → Impostazioni → API
- **Token SmartThings**: account.smartthings.com/tokens, con i permessi
  sui dispositivi

Il token SmartThings comanda tutti i dispositivi del tuo account: dallo
a qualcuno solo se ti fidi di lui come di te.

## Installazione sul telefono

Apri l'indirizzo in Safari, poi Condividi → Aggiungi a Home.
Diventa un'icona come un'app normale.

## Cosa non fa

**Apre l'app giusta, non il titolo.** Il titolo lo cerchi col
telecomando: SmartThings non espone il lancio con deep link.

**Non scrive testo.** La capability del telecomando ha 17 tasti e zero
lettere. Scrivere nei campi di ricerca richiede il collegamento diretto
alla TV, che funziona solo da un computer sulla rete di casa.

## Configurazione

La mappa provider → app e l'elenco degli abbonamenti sono due costanti
in cima allo script dentro `index.html`: `MAPPA` e `SERVIZI`.
Gli id delle app si trovano aprendo l'app col telecomando e leggendo
`tvChannel.tvChannelName` dall'API SmartThings.

Attenzione a `SERVIZI`: una voce di troppo non dà errore, dà una
risposta sbagliata.
