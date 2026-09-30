#!/usr/bin/env python3
"""
Scrive sul Fire TV Stick usando SOLO la libreria standard di Python.

    python3 firestick.py --ip 192.168.0.118 --prova
    python3 firestick.py --ip 192.168.0.118 --scrivi "the bear"

PERCHE' ESISTE, e perche' vale piu' di quello che abbiamo fatto per la
Samsung: il Fire TV parla ADB, e ADB ha "input text" - il testo si
scrive DIRETTAMENTE nel campo a fuoco. Niente griglie, niente ancore,
niente passi da misurare. Sulla Samsung abbiamo dovuto navigare sette
tastiere a frecce perche' la TV non offriva altro; qui non serve.

E gira dal TELEFONO, come scrivi_telefono.py: nessuna dipendenza, solo
socket e interi. Chi usa la TV non vuole niente sempre acceso in casa,
e questo vincolo decide l'architettura.

LA PARTE DIFFICILE E' L'AUTENTICAZIONE. ADB chiede di firmare un token
con RSA, e senza librerie va fatta a mano:
  - la firma e' pow(messaggio, d, n), cioe' una riga con gli interi di
    Python, che sono a precisione arbitraria;
  - la chiave pubblica va mandata in un formato binario suo, che
    Android si e' inventato (struct RSAPublicKey), e che include un
    paio di valori precalcolati per Montgomery;
  - il padding e' PKCS#1 v1.5, e il token di 20 byte viene trattato
    come se fosse gia' un digest SHA-1.
"""

import base64
import hashlib
import json
import os
import random
import socket
import struct
import sys
import time

# --- il protocollo ----------------------------------------------------
#
# Ogni messaggio e' 24 byte di intestazione piu' i dati. Sei interi a
# 32 bit, little-endian: comando, due argomenti, lunghezza dei dati,
# checksum dei dati, e il comando negato - che serve solo a verificare
# di essere allineati.

CNXN = 0x4E584E43
AUTH = 0x48545541
OPEN = 0x4E45504F
OKAY = 0x59414B4F
WRTE = 0x45545257
CLSE = 0x45534C43

NOMI = {CNXN: "CNXN", AUTH: "AUTH", OPEN: "OPEN",
        OKAY: "OKAY", WRTE: "WRTE", CLSE: "CLSE"}

AUTH_TOKEN = 1
AUTH_FIRMA = 2
AUTH_CHIAVE = 3

VERSIONE = 0x01000000
MAX_DATI = 256 * 1024


def intestazione(comando, arg0, arg1, dati=b""):
    """Il messaggio pronto da mandare."""
    return struct.pack("<6I", comando, arg0, arg1, len(dati),
                       sum(dati) & 0xFFFFFFFF,
                       comando ^ 0xFFFFFFFF) + dati


class Adb:
    """Una connessione ADB. Tiene il socket e legge i messaggi interi,
    perche' un socket non garantisce che arrivino tutti insieme."""

    def __init__(self, ip, porta=5555, timeout=10):
        self.s = socket.create_connection((ip, porta), timeout=timeout)
        self.locale = 1

    def esatti(self, quanti):
        pezzi = b""
        while len(pezzi) < quanti:
            p = self.s.recv(quanti - len(pezzi))
            if not p:
                raise ConnectionError("il Fire TV ha chiuso la connessione")
            pezzi += p
        return pezzi

    def manda(self, comando, arg0=0, arg1=0, dati=b""):
        self.s.sendall(intestazione(comando, arg0, arg1, dati))

    def leggi(self):
        testa = self.esatti(24)
        comando, arg0, arg1, quanti, _crc, verifica = struct.unpack("<6I", testa)
        if comando ^ 0xFFFFFFFF != verifica:
            raise ConnectionError("messaggio ADB non allineato")
        dati = self.esatti(quanti) if quanti else b""
        return comando, arg0, arg1, dati

    def chiudi(self):
        try:
            self.s.close()
        except OSError:
            pass


# --- RSA a mano -------------------------------------------------------
#
# Serve perche' ADB chiede una firma e sul telefono non ci sono
# librerie. Gli interi di Python sono a precisione arbitraria, quindi
# la matematica e' gratis: la firma e' pow(messaggio, d, n).
#
# LA CHIAVE SI RIGENERA DA UN SEME, invece di essere salvata. Sul
# telefono non ci sono file - e' la stessa ragione per cui il token
# della Samsung viaggia nel comando. Un seme di poche cifre sta in un
# comando; una chiave privata da millesettecento caratteri no.
#
# Il prezzo, detto chiaramente: una chiave derivata da un seme corto e'
# piu' debole di una casuale. Qui serve ad accoppiare due dispositivi
# sulla rete di casa, non a proteggere un conto in banca - e chi ha il
# seme ha comunque bisogno di stare sulla stessa rete.

