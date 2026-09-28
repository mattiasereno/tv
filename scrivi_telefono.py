#!/usr/bin/env python3
"""
Scrive testo sulla TV usando SOLO la libreria standard di Python.

    python3 scrivi_telefono.py "the bear"
    python3 scrivi_telefono.py --tasto KEY_HOME
    python3 scrivi_telefono.py --token                  il token della TV
    python3 scrivi_telefono.py --ascolta                che tastiera ha
    python3 scrivi_telefono.py --digita "the bear"      dentro l'app
    python3 scrivi_telefono.py --apri "the bear"        strada + scrittura
    python3 scrivi_telefono.py --percorso "the bear"    solo i tasti

Perche' esiste: il testo sulla TV passa solo da un WebSocket con la
verifica del certificato disattivata. Un browser non puo' farlo per
progetto (il certificato della TV vale solo per 127.0.0.1), e le
Scorciatoie iOS non parlano WebSocket.

Ma un'app-terminale su iPhone (a-Shell, iSH) esegue Python. Se lo
script non ha dipendenze, il TELEFONO diventa il ponte verso la TV,
senza nessun computer accesso. Per questo qui non si importa
samsungtvws ne' websocket-client: solo socket, ssl, base64, json.

Serve il token della TV, quello in token.txt, ottenuto una volta
sola accettando il popup.

Variabili utili:
    TV_IP     indirizzo della TV (predefinito 192.168.0.84)
    TV_NOME   nome con cui ci presentiamo (predefinito TVProject)
    TV_TOKEN  token, se non vuoi usare token.txt
    TV_PORTA  8002 con TLS (predefinito), 8001 in chiaro (rifiutata
              dalla TV: risponde ms.channel.unauthorized)
"""

import base64
import json
import os
import re
import socket
import struct
import sys
import time

def opzioni_da_argv():
    """Legge le opzioni scritte come --chiave=valore e le toglie da
    argv, mettendole nell'ambiente.

    Serve perche' a-Shell non e' una shell completa: il prefisso
    VAR=valore davanti a un comando non lo interpreta (e non capisce
    nemmeno ";" per concatenare). Quindi tutto quello che altrove si
    passerebbe nell'ambiente, dal telefono deve stare negli
    ARGOMENTI.

    Va chiamata QUI, prima delle costanti qui sotto: quelle leggono
    l'ambiente una volta sola, all'avvio, e farlo dopo sarebbe
    tardi."""
    nomi = {"nome": "TV_NOME", "token": "TV_TOKEN", "ip": "TV_IP",
            "porta": "TV_PORTA", "passo": "TV_PASSO",
            "naviga": "TV_NAVIGA", "carica": "TV_CARICA",
            "tastiera": "TV_TASTIERA", "azzera": "TV_AZZERA",
            "app": "TV_APP", "tastiere": "TV_TASTIERE"}
    resto, ignote = [sys.argv[0] if sys.argv else ""], []
    for pezzo in sys.argv[1:]:
        if pezzo.startswith("--") and "=" in pezzo:
            chiave, valore = pezzo[2:].split("=", 1)
            if chiave in nomi:
                os.environ[nomi[chiave]] = valore
                continue
            ignote.append(pezzo)
        resto.append(pezzo)
    sys.argv[:] = resto
    # Un'opzione scritta male non va ignorata in silenzio: finirebbe
    # fra gli argomenti e, nel peggiore dei casi, dentro il titolo.
    return ignote


OPZIONI_IGNOTE = opzioni_da_argv()

TV = os.environ.get("TV_IP", "192.168.0.84")
# 8002 con TLS, e la verifica del certificato disattivata: quello
# della TV ha subjectAltName IP 127.0.0.1, quindi non puo' valere per
# l'indirizzo in rete. E' anche il motivo per cui un browser non
# potra' MAI aprire questa connessione, nemmeno fidandosi della CA.
#
# La 8001 in chiaro NON e' una scorciatoia utilizzabile, provato:
# l'handshake passa (101) ma il canale risponde
# ms.channel.unauthorized, col token e senza. La TV pretende TLS.
# Quindi serve un Python col modulo ssl - che c'e' sia in a-Shell
# sia in iSH.
PORTA = int(os.environ.get("TV_PORTA", "8002"))
# Il nome con cui ci presentiamo alla TV. La TV tiene un elenco di
# dispositivi autorizzati e NEGATI, e risponde 403 a quelli negati.
# Se un popup scaduto ha registrato un rifiuto, presentarsi con un
# nome nuovo fa ricomparire la richiesta di permesso.
NOME = os.environ.get("TV_NOME", "TVProject")


def inquadra(carico):
    """Un frame di testo. I client DEVONO mascherare, dice il protocollo."""
    testa = bytes([0x81])                       # FIN + opcode testo
    n = len(carico)
    if n < 126:
        testa += bytes([0x80 | n])
    elif n < 65536:
        testa += bytes([0x80 | 126]) + struct.pack(">H", n)
    else:
        testa += bytes([0x80 | 127]) + struct.pack(">Q", n)
    maschera = os.urandom(4)
    return testa + maschera + bytes(b ^ maschera[i % 4] for i, b in enumerate(carico))


class Lettore:
    """Legge dal socket tenendo un buffer.

    Serve perche' leggendo le intestazioni della risposta si possono
    consumare anche i primi byte del frame successivo: senza buffer
    quei byte andrebbero persi e il frame risulterebbe disallineato.
    Sulla 8002 non si notava per via dei confini dei record TLS.
    """

    def __init__(self, s):
        self.s = s
        self.avanzi = b""

    def esatti(self, n):
        while len(self.avanzi) < n:
            p = self.s.recv(max(4096, n - len(self.avanzi)))
            if not p:
                raise ConnectionError("connessione chiusa")
            self.avanzi += p
        d, self.avanzi = self.avanzi[:n], self.avanzi[n:]
        return d

    def fino_a(self, fine):
        while fine not in self.avanzi:
            p = self.s.recv(4096)
            if not p:
                raise ConnectionError("connessione chiusa")
            self.avanzi += p
        i = self.avanzi.index(fine) + len(fine)
        d, self.avanzi = self.avanzi[:i], self.avanzi[i:]
        return d

    def frame(self):
        b1, b2 = self.esatti(2)
        opcode = b1 & 0x0F
        n = b2 & 0x7F
        if n == 126:
            n = struct.unpack(">H", self.esatti(2))[0]
        elif n == 127:
            n = struct.unpack(">Q", self.esatti(8))[0]
        carico = self.esatti(n) if n else b""
        return opcode, carico


