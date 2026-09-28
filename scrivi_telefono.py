#!/usr/bin/env python3
"""
Scrive testo sulla TV usando SOLO la libreria standard di Python.

    python3 scrivi_telefono.py "the bear"
    python3 scrivi_telefono.py --tasto KEY_HOME

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
"""

import base64
import json
import os
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
NOME = "TVProject"


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


def manda(comando):
    nome = base64.b64encode(NOME.encode()).decode()
    percorso = "/api/v2/channels/samsung.remote.control?name=" + nome
    # Il token serve su ENTRAMBE le porte: sulla 8001 senza token
    # l'handshake passa ma la TV risponde ms.channel.unauthorized.
    token = os.environ.get("TV_TOKEN") or leggi_token()
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
                s.sendall(inquadra(json.dumps(comando).encode()))
                return benvenuto.get("data", {}).get("token")
            raise ConnectionError("canale non pronto: " + str(benvenuto)[:120])
        raise ConnectionError("nessun evento di connessione dalla TV")
    finally:
        try:
            s.close()
        except Exception:
            pass


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
            t = open(p).read().strip()
            if t:
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


def scrivi(testo):
    return manda({
        "method": "ms.remote.control",
        "params": {
            "Cmd": base64.b64encode(testo.encode("utf-8")).decode(),
            "DataOfCmd": "base64",
            "TypeOfRemote": "SendInputString",
        },
    })


def tasto(nome):
    return manda({
        "method": "ms.remote.control",
        "params": {"Cmd": "Click", "DataOfCmd": nome,
                   "Option": "false", "TypeOfRemote": "SendRemoteKey"},
    })


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    try:
        if sys.argv[1] == "--tasto":
            tasto(sys.argv[2])
            print(f"  mandato {sys.argv[2]}")
        else:
            testo = " ".join(sys.argv[1:])
            scrivi(testo)
            print(f'  scritto "{testo}"')
            print("  Se sulla TV non c'era un campo a fuoco, e' stato ignorato.")
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
