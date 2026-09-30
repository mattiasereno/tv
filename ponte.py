#!/usr/bin/env python3
"""
PONTE: resta in piedi, tiene aperto il collegamento col Fire Stick, e
scrive un'ora al secondo - sullo schermo E sul Fire Stick.

PERCHE' QUESTA FORMA, dopo sei tentativi a vuoto. Su a-Shell, di
tutto quello che ho provato ha stampato SOLO la versione precedente
di questo file. La differenza non era il codice: era che questo NON
FINISCE. Un comando che termina subito non fa vedere la sua uscita -
ecco perche' perfino `python3 -c "print(123)"` sembrava muto.

Quindi: la misura sta dentro un programma che resta in piedi.

A COSA SERVE: sapere se iOS lascia girare a-Shell quando esci
dall'app. Se si', l'app puo' diventare un telecomando vero - il
collegamento ADB resta aperto e le frecce costano millisecondi
invece di due secondi. Se no, non c'e' strada.

COME SI LEGGE: le righe sullo schermo e il file sul Fire Stick
raccontano la stessa cosa da due lati. Se le ore sono continue, ha
girato anche in sottofondo. Se c'e' un buco, iOS l'ha fermato.

    python3 -c "import urllib.request as u;exec(u.urlopen('https://mattiasereno.github.io/tv/ponte.py').read())"

Poi: resta qui dieci secondi, esci un minuto, torna e guarda.
"""
import sys
import time
import urllib.request

IP = "192.168.0.121"
DOVE = "/sdcard/battito.txt"


def di(t):
    sys.stdout.write(t + "\n")
    sys.stdout.flush()


di("")
di("  PONTE - resto in piedi e scrivo un'ora al secondo.")
di("")
di("  Mi collego al Fire Stick...")

# firestick.py fa il mestiere difficile: ADB da zero.
_f = {}
exec(urllib.request.urlopen(
    "https://mattiasereno.github.io/tv/firestick.py").read(), _f)

try:
    a, chi = _f["collega"](IP, "tvproject", 5555, b"tvproject@telefono",
                           timeout=20)
except Exception as e:
    di("  NON MI COLLEGO: %s" % e)
    di("  (il Fire Stick e' accesso? il Debug ADB e' attivo?)")
    di("")
    di("  Resto qui in piedi cosi' puoi leggere. Ctrl-C per uscire.")
    while True:
        time.sleep(3600)

di("  collegato: %s" % chi[:40])
_f["comanda"](a, "echo PARTITO $(date +%H:%M:%S) > " + DOVE, 15)
di("")
di("  ADESSO: resta qui 10 secondi, poi ESCI un minuto, poi TORNA.")
di("")

n = 0
while True:
    n += 1
    ora = time.strftime("%H:%M:%S")
    try:
        _f["comanda"](a, "echo " + ora + " riga " + str(n) + " >> " + DOVE, 15)
        di("  %s   riga %d" % (ora, n))
    except Exception as e:
        di("  %s   CADUTO al giro %d: %s" % (ora, n, e))
        di("  Resto qui in piedi. Ctrl-C per uscire.")
        while True:
            time.sleep(3600)
    time.sleep(1)
