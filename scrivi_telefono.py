#!/usr/bin/env python3
"""
Scrive testo sulla TV usando SOLO la libreria standard di Python.

    python3 scrivi_telefono.py "the bear"
    python3 scrivi_telefono.py --tasto KEY_HOME
    python3 scrivi_telefono.py --digita "the bear"      dentro l'app
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


def manda(comandi, ascolta=0.0):
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
                    f'       TV_NOME=iPhone python3 {os.path.basename(__file__)} --tasto KEY_VOLUP\n'
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
                import time
                for c in comandi:
                    # una voce puo' essere ("pausa", secondi): la TV ha
                    # bisogno di tempo fra un tasto e il successivo, e
                    # riconnettersi per ogni tasto sarebbe lento e fragile
                    if isinstance(c, tuple) and c[0] == "pausa":
                        time.sleep(c[1])
                        continue
                    s.sendall(inquadra(json.dumps(c).encode()))
                nuovo = str(benvenuto.get("data", {}).get("token") or "")
                if nuovo and nuovo != token:
                    salva_token(nuovo)
                if ascolta <= 0:
                    return []
                # Ascolto: quello che la TV dice vale piu' di quello
                # che posso supporre io.
                eventi = []
                s.settimeout(ascolta)
                try:
                    while True:
                        op, car = lettore.frame()
                        if op != 1:
                            continue
                        try:
                            eventi.append(json.loads(car.decode()))
                        except ValueError:
                            pass
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
    percorso = DOVE_TOKEN or os.path.join(os.getcwd(), "token.txt")
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
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "token.txt"),
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

PASSO = float(os.environ.get("TV_PASSO", "0.12"))
APP = os.environ.get("TV_APP", "netflix")


def carica_tastiere():
    """tastiere.py sta accanto a questo script, non nella cartella da
    cui lo lanci: su a-Shell si parte sempre dalla home."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import tastiere
    except ImportError:
        raise ConnectionError(
            "manca tastiere.py, che contiene le disposizioni dei tasti.\n"
            "  Va scaricato accanto a questo script:\n"
            "     curl -O https://mattiasereno.github.io/tv/tastiere.py")
    return tastiere


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
        if sys.argv[1] in ("--digita", "--percorso"):
            solo_vedere = sys.argv[1] == "--percorso"
            resto = sys.argv[2:]
            app = APP
            tastiere = carica_tastiere()
            if resto and resto[0] in tastiere.DISPOSIZIONI:
                app, resto = resto[0], resto[1:]
            elif resto and resto[0].lower() in tastiere.SENZA_DISPOSIZIONE:
                # senza questo controllo "--digita now the bear"
                # scriverebbe "now the bear" su Netflix, in silenzio
                raise ConnectionError(
                    f'della tastiera di "{resto[0]}" non ho la disposizione, '
                    "e non la\n  posso indovinare: la TV non dice niente di "
                    "cosa ha sullo schermo.\n  Ce l'ho per: "
                    + ", ".join(k for k in tastiere.DISPOSIZIONI
                                if k != "prova"))
            testo = " ".join(resto)
            if not testo:
                print("  e cosa scrivo? Esempio:")
                print(f'     python3 {os.path.basename(__file__)} '
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
        if sys.argv[1] == "--tasto":
            tasto(sys.argv[2])
            print(f"  mandato {sys.argv[2]}")
        else:
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
        print("  " + str(e))
        if "unauthorized" in str(e):
            print("  Il token non e' valido per questa TV. Rifallo dal computer:")
            print("    venv/bin/python3 tastiera.py collega")
        sys.exit(1)
    except OSError as e:
        nome = os.path.basename(__file__)
        print(f"  Non completo il collegamento a {TV}:{PORTA} ({e.__class__.__name__}).")
        print()
        print("  Tre cause possibili, in ordine di probabilita':")
        print("  1. GUARDA LA TV: con un token non valido la TV non")
        print("     rifiuta, mostra il popup di autorizzazione e aspetta.")
        print("     Se c'e', accettalo. Se non lo accetti, e' questo timeout.")
        print("  2. Non sei sulla rete di casa, o la TV e' spenta.")
        print(f"  3. L'indirizzo e' cambiato. In quel caso:")
        print(f'       TV_IP=192.168.0.x python3 {nome} "the bear"')
        sys.exit(1)


if __name__ == "__main__":
    main()
