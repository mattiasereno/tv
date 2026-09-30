#!/usr/bin/env python3
"""
BATTITO: il telefono scrive un'ora al secondo SUL FIRE STICK.

Perche' cosi', dopo tre tentativi falliti:
  1. stampare a schermo non serve: a-Shell, sul telefono, NON MOSTRA
     l'uscita dei comandi lanciati a mano - nemmeno print(123).
  2. bussare al Mac non serve: il firewall del Mac blocca le
     connessioni in arrivo, e non e' roba da spegnere per una prova.
  3. il Fire Stick invece il telefono lo raggiunge GIA' - e' la
     strada che fa funzionare la ricerca dei titoli. Quindi il
     testimone e' lui: il telefono gli scrive dentro un file, e il
     file si legge dal Mac.

E questa prova e' anche il PROTOTIPO del ponte: apre UN collegamento
ADB e lo tiene aperto per novanta secondi, scrivendo una riga al
secondo. Se regge mentre il telefono e' su un'altra app, il
telecomando vero si puo' fare - perche' e' esattamente quello che
dovrebbe fare.

    python3 -c "import urllib.request as u;exec(u.urlopen('https://mattiasereno.github.io/tv/battito.py').read())"
"""
import time
import urllib.request

IP = "192.168.0.121"
DOVE = "/sdcard/battito.txt"
GIRI = 90

# firestick.py fa il mestiere difficile: ADB da zero.
_f = {}
exec(urllib.request.urlopen(
    "https://mattiasereno.github.io/tv/firestick.py").read(), _f)

a, chi = _f["collega"](IP, "tvproject", 5555, b"tvproject@telefono",
                       timeout=60)

# si riparte da zero a ogni prova
_f["comanda"](a, "rm -f " + DOVE, 15)

for n in range(1, GIRI + 1):
    try:
        _f["comanda"](a, "echo $(date +%H:%M:%S) riga " + str(n) +
                      " >> " + DOVE, 15)
    except Exception:
        # il collegamento e' caduto: da qui in poi non scrive piu',
        # e il file dira' fino a dove e' arrivato
        break
    time.sleep(1)
