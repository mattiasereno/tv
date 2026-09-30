#!/usr/bin/env python3
"""
BATTITO: bussa al Mac una volta al secondo, per un minuto e mezzo.

Serve perche' a-Shell, sul telefono, NON MOSTRA l'uscita dei comandi
lanciati a mano: nemmeno `python3 -c "print(123)"` stampa qualcosa.
Verificato da chi la usa. Quindi ogni prova che dipende dallo schermo
di a-Shell non misura niente.

Allora la misura la legge l'altro capo: questo script bussa a un
server sul Mac, e il Mac scrive l'ora di ogni colpo. Dopo, il file
dei colpi si guarda dal Mac.

DUE RISPOSTE IN UNA:
  1. se arriva anche UN solo colpo -> il comando gira, ed e' solo
     l'uscita che non si vede
  2. se i colpi continuano mentre il telefono e' su un'altra app ->
     iOS lascia vivo a-Shell, e il telecomando del Fire Stick si
     puo' fare. Se si fermano quando esci e riprendono quando torni,
     no.

L'indirizzo del Mac e' scritto dentro di proposito: gli argomenti
dietro a `python3 -c` passano da due interpreti e almeno uno se li
mangia - e' il motivo per cui `--vivo` non ha funzionato.

    python3 -c "import urllib.request as u;exec(u.urlopen('https://mattiasereno.github.io/tv/battito.py').read())"
"""
import time
import urllib.request

DOVE = "http://192.168.0.98:8123/b"
GIRI = 90

for n in range(1, GIRI + 1):
    try:
        urllib.request.urlopen(DOVE + "?n=%d" % n, timeout=3).read()
    except Exception:
        pass          # rete via: si riprova al giro dopo
    time.sleep(1)
