#!/usr/bin/env python3
"""
Scrivere su una tastiera a schermo muovendosi a frecce.

Perche' serve: nessuna delle sette app usa l'IME di Tizen, quindi il
testo iniettato non arriva da nessuna parte. Misurato il 28/09/2026
con --ascolta e il metodo del separatore: Netflix, NOW, Prime Video,
Disney+ e HBO Max restano mute quando il loro campo va a fuoco,
mentre la ricerca Samsung annuncia imeStart. Mediaset Infinity e
Discovery+ hanno una tastiera propria vista a schermo. L'unica strada
e' muoversi sulla loro tastiera e premere OK su ogni lettera.

Qui c'e' solo il CALCOLO dei percorsi, senza rete, cosi' si prova da
solo: python3 prove/prova_tastiere.py

TUTTO QUELLO CHE C'E' QUI SU NETFLIX E' MISURATO SULLA TV, non preso
dalle fonti. Le fonti (blogs.sas.com e ediblecode.com) avevano
ragione sulla griglia delle lettere e sulla partenza, e TORTO sui
bordi: dicevano che bloccano, invece GIRANO.
"""

SPAZIO = " "
CANCELLA = "\b"

# --- come si modella una tastiera -------------------------------------
#
# Una griglia di celle. I tasti larghi (spazio, cancella) occupano
# piu' celle con la stessa etichetta.
#
# QUELLO CHE E' STATO MISURATO SU NETFLIX, in ordine di scoperta:
#
# 1. la griglia delle lettere e la partenza sulla A.
#    --digita "z" ha scritto "z". Il percorso era giu'x4+destra, che
#    non tocca nessun bordo: per questo la prova e' valida anche non
#    sapendo ancora niente dei bordi.
#
# 2. I BORDI GIRANO, non bloccano. Un ancoraggio fatto di LEFT e UP a
#    fondo corsa ha portato il cursore A DESTRA e fatto perdere la
#    query. Con i bordi che girano non esiste nessun punto di
#    riaggancio: serve sapere da dove si parte, e quindi aprire la
#    ricerca da zero.
#
# 3. DA UN TASTO LARGO SI SCENDE SULLA SUA COLONNA CENTRALE.
#    Passando per CANCELLA (colonne 3-5) e scendendo si arriva su "e",
#    che sta in colonna 4: il centro. Questo rende i tasti larghi
#    deterministici, e quindi lo spazio scrivibile.
#
# LA REGOLA CHE TIENE TUTTO INSIEME: non si va MAI in orizzontale
# sulla riga dei tasti larghi. La' ci sono due tasti soli, larghi tre
# celle ciascuno, e un passo di lato salta all'altro in modo che il
# modello a celle non sa contare. Ai tasti larghi ci si arriva
# ESCLUSIVAMENTE da sotto, salendo dalla colonna giusta.
#
# Grazie a quella regola i percorsi non toccano mai un bordo, e allora
# valgono sia che i bordi blocchino sia che girino: e' la ragione per
# cui si possono calcolare senza sapere come e' fatto un bordo. Le
# prove lo verificano su entrambi i modelli.

