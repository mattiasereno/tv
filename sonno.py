#!/usr/bin/env python3
"""
SONNO: iOS sospende a-Shell quando esci dall'app?

E' la domanda che decide se il telecomando del Fire Stick si puo'
fare. Se a-Shell continua a girare in sottofondo, puo' tenere aperto
il collegamento ADB e le frecce costano millisecondi. Se viene
sospeso, no: e ogni tasto resta un viaggio da due secondi.

COME MISURA, e perche' cosi': dorme un secondo per volta, sessanta
volte, e si SEGNA l'ora di ogni giro. Non stampa niente nel
frattempo. Alla fine stampa il verdetto tutto insieme.

Perche' non stampa durante: le due versioni precedenti stampavano
ogni secondo e su a-Shell NON SI VEDEVA NIENTE, nemmeno con l'app in
primo piano. Probabile che a-Shell ridisegni lo schermo quando il
comando finisce, non mentre gira. Questa versione non dipende da
come e' fatto quel terminale: conta gli orologi, e parla alla fine.

Il trucco: se iOS sospende il processo, il tempo VERO passa ma i
giri no. Sessanta giri da un secondo devono durare sessanta secondi.
Se ne durano centoventi, sessanta li ha passati sospeso.

    python3 -c "import urllib.request as u;exec(u.urlopen('https://mattiasereno.github.io/tv/sonno.py').read())"
"""
import sys
import time

GIRI = 60


def di(testo):
    sys.stdout.write(testo + "\n")
    sys.stdout.flush()


di("")
di("  SONNO - misuro per un minuto, poi parlo.")
di("")
di("   ADESSO vai via da a-Shell e resta fuori un minuto.")
di("   Poi torna: trovi il verdetto scritto qui.")
di("")

partenza = time.time()
ore = [partenza]
for _ in range(GIRI):
    time.sleep(1)
    ore.append(time.time())

durata = ore[-1] - partenza
buchi = [(ore[i + 1] - ore[i]) for i in range(len(ore) - 1)]
buco = max(buchi)
quando = buchi.index(buco)

di("  ---------------------------------------------")
di("  giri fatti:        %d" % GIRI)
di("  dovevano durare:   %d s" % GIRI)
di("  sono durati:       %.1f s" % durata)
di("  pausa piu' lunga:  %.1f s  (al giro %d)" % (buco, quando + 1))
di("  ---------------------------------------------")
di("")

# Tre secondi di margine: un telefono che fa altro puo' allungare un
# sleep di qualche decimo, non di secondi.
if buco < 3:
    di("  A-SHELL HA GIRATO SENZA INTERRUZIONI.")
    di("  Se sei stato fuori un minuto, iOS lo lascia vivo in")
    di("  sottofondo: IL TELECOMANDO SI PUO' FARE.")
else:
    di("  A-SHELL E' STATO FERMATO per %.0f secondi." % buco)
    di("  iOS lo sospende quando esci: non puo' tenere aperto il")
    di("  collegamento, e il telecomando dall'app non si fa.")
di("")
di("  (se NON sei uscito da a-Shell, questa misura non dice niente:")
di("   rilancia e vai via per davvero)")
