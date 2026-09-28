#!/usr/bin/env python3
"""
Scrivere su una tastiera a schermo muovendosi a frecce.

Perche' serve: Netflix e NOW hanno una tastiera PROPRIA, non quella di
Tizen, quindi il testo iniettato (SendInputString) non arriva - provato
col cursore dentro il campo: zero eventi IME, mentre la ricerca Samsung
risponde imeUpdate. L'unica strada e' muoversi sulla loro tastiera e
premere OK su ogni lettera.

Qui c'e' solo il CALCOLO dei percorsi, senza rete, cosi' si prova da
solo: `python3 tastiere.py --prove`.

Il rischio da tenere presente: non c'e' nessun riscontro dalla TV. Se
una disposizione e' sbagliata di una colonna, scrive spazzatura e
niente puo' accorgersene. Per questo ogni disposizione ha la fonte
scritta accanto, e va riprovata dopo un aggiornamento dell'app.
"""

# --- come si modella una tastiera -------------------------------------
#
# Una griglia di celle, 6 colonne per Netflix. I tasti larghi (spazio,
# cancella) occupano piu' celle con la stessa etichetta: nel modello
# muoversi dentro un tasto largo "costa" un passo per cella, sulla TV
# invece costa un passo solo. La differenza e' innocua in una sola
# direzione:
#
#   verso SINISTRA i passi in eccesso finiscono contro il bordo e non
#   fanno niente, quindi si arriva comunque sul tasto giusto;
#   verso DESTRA i passi in eccesso escono dalla tastiera.
#
# Da qui due regole, controllate dalle prove in fondo:
#   1. lo spazio sta in colonna 0, cosi' lo si raggiunge sempre andando
#      a sinistra o restando fermi, mai a destra;
#   2. CANCELLA non e' mai una destinazione.
#
# Dopo un tasto largo non si sa su quale cella si scenda (il tasto ne
# copre tre), quindi si riaggancia: giu' e poi tutto a sinistra, che
# contro il bordo e' una posizione certa.

SPAZIO = " "
CANCELLA = "\b"

DISPOSIZIONI = {
    # Fonte: blogs.sas.com/content/iml/2018/09/12 (griglia 6x7, lettere
    # in ordine alfabetico, spazio e cancella da 3 colonne sopra le
    # lettere, cursore iniziale su A, nessun wrap-around) piu'
    # ediblecode.com/blog/tv-keyboards ("A-Z layout, 6x6, numeri
    # inclusi, nessun wrap"). Le due fonti concordano.
    "netflix": {
        "nome": "Netflix",
        "griglia": [
            SPAZIO * 3 + CANCELLA * 3,
            "abcdef",
            "ghijkl",
            "mnopqr",
            "stuvwx",
            "yz0123",
            "456789",
        ],
        "partenza": (1, 0),      # il cursore arriva su A
        "larghi": {SPAZIO, CANCELLA},
    },
    # Griglia finta, serve solo alle prove.
    "prova": {
        "nome": "prova",
        "griglia": ["abcdef", "ghijkl", "mnopqr", "stuvwx", "yz0123"],
        "partenza": (0, 0),
        "larghi": set(),
    },
}


# App che ci sono ma di cui non conosco la tastiera. Servono a
# rifiutare il lavoro invece di scrivere il loro nome come se fosse un
# titolo: ognuna ha una disposizione sua, e la TV non la sa dire.
SENZA_DISPOSIZIONE = {
    "now", "nowtv", "disney", "disney+", "prime", "primevideo",
    "apple", "appletv", "hbo", "hbomax", "max", "infinity",
    "mediaset", "discovery", "discovery+", "youtube",
}


def posizioni(griglia):
    """Dove sta ogni carattere. Per i tasti larghi vince la cella piu'
    a sinistra, che e' quella raggiungibile senza andare a destra."""
    dove = {}
    for r, riga in enumerate(griglia):
        for c, ch in enumerate(riga):
            dove.setdefault(ch, (r, c))
    return dove


def muovi(griglia, da, verso):
    """Un passo. Ai bordi il cursore resta dov'e', come sulla TV."""
    r, c = da
    if verso == "UP":
        r = max(0, r - 1)
    elif verso == "DOWN":
        r = min(len(griglia) - 1, r + 1)
    elif verso == "LEFT":
        c = max(0, c - 1)
    elif verso == "RIGHT":
        c = min(len(griglia[r]) - 1, c + 1)
    return (r, min(c, len(griglia[r]) - 1))


def percorso(griglia, da, a):
    """I tasti per andare da una cella all'altra: prima in verticale,
    poi in orizzontale. Cambiando riga la colonna si schiaccia sulla
    larghezza della riga nuova, e calcolarla dopo lo spostamento
    verticale evita di contare passi che la TV non farebbe."""
    passi, pos = [], da
    # I due cicli hanno un tetto perche' una disposizione incoerente
    # non deve appendere in silenzio: dentro a-Shell, sul telefono,
    # sarebbe un blocco muto invece di un errore da leggere.
    tetto = len(griglia) + max(len(r) for r in griglia) + 2
    for _ in range(tetto):
        if pos[0] == a[0]:
            break
        passi.append("DOWN" if a[0] > pos[0] else "UP")
        pos = muovi(griglia, pos, passi[-1])
    for _ in range(tetto):
        if pos[1] == a[1]:
            break
        passi.append("RIGHT" if a[1] > pos[1] else "LEFT")
        nuovo = muovi(griglia, pos, passi[-1])
        if nuovo == pos:        # bordo: insistere non serve
            passi.pop()
            break
        pos = nuovo
    if pos != a:
        raise ValueError(f"disposizione incoerente: da {da} non si arriva a {a}")
    return passi, pos