BIT = 2048
ESPONENTE = 65537


def _primo(rnd, bit):
    """Un primo probabile di `bit` bit, pescato da `rnd`."""
    while True:
        n = rnd.getrandbits(bit) | (1 << (bit - 1)) | 1
        if _forse_primo(n):
            return n


def _forse_primo(n, giri=24):
    """Miller-Rabin. Con 24 giri la probabilita' di sbagliare e' sotto
    2^-48: per accoppiare due dispositivi in casa basta e avanza."""
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n % p == 0:
            return n == p
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for _ in range(giri):
        a = random.randrange(2, n - 1)
        x = pow(a, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def chiave(seme):
    """La coppia di chiavi, ricavata dal seme. Lo stesso seme da'
    sempre la stessa chiave, ed e' questo che rende inutile salvarla."""
    rnd = random.Random("tvproject-adb:" + str(seme))
    while True:
        p = _primo(rnd, BIT // 2)
        q = _primo(rnd, BIT // 2)
        if p == q:
            continue
        n = p * q
        if n.bit_length() != BIT:
            continue
        phi = (p - 1) * (q - 1)
        if phi % ESPONENTE == 0:
            continue
        return n, pow(ESPONENTE, -1, phi)


# Il prefisso che dice "quello che segue e' un digest SHA-1". ADB
# firma il token di 20 byte come se fosse gia' un digest, quindi il
# prefisso va messo a mano.
DIGEST_SHA1 = bytes.fromhex("3021300906052b0e03021a05000414")


def firma(token, n, d):
    """La firma PKCS#1 v1.5 del token, come la vuole ADB."""
    corpo = DIGEST_SHA1 + token
    riempimento = b"\xff" * (BIT // 8 - 3 - len(corpo))
    em = b"\x00\x01" + riempimento + b"\x00" + corpo
    return pow(int.from_bytes(em, "big"), d, n).to_bytes(BIT // 8, "big")


def chiave_per_android(n, nome=b"tvproject@telefono"):
    """La chiave pubblica nel formato che Android si e' inventato.

    E' una struttura binaria little-endian con dentro due valori
    precalcolati per la moltiplicazione di Montgomery - n0inv e rr -
    che non servono a noi ma il dispositivo li pretende."""
    parole = BIT // 32
    n0inv = (-pow(n, -1, 1 << 32)) % (1 << 32)
    rr = pow(1 << BIT, 2, n)
    grezzo = (struct.pack("<II", parole, n0inv)
              + n.to_bytes(BIT // 8, "little")
              + rr.to_bytes(BIT // 8, "little")
              + struct.pack("<I", ESPONENTE))
    return base64.b64encode(grezzo) + b" " + nome + b"\x00"


# --- collegarsi --------------------------------------------------------
#
# Il giro e' questo, e l'ordine conta:
#   noi   CNXN                  "ciao, sono un host"
#   lui   AUTH token            "firmami questi 20 byte"
#   noi   AUTH firma
#   lui   CNXN                  se ci conosce, siamo dentro
#         oppure AUTH token     se NON ci conosce, richiede
#   noi   AUTH chiave pubblica
#   lui   mostra il popup, e dopo l'accettazione manda CNXN
#
# Quindi il secondo token non e' un errore: e' il modo che ha di dire
# "non ti conosco, presentati".

# La chiave tenuta da parte. Derivarla costa 1.56 s MISURATI, che
# sono meta' del tempo di ogni comando: su un tasto «pausa» si sente
# tutto, e su una fila di tasti si paga una volta sola ma si paga.
#
# Non e' un segreto nuovo in un posto nuovo: dal seme la chiave si
# rifa' IDENTICA, quindi questo file e' la copia di una cosa che
# chiunque abbia il telefono puo' rigenerare in un secondo e mezzo.
# Il seme sta nel comando, non qui.
CACHE_VERSIONE = 1


def dove_tenere_la_chiave(seme):
    """Il file della cache, nella prima cartella scrivibile che trovo.

    Su a-Shell e' ~/Documents; sul Mac pure. Se non se ne trova
    nessuna si torna a derivare ogni volta: lento, non rotto."""
    marchio = hashlib.sha256(("firechiave:" + seme).encode()).hexdigest()[:12]
    for d in (os.path.expanduser("~/Documents"), os.path.expanduser("~"),
              "/tmp"):
        try:
            if os.path.isdir(d) and os.access(d, os.W_OK):
                return os.path.join(d, ".firechiave-" + marchio + ".json")
        except OSError:
            continue
    return None


def chiave_tenuta(seme, usa_cache=True):
    if not usa_cache:
        return chiave(seme)
    f = dove_tenere_la_chiave(seme)
    if f and os.path.exists(f):
        try:
            with open(f) as h:
                dati = json.load(h)
            if int(dati.get("versione", 0)) == CACHE_VERSIONE:
                n, d = int(dati["n"]), int(dati["d"])
                # UNA verifica, perche' una cache corrotta che passa per
                # buona darebbe un errore di autorizzazione
                # incomprensibile: 2 elevato a e*d dev'essere 2.
                if pow(pow(2, 65537, n), d, n) == 2:
                    return n, d
        except Exception:
            pass          # cache illeggibile o sbagliata: si rifa'
    n, d = chiave(seme)
    if f:
        try:
            with open(f, "w") as h:
                json.dump({"versione": CACHE_VERSIONE,
                           "n": str(n), "d": str(d)}, h)
            os.chmod(f, 0o600)
        except OSError:
            pass          # non si puo' scrivere: pazienza, si rideriva
    return n, d


def collega(ip, seme, porta=5555, nome=b"tvproject@telefono", timeout=10,
            usa_cache=True):
    n, d = chiave_tenuta(seme, usa_cache)
    a = Adb(ip, porta, timeout)
    a.manda(CNXN, VERSIONE, MAX_DATI, b"host::\x00")
    token_visti = 0
    for _ in range(8):
        comando, arg0, _arg1, dati = a.leggi()
        if comando == CNXN:
            return a, dati.split(b"\x00")[0].decode(errors="replace")
        if comando != AUTH:
            continue
        if arg0 != AUTH_TOKEN:
            continue
        token_visti += 1
        if token_visti == 1:
            a.manda(AUTH, AUTH_FIRMA, 0, firma(dati, n, d))
        else:
            # Non ci conosce: gli mandiamo la chiave e lui chiede a
            # chi guarda la TV se ci autorizza.
            a.manda(AUTH, AUTH_CHIAVE, 0, chiave_per_android(n, nome))
    a.chiudi()
    raise ConnectionError(
        "il Fire TV non ha completato il collegamento.\n"
        "  GUARDA LO SCHERMO: la prima volta compare un popup che chiede\n"
        "  di consentire il debug da questo dispositivo. Accettalo, e\n"
        "  spunta 'consenti sempre' per non rivederlo.")


def comanda(a, riga, attesa=15.0):
    """Esegue un comando di shell sul Fire TV e restituisce l'uscita.

    OGNI MESSAGGIO PORTA L'ID DEL FLUSSO, e va guardato: dopo che noi
    mandiamo il nostro CLSE, adbd manda il SUO, che resta nel
    cuscinetto. Senza controllare l'id, quel CLSE avanzato chiudeva
    subito il comando DOPO, che tornava vuoto - e l'uscita sembrava
    spostata di uno.
    Sintomo visto per davvero: un `pm install` che non diceva niente e
    la sua «Success» che compariva al comando successivo."""
    mio = a.locale
    a.locale += 1
    a.s.settimeout(attesa)
    a.manda(OPEN, mio, 0, b"shell:" + riga.encode() + b"\x00")
    uscita, remoto = b"", 0
    for _ in range(4000):
        try:
            comando, arg0, arg1, dati = a.leggi()
        except (socket.timeout, OSError):
            break
        # arg1 e' il NOSTRO id per i messaggi che riguardano noi.
        # Quelli di un flusso vecchio si buttano.
        if arg1 and arg1 != mio:
            continue
        if comando == OKAY:
            remoto = arg0
        elif comando == WRTE:
            uscita += dati
            a.manda(OKAY, mio, arg0 or remoto)
        elif comando == CLSE:
            a.manda(CLSE, mio, arg0 or remoto)
            break
    return uscita.decode(errors="replace")


def comanda_grezza(a, riga, attesa=30.0):
    """Come comanda(), ma restituisce i BYTE senza decodificarli.

    Serve per screencap: una PNG passata da decode() si rovina. Ed e'
    la cosa che sulla Samsung non si poteva fare per niente - la' non
    c'era modo di sapere cosa ci fosse a schermo, e ogni singolo fatto
    e' stato misurato usando come sensore chi guardava la TV."""
    a.s.settimeout(attesa)
    a.manda(OPEN, a.locale, 0, b"shell:" + riga.encode() + b"\x00")
    uscita, remoto = b"", 0
    for _ in range(20000):
        try:
            comando, arg0, _arg1, dati = a.leggi()
        except (socket.timeout, OSError):
            break
        if comando == OKAY:
            remoto = arg0
        elif comando == WRTE:
            uscita += dati
            a.manda(OKAY, a.locale, arg0 or remoto)
        elif comando == CLSE:
            a.manda(CLSE, a.locale, arg0 or remoto)
            break
    a.locale += 1
    return uscita


# Gli accenti si appiattiscono, non si buttano: "perche'" scritto
# senza la e finale diventa "perch", e la ricerca non trova niente,
# mentre "perche" la trova. Su Samsung invece le vocali accentate si
# battono per davvero, perche' Prime Video ha una riga di tasti per
# loro; qui non c'e' una tastiera da navigare, c'e' una shell, e
# "input text" con UTF-8 non e' affidabile.
ACCENTI = str.maketrans({
    "à": "a", "á": "a", "â": "a", "ä": "a", "ã": "a", "å": "a",
    "è": "e", "é": "e", "ê": "e", "ë": "e",
    "ì": "i", "í": "i", "î": "i", "ï": "i",
    "ò": "o", "ó": "o", "ô": "o", "ö": "o", "õ": "o", "ø": "o",
    "ù": "u", "ú": "u", "û": "u", "ü": "u",
    "ç": "c", "ñ": "n", "ß": "ss", "æ": "ae", "œ": "oe",
    "'": " ", "\u2019": " ",
    # i separatori diventano spazi, non niente: "WALL\u00b7E" senza il
    # punto diventa "walle", con lo spazio resta "wall e"
    "\u00b7": " ", ":": " ", "\u2013": " ", "\u2014": " ", "/": " ",
})


def _apice(testo):
    """Racchiude una stringa fra apici singoli per la shell, in modo
    sicuro: l'unico carattere che un apice singolo non protegge e'
    l'apice singolo stesso, e si chiude/riapre con la sequenza
    '\\'' ."""
    return "'" + testo.replace("'", "'\\''") + "'"


def per_input_text(testo):
    """Il testo come lo vuole "input text": gli spazi diventano %s, e
    quello che potrebbe rompere la riga di shell si toglie.

    Non e' pignoleria: "input text" passa da una shell, e un apostrofo
    o un punto e virgola la spezzerebbero."""
    piatto = testo.lower().translate(ACCENTI)
    pulito = "".join(c for c in piatto if c.isalnum() or c in " -_.")
    return " ".join(pulito.split()).replace(" ", "%s")


# --- la ricerca globale ------------------------------------------------

# Coordinate MISURATE a mano sulla schermata vera, non dedotte, e
# confermate due volte: "4 ristoranti" -> NOW e "harry potter" ->
# HBO Max le hanno usate identiche. Sono punti-schermo fissi: se
# Amazon cambia la disposizione si rompono IN SILENZIO, e per questo
# stanno tutte qui, con un nome, invece che sparse nel codice. Sette
# numeri da mantenere invece di sette tastiere.
RICERCA = {
    "lente":    (331, 580),   # la lente nella barra in alto
    "campo":    (530, 718),   # il campo "Cerca"
    # la lente DENTRO la pillola: sta sempre qui, mentre la pillola si
    # allarga col testo che scrivi
    "conferma": (160, 618),
    "primo":    (336, 583),   # il poster del primo risultato
    "servizio": (197, 817),   # il riquadro sotto "Guarda ora con X"
}

# Dove fermarsi. Il default e' "risultati" DI PROPOSITO: aprire il
# primo risultato alla cieca e' la cosa che chi usa la TV ha detto di
# non volere, e la pagina dei risultati mostra i poster con nome e
# anno, piu' quale servizio ce l'ha.
TAPPE = {
    "risultati": [],
    "titolo":    ["primo"],
    "servizio":  ["primo", "servizio"],
}


def cerca(a, titolo, fino="risultati", passo=1.2, attesa=15.0, eco=print):
    """Scrive il titolo nella ricerca globale del Fire TV.

    Non usa la ricerca DENTRO le app: quella del Fire TV copre tutte
    le app insieme, e dice da se' quali hai ("Guarda ora con X") e
    quali no ("Disponibile con X" e un prezzo)."""
    if fino not in TAPPE:
        raise ValueError("non so fermarmi a «" + fino + "»: "
                         + ", ".join(TAPPE))
    # Il titolo si controlla PRIMA di toccare qualunque cosa: se il
    # controllo sta in fondo alla catena, un titolo che si svuota
    # lascia la TV sulla ricerca con un campo vuoto.
    testo = per_input_text(titolo)
    if not any(c.isalnum() for c in testo):
        raise ValueError("del titolo non resta niente di scrivibile")

    def tocca(dove):
        x, y = RICERCA[dove]
        eco(f"  tocco {dove} ({x},{y})")
        comanda(a, f"input tap {x} {y}", attesa)
        time.sleep(passo)

    # HOME prima di tutto: non si sa da dove si parte, e la barra di
    # ricerca esiste solo sulla schermata iniziale. Su Samsung questo
    # e' un mestiere da BACK ripetuti; qui e' un tasto.
    eco("  HOME")
    comanda(a, "input keyevent KEYCODE_HOME", attesa)
    time.sleep(passo * 2)

    tocca("lente")
    tocca("campo")

    eco(f'  scrivo "{titolo}" -> {testo}')
    comanda(a, "input text " + testo, attesa)
    time.sleep(passo)

    tocca("conferma")
    for tappa in TAPPE[fino]:
        tocca(tappa)
    return testo


# --- i tasti ----------------------------------------------------------

# I nomi corti che usa l'app, e il keyevent vero. I nomi corti
# servono perche' viaggiano in un argomento unico attraverso la
# Scorciatoia, e "KEYCODE_DPAD_DOWN" ripetuto dieci volte e' una riga
# lunghissima per niente.
TASTI = {
    "UP": "KEYCODE_DPAD_UP",
    "DOWN": "KEYCODE_DPAD_DOWN",
    "LEFT": "KEYCODE_DPAD_LEFT",
    "RIGHT": "KEYCODE_DPAD_RIGHT",
    "OK": "KEYCODE_DPAD_CENTER",
    "BACK": "KEYCODE_BACK",
    "HOME": "KEYCODE_HOME",
    "MENU": "KEYCODE_MENU",
    "PLAY": "KEYCODE_MEDIA_PLAY_PAUSE",
    "INDRE": "KEYCODE_MEDIA_REWIND",
    "AVANTI": "KEYCODE_MEDIA_FAST_FORWARD",
    "STOP": "KEYCODE_MEDIA_STOP",
    "DORMI": "KEYCODE_SLEEP",
    "SVEGLIA": "KEYCODE_WAKEUP",
}


def tasti(a, elenco, passo=0.35, attesa=15.0, eco=print):
    """Manda una fila di tasti in UN SOLO collegamento.

    E' il punto: aprire un collegamento per ogni tasto vuol dire tre
    secondi per freccia - la generazione della chiave da sola ne vale
    uno e mezzo - e una croce direzionale cosi' non si puo' usare. Qui
    si paga una volta e si mandano tutti."""
    fuori = []
    for nome in elenco:
        corto = str(nome).strip().upper()
        if not corto:
            continue
        if corto not in TASTI:
            raise ValueError("non conosco il tasto «" + corto + "»: "
                             + " ".join(sorted(TASTI)))
        eco("  " + corto)
        comanda(a, "input keyevent " + TASTI[corto], attesa)
        fuori.append(corto)
        time.sleep(passo)
    if not fuori:
        raise ValueError("nessun tasto da mandare")
    return fuori


# --- la prova del ponte -----------------------------------------------

BATTITO_DOVE = "/sdcard/battito.txt"


def battito(a, giri=90, attesa=15.0, eco=print):
    """Tiene aperto UN collegamento e scrive un'ora al secondo SUL
    FIRE STICK.

    Serve a rispondere alla domanda che decide se il telecomando si
    puo' fare: iOS lascia girare a-Shell quando esci dall'app? Se le
    righe non hanno buchi, si'.

    Il testimone e' il Fire Stick e non lo schermo del telefono,
    perche' a-Shell non mostra l'uscita dei comandi, e non e' il Mac
    perche' il firewall del Mac blocca le connessioni in arrivo.

    Ed e' il PROTOTIPO del ponte: un collegamento aperto a lungo con
    tanti comandi dentro e' esattamente quello che dovrebbe fare."""
    comanda(a, "rm -f " + BATTITO_DOVE, attesa)
    # Un segno SUBITO, appena il collegamento c'e'. Serve a
    # distinguere tre casi che da fuori sembrano uguali:
    #   file assente        -> non si e' mai collegato
    #   solo PARTITO        -> collegato e poi fermato subito
    #   PARTITO + righe     -> ha girato, e i buchi dicono quanto
    comanda(a, "echo PARTITO $(date +%H:%M:%S) > " + BATTITO_DOVE, attesa)
    fatti = 0
    for n in range(1, giri + 1):
        try:
            comanda(a, "echo $(date +%H:%M:%S) riga " + str(n) +
                    " >> " + BATTITO_DOVE, attesa)
        except Exception:
            break     # caduto: il file dira' fino a dove e' arrivato
        fatti = n
        time.sleep(1)
    eco("  scritte %d righe in %s" % (fatti, BATTITO_DOVE))
    return fatti


# --- mettere un file sul Fire TV ---------------------------------------


def deposita(a, locale, remoto, pezzo=1500, attesa=30.0, eco=print):
    """Copia un file sul Fire TV passando dalla shell.

    Perche' non `adb push`: adb usa una chiave SUA, che il Fire TV non
    ha autorizzato, e farla autorizzare vuol dire accettare un popup
    stando davanti al proiettore. La nostra chiave invece e' gia'
    autorizzata, ma il nostro client parla solo il servizio «shell».
    Quindi il file viaggia in base64 a pezzi, e lo rimette insieme
    `toybox base64 -d` dall'altra parte.

    Lento (qualche decina di comandi) ma non chiede niente a nessuno."""
    import base64 as _b64
    dati = open(locale, "rb").read()
    testo = _b64.b64encode(dati).decode()
    b64 = remoto + ".b64"
    comanda(a, "rm -f " + b64 + " " + remoto, attesa)
    quanti = (len(testo) + pezzo - 1) // pezzo
    for i in range(quanti):
        fetta = testo[i * pezzo:(i + 1) * pezzo]
        comanda(a, "echo -n " + fetta + " >> " + b64, attesa)
        eco("  pezzo %d/%d" % (i + 1, quanti))
    comanda(a, "toybox base64 -d " + b64 + " > " + remoto, attesa)
    comanda(a, "rm -f " + b64, attesa)
    detto = comanda(a, "wc -c < " + remoto, attesa).strip()
    eco("  %s byte sul Fire TV (%d attesi)" % (detto, len(dati)))
    if detto != str(len(dati)):
        raise ValueError("il file e' arrivato incompleto")
    return remoto


# --- da riga di comando ------------------------------------------------

def opzioni(argv):
    """Le opzioni come --chiave=valore, anche dentro un argomento
    unico: la Scorciatoia iOS passa tutto in un pezzo solo, come per
    scrivi_telefono.py."""
    noti = {"ip", "porta", "seme", "nome", "attesa", "fino", "passo",
            "cache"}
    valori, resto, ignote = {}, [], []
    for pezzo in argv:
        tenute = []
        for parola in pezzo.split(" "):
            if parola.startswith("--") and "=" in parola:
                chiave_, valore = parola[2:].split("=", 1)
                if chiave_ in noti:
                    valori[chiave_] = valore
                    continue
                ignote.append(parola)
            tenute.append(parola)
        rimasto = " ".join(x for x in tenute if x)
        if rimasto:
            resto.append(rimasto)
    return valori, resto, ignote


def separa(resto):
    """Il comando e il suo argomento, da qualunque forma arrivino.

    La Scorciatoia iOS passa tutto in UN argomento unico, quindi
    ["--cerca the bear"] e ["--cerca", "the bear"] devono valere la
    stessa cosa. Prendendo resto[0] il primo caso dava un comando che
    si chiamava "--cerca the bear"."""
    parole = " ".join(resto).split()
    if not parole:
        return "", ""
    return parole[0], " ".join(parole[1:])


AIUTO = """  FIRE TV STICK, dal telefono e senza dipendenze

    python3 firestick.py --ip=192.168.0.118 --prova
    python3 firestick.py --ip=192.168.0.118 --app
    python3 firestick.py --ip=192.168.0.118 --cerca "the bear"
    python3 firestick.py --ip=192.168.0.118 --fino=titolo --cerca "the bear"
    python3 firestick.py --ip=192.168.0.118 --scrivi "the bear"
    python3 firestick.py --ip=192.168.0.118 --tasto DOWN
    python3 firestick.py --ip=192.168.0.118 --tasti "DOWN DOWN RIGHT OK"
    python3 firestick.py --ip=192.168.0.118 --battito
    python3 firestick.py --ip=192.168.0.118 --installa app.apk
    python3 firestick.py --ip=192.168.0.118 --schermata foto.png
    python3 firestick.py --ip=192.168.0.118 --shell "dumpsys power | head"

  Prima di tutto, sul Fire TV col telecomando:
    Impostazioni -> Il mio Fire TV -> Opzioni per sviluppatori
    -> Debug ADB -> Attiva
  Se non vedi le opzioni per sviluppatori: Informazioni -> premi OK
  sette volte sul nome del dispositivo.

  --cerca usa la RICERCA GLOBALE del Fire TV, non quella dentro le
  app: copre tutte le app insieme e dice da se' quali ce l'hanno
  ("Guarda ora con X") e quali no ("Disponibile con X" e il prezzo).
  Si ferma sui RISULTATI e scegli tu. Con --fino=titolo apre il primo
  risultato e ti fa vedere la pagina; con --fino=servizio parte.

  --tasti manda una fila di tasti in UN SOLO collegamento, e questo e'
  il punto: un collegamento per tasto vuol dire tre secondi per
  freccia. I nomi corti sono:
    UP DOWN LEFT RIGHT OK BACK HOME MENU
    PLAY INDRE AVANTI STOP DORMI SVEGLIA

  La chiave derivata viene TENUTA DA PARTE in un file nascosto: farla
  costa un secondo e mezzo, ed e' meta' del tempo di ogni comando.
  Con --cache=0 la si rifa' ogni volta.

  Il SEME (--seme=) decide la chiave: lo stesso seme da' sempre la
  stessa chiave, quindi il Fire TV ti riconosce senza che nulla venga
  salvato su disco. Cambiarlo vuol dire riautorizzare."""


def main():
    valori, resto, ignote = opzioni(sys.argv[1:])
    if ignote:
        print("  non conosco l'opzione " + " ".join(ignote))
        print("  quelle buone sono: --ip= --porta= --seme= --nome= --attesa=")
        return 1
    if not resto:
        print(AIUTO)
        return 0

    ip = valori.get("ip") or os.environ.get("FIRE_IP", "")
    if not ip:
        print("  mi serve l'indirizzo del Fire TV: --ip=192.168.0.x")
        print("  lo trovi in Impostazioni -> Il mio Fire TV -> Informazioni")
        print("  -> Rete")
        return 1
    seme = valori.get("seme") or os.environ.get("FIRE_SEME", "tvproject")
    porta = int(valori.get("porta", 5555))
    # Generosa per default: la prima volta si aspetta che una persona
    # accetti un popup sullo schermo.
    attesa = float(valori.get("attesa", 60))
    # Il passo fra un tocco e l'altro: il Fire TV deve avere il tempo
    # di disegnare la schermata nuova, o il tocco successivo cade sul
    # posto sbagliato. Misurato: 1.2 s regge.
    passo = float(valori.get("passo", 1.2))
    nome = valori.get("nome", "tvproject@telefono").encode()

    comando, argomento = separa(resto)

    try:
        print(f"  mi collego a {ip}:{porta}, chiave dal seme «{seme}»")
        # L'attesa vale anche per l'HANDSHAKE, non solo per i comandi:
        # la prima volta il Fire TV mostra un popup e sta fermo finche'
        # qualcuno non lo accetta. Con dieci secondi fissi scadeva
        # prima che si facesse in tempo a prendere il telecomando.
        a, chi = collega(ip, seme, porta, nome, timeout=attesa,
                         usa_cache=valori.get("cache") != "0")
        print(f"  collegato: {chi}")

        if comando == "--prova":
            print("  " + comanda(a, "getprop ro.product.model", attesa).strip())
            print("  " + comanda(a, "getprop ro.build.version.release", attesa).strip())
            print("  Il collegamento funziona. Da qui si puo' scrivere testo")
            print("  DIRETTAMENTE, senza navigare nessuna tastiera.")
        elif comando == "--app":
            fuori = comanda(a, "dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'", attesa)
            print("  " + (fuori.strip() or "(niente)"))
        elif comando == "--scrivi":
            if not argomento:
                print("  e cosa scrivo?")
                return 1
            testo = per_input_text(argomento)
            print(f'  scrivo "{argomento}" come input text: {testo}')
            comanda(a, "input text " + testo, attesa)
            print("  Mandato. Guarda lo schermo: se il campo era a fuoco,")
            print("  il testo c'e' tutto in una volta.")
        elif comando == "--tasto":
            # il nome corto se lo conosco, altrimenti alla lettera:
            # cosi' resta possibile provare un keyevent qualsiasi
            secco = argomento.strip().upper()
            vero = TASTI.get(secco, argomento)
            comanda(a, "input keyevent " + vero, attesa)
            print(f"  mandato {vero}")
        elif comando == "--tasti":
            fatti = tasti(a, argomento.replace(",", " ").split(),
                          passo=min(passo, 0.5), attesa=attesa)
            print(f"  mandati {len(fatti)} tasti in un solo collegamento")
        elif comando == "--schermata":
            dove = argomento or "schermata.png"
            byte = comanda_grezza(a, "screencap -p", attesa)
            # Alcune versioni di Android traducono \n in \r\n sullo
            # stream di shell e rovinano le PNG: se la firma non torna,
            # si prova a disfare la traduzione.
            if not byte.startswith(b"\x89PNG"):
                byte = byte.replace(b"\r\n", b"\n")
            with open(dove, "wb") as f:
                f.write(byte)
            buona = byte.startswith(b"\x89PNG")
            print(f"  {len(byte)} byte in {dove}"
                  + ("" if buona else "  (NON sembra una PNG)"))
        elif comando == "--cerca":
            if not argomento:
                print("  e cosa cerco?")
                return 1
            fino = valori.get("fino", "risultati")
            cerca(a, argomento, fino=fino, passo=passo, attesa=attesa)
            print("  Fatto. " + ({
                "risultati": "Sei sui risultati: scegli tu il titolo.",
                "titolo": "Sei sulla pagina del titolo: guarda che sia "
                          "quello giusto e premi OK.",
                "servizio": "Dovrebbe essere partito.",
            })[fino])
        elif comando == "--battito":
            print("  Tengo il collegamento aperto e scrivo una riga al")
            print("  secondo. ESCI DALL'APP e resta fuori un minuto.")
            battito(a, giri=int(argomento or 90), attesa=attesa)
        elif comando == "--deposita":
            pezzi = argomento.split()
            if len(pezzi) != 2:
                print("  --deposita <file locale> <percorso sul Fire TV>")
                return 1
            deposita(a, pezzi[0], pezzi[1], attesa=attesa)
        elif comando == "--installa":
            if not argomento:
                print("  --installa <file.apk>")
                return 1
            dove = "/data/local/tmp/da-installare.apk"
            deposita(a, argomento, dove, attesa=attesa)
            print("  installo...")
            # -t serve: senza, pm rifiuta in silenzio (uscita vuota).
            print("  " + comanda(a, "pm install -r -t " + dove + " 2>&1",
                                 120).strip())
            comanda(a, "rm -f " + dove, attesa)
        elif comando == "--helper":
            # L'AIUTANTE DELLE FRECCE. Un `nc -L` che gira come utente
            # shell (uid 2000) e per ogni richiesta HTTP fa `input
            # keyevent`. E' l'unico modo di iniettare le frecce nelle
            # app: un'app non puo', un processo shell si'.
            #
            # Perche' via ADB e non dall'app: solo un processo START-ato
            # da shell E' shell. L'app (uid app) non lo puo' generare;
            # noi via ADB si'. Va (ri)acceso dopo un riavvio del Fire
            # Stick - un processo non sopravvive a un reboot.
            #
            # LA FORMA CONTA, misurata: `nohup nc -L ... &` in UNA riga
            # sopravvive alla chiusura della connessione; `setsid` da
            # solo o un `while` in uno script no.
            gestore = ("read line; "
                       "k=$(echo \"$line\" | "
                       "toybox sed -n 's/.*[?&]k=\\([0-9]*\\).*/\\1/p'); "
                       "case \"$k\" in "
                       "3|4|19|20|21|22|23|66|82|85|86|89|90) "
                       "input keyevent \"$k\" ;; esac; "
                       "printf 'HTTP/1.1 200 OK\\r\\n"
                       "Content-Length: 2\\r\\n"
                       "Access-Control-Allow-Origin: *\\r\\n"
                       "Connection: close\\r\\n\\r\\nok'")
            comanda(a, "printf '%s' " + _apice(gestore) +
                    " > /data/local/tmp/hkey.sh; chmod 755 "
                    "/data/local/tmp/hkey.sh", attesa)
            # prima spengo un eventuale vecchio helper, in un comando A
            # PARTE: nella stessa riga del lancio, il pkill ucciderebbe
            # anche il nc appena nato.
            comanda(a, "pkill -f 'nc -L -p 8081' 2>/dev/null; "
                    "toybox true", attesa)
            time.sleep(1)
            # TUTTO IN UNA RIGA, e non e' pignoleria: il lancio in
            # background e un seguito (sleep + netstat) devono stare
            # nello STESSO comando. Il servizio «shell» di ADB uccide il
            # gruppo quando il flusso si chiude; tenendo la riga viva un
            # momento dopo il &, nc fa in tempo a farsi adottare da init
            # (PPID 1) e sopravvive. Misurato: cosi' regge, con il
            # lancio da solo no.
            su = comanda(
                a,
                "nohup toybox nc -L -p 8081 /data/local/tmp/hkey.sh "
                "</dev/null >/dev/null 2>&1 & "
                "sleep 2; toybox netstat -ltn | grep 8081", attesa).strip()
            if su:
                print("  aiutante delle frecce ACCESO sulla 8081")
            else:
                print("  non sono riuscito ad accenderlo (riprova)")
                return 1
        elif comando == "--shell":
            print(comanda(a, argomento, attesa))
        else:
            print(f'  "{comando}" non lo conosco.')
            print(AIUTO)
            return 1
        a.chiudi()
        return 0

    except ConnectionRefusedError:
        print(f"  {ip}:{porta} rifiuta il collegamento.")
        print("  Vuol dire che il DEBUG ADB non e' attivo sul Fire TV, o")
        print("  che quell'indirizzo e' di qualcos'altro.")
        print("  Impostazioni -> Il mio Fire TV -> Opzioni per sviluppatori")
        return 1
    except ConnectionError as e:
        print("  " + str(e))
        return 1
    except OSError as e:
        print(f"  non arrivo a {ip}:{porta} ({e.__class__.__name__}).")
        print("  Il Fire TV e' acceso e sulla rete di casa?")
        return 1


if __name__ == "__main__":
    sys.exit(main())