DISPOSIZIONI = {
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
        "partenza": (1, 0),       # il cursore arriva sulla A
        # La strada dal lancio al campo di ricerca. DUE strade, non
        # una, e la differenza non e' un dettaglio: un'app appena
        # lanciata sta in uno stato CONOSCIUTO, un'app gia' aperta sta
        # in uno stato QUALUNQUE, e da uno stato qualunque non esiste
        # nessuna sequenza deterministica.
        #
        # Nel flusso vero conta solo la prima: il pulsante nell'app
        # lancia l'app, quindi parte sempre da freddo. L'app sa da
        # sola in quale caso si trova, perche' lancia() legge
        # tvChannelName prima di lanciare.
        #
        # Vuote perche' non sono misurate: sono diverse per ogni app,
        # non le documenta nessuno e non si indovinano - un tentativo
        # alla cieca ha aperto il menu Impostazioni. Le riempie chi
        # guarda la TV, che quella strada la fa ogni giorno col
        # telecomando.
        # MISURATO: BACK porta il fuoco sul tasto Home in alto, e un
        # BACK in piu' quando e' gia' la' NON FA NIENTE. Quindi e' un
        # fondo idempotente, e questo risolve il problema dello stato
        # che sopravvive: la profondita' varia (2 BACK se la
        # riproduzione e' partita dalla home, 3 se si e' entrati in un
        # titolo), ma esagerare non costa niente. Cinque bastano con
        # margine.
        # E' lo stesso meccanismo che serviva sulla tastiera e che la'
        # non c'era: un punto dove sbattere per sapere dove si sta.
        # L'OK IN MEZZO, non in testa, e' quello che rende la
        # normalizzazione valida in entrambi i casi:
        #
        #  a freddo l'app parte dal SELETTORE PROFILI. I BACK non
        #  fanno niente, l'OK scegle il profilo, si arriva alla home,
        #  e i secondi BACK portano sul tasto Home in alto.
        #
        #  a caldo l'app riprende dentro qualcosa. I primi BACK
        #  portano sul tasto Home in alto, l'OK preme PROPRIO quel
        #  tasto - cioe' va alla home, innocuo - e i secondi BACK ci
        #  riportano sul tasto.
        #
        # Le due strade convergono, e l'OK non puo' fare danni perche'
        # in entrambi i casi cade su qualcosa che porta a casa. Un OK
        # in TESTA invece, a caldo, cadrebbe su qualunque cosa fosse a
        # fuoco: magari far partire un titolo.
        #
        # VERIFICATO il 28/09/2026: BACK sul selettore profili NON FA
        # NIENTE. Era l'ultima assunzione, ed era quella che poteva
        # fare il danno peggiore: se BACK fosse uscito da Netflix, le
        # pressioni dopo sarebbero finite sulla home della TV, dove un
        # OK puo' aprire qualunque cosa.
        "normalizza": ["BACK"] * 5 + ["OK"] + ["BACK"] * 5,
        # MISURATO: dal tasto Home in alto, un passo a SINISTRA c'e'
        # la ricerca, e premendo OK si apre col cursore sulla A - la
        # stessa casella di partenza che la disposizione dichiara,
        # quindi la strada e digita si incastrano senza aggiustamenti.
        "strada": ["LEFT", "OK"],
        "bordi": "girano",        # MISURATO, contro le fonti
        "larghi": {SPAZIO, CANCELLA},
    },
    # Griglia finta senza tasti larghi, per le prove.
    "prova": {
        "nome": "prova",
        "griglia": ["abcdef", "ghijkl", "mnopqr", "stuvwx", "yz0123"],
        "partenza": (0, 0),
        "bordi": "fermano",
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
    a sinistra; il centro lo calcola `campata`."""
    dove = {}
    for r, riga in enumerate(griglia):
        for c, ch in enumerate(riga):
            dove.setdefault(ch, (r, c))
    return dove


def campata(griglia, riga, colonna):
    """Da dove a dove arriva il tasto che occupa questa cella.

    Un tasto largo e' una fila di celle con la stessa etichetta, e
    serve saperne l'estensione per due motivi: per trovarne il centro,
    che e' dove si scende, e per sapere da quali colonne ci si arriva
    salendo."""
    riga_testo = griglia[riga]
    ch = riga_testo[colonna]
    a = colonna
    while a > 0 and riga_testo[a - 1] == ch:
        a -= 1
    b = colonna
    while b < len(riga_testo) - 1 and riga_testo[b + 1] == ch:
        b += 1
    return a, b


def centro(griglia, riga, colonna):
    """La colonna centrale del tasto che occupa questa cella.

    MISURATO su Netflix: scendendo da CANCELLA (colonne 3-5) si arriva
    su "e", colonna 4. Il centro, non il bordo."""
    a, b = campata(griglia, riga, colonna)
    return (a + b) // 2


def muovi(griglia, da, verso, bordi="fermano"):
    """Un passo.

    `bordi` e' la cosa piu' difficile da sapere di una tastiera:
    "fermano" vuol dire che a fondo corsa il cursore resta dov'e',
    "girano" che ricompare dall'altro lato. Netflix GIRA, misurato.

    Scendendo da un tasto largo si arriva sulla sua colonna centrale,
    anche questo misurato."""
    r, c = da
    alte = len(griglia)
    if verso in ("UP", "DOWN"):
        passo = -1 if verso == "UP" else 1
        if verso == "DOWN":
            c = centro(griglia, r, c)     # dai tasti larghi si scende al centro
        r = ((r + passo) % alte if bordi == "girano"
             else max(0, min(alte - 1, r + passo)))
    else:
        passo = -1 if verso == "LEFT" else 1
        larga = len(griglia[r])
        c = ((c + passo) % larga if bordi == "girano"
             else max(0, min(larga - 1, c + passo)))
    return (r, min(c, len(griglia[r]) - 1))


def percorso(griglia, da, a, bordi="fermano"):
    """I tasti per andare da una cella all'altra: prima in verticale,
    poi in orizzontale, a delta esatto.

    Un percorso a delta esatto non tocca mai un bordo, e per questo
    vale sia coi bordi che bloccano sia con quelli che girano. Le
    prove lo verificano sui due modelli."""
    passi, pos = [], da
    # I cicli hanno un tetto perche' una disposizione incoerente non
    # deve appendere in silenzio: dentro a-Shell, sul telefono,
    # sarebbe un blocco muto invece di un errore da leggere.
    tetto = len(griglia) + max(len(r) for r in griglia) + 2
    for _ in range(tetto):
        if pos[0] == a[0]:
            break
        passi.append("DOWN" if a[0] > pos[0] else "UP")
        pos = muovi(griglia, pos, passi[-1], bordi)
    for _ in range(tetto):
        if pos[1] == a[1]:
            break
        passi.append("RIGHT" if a[1] > pos[1] else "LEFT")
        pos = muovi(griglia, pos, passi[-1], bordi)
    if pos != a:
        raise ValueError(f"disposizione incoerente: da {da} non si "
                         f"arriva a {a}")
    return passi, pos


def percorso_largo(griglia, da, ch, bordi="fermano"):
    """I tasti per arrivare su un tasto largo (spazio, cancella).

    Ci si arriva SOLO da sotto: prima si va in orizzontale sulla riga
    delle lettere, sotto il tasto, e solo dopo si sale. Muoversi in
    orizzontale sulla riga dei tasti larghi salterebbe fra i due tasti
    in un modo che il modello a celle non sa contare."""
    dove = posizioni(griglia)
    if ch not in dove:
        raise ValueError(f"{ch!r} non e' su questa tastiera")
    riga_larga = dove[ch][0]
    a, b = campata(griglia, riga_larga, dove[ch][1])
    colonna = (a + b) // 2
    if da[0] == riga_larga:
        raise ValueError("dalla riga dei tasti larghi non si naviga di "
                         "lato: prima si scende")
    passi, pos = [], da
    # orizzontale PRIMA, sulla riga delle lettere dove contare e' sicuro
    for _ in range(len(griglia[da[0]]) + 1):
        if pos[1] == colonna:
            break
        passi.append("RIGHT" if colonna > pos[1] else "LEFT")
        pos = muovi(griglia, pos, passi[-1], bordi)
    # poi in su, fino alla riga del tasto largo
    for _ in range(len(griglia) + 1):
        if pos[0] == riga_larga:
            break
        passi.append("UP")
        pos = muovi(griglia, pos, "UP", bordi)
    if griglia[pos[0]][pos[1]] != ch:
        raise ValueError(f"non arrivo su {ch!r}: sono su "
                         f"{griglia[pos[0]][pos[1]]!r}")
    return passi, pos


def digita(testo, app="netflix", azzera=0):
    """La sequenza di tasti per scrivere un testo dentro l'app.

    PRETENDE che il cursore sia sulla casella di partenza dichiarata
    dalla disposizione, cioe' che la ricerca sia appena stata aperta.
    Con i bordi che girano non c'e' modo di rimettersi in posizione da
    soli: a fondo corsa il cursore non si ferma, ricompare dall'altro
    lato. E' un limite misurato, non una scelta.

    `azzera` e' quante volte premere CANCELLA prima di scrivere, per i
    campi che hanno gia' dentro qualcosa. Zero di default: in un campo
    vuoto non si sa cosa faccia cancella, e su questa TV non c'e' modo
    di sapere se il campo e' vuoto.

    Ritorna (tasti, saltati). I caratteri che non stanno sulla
    tastiera finiscono in `saltati` invece di essere ignorati in
    silenzio: chi chiama decide se sono accettabili."""
    d = DISPOSIZIONI[app]
    griglia, larghi = d["griglia"], d["larghi"]
    bordi = d.get("bordi", "fermano")
    dove = posizioni(griglia)
    pos = tuple(d["partenza"])
    tasti, saltati = [], []

    def vai(carattere):
        """I passi fino a un carattere, per la via giusta secondo che
        sia un tasto largo o una lettera."""
        if carattere in larghi:
            return percorso_largo(griglia, pos, carattere, bordi)
        return percorso(griglia, pos, dove[carattere], bordi)

    if azzera:
        if CANCELLA not in dove:
            raise ValueError(f"{d['nome']}: non so dov'e' il tasto cancella")
        passi, pos = vai(CANCELLA)
        tasti += passi + ["OK"] * azzera

    for ch in testo.lower():
        if ch not in dove or ch == CANCELLA:
            saltati.append(ch)
            continue
        passi, pos = vai(ch)
        tasti += passi + ["OK"]

    return tasti, saltati


def simula(tasti, app="netflix", da=None, bordi=None):
    """Cosa scriverebbe davvero quella sequenza di tasti. Non e' una
    comodita': e' il modo di provare `digita` senza la TV, generando i
    tasti e rieseguendoli per vedere se torna la parola.

    `bordi` serve a rieseguire lo stesso percorso nei due mondi
    possibili: se il testo esce giusto in entrambi, il percorso non
    dipende da come sono fatti i bordi."""
    d = DISPOSIZIONI[app]
    griglia = d["griglia"]
    come = bordi or d.get("bordi", "fermano")
    pos = tuple(da) if da else tuple(d["partenza"])
    scritto = ""
    for t in tasti:
        if t == "OK":
            ch = griglia[pos[0]][pos[1]]
            scritto = scritto[:-1] if ch == CANCELLA else scritto + ch
        else:
            pos = muovi(griglia, pos, t, come)
    return scritto


# --- misurare una tastiera che non si conosce --------------------------
#
# Per le app di cui non so la disposizione non serve una foto: si fa
# scrivere all'app la propria tastiera dentro il suo campo di ricerca.
# Premendo OK su ogni casella lungo una riga, nel campo compare la
# riga in chiaro, e chi guarda la TV la legge e me la detta.
#
# Le sonde sono RELATIVE: partono da dove sta il cursore e si muovono
# di un passo alla volta. Una prima versione partiva "dall'angolo",
# andando a fondo corsa a sinistra e in su, e su Netflix ha fatto
# perdere la query: con i bordi che girano l'angolo non esiste. Una
# sonda non puo' dare per buono un comportamento dei bordi, perche' il
# comportamento dei bordi e' una delle cose da misurare - e si vede
# proprio dalla coda della sonda: se gli ultimi caratteri si RIPETONO
# il bordo ferma, se RICOMINCIANO dal primo il bordo gira.

def taratura(fase, quanti=6):
    """I tasti di una sonda per misurare una tastiera sconosciuta.

    fase "riga":    OK e poi passi a destra -> i caratteri della riga
                    dove sta il cursore, e come si comporta il bordo
    fase "colonna": OK e poi passi in giu'  -> la colonna, e il bordo

    Va usata con la ricerca appena aperta, cosi' si sa da dove parte.
    `quanti` si tiene basso e si alza a poco a poco guardando la TV:
    su una tastiera sconosciuta non si sa cosa ci sia oltre il bordo."""
    if fase not in ("riga", "colonna"):
        raise ValueError(f'fase sconosciuta: "{fase}"')
    verso = "RIGHT" if fase == "riga" else "DOWN"
    tasti = ["OK"]
    for _ in range(quanti):
        tasti += [verso, "OK"]
    return tasti
