#!/usr/bin/env python3
"""
VIVO: stampa l'ora ogni secondo. Nient'altro.

Serve a rispondere a UNA domanda, e non ce n'e' una piu' importante
per il telecomando del Fire Stick:

    iOS lascia girare a-Shell quando esci dall'app?

Se SI', l'app puo' diventare un telecomando vero: a-Shell tiene
aperto il collegamento ADB e le frecce costano millisecondi invece di
due secondi. Se NO, non c'e' strada, e restano i quattro tasti da un
tocco.

Si lancia cosi', e NON vuole argomenti - la forma identica a quella
che funziona nella Scorciatoia:

    python3 -c "import urllib.request as u;exec(u.urlopen('https://mattiasereno.github.io/tv/vivo.py').read())"

Poi: vai via da a-Shell, resta fuori un minuto, torna e guarda.
Ore continue = ha girato. Un buco = iOS lo ha sospeso.

PERCHE' SENZA ARGOMENTI: la prima versione era `ponte.py --vivo`, e
su a-Shell non ha stampato niente. Un argomento dietro a `python3 -c`
passa da due interpreti prima di arrivare al codice, e ognuno dei due
puo' mangiarselo. Uno script per ogni mestiere costa un file e toglie
un modo di sbagliare.

E PERCHE' TUTTO CON flush: se l'uscita e' a blocchi, le righe
restano nel cuscinetto e sullo schermo non compare niente - che e'
esattamente il sintomo visto.
"""
import sys
import time


def di(testo):
    sys.stdout.write(testo + "\n")
    sys.stdout.flush()


di("")
di("  VIVO - stampo l'ora ogni secondo.")
di("")
di("   1. VAI VIA da a-Shell (schermata Home, o un'altra app)")
di("   2. resta fuori UN MINUTO")
di("   3. TORNA qui e guarda le righe")
di("")
di("  ore continue  -> a-Shell ha girato in sottofondo: si puo' fare")
di("  un buco       -> iOS lo ha sospeso: non c'e' strada")
di("")
di("  (per fermarlo: Ctrl-C)")
di("")

n = 0
while True:
    n += 1
    di("  %s   riga %d" % (time.strftime("%H:%M:%S"), n))
    time.sleep(1)