def manda(comandi, ascolta=0.0, scadenza=None, eco=False):
    """Manda uno o piu' comandi. Con ascolta>0 resta in ascolto per
    quel tempo e restituisce gli eventi che la TV manda: e' l'unico
    modo di sapere qualcosa invece di indovinare."""
    if isinstance(comandi, dict):
        comandi = [comandi]
    nome = base64.b64encode(NOME.encode()).decode()
    percorso = "/api/v2/channels/samsung.remote.control?name=" + nome
    # Il token serve su ENTRAMBE le porte: sulla 8001 senza token
    # l'handshake passa ma la TV risponde ms.channel.unauthorized.
    token = re.sub(r"\D", "", os.environ.get("TV_TOKEN", "")) or leggi_token()
    if token:
        percorso += "&token=" + token
    chiave = base64.b64encode(os.urandom(16)).decode()

    grezzo = socket.create_connection((TV, PORTA), timeout=10)
    s = grezzo
    if PORTA == 8002:
        import ssl
        s = ssl._create_unverified_context().wrap_socket(grezzo, server_hostname=TV)

    try:
        s.sendall((
            f"GET {percorso} HTTP/1.1\r\n"
            f"Host: {TV}:{PORTA}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {chiave}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).encode())

        lettore = Lettore(s)
        prima = lettore.fino_a(b"\r\n\r\n").split(b"\r\n")[0].decode(errors="replace")
        if "101" not in prima:
            if "403" in prima:
                raise ConnectionError(
                    "handshake rifiutato: " + prima + "\n"
                    "  403 vuol dire che la TV ha questo dispositivo fra i NEGATI,\n"
                    "  non che non ti conosce. Due strade:\n"
                    "  1. presentati con un nome nuovo, cosi' ti richiede il permesso:\n"
                    f'       TV_NOME=iPhone python3 {mio_nome()} --tasto KEY_VOLUP\n'
                    "  2. sblocca il vecchio sulla TV: Impostazioni -> Generali ->\n"
                    "     Gestione dispositivi esterni -> Gestione connessione\n"
                    "     dispositivi -> Elenco dispositivi")
            raise ConnectionError("handshake rifiutato: " + prima)

        # La TV manda ms.channel.connect: aspettarlo evita di scrivere
        # prima che il canale sia pronto. Salto eventuali frame di
        # controllo (ping) che non sono testo.
        for _ in range(5):
            opcode, carico = lettore.frame()
            if opcode != 1:
                continue
            benvenuto = json.loads(carico.decode() or "{}")
            if benvenuto.get("event") == "ms.channel.connect":
                for c in comandi:
                    # una voce puo' essere ("pausa", secondi): la TV ha
                    # bisogno di tempo fra un tasto e il successivo, e
                    # riconnettersi per ogni tasto sarebbe lento e fragile
                    if isinstance(c, tuple) and c[0] == "pausa":
                        time.sleep(c[1])
                        continue
                    s.sendall(inquadra(json.dumps(c).encode()))
                nuovo = str(benvenuto.get("data", {}).get("token") or "")
                global ULTIMO_TOKEN
                ULTIMO_TOKEN = nuovo
                if nuovo and nuovo != token:
                    salva_token(nuovo)
                if ascolta <= 0:
                    return []
                # Ascolto: quello che la TV dice vale piu' di quello
                # che posso supporre io.
                #
                # `ascolta` e' quanto SILENZIO aspettare prima di
                # smettere: va bene per un ascolto breve dopo un
                # comando. `scadenza` invece e' un tempo TOTALE, e
                # serve a stare in ascolto a lungo senza dover
                # indovinare quando succedera' qualcosa. Con `eco` gli
                # eventi si vedono mentre arrivano, invece che tutti
                # alla fine.
                eventi = []
                fine = None if scadenza is None else time.time() + scadenza
                s.settimeout(min(2.0, ascolta) if fine else ascolta)
                try:
                    while True:
                        if fine and time.time() >= fine:
                            break
                        try:
                            op, car = lettore.frame()
                        except socket.timeout:
                            if fine:
                                continue     # silenzio, ma c'e' tempo
                            raise
                        if op != 1:
                            continue
                        try:
                            e = json.loads(car.decode())
                        except ValueError:
                            continue
                        eventi.append(e)
                        if eco:
                            nome = e.get("event") or "?"
                            dati = e.get("data")
                            print(f"  {time.strftime('%H:%M:%S')}  {nome}"
                                  + (f"   {dati}" if dati else ""),
                                  flush=True)
                except (OSError, ConnectionError):
                    pass
                return eventi
            raise ConnectionError("canale non pronto: " + str(benvenuto)[:120])
        raise ConnectionError("nessun evento di connessione dalla TV")
    finally:
        try:
            s.close()
        except Exception:
            pass


DOVE_TOKEN = None      # il file da cui il token e' stato letto


def salva_token(nuovo):
    """La TV emette un token nuovo quando accetti il popup, dentro
    l'evento ms.channel.connect. Se non lo si salva, la volta dopo ci
    si presenta col token vecchio e la TV richiede il permesso da
    capo: era esattamente il sintomo "me lo chiede ogni volta"."""
    # Eseguito al volo - il caso del telefono - non c'e' nessun file
    # da aggiornare, e scriverne uno sarebbe peggio: si e' gia' visto
    # cosa combina una copia salvata che non si aggiorna mai. Quindi
    # il token si DICE, e chi legge lo mette nell'app una volta.
    if not sono_un_file():
        print()
        print("  LA TV HA DATO UN TOKEN NUOVO:")
        print(f"      {nuovo}")
        print("  Mettilo nell'app: Opzioni -> Token della TV, salva, poi")
        print("  ricopia il comando e reincollalo nella Scorciatoia.")
        print("  Da quel momento la TV non chiede piu' il permesso.")
        return
    percorso = DOVE_TOKEN or os.path.join(mia_cartella(), "token.txt")
    try:
        with open(percorso, "w") as f:
            f.write(nuovo + "\n")
        print(f"  (token aggiornato in {percorso})")
    except OSError as e:
        print(f"  Non riesco a salvare il token nuovo in {percorso}: {e}")
        print(f"  Salvalo a mano:  echo {nuovo} > token.txt")


def leggi_token():
    """Il token, cercato in piu' posti: su a-Shell la cartella di
    lavoro non e' quella dello script, quindi un percorso solo non
    basta."""
    candidati = [
        os.path.join(mia_cartella(), "token.txt"),
        os.path.join(os.getcwd(), "token.txt"),
        os.path.expanduser("~/token.txt"),
        os.path.expanduser("~/Documents/token.txt"),
    ]
    for p in candidati:
        if os.path.exists(p):
            # Il token e' solo cifre: scarto tutto il resto. Un "%"
            # copiato per sbaglio dall'output di zsh, uno spazio o un
            # ritorno a capo facevano rispondere 403 alla TV, e da un
            # 403 nessuno indovina che il problema e' un carattere.
            t = re.sub(r"\D", "", open(p).read())
            if t:
                global DOVE_TOKEN
                DOVE_TOKEN = p
                return t
    print("Non trovo il token. L'ho cercato in:")
    for p in candidati:
        print("  " + p)
    print()
    print("Mettilo in uno di quei file, oppure passalo cosi':")
    print('  TV_TOKEN=12345678 python3 scrivi_telefono.py "the bear"')
    print()
    print("Si ottiene una volta sola dal computer, con:")
    print("  venv/bin/python3 tastiera.py collega")
    sys.exit(1)


def scrivi(testo, ascolta=1.2):
    # Il preparatorio lo manda anche la libreria prima del PRIMO
    # testo, e io non lo mandavo: senza, certe app potrebbero non
    # accorgersi dell'inserimento.
    preparatorio = {
        "method": "ms.channel.emit",
        "params": {"event": "custom.remote.textReceived", "to": "broadcast"},
    }
    inserimento = {
        "method": "ms.remote.control",
        "params": {
            "Cmd": base64.b64encode(testo.encode("utf-8")).decode(),
            "DataOfCmd": "base64",
            "TypeOfRemote": "SendInputString",
        },
    }
    return manda([preparatorio, inserimento], ascolta=ascolta)


def tasto(nome):
    return manda({
        "method": "ms.remote.control",
        "params": {"Cmd": "Click", "DataOfCmd": nome,
                   "Option": "false", "TypeOfRemote": "SendRemoteKey"},
    })


def cmd_tasto(nome):
    return {"method": "ms.remote.control",
            "params": {"Cmd": "Click", "DataOfCmd": nome,
                       "Option": "false", "TypeOfRemote": "SendRemoteKey"}}


def cmd_testo(testo):
    return {"method": "ms.remote.control",
            "params": {"Cmd": base64.b64encode(testo.encode("utf-8")).decode(),
                       "DataOfCmd": "base64",
                       "TypeOfRemote": "SendInputString"}}


# La strada per la ricerca globale della TV, contata col telecomando
# alla mano su questo modello: Home, quattro volte sinistra, OK.
# NON e' ricavabile dall'API: la TV non dice niente del suo schermo.
# Un aggiornamento del firmware che sposta la lente la rompe, e
# l'app non potra' accorgersene.
# I DUE OK servono entrambi: il primo apre la ricerca, il secondo
# mette a fuoco il campo di testo. Con uno solo la ricerca si apriva
# ma restava vuota, e la TV non mandava nessun evento IME.
# KEY_SEARCH apre la ricerca globale della TV DIRETTAMENTE.
#
# Vale la pena scrivere come ci siamo arrivati, perche' e' la
# differenza fra una cosa che funziona e una che sembra funzionare:
# prima navigavo a frecce (HOME + 4 volte sinistra + OK), e su otto
# tentativi riusciva una volta - perche' dipendeva da dove si trovava
# il cursore, e la TV non dice NIENTE del proprio schermo, quindi non
# c'era modo di saperlo. Con KEY_SEARCH non dipende da niente.
#
# Verificato due volte di fila: la TV risponde ms.remote.imeUpdate,
# che e' l'unica conferma vera che il testo sia entrato nel campo.
# L'OK dopo non serve: il campo prende il fuoco da solo.
# EXIT prima di SEARCH, e serve: dopo una ricerca la TV mostra i
# RISULTATI con la tastiera chiusa, e da quella schermata KEY_SEARCH
# ESCE invece di riaprire. Il sintomo era uno schema alternato -
# funziona, non funziona, funziona - con la TV che rispondeva
# ms.remote.imeEnd. Con EXIT davanti: tre su tre.
STRADA_RICERCA = os.environ.get("TV_STRADA", "EXIT,SEARCH")

TASTI_VERI = {"HOME": "KEY_HOME", "LEFT": "KEY_LEFT", "RIGHT": "KEY_RIGHT",
              "UP": "KEY_UP", "DOWN": "KEY_DOWN", "OK": "KEY_ENTER",
              "BACK": "KEY_RETURN", "EXIT": "KEY_EXIT"}


def cerca_adattiva(testo, dopo=""):
    """Scrive il titolo nella ricerca della TV, aprendola se serve.

    Prima PROVA a scrivere: se la ricerca e' gia' aperta funziona
    subito, e premere KEY_SEARCH a quel punto la CHIUDEREBBE - e'
    successo. Solo se il testo non arriva apre la ricerca e riprova.

    ms.remote.imeUpdate e' l'unico segnale di ritorno che la TV
    concede, e qui serve a decidere invece di indovinare.
    """
    def arrivato(eventi):
        return any("imeUpdate" in (e.get("event") or "") for e in eventi)

    eventi = scrivi(testo, ascolta=1.2)
    if arrivato(eventi):
        return eventi, "era gia' aperta"

    eventi = cerca(testo, dopo)
    if arrivato(eventi):
        return eventi, "l'ho aperta io"
    return eventi, "non riuscito"


def cerca(testo, dopo="", pausa=0.7):
    """Apre la ricerca della TV, scrive il titolo e, se indicato,
    percorre la strada fino al primo risultato."""
    seq = []
    for t in STRADA_RICERCA.split(","):
        t = t.strip().upper()
        if not t:
            continue
        seq.append(cmd_tasto(TASTI_VERI.get(t, t if t.startswith("KEY_") else "KEY_" + t)))
        seq.append(("pausa", pausa))
    # La ricerca deve finire di aprirsi E mettere a fuoco il campo.
    # Scrivere troppo presto e' la causa di "si apre ma resta vuota":
    # e' successo davvero con 1.2 secondi.
    seq.append(("pausa", float(os.environ.get("TV_ATTESA", "4.0"))))
    seq.append({"method": "ms.channel.emit",
                "params": {"event": "custom.remote.textReceived", "to": "broadcast"}})
    seq.append(cmd_testo(testo))
    for t in [x for x in dopo.split(",") if x.strip()]:
        t = t.strip().upper()
        seq.append(("pausa", pausa))
        seq.append(cmd_tasto(TASTI_VERI.get(t, t if t.startswith("KEY_") else "KEY_" + t)))
    return manda(seq, ascolta=1.0)


# --- scrivere DENTRO l'app, sulla sua tastiera --------------------------
#
# Netflix e NOW hanno una tastiera propria e il testo iniettato non
# arriva: provato col cursore nel campo, zero eventi IME, mentre la
# ricerca Samsung risponde imeUpdate. Pero' quella tastiera si naviga
# a frecce, e i percorsi si calcolano: li fa tastiere.py.

# Quanto aspettare fra un tasto e il successivo, misurato provando:
#   0,12s  Netflix PERDE pressioni. "the bear" e' uscito "nbear", e
#          nessun prefisso perso lo spiega: le saltate erano SPARSE,
#          che e' la firma del troppo veloce.
#   0,15s  REGGE l'alfabeto intero, 71 pressioni di fila, che e' la
#          sequenza piu' densa possibile - le lettere consecutive
#          stanno a un passo l'una dall'altra.
# Il margine e' sottile e una lettera persa NON SI VEDE, quindi resta
# regolabile: se un'app si rivela piu' lenta di Netflix, TV_PASSO.
PASSO = float(os.environ.get("TV_PASSO", "0.15"))
# Quanto aspettare che la tastiera COMPAIA dopo aver aperto la
# ricerca. Diverso dal passo: qui c'e' una schermata da disegnare.
ATTESA_TASTIERA = float(os.environ.get("TV_TASTIERA", "3"))
# La pausa fra i tasti di NAVIGAZIONE (i BACK della normalizzazione, i
# passi sulla barra). Separata dal passo di scrittura, e non piu'
# ricavata da quello: erano legate come PASSO*4, e abbassando il passo
# di scrittura da 0,3 a 0,15 la navigazione e' passata da 1,2s a 0,6s
# senza che fosse una decisione. Cambiare schermata dentro un'app
# costa piu' che spostarsi di una casella sulla tastiera, e le due
# cose non hanno motivo di muoversi insieme.
PASSO_NAVIGA = float(os.environ.get("TV_NAVIGA", "1.2"))

# Il token che la TV ha consegnato nell'ultimo collegamento. Serve a
# --token per poterlo DIRE: sul telefono non c'e' nessun file dove
# salvarlo, quindi l'unico modo di conservarlo e' che una persona lo
# legga e lo metta nelle Opzioni dell'app.
ULTIMO_TOKEN = ""
APP = os.environ.get("TV_APP", "netflix")


# Da dove prendere le disposizioni dei tasti. Si puo' puntare a un
# file locale con TV_TASTIERE, che serve alle prove e a fissare una
# versione se un giorno serve.
DA_DOVE = os.environ.get(
    "TV_TASTIERE", "https://mattiasereno.github.io/tv/tastiere.py")


# Questo script puo' girare anche SENZA essere un file su disco:
# eseguito al volo dentro python3 -c, __file__ non esiste e ogni suo
# uso esplode con NameError. Serve per la Scorciatoia iOS, dove il
# percorso dello script non si sa: si scarica e si esegue, e cosi' sul
# telefono non resta nessuna copia da aggiornare a mano.
def mia_cartella():
    """Dove sta questo script, o la cartella corrente se non e' un
    file."""
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        return os.getcwd()


def mio_nome():
    """Come chiamarmi nei messaggi di aiuto."""
    try:
        return os.path.basename(__file__)
    except NameError:
        return "scrivi_telefono.py"


def sono_un_file():
    """Se questo script e' un file su disco o e' stato eseguito al
    volo. Cambia dove cercare le disposizioni dei tasti, e non e' un
    dettaglio: vedi carica_tastiere."""
    try:
        __file__
        return True
    except NameError:
        return False


def carica_tastiere():
    """Le disposizioni dei tasti, da accanto allo script o dalla rete.

    LA REGOLA, e il perche' conta:

    Se questo script E' un file (sul computer, dentro il repo), le
    disposizioni si prendono da accanto: quello e' il sorgente, ed e'
    giusto che comandi.

    Se invece e' stato eseguito AL VOLO - il caso del telefono - le
    disposizioni si scaricano OGNI VOLTA e si tengono in memoria,
    senza mai salvarle su disco. Prima venivano scaricate solo se
    mancavano, e il risultato e' stato che il telefono ha continuato a
    usare un tastiere.py vecchio mentre il difetto era gia' corretto e
    pubblicato: la traccia dell'errore indicava righe che non
    esistevano piu'. Un file salvato una volta non si aggiorna mai, ed
    e' la stessa classe di guasti che il "niente file" doveva
    eliminare."""
    if sono_un_file():
        sys.path.insert(0, mia_cartella())
        try:
            import tastiere
            return tastiere
        except ImportError:
            pass          # manca accanto: si scarica come sul telefono

    if not DA_DOVE.startswith("http"):
        with open(DA_DOVE) as f:
            testo = f.read()
        return esegui_tastiere(testo)

    print("  prendo le disposizioni dei tasti da " + DA_DOVE)
    import urllib.request
    try:
        with urllib.request.urlopen(DA_DOVE, timeout=20) as risposta:
            testo = risposta.read().decode("utf-8")
    except Exception as e:
        raise ConnectionError(
            f"non riesco a scaricarle ({e.__class__.__name__}).\n"
            "  Serve internet. Oppure indica un file locale:\n"
            "     TV_TASTIERE=./tastiere.py ...")
    return esegui_tastiere(testo)


def esegui_tastiere(testo):
    """Trasforma il testo scaricato in un modulo, in memoria.

    Il controllo sul contenuto non e' una formalita': una pagina
    d'errore travestita da 200 diventerebbe un modulo vuoto, e il
    messaggio che ne segue parlerebbe di tutt'altro."""
    if "DISPOSIZIONI" not in testo or "def digita" not in testo:
        raise ConnectionError(
            "quello che e' arrivato non sono le disposizioni "
            f"({len(testo)} byte).\n  Forse l'indirizzo e' cambiato: "
            + DA_DOVE)
    import types
    modulo = types.ModuleType("tastiere")
    modulo.__file__ = DA_DOVE
    exec(compile(testo, DA_DOVE, "exec"), modulo.__dict__)
    sys.modules["tastiere"] = modulo
    return modulo


def separa_app(argomenti, tastiere):
    """Divide "netflix the bear" in ("netflix", "the bear").

    Si guarda la prima PAROLA e non il primo argomento, perche' la
    Scorciatoia iOS passa tutto in un pezzo unico.

    Sta in una funzione sola perche' ci sono tre comandi che devono
    capirlo allo STESSO modo: --apri che lo fa, --digita che scrive
    senza navigare, e --percorso che mostra cosa farebbe. Quando
    --percorso interpretava diversamente, mostrava un percorso che
    non era quello che sarebbe stato eseguito - e una prova a secco
    che non corrisponde all'esecuzione e' peggio di nessuna prova."""
    testo = " ".join(argomenti).strip()
    pezzi = testo.split(None, 1)
    primo = pezzi[0].lower() if pezzi else ""
    if primo in tastiere.DISPOSIZIONI and primo != "prova":
        return primo, (pezzi[1] if len(pezzi) > 1 else "")
    if primo in tastiere.SENZA_DISPOSIZIONE:
        raise ConnectionError(
            f'della tastiera di "{pezzi[0]}" non ho la disposizione, e '
            "non\n  la posso indovinare: la TV non dice niente di cosa "
            "ha sullo schermo.\n  Ce l'ho per: "
            + ", ".join(k for k in tastiere.DISPOSIZIONI if k != "prova"))
    return APP, testo


def digita_in_app(testo, app=None, azzera=0, passo=None):
    """Scrive il titolo sulla tastiera a schermo dell'app, a frecce.

    Tutto in UNA connessione: riaprirla per ogni tasto sarebbe lento e
    la TV a volte rifiuta le riconnessioni rapide.

    Da sapere: la TV non dice niente di cosa c'e' sullo schermo, quindi
    qui non c'e' NESSUN riscontro. Se il cursore non parte da dove la
    disposizione dice, il titolo esce sbagliato e nessuno se ne
    accorge. Per questo c'e' --percorso, che mostra i tasti senza
    mandarli."""
    tastiere = carica_tastiere()
    app = app or APP
    passo = PASSO if passo is None else passo
    if app not in tastiere.DISPOSIZIONI or app == "prova":
        raise ConnectionError(
            f'non ho la disposizione della tastiera di "{app}".\n'
            "  Ce l'ho per: "
            + ", ".join(k for k in tastiere.DISPOSIZIONI if k != "prova")
            + "\n  Ogni app ne ha una diversa e la TV non la sa dire:\n"
            "  serve guardarla e scriverla in tastiere.py.")

    tasti, saltati = tastiere.digita(testo, app, azzera=azzera)
    if not tasti:
        raise ConnectionError(f'"{testo}" non ha nemmeno un carattere '
                              "presente su quella tastiera.")

    seq = []
    prima = os.environ.get("TV_PRIMA", "")
    for t in [x.strip() for x in prima.split(",") if x.strip()]:
        seq.append(cmd_tasto(TASTI_VERI.get(t, t if t.startswith("KEY_")
                                            else "KEY_" + t)))
        seq.append(("pausa", passo))
    for t in tasti:
        seq.append(cmd_tasto(TASTI_VERI[t]))
        seq.append(("pausa", passo))

    manda(seq)
    return tasti, saltati


# I comandi che questa copia conosce. Serve a rifiutare un "--"
# sconosciuto invece di DIGITARLO sulla TV: e' successo con --ascolta
# su una copia vecchia del telefono, che non avendolo fra i comandi
# l'ha scritto nel campo di ricerca come se fosse un titolo.
COMANDI = ("--cerca", "--tasto", "--tasti", "--digita",
           "--percorso", "--apri", "--taratura", "--ascolta",
           "--token", "--testo")

PROTOCOLLO = """  MISURARE LA TASTIERA DI UN'APP CHE NON CONOSCO

  Non serve una foto: si fa scrivere all'app la propria tastiera
  dentro il suo campo di ricerca, e tu la leggi dalla TV.

  PRIMA DI TUTTO, la domanda che conta: quell'app usa la tastiera
  della TV o una sua? Si scopre SENZA mandare niente:
       python3 scrivi_telefono.py --ascolta
  poi apri la ricerca dell'app e mettiti nel campo. Se l'app usa
  l'IME di Tizen la TV annuncia imeStart da sola, e allora hai
  finito: il testo si scrive diretto, nessuna macro.
  Se in ascolto non arriva niente, l'app ha una tastiera sua, e
  allora si misura cosi', col cursore su una lettera:

    1.  --taratura angolo         va nell'angolo in alto a sinistra e
                                  scrive quel carattere
    2.  --taratura colonna        scende la prima colonna: dice i
                                  caratteri e quante righe ci sono
                                  (in fondo si ripetono: quello e' il
                                  bordo)
    3.  --taratura riga 1         percorre la seconda riga, 5 passi
        --taratura riga 1 8       ...o 8, se 5 non bastano
        --taratura riga 2  ...    e cosi' per ogni riga

  Fra una sonda e l'altra svuota il campo a mano, altrimenti i
  caratteri si sommano e non si capisce piu' niente.

  ATTENZIONE: a DESTRA di troppo alcune app escono dalla tastiera
  (Netflix porta al menu). Percio' si parte da 5 passi e si alza.
  A SINISTRA e in ALTO no: i passi in eccesso sbattono sul bordo e
  non fanno niente, ed e' proprio quello che rende l'angolo un punto
  di partenza certo senza sapere niente della griglia.
"""


def spiega_rete(e):
    """Perche' il collegamento alla TV non riesce, e cosa fare.

    In una funzione sola perche' serve a DUE rami diversi: gli errori
    del sistema arrivano come ConnectionRefusedError (che e' un
    ConnectionError) o come altri OSError, e dare la spiegazione solo
    a uno dei due lasciava l'altro con "[Errno 61] Connection
    refused" e nient'altro."""
    rifiutata = isinstance(e, ConnectionRefusedError)
    print(f"  Non completo il collegamento a {TV}:{PORTA} "
          f"({e.__class__.__name__}).")
    print()
    # Rifiutata e senza risposta sono due cose diverse, e dire le
    # stesse cause per entrambe manda a cercare nel posto sbagliato:
    # e' costato mezz'ora a cercare un problema di token mentre la TV
    # era semplicemente in standby.
    if rifiutata:
        print("  RIFIUTATA vuol dire che qualcuno ha risposto «no»: la TV")
        print("  e' in rete ma i suoi servizi sono spenti. Succede quando")
        print("  la TV e' in STANDBY - la rete resta viva per SmartThings,")
        print("  il resto no.")
        print("  Accendi la TV e riprova. Se e' accesa, l'indirizzo e' di")
        print("  qualcos'altro:")
        print(f'       TV_IP=192.168.0.x python3 {mio_nome()} "the bear"')
        return
    print("  NESSUNA RISPOSTA (non un rifiuto), e le cause sono altre:")
    print("  1. GUARDA LA TV: con un token non valido la TV non")
    print("     rifiuta, mostra il popup di autorizzazione e aspetta.")
    print("     Se c'e', accettalo. Se non lo accetti, e' questo timeout.")
    print("  2. Non sei sulla rete di casa.")
    print("  3. L'indirizzo e' cambiato. In quel caso:")
    print(f'       TV_IP=192.168.0.x python3 {mio_nome()} "the bear"')


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    try:
        if sys.argv[1] == "--cerca":
            testo = " ".join(sys.argv[2:])
            dopo = os.environ.get("TV_DOPO", "")
            print(f'  cerco "{testo}" sulla TV')
            eventi, come = cerca_adattiva(testo, dopo)
            if come != "non riuscito":
                print(f"  ({come})")
            nomi = [e.get("event") for e in eventi if e.get("event")]
            # imeUpdate e' la conferma che il campo ha ricevuto il testo:
            # e' l'unica cosa che la TV dice del proprio schermo.
            if any("imeUpdate" in n for n in nomi):
                print(f'  FATTO: "{testo}" e\' nel campo di ricerca della TV.')
            elif any("imeStart" in n for n in nomi):
                print("  La tastiera si e' aperta ma il testo non risulta arrivato.")
                print("  Prova ad allungare l'attesa:  TV_ATTESA=6 ...")
            elif nomi:
                print("  La TV ha risposto:", ", ".join(nomi))
                print("  Nessun evento di tastiera: la ricerca forse non si e' aperta.")
            else:
                print("  La TV non ha risposto niente: la ricerca non si e' aperta.")
                print(f"  La strada e' {STRADA_RICERCA}, si cambia con TV_STRADA.")
            return
        if sys.argv[1] == "--token":
            # Il token e' legato al NOME con cui ci si presenta: due
            # dispositivi con lo stesso nome si rubano il permesso a
            # vicenda, e il sintomo e' "me lo chiede ogni volta".
            # Percio' il telefono conviene che abbia un nome suo.
            usato = re.sub(r"\D", "", os.environ.get("TV_TOKEN", "")) \
                or leggi_token()
            print(f"  mi presento alla TV come «{NOME}»")
            print(f"  col token {'che hai passato' if usato else 'NESSUNO'}"
                  + (f" ({len(usato)} cifre)" if usato else ""))
            print("  Se la TV chiede il permesso, ACCETTALO adesso.")
            manda([], ascolta=1.0)
            print()
            if not ULTIMO_TOKEN:
                # Il collegamento e' riuscito (altrimenti manda()
                # avrebbe alzato un'eccezione), e la TV non ha
                # consegnato niente: vuol dire che ha ACCETTATO quello
                # che le abbiamo dato. E' la notizia buona, e prima
                # qui c'era scritto il contrario.
                print("  La TV ha accettato il token che hai passato, e non")
                print("  ne ha dato uno nuovo: va tutto bene, con questo")
                print(f"  nome («{NOME}») non chiedera' il permesso.")
                if not usato:
                    print("  Attenzione: non stavi passando nessun token, e")
                    print("  il collegamento e' riuscito comunque. Vuol dire")
                    print("  che la TV conosce gia' questo nome.")
                return
            if ULTIMO_TOKEN == usato:
                print(f"  TOKEN: {ULTIMO_TOKEN}")
                print("  E' lo stesso che stavi usando: la TV ti conosce e")
                print("  non dovrebbe chiedere piu' niente con questo nome.")
            else:
                print(f"  TOKEN NUOVO: {ULTIMO_TOKEN}")
                print("  Diverso da quello che stavi usando, ed e' questo il")
                print("  motivo per cui la TV chiedeva il permesso ogni volta.")
            print()
            print("  Mettilo nell'app: Opzioni -> Token della TV, salva,")
            print("  poi ricopia il comando (contiene il token) e reincollalo")
            print("  nella Scorciatoia.")
            return
        if sys.argv[1] == "--tasti":
            # Sonde corte scritte a mano, per misurare una tastiera un
            # fatto alla volta. Piu' onesto di una sonda lunga: ogni
            # pressione in piu' e' una supposizione in piu'.
            nomi = [x.strip().upper()
                    for x in " ".join(sys.argv[2:]).replace(" ", ",").split(",")
                    if x.strip()]
            if not nomi:
                print("  esempio:  --tasti DOWN,OK")
                print("  tasti:    " + " ".join(sorted(TASTI_VERI)))
                return
            ignoti = [n for n in nomi if n not in TASTI_VERI]
            if ignoti:
                raise ConnectionError(
                    "non conosco " + " ".join(ignoti) + "\n  conosco: "
                    + " ".join(sorted(TASTI_VERI)))
            seq = []
            for n in nomi:
                seq.append(cmd_tasto(TASTI_VERI[n]))
                seq.append(("pausa", PASSO))
            manda(seq)
            print("  mandate " + str(len(nomi)) + " pressioni: "
                  + ",".join(nomi))
            print("  Guarda la TV e dimmi cosa e' cambiato.")
            return
        if sys.argv[1] == "--ascolta":
            secondi = float(sys.argv[2]) if len(sys.argv) > 2 else 25.0
            print(f"  in ascolto per {secondi:.0f} secondi, senza mandare")
            print("  niente. Adesso apri la ricerca dell'app sulla TV e")
            print("  mettiti nel campo di testo.")
            # Non manda nessun comando: se l'app usa l'IME di Tizen, la
            # TV annuncia imeStart da sola appena il campo va a fuoco.
            # Cosi' si sa che tastiera ha un'app senza toccare lo
            # schermo, che e' l'unico modo di saperlo senza rischi.
            # La TV CHIUDE la connessione subito dopo una sessione
            # IME: e' successo il 28/09 alle 12:38:49, un secondo dopo
            # gli eventi, e l'ascolto e' morto dopo 20 secondi su 300
            # dicendo "3 eventi in tutto" come se avesse coperto tutto
            # il tempo. Un ascolto troncato spacciato per completo fa
            # concludere il falso: le app aperte dopo sembravano mute.
            # Percio' adesso si ricollega, e dice quanto ha coperto.
            inizio = time.time()
            fine = inizio + secondi
            eventi, cadute, giri = [], 0, 0
            while time.time() < fine:
                resto = fine - time.time()
                try:
                    eventi += manda([], ascolta=min(5.0, resto),
                                    scadenza=resto, eco=True)
                    giri += 1
                except OSError as e:
                    # Al PRIMO collegamento un errore va spiegato per
                    # bene (TV spenta, token da accettare, IP
                    # cambiato): ci pensa chi chiama, e quindi rilancio.
                    # A meta' ascolto invece basta dirlo e fermarsi.
                    if giri == 0:
                        raise
                    print(f"  {time.strftime('%H:%M:%S')}  non mi "
                          f"ricollego piu' ({e.__class__.__name__})",
                          flush=True)
                    break
                if time.time() < fine:
                    cadute += 1
                    print(f"  {time.strftime('%H:%M:%S')}  la TV ha chiuso, "
                          "mi ricollego", flush=True)
                    time.sleep(1.0)
            coperti = time.time() - inizio
            print(f"\n  ascoltati {coperti:.0f} secondi su {secondi:.0f}"
                  + (f", con {cadute} riconnessioni" if cadute else ""))
            if coperti < secondi * 0.9:
                print("  ATTENZIONE: l'ascolto e' finito prima del tempo.")
                print("  Quello che hai aperto DOPO non e' stato misurato.")
            if not eventi:
                # Il silenzio ha DUE spiegazioni e questo script non
                # puo' distinguerle: l'app ha una tastiera sua, oppure
                # nessuno e' andato nel campo. Dirne una sola sarebbe
                # una conclusione inventata.
                print("\n  La TV non ha detto niente in tutto quel tempo.")
                print("  Due spiegazioni, e da qui non si distinguono:")
                print("   - l'app ha una tastiera SUA (serve la taratura)")
                print("   - il campo di testo non e' andato a fuoco")
                print("  Prima di concludere, fai la PROVA IN BIANCO: un")
                print("  ascolto mentre apri la ricerca della TV (Home,")
                print("  poi la lente), che la tastiera di Tizen la usa")
                print("  di sicuro. Se anche quella tace, il problema e'")
                print("  nell'ascolto, non nell'app.")
                return
            print(f"  {len(eventi)} eventi in tutto.")
            nomi = " ".join(e.get("event") or "" for e in eventi)
            if "ime" in nomi.lower():
                print("\n  C'E' UN IME DI TIZEN: questa app usa la tastiera")
                print("  della TV, quindi il testo si scrive DIRETTO e non")
                print("  serve nessuna macro:")
                print('     python3 scrivi_telefono.py "the bear"')
            else:
                print("\n  Eventi si', ma nessuno di tastiera: l'app ha una")
                print("  tastiera sua. Serve la taratura.")
            return
        if sys.argv[1] == "--taratura":
            tastiere = carica_tastiere()
            fase = sys.argv[2] if len(sys.argv) > 2 else ""
            if fase not in ("angolo", "colonna", "riga"):
                print(PROTOCOLLO)
                return
            indice = int(sys.argv[3]) if len(sys.argv) > 3 else 0
            quanti = int(sys.argv[4]) if len(sys.argv) > 4 else (
                5 if fase == "riga" else 8)
            tasti = tastiere.taratura(fase, quanti=quanti, indice=indice)
            # La taratura non ha bisogno di nessuna disposizione: e'
            # proprio lo strumento per ricavarne una. Percio' non passa
            # da digita_in_app, che invece ne pretende una.
            seq = []
            for t in tasti:
                seq.append(cmd_tasto(TASTI_VERI[t]))
                seq.append(("pausa", PASSO))
            manda(seq)
            print(f"  sonda {fase}"
                  + (f" {indice}" if fase == "riga" else "")
                  + f": {len(tasti)} pressioni mandate.")
            print("  LEGGI IL CAMPO DI RICERCA SULLA TV e dimmi cosa c'e'")
            print("  scritto, carattere per carattere, spazi compresi.")
            if fase == "colonna":
                print("  In fondo i caratteri si RIPETONO: e' il bordo")
                print("  basso, e da quante ripetizioni ci sono si")
                print("  capisce quante righe ha la tastiera.")
            else:
                print("  Se la tastiera si e' chiusa o sei finito nel")
                print(f"  menu, sei andato a destra di troppo: rifai con")
                print(f"     --taratura riga {indice} {max(1, quanti - 2)}")
            print("  Poi svuota il campo a mano prima della prossima sonda.")
            return
        if sys.argv[1] == "--apri":
            # Il pezzo che chiude il cerchio: dall'app appena aperta
            # al titolo scritto nella sua ricerca.
            #
            # Il lancio dell'app NON sta qui e non ci puo' stare:
            # passa dal cloud SmartThings, e il token vive nel browser
            # del telefono. Sul WebSocket locale ed.apps.launch non fa
            # niente, provato. Quindi lancia l'app, e poi chiama
            # questo per la parte che solo la LAN puo' fare.
            tastiere = carica_tastiere()
            app, testo = separa_app(sys.argv[2:], tastiere)
            if not testo:
                print("  e cosa cerco? Esempio:")
                print(f'     python3 {mio_nome()} '
                      f'--apri "the bear"')
                return
            d = tastiere.DISPOSIZIONI[app]
            # La normalizzazione viene PRIMA della strada e va
            # sempre: l'app riprende lo stato dove era, e senza
            # riportarla a un punto noto contare i passi non serve a
            # niente. Su Netflix e' BACK ripetuto, che sul tasto Home
            # in alto sbatte senza fare danni.
            normalizza = list(d.get("normalizza", []))
            strada = [x.strip().upper() for x in
                      (os.environ.get("TV_PRIMA", "").split(",")
                       if os.environ.get("TV_PRIMA") else d.get("strada", []))
                      if x.strip()]
            if not strada:
                raise ConnectionError(
                    f"la strada dal lancio di {d['nome']} al campo di "
                    "ricerca non\n  e' ancora misurata, e senza quella "
                    "--apri scriverebbe alla cieca\n  dove capita. Si "
                    "misura guardando la TV, oppure si passa a mano:\n"
                    f'     TV_PRIMA=UP,LEFT,LEFT,OK python3 '
                    f'{mio_nome()} --apri "{testo}"\n'
                    "  Con la ricerca gia' aperta a mano, invece:\n"
                    f'     python3 {mio_nome()} '
                    f'--digita "{testo}"')
            attesa = float(os.environ.get("TV_CARICA", "6"))
            print(f'  aspetto {attesa:.0f}s che {d["nome"]} finisca di '
                  "caricare")
            azzera = int(os.environ.get("TV_AZZERA", "0"))
            tasti, saltati = tastiere.digita(testo, app, azzera=azzera)
            seq = [("pausa", attesa)]
            for t in normalizza + strada:
                seq.append(cmd_tasto(TASTI_VERI.get(
                    t, t if t.startswith("KEY_") else "KEY_" + t)))
                seq.append(("pausa", PASSO_NAVIGA))
            seq.append(("pausa", ATTESA_TASTIERA))
            for t in tasti:
                seq.append(cmd_tasto(TASTI_VERI[t]))
                seq.append(("pausa", PASSO))
            manda(seq)
            print(f"  normalizzo: {','.join(normalizza)}")
            print(f"  strada: {','.join(strada)}")
            print(f'  poi "{testo}": {len(tasti)} pressioni')
            print("  Guarda la TV: e' l'unico riscontro che esiste.")
            if saltati:
                print("  fuori tastiera, saltati: " + "".join(saltati))
            return
        if sys.argv[1] in ("--digita", "--percorso"):
            solo_vedere = sys.argv[1] == "--percorso"
            tastiere = carica_tastiere()
            app, testo = separa_app(sys.argv[2:], tastiere)
            if not testo:
                print("  e cosa scrivo? Esempio:")
                print(f'     python3 {mio_nome()} '
                      f'{sys.argv[1]} "the bear"')
                return
            azzera = int(os.environ.get("TV_AZZERA", "0"))
            if solo_vedere:
                tasti, saltati = tastiere.digita(testo, app, azzera=azzera)
                print(f'  "{testo}" su {tastiere.DISPOSIZIONI[app]["nome"]}: '
                      f"{len(tasti)} pressioni")
                print("  " + ",".join(tasti))
                print(f"  scriverebbe: {tastiere.simula(tasti, app)!r}")
            else:
                print(f'  scrivo "{testo}" sulla tastiera di '
                      f'{tastiere.DISPOSIZIONI[app]["nome"]}')
                tasti, saltati = digita_in_app(testo, app, azzera=azzera)
                print(f"  mandate {len(tasti)} pressioni.")
                print("  Guarda la TV: e' l'unico riscontro che esiste.")
                print("  Se il campo non era a fuoco, o il cursore non era")
                print("  sulla prima lettera, il testo esce sbagliato.")
            if saltati:
                print("  fuori tastiera, saltati: " + "".join(saltati))
            return
        if OPZIONI_IGNOTE:
            raise ConnectionError(
                "non conosco l'opzione " + " ".join(OPZIONI_IGNOTE) + "\n"
                "  Le opzioni si scrivono --chiave=valore, e sono:\n"
                "     --nome= --token= --ip= --porta= --passo= --naviga=\n"
                "     --carica= --tastiera= --azzera= --app= --tastiere=")
        if sys.argv[1].startswith("-") and sys.argv[1] not in COMANDI:
            raise ConnectionError(
                f'"{sys.argv[1]}" non e\' un comando che conosco, e non lo\n'
                "  scrivo sulla TV per sicurezza: un comando digitato per\n"
                "  sbaglio nel campo di ricerca non si vede arrivare.\n"
                "  Questa copia conosce: " + " ".join(COMANDI) + "\n"
                "  Se quel comando dovrebbe esistere, la copia che hai e'\n"
                "  vecchia. Riscaricala:\n"
                "     curl -O https://mattiasereno.github.io/tv/"
                + mio_nome() + "\n"
                "     curl -O https://mattiasereno.github.io/tv/tastiere.py\n"
                "  Per scrivere davvero un testo che comincia per meno:\n"
                f'     python3 {mio_nome()} --testo '
                f'"{sys.argv[1]}"')
        if sys.argv[1] == "--tasto":
            tasto(sys.argv[2])
            print(f"  mandato {sys.argv[2]}")
        else:
            if sys.argv[1] == "--testo":
                del sys.argv[1]
            testo = " ".join(sys.argv[1:])
            eventi = scrivi(testo)
            print(f'  mandato "{testo}"')
            nomi = [e.get("event") for e in eventi if e.get("event")]
            if nomi:
                print("  la TV ha risposto:", ", ".join(nomi))
            ime = [n for n in nomi if "ime" in n.lower()]
            if ime:
                print("  c'e' una tastiera aperta sulla TV: l'inserimento e' arrivato.")
            else:
                print("  La TV non ha segnalato nessuna tastiera aperta.")
                print("  Questo inserimento funziona solo dove la TV usa la PROPRIA")
                print("  tastiera: la sua ricerca globale, il browser, e alcune app.")
                print("  Netflix usa una tastiera sua e non lo riceve.")
                print("  Prova sulla ricerca della TV: tasto Home, poi la lente.")
    except ConnectionError as e:
        # Una traccia di stack su un telefono non aiuta nessuno.
        #
        # ConnectionError e' sia la MIA (con un messaggio scritto per
        # essere letto) sia quella del sistema operativo, che arriva
        # come "[Errno 61] Connection refused" - in inglese e senza
        # dire cosa fare. Le prime si stampano, le seconde vanno
        # tradotte, e il telefono e' proprio il posto dove un
        # messaggio criptico non si puo' permettere.
        if isinstance(e, (ConnectionRefusedError, ConnectionResetError,
                          ConnectionAbortedError, BrokenPipeError)):
            spiega_rete(e)
        print("  " + str(e))
        if "unauthorized" in str(e):
            print("  Il token non e' valido per questa TV. Rifallo dal computer:")
            print("    venv/bin/python3 tastiera.py collega")
        sys.exit(1)
    except OSError as e:
        spiega_rete(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