def riaggancio(griglia):
    """Giu' di una riga e tutto a sinistra: ovunque si fosse, dopo si e'
    nella prima colonna della riga sotto. Serve dopo un tasto largo,
    dove non si sa su quale cella si scende."""
    colonne = max(len(r) for r in griglia)
    return ["DOWN"] + ["LEFT"] * (colonne - 1)


def digita(testo, app="netflix", azzera=0):
    """La sequenza di tasti per scrivere un testo dentro l'app.

    `azzera` e' quante volte premere CANCELLA prima di scrivere, per i
    casi in cui il campo ha gia' dentro qualcosa. Zero di default: in
    un campo vuoto premere cancella non si sa cosa faccia, e su questa
    TV non c'e' modo di sapere se il campo e' vuoto.

    Ritorna (tasti, saltati). I caratteri che non stanno sulla tastiera
    finiscono in `saltati` invece di essere ignorati in silenzio: chi
    chiama decide se sono accettabili."""
    d = DISPOSIZIONI[app]
    griglia, larghi = d["griglia"], d["larghi"]
    dove = posizioni(griglia)
    pos = tuple(d["partenza"])
    tasti, saltati = [], []

    if azzera:
        if CANCELLA not in dove:
            raise ValueError(f"{d['nome']}: non so dov'e' il tasto cancella")
        # Si arriva a CANCELLA da SOTTO, salendo. Raggiungerlo di lato
        # vorrebbe dire muoversi a destra sulla riga dei tasti larghi,
        # dove un passo di troppo esce dalla tastiera.
        passi, pos = percorso(griglia, pos, (dove[CANCELLA][0] + 1,
                                            dove[CANCELLA][1]))
        tasti += passi + ["UP"] + ["OK"] * azzera
        tasti += riaggancio(griglia)
        pos = (dove[CANCELLA][0] + 1, 0)

    for ch in testo.lower():
        if ch not in dove or ch == CANCELLA:
            saltati.append(ch)
            continue
        passi, pos = percorso(griglia, pos, dove[ch])
        tasti += passi + ["OK"]
        if ch in larghi:
            tasti += riaggancio(griglia)
            pos = (pos[0] + 1, 0)

    return tasti, saltati


# --- misurare una tastiera che non si conosce --------------------------
#
# Per le app di cui non so la disposizione non serve una foto: si fa
# scrivere all'app la propria tastiera dentro il suo campo di ricerca.
# Premendo OK su ogni casella lungo una riga, nel campo compare la riga
# in chiaro, e chi guarda la TV la legge e me la detta. E' una misura,
# non una supposizione.
#
# I bordi rendono la cosa possibile: LEFT e UP a fondo corsa portano
# all'angolo in alto a sinistra, che e' un punto di partenza certo
# anche senza sapere niente della griglia.

def taratura(fase, quanti=8, indice=0, corsa=14):
    """I tasti di una sonda per misurare una tastiera sconosciuta.

    fase "angolo":  va nell'angolo e premi OK -> il carattere di la'
    fase "colonna": scende la prima colonna -> quanti caratteri e
                    quante righe (in fondo si ripete, e il bordo si
                    vede da quello)
    fase "riga":    percorre la riga `indice` -> i caratteri in ordine

    `corsa` e' quante volte insistere contro il bordo: di piu' del
    necessario non fa danno, i passi in eccesso non si muovono.

    ATTENZIONE: andare a DESTRA di troppo su alcune app esce dalla
    tastiera (su Netflix porta al menu). Percio' `quanti` nella fase
    riga si tiene basso e si alza a poco a poco, guardando la TV."""
    if fase not in ("angolo", "colonna", "riga"):
        raise ValueError(f'fase sconosciuta: "{fase}"')

    # all'angolo in alto a sinistra ci si arriva senza sapere niente:
    # a fondo corsa i bordi fermano il cursore
    tasti = ["LEFT"] * corsa + ["UP"] * corsa
    if fase == "angolo":
        return tasti + ["OK"]
    if fase == "colonna":
        tasti += ["OK"]
        for _ in range(quanti):
            tasti += ["DOWN", "OK"]
        return tasti
    tasti += ["DOWN"] * indice + ["OK"]
    for _ in range(quanti):
        tasti += ["RIGHT", "OK"]
    return tasti


def simula(tasti, app="netflix"):
    """Cosa scriverebbe davvero quella sequenza di tasti. Non e' una
    comodita': e' il modo di provare `digita` senza la TV, generando i
    tasti e rieseguendoli per vedere se torna la parola."""
    d = DISPOSIZIONI[app]
    griglia = d["griglia"]
    pos = tuple(d["partenza"])
    scritto = ""
    for t in tasti:
        if t == "OK":
            ch = griglia[pos[0]][pos[1]]
            scritto = scritto[:-1] if ch == CANCELLA else scritto + ch
        else:
            pos = muovi(griglia, pos, t)
    return scritto
