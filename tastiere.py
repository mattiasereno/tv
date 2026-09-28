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
# Un tasto che esiste, occupa una casella, ma non scrive testo: "123",
# i simboli, le maiuscole. Serve che stia nella griglia perche' i
# passi si contano anche sopra di lui, ma non deve mai essere una
# destinazione - e non lo e', perche' nessun titolo contiene questo
# carattere.
ALTRO = "\x00"
# Il tasto che svuota TUTTO il campo in una pressione - il cestino di
# HBO Max. Vale piu' di N cancella: una pressione sola e la certezza
# di partire da vuoto, invece di indovinare quanto c'era dentro.
SVUOTA = "\x01"

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
        # Come su NOW: cancellare qualche carattere prima di scrivere
        # rende il risultato indipendente da cosa c'era nel campo, e su
        # Netflix la ricerca vecchia RESTA (visto: "thebear" era ancora
        # li' al giro dopo). Su Netflix CANCELLA e' un tasto largo e ci
        # si arriva da sotto, salendo dalla colonna centrale.
        # NON ANCORA PROVATO SULLA TV su Netflix, a differenza di NOW.
        "azzera": 3,
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
        # Nessuna ancora possibile: coi bordi che girano, a fondo
        # corsa il cursore non si ferma, ricompare dall'altro lato.
        "ancoraggio": None,
        "larghi": {SPAZIO, CANCELLA},
    },
    "now": {
        "nome": "NOW",
        # MISURATO SULLA TV il 28/09/2026, sonda per sonda.
        # QWERTY, non alfabetica come Netflix. Il cursore arriva sulla
        # q. Nessun tasto largo: cancella e spazio sono tasti singoli,
        # e questo rende tutto piu' semplice che su Netflix.
        "griglia": [
            "qwertyuiop",
            "asdfghjkl" + CANCELLA,
            "zxcvbnm" + ALTRO * 2 + SPAZIO,
        ],
        "partenza": (0, 0),       # la q
        # I BORDI, misurati uno per uno muovendo SENZA premere:
        #   destra   BLOCCA  (15 passi dalla q si fermano sulla p)
        #   alto     BLOCCA  (5 passi in su dalla p restano sulla p)
        #   basso    PERDE   (6 passi in giu' dalla q finiscono su un
        #                    titolo: la prima versione premeva OK la'
        #                    e ha fatto partire un programma)
        #   sinistra PERDE   (15 passi a sinistra sono usciti dalla
        #                    tastiera, stesso guaio)
        # I percorsi a delta esatto non toccano nessun bordo, quindi
        # quelli che perdono non danno fastidio. I due che bloccano
        # invece sono un regalo: danno un'ANCORA, che su Netflix non
        # esiste.
        "bordi": "fermano",
        "larghi": set(),
        "ancoraggio": {"tasti": ["RIGHT"] * 15 + ["UP"] * 5,
                       "arrivo": (0, 9)},
        # MISURATO: su NOW la normalizzazione non e' "BACK a
        # ripetizione" come su Netflix, perche' qui il BACK di troppo
        # NON e' gratis: apre la richiesta di conferma per uscire
        # dall'app. E i due stati si ALTERNANO:
        #     home -> BACK -> conferma
        #     conferma -> BACK -> home col menu a tendina aperto
        # Quindi dopo N BACK non si sa in quale dei due si e'.
        #
        # Si fanno convergere sfruttando due cose misurate:
        #   - nella conferma e' evidenziato "RESTA", quindi OK e'
        #     sicuro e porta al menu a tendina con Home evidenziata;
        #   - nel menu e' evidenziata "Home", quindi OK va alla home.
        # Da cui:
        #     BACK x8   -> conferma OPPURE home col menu
        #     OK        -> menu (da conferma) oppure home (da menu)
        #     BACK      -> conferma, DA ENTRAMBE
        #     OK        -> menu col Home evidenziato, certo
        # TROVATA da chi guarda la TV, il 28/09/2026, dopo che i
        # miei tre tentativi dedotti erano falliti. Sei BACK e poi DUE
        # volte su+OK:
        #     BACK x6        porta in un punto da cui i due su+OK
        #                    funzionano
        #     UP, OK         il primo passaggio
        #     UP, OK         il secondo, e la ricerca si apre
        # VERIFICATO partendo da dentro un titolo della home: la
        # ricerca si e' aperta e --digita ha scritto "the bear".
        #
        # IL MODELLO, ricavato provando una variante che NON funziona:
        # mettendo un OK davanti, la sequenza e' finita "nel menu sopra
        # quello in cui ero". Cioe' questa sequenza atterra sempre
        # sulla voce di menu SOPRA LA SEZIONE CORRENTE.
        #
        # Da cui: funziona perche' la RICERCA sta sopra HOME. Quindi
        # funziona esattamente quando la sezione corrente e' Home.
        # Se sei in un'altra sezione apre la voce sopra QUELLA: lo
        # vedi subito, non rompe niente, e si rimedia con due tasti.
        #
        # E' un limite dichiarato, non un difetto nascosto: chi usa la
        # TV ha scelto di non navigare a mano fra le sezioni e di far
        # fare tutto al telefono, e con quella premessa la sezione
        # resta Home.
        #
        # L'OK INIZIALE serve al caso a freddo, quando NOW parte dal
        # SELETTORE PROFILI: la' scegle il profilo. E non sposta
        # l'allineamento, perche' aggiunge profondita' che i sei BACK
        # riassorbono.
        # Me l'ero convinto del contrario leggendo male una prova:
        # quella prova partiva da una sezione NON Home (l'avevo
        # chiesto io), quindi finire "sul menu sopra quella sezione"
        # era il comportamento GIUSTO, non un disallineamento.
        # Quante volte premere CANCELLA prima di scrivere. Serve
        # perche' non si puo' vedere lo schermo: un OK della
        # navigazione e' arrivato anche sulla tastiera e ha scritto una
        # "q" di troppo ("qthe bear"), e una ricerca vecchia potrebbe
        # essere rimasta nel campo. Cancellare qualche carattere rende
        # il risultato indipendente da cosa c'era prima.
        # Su NOW il cancella e' un tasto SINGOLO in riga 1 colonna 9,
        # quindi raggiungerlo costa poco e non ha ambiguita'.
        "azzera": 3,
        "normalizza": ["OK"] + ["BACK"] * 6,
        "strada": ["UP", "OK", "UP", "OK"],
    },
    "disney": {
        "nome": "Disney+",
        # MISURATO SULLA TV il 28/09/2026. Alfabetica come Netflix, ma
        # 7 colonne invece di 6, e con i numeri di fila dopo la z.
        # Il cursore arriva sullo SPAZIO, in alto a destra.
        #
        # La sonda della prima colonna ha scritto "f m t 1 8 0" (il
        # primo OK era sullo spazio, invisibile). Sono esattamente le
        # colonne 5 delle righe sotto, e le due righe finali sono state
        # dedotte dall'aritmetica e poi CONFERMATE guardando lo
        # schermo.
        "griglia": [
            CANCELLA * 4 + SPAZIO * 3,
            "abcdefg",
            "hijklmn",
            "opqrstu",
            "vwxyz12",
            "3456789",
            "0",
        ],
        "partenza": (0, 5),       # sullo spazio, in alto a destra
        # LO SPAZIO NON SI RIESCE A PREMERE, e non perche' non si sappia
        # dov'e': sta sopra "e f g" (confermato guardando), quindi la
        # colonna centrale e' quella della f ed e' esattamente dove il
        # codice mira. L'OK la' non ha scritto niente e non ha
        # cancellato niente: la pressione si e' PERSA, probabilmente
        # arrivata mentre il fuoco si stava ancora spostando.
        # "Non so dov'e'" e "so dov'e' ma la pressione si perde" sono
        # due cose diverse, e questa e' la seconda: si risolverebbe
        # rallentando il passo intorno al tasto largo.
        # Non vale la pena: VERIFICATO che la ricerca di Disney+ TROVA
        # il titolo anche senza lo spazio ("thebear" ha trovato The
        # Bear). Percio' lo spazio si salta e si DICHIARA, come i
        # numeri su NOW.
        "non_scrivibili": {SPAZIO},
        # DA MISURARE: i bordi. Fino a prova contraria si assume che
        # fermino, ma i percorsi a delta esatto non li toccano, quindi
        # la scrittura funziona comunque. Senza saperlo non si puo'
        # dire se esiste un'ancora.
        "bordi": "fermano",
        "larghi": {SPAZIO, CANCELLA},
        "ancoraggio": None,
        # L'ultima riga ha il solo "0": scendendoci la colonna si
        # schiaccia, ed e' proprio quello che ha fatto la sonda.
        "azzera": 3,
        # MISURATO, e Disney+ e' il caso FORTUNATO: il suo menu a
        # tendina e' BLOCCATO sopra e sotto, non gira come quello di
        # NOW. Percio' "su a fondo corsa" atterra sempre sulla prima
        # voce, qualunque sia la sezione da cui arrivi - ed e' l'ancora
        # che su NOW non esisteva e che ci e' costata tre tentativi.
        #     voce 1   selettore profili
        #     voce 2   CERCA, e cliccandola si arriva sullo SPAZIO,
        #              cioe' esattamente la partenza qui sopra
        #
        # L'OK iniziale serve al caso a freddo (selettore profili):
        # scegle il profilo. Nel caso a caldo cade su quello che e' a
        # fuoco e i BACK dopo lo disfanno.
        #
        # E "su a fondo corsa, giu', OK" e' SICURO IN ENTRAMBI GLI
        # STATI, che e' la cosa che rende tutto questo accettabile:
        #   - nel menu porta sulla ricerca;
        #   - nella finestra "vuoi uscire" - dove su Disney+ e'
        #     evidenziato ESCI, non Resta - il su sbatte su Esci, il
        #     giu' va su ANNULLA e l'OK annulla.
        # Quindi non puo' chiudere l'app. Su NOW l'evidenziato era
        # Resta e il rischio non c'era; qui c'era, e si aggira.
        "normalizza": ["OK"] + ["BACK"] * 6,
        "strada": ["UP"] * 6 + ["DOWN", "OK"],
    },
    "hbomax": {
        "nome": "HBO Max",
        # MISURATO SULLA TV il 28/09/2026. La griglia delle lettere e'
        # IDENTICA a Netflix - alfabetica, 6 colonne - e il cursore
        # arriva sulla a. La differenza e' che la riga dei tasti
        # larghi sta SOTTO invece che sopra, e ha TRE tasti invece di
        # due: cancella, spazio e CESTINO.
        #
        # La sonda della colonna ha scritto "agmsy4" e poi ha
        # CANCELLATO il 4: la settima pressione era sul cancella, che
        # sta sotto la colonna del 4. Conferma la griglia e la riga in
        # fondo in un colpo.
        "griglia": [
            "abcdef",
            "ghijkl",
            "mnopqr",
            "stuvwx",
            "yz0123",
            "456789",
            CANCELLA * 2 + SPAZIO * 2 + SVUOTA * 2,
        ],
        "partenza": (0, 0),       # la a
        # I BORDI, misurati muovendo SENZA premere:
        #   alto e basso  BLOCCANO
        #   destra        PERDE, il fuoco esce sui RISULTATI
        #   sinistra      PERDE, il fuoco esce sul MENU A TENDINA
        "bordi": "fermano",
        "larghi": {CANCELLA, SPAZIO, SVUOTA},
        # L'ANCORA, e usa proprio il bordo che perde:
        #   sinistra a fondo corsa  -> esce sul menu a tendina
        #   destra                  -> rientra in PRIMA COLONNA (sulla
        #                              a, verificato)
        #   su a fondo corsa        -> riga 0, perche' il verticale
        #                              blocca
        # Quindi si arriva sempre sulla a, da qualunque casella. Un
        # bordo che perde non e' sempre un problema: qui e' la porta.
        "ancoraggio": {"tasti": ["LEFT"] * 10 + ["RIGHT"] + ["UP"] * 7,
                       "arrivo": (0, 0)},
        # Col cestino basta UNA pressione per svuotare il campo.
        "azzera": 1,
        # HBO MAX E' LENTA. A 0,15s - il passo che va bene su Netflix,
        # NOW e Disney+ - scarta quasi tutto: 47 pressioni hanno
        # prodotto una sola "c". A 0,5s "it" e' uscito giusto.
        # Il passo e' una proprieta' dell'APP, non del progetto.
        # Provato: 0,5s giusto, 0,4s giusto, 0,3s giusto, 0,2s TROPPO
        # VELOCE (lettere perse). Fissato 0,3 con un gradino di
        # margine, perche' una lettera persa non si vede.
        "passo": 0.3,
        # MISURATO, e qui la convergenza e' pulita.
        # BACK a ripetizione alterna MENU A TENDINA e CONFERMA
        # D'USCITA, come su NOW. Ma su HBO Max i due stati si fanno
        # convergere con DESTRA + BACK:
        #   dalla conferma: destra sposta su "No" senza attivare
        #                   niente, BACK chiude -> MENU
        #   dal menu:       destra esce sui contenuti, BACK rientra
        #                   -> MENU
        # Verificato da entrambi. Quindi i BACK in eccesso sono
        # GRATIS: qualunque stato raggiungano, la coppia li porta nel
        # menu.
        #
        # E soprattutto: fino a qui NON si preme mai OK. Serviva,
        # perche' nella conferma d'uscita di HBO Max e' selezionato
        # "Si'" - un OK al buio chiuderebbe l'app. L'OK si preme solo
        # dopo, quando si e' certi di stare nel menu.
        # L'OK IN TESTA serve al caso a freddo, quando l'app parte dalla
        # PAGINA DEI PROFILI: la' scegle il profilo. Nel caso normale
        # cade su quello che e' a fuoco - dentro un titolo fa partire
        # qualcosa - e gli otto BACK lo disfano.
        # UNICO RISCHIO, specifico di HBO Max: se l'app riprendesse con
        # la CONFERMA D'USCITA gia' a schermo, quell'OK cadrebbe su
        # "Si'" e chiuderebbe l'app. Improbabile (un'app non riprende
        # su una finestra di conferma), ma su NOW e Disney+ questo
        # rischio non c'e', perche' la' non e' selezionato "esci".
        "normalizza": ["OK"] + ["BACK"] * 8 + ["RIGHT", "BACK"],
        # Il menu BLOCCA sopra e sotto (come Disney+, non come NOW),
        # quindi su a fondo corsa atterra sulla prima voce. La ricerca
        # e' la TERZA.
        "strada": ["UP"] * 8 + ["DOWN", "DOWN", "OK"],
    },
    "prime": {
        "nome": "Prime Video",
        # MISURATO SULLA TV il 28/09/2026, letta riga per riga.
        # Alfabetica come Netflix - non QWERTY, come diceva la rete -
        # ma con le VOCALI ACCENTATE dopo la z, e i numeri che
        # partono da 1 invece che da 0. Il cursore arriva sulla a.
        # Gli accenti sono una buona notizia: i titoli italiani si
        # scrivono per davvero.
        "griglia": [
            "abcdef",
            "ghijkl",
            "mnopqr",
            "stuvwx",
            "yz\u00e0\u00e8\u00e9\u00ec",
            "\u00f2\u00f9" + "1234",
            "567890",
            SPAZIO * 2 + CANCELLA * 2 + SVUOTA * 2,
        ],
        "partenza": (0, 0),       # la a
        # DA MISURARE: i bordi, e quindi se esiste un'ancora.
        "bordi": "fermano",
        "larghi": {SPAZIO, CANCELLA, SVUOTA},
        "ancoraggio": None,
        "azzera": 1,              # c'e' il cestino
        # PROVATO: a 0,3s "the bear" esce giusto. Si potrebbe
        # stringere, non provato.
        "passo": 0.3,
        # DA MISURARE
        "normalizza": [],
        "strada": [],
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

# Discovery+ e HBO Max sono LA STESSA PIATTAFORMA: il pacchetto di HBO
# Max su questa TV e' 5b8c3eb16b.BeamCTVDev, e "Beam" e' il nome
# interno di Warner Bros. Discovery. Chi guarda la TV ha detto che le
# due app sono "esattamente uguali", e la disposizione si riusa - ma
# resta una COPIA DICHIARATA, non un caso: se un giorno divergono,
# basta staccarla qui.
# La griglia e' identica (letta riga per riga: abcdef / ghijkl /
# mnopqr / stuvwx / yz0123 / 456789, e in fondo cancella, spazio,
# cestino). Ma DISCOVERY+ E' ANCORA PIU' LENTA: a 0,3s - il passo che
# va bene su HBO Max - "the bear" e' uscito "thk beb". Gli errori
# erano SPARSI (terza e settima lettera sbagliate, le altre giuste,
# una mancante), e nessuna casella di partenza produce quella stringa:
# quindi non era uno sfasamento dell'ancora, erano pressioni perse.
DISPOSIZIONI["discovery"] = dict(DISPOSIZIONI["hbomax"],
                                 nome="Discovery+", passo=0.5)


# App che ci sono ma di cui non conosco la tastiera. Servono a
# rifiutare il lavoro invece di scrivere il loro nome come se fosse un
# titolo: ognuna ha una disposizione sua, e la TV non la sa dire.
SENZA_DISPOSIZIONE = {
    "apple", "appletv", "infinity",
    "mediaset", "youtube",
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
    passi, pos = [], da
    if pos[0] == riga_larga:
        # Si arriva qui con due tasti larghi di fila: "Amori &
        # incantesimi" ha due spazi vicini, perche' la & non e' sulla
        # tastiera e viene saltata. Dopo il primo spazio il cursore e'
        # sulla riga larga, e di lato non ci si muove - quindi si
        # scende, e da sotto si risale come sempre. Prima questo caso
        # era un errore, e un titolo vero l'ha trovato subito.
        via = "DOWN" if riga_larga == 0 else "UP"
        passi.append(via)
        pos = muovi(griglia, pos, via, bordi)
    # orizzontale PRIMA, sulla riga delle lettere dove contare e' sicuro
    for _ in range(len(griglia[pos[0]]) + 1):
        if pos[1] == colonna:
            break
        passi.append("RIGHT" if colonna > pos[1] else "LEFT")
        pos = muovi(griglia, pos, passi[-1], bordi)
    # poi in verticale fino alla riga dei tasti larghi. La direzione
    # dipende da DOVE STA quella riga: sopra le lettere su Netflix e
    # Disney+, SOTTO su HBO Max. Darla per scontata rompeva HBO Max.
    for _ in range(len(griglia) + 1):
        if pos[0] == riga_larga:
            break
        via = "DOWN" if riga_larga > pos[0] else "UP"
        passi.append(via)
        pos = muovi(griglia, pos, via, bordi)
    if griglia[pos[0]][pos[1]] != ch:
        raise ValueError(f"non arrivo su {ch!r}: sono su "
                         f"{griglia[pos[0]][pos[1]]!r}")
    return passi, pos


def ancoraggio(app="netflix"):
    """I tasti per portarsi in un punto CERTO della tastiera, e dove
    si finisce.

    Non e' una formula: e' un fatto misurato, diverso per ogni
    tastiera, e sta scritto nella disposizione. Su NOW sono destra e
    su a fondo corsa, perche' quei due bordi bloccano. Su Netflix non
    esiste, perche' i bordi girano e a fondo corsa il cursore
    ricompare dall'altro lato.

    Serve perche' dopo aver scritto il cursore resta sull'ultima
    lettera, e perche' qualcuno potrebbe averlo mosso col telecomando.
    Dove c'e', il punto di partenza non conta piu'."""
    d = DISPOSIZIONI[app]
    anc = d.get("ancoraggio")
    if not anc:
        raise ValueError(
            f"{d['nome']}: nessun ancoraggio. I bordi non bloccano, "
            "quindi a fondo corsa il cursore non si ferma: serve sapere "
            "da dove parte, e aprire la ricerca da zero.")
    return list(anc["tasti"]), tuple(anc["arrivo"])


def digita(testo, app="netflix", azzera=0, ancora=None):
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
    non_scrivibili = d.get("non_scrivibili", set())
    pos = tuple(d["partenza"])
    tasti, saltati = [], []

    # Se la tastiera ha un'ancora si usa: costa qualche pressione e in
    # cambio il punto di partenza non conta piu'. Dove non c'e' si
    # PRETENDE che il cursore stia sulla casella dichiarata, cioe' che
    # la ricerca sia appena stata aperta.
    if ancora is None:
        ancora = bool(d.get("ancoraggio"))
    if ancora:
        passi, pos = ancoraggio(app)
        tasti += passi

    # Prima si toglie quello che non si puo' scrivere, POI si
    # accorpano gli spazi rimasti. Senza questo, "Amori & incantesimi"
    # diventava "amori  incantesimi" con due spazi: due pressioni
    # sprecate e una ricerca meno pulita. I caratteri togliti si
    # dichiarano comunque, in `saltati`.
    pulito = []
    for ch in testo.lower():
        if ch in dove and ch != CANCELLA and ch not in non_scrivibili:
            if ch == SPAZIO and (not pulito or pulito[-1] == SPAZIO):
                continue                # niente spazi doppi ne' in testa
            pulito.append(ch)
        else:
            saltati.append(ch)
            # Un buco resta un buco: al posto del carattere saltato ci
            # va uno spazio. Ma solo se lo spazio si puo' scrivere -
            # altrimenti saltando lo SPAZIO si finirebbe per
            # inserirne uno, che e' un cerchio.
            if (pulito and pulito[-1] != SPAZIO
                    and SPAZIO in dove and SPAZIO not in non_scrivibili):
                pulito.append(SPAZIO)
    while pulito and pulito[-1] == SPAZIO:
        pulito.pop()                    # niente spazio in coda
    testo = "".join(pulito)

    def vai(carattere):
        """I passi fino a un carattere, per la via giusta secondo che
        sia un tasto largo o una lettera."""
        if carattere in larghi:
            return percorso_largo(griglia, pos, carattere, bordi)
        return percorso(griglia, pos, dove[carattere], bordi)

    if azzera:
        # Col cestino una pressione svuota tutto, e non serve
        # indovinare quanti caratteri c'erano nel campo. Dove non c'e',
        # si preme cancella `azzera` volte.
        if SVUOTA in dove:
            passi, pos = vai(SVUOTA)
            tasti += passi + ["OK"]
        elif CANCELLA in dove:
            passi, pos = vai(CANCELLA)
            tasti += passi + ["OK"] * azzera
        else:
            raise ValueError(f"{d['nome']}: non so dov'e' il tasto cancella")

    for ch in testo:
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
            if ch == CANCELLA:
                scritto = scritto[:-1]
            elif ch == SVUOTA:
                scritto = ""
            else:
                scritto += ch
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

def taratura(fase, quanti=6, giu=0):
    """I tasti di una sonda per misurare una tastiera sconosciuta.

    fase "colonna": OK e poi passi in GIU'  -> la prima colonna, e
                    quante righe ci sono (in fondo si ripete o
                    ricomincia, e da quello si vede il bordo)
    fase "riga":    scende `giu` volte, poi OK e passi a DESTRA -> i
                    caratteri di quella riga

    Va usata con la ricerca appena aperta e il cursore non toccato,
    cosi' si sa da dove parte.

    `quanti` si tiene basso e si alza a poco a poco guardando la TV:
    su una tastiera sconosciuta non si sa cosa ci sia oltre il bordo,
    e a destra su Netflix si esce dalla tastiera.

    Le sonde sono RELATIVE, e non danno per buono niente sui bordi:
    una prima versione partiva "dall'angolo" andando a fondo corsa, e
    su Netflix ha fatto perdere la query, perche' con i bordi che
    girano l'angolo non esiste. Il comportamento dei bordi e' una
    delle cose DA misurare, e si vede dalla coda della sonda: se gli
    ultimi caratteri si RIPETONO il bordo ferma, se RICOMINCIANO dal
    primo il bordo gira."""
    if fase not in ("riga", "colonna"):
        raise ValueError(f'fase sconosciuta: "{fase}"')
    tasti = ["DOWN"] * giu + ["OK"]
    verso = "RIGHT" if fase == "riga" else "DOWN"
    for _ in range(quanti):
        tasti += [verso, "OK"]
    return tasti
