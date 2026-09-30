#!/usr/bin/env python3
"""
IL PONTE: un piccolo server dentro a-Shell, sul telefono.

A cosa serve, e perche' non e' un dettaglio. Una pagina web NON puo'
aprire una socket TCP, quindi non puo' parlare ADB col Fire Stick.
L'unico modo perche' l'app diventi un telecomando vero - frecce
istantanee invece di due secondi per tasto - e' che qualcuno tenga
aperto il collegamento ADB e prenda ordini via HTTP.

a-Shell lo puo' fare. La domanda che decide tutto e' un'altra:

    iOS lascia vivo a-Shell mentre Safari e' in primo piano?

Se SI', questo file diventa il ponte vero e il telecomando si fa.
Se NO, non c'e' strada e si resta ai quattro tasti da un tocco.

LA PROVA BUONA E' SENZA BROWSER. Su iOS Safari si rifiuta di aprire
un http:// semplice (verificato da chi la usa), quindi la pagina qui
sotto non misura niente. Ma la domanda non riguarda Safari, riguarda
a-Shell: basta stampare l'ora ogni secondo, andare via, tornare, e
guardare se ci sono buchi.

    python3 -c "...scarica...".read()) --vivo

QUESTA, con la pagina, e' la versione col browser:

    python3 -c "import urllib.request as u;exec(u.urlopen('https://mattiasereno.github.io/tv/ponte.py').read())"

poi si lascia a-Shell APERTO, si passa a Safari e si apre
http://127.0.0.1:8123 . La pagina si interroga da sola ogni secondo e
dice da quanto tempo il ponte non risponde piu'. Non serve
ricaricare: basta guardarla.

Nota sul mixed content: questa pagina e' servita dal ponte stesso, in
http, quindi parla con 127.0.0.1 nella STESSA origine. Nessun blocco
https->http, che e' il muro contro cui muore ogni altra idea.
"""
import http.server
import socketserver
import time

PORTA = 8123
PARTITO = time.time()
CHIESTE = [0]

PAGINA = """<!doctype html><html lang=it><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Ponte</title>
<style>
 body{margin:0;padding:28px 20px;background:#0E1519;color:#E8EEF2;
      font:17px/1.5 -apple-system,system-ui,sans-serif}
 h1{font-size:22px;margin:0 0 18px}
 .q{padding:16px;border-radius:14px;background:#16222D;
    border:1px solid #24353F;margin:0 0 12px}
 .n{font-size:34px;font-weight:700;margin:0}
 .e{color:#8CA2B2;font-size:14px;margin:4px 0 0}
 .si{color:#7BD88F} .no{color:#E8798A}
</style>
<h1>Il ponte e&#39; vivo?</h1>
<div class=q><p class=n id=stato>controllo&hellip;</p>
<p class=e id=dettaglio></p></div>
<div class=q><p class=e>Risposte ricevute: <b id=quante>0</b><br>
Ultima risposta: <b id=quando>mai</b><br>
Buche (nessuna risposta): <b id=buche>0</b></p></div>
<div class=q><p class=e>Lascia a-Shell aperto, resta qui un minuto e
guarda. Se il numero delle risposte continua a salire, iOS lascia
vivo a-Shell e il telecomando si puo&#39; fare. Se si ferma, no.</p></div>
<script>
let ok=0,ko=0,ultima=null;
const $=i=>document.getElementById(i);
async function batti(){
  try{
    const r=await fetch("/vivo?t="+Date.now(),{cache:"no-store"});
    if(!r.ok) throw new Error(r.status);
    const d=await r.json();
    ok++; ultima=Date.now();
    $("stato").textContent="VIVO"; $("stato").className="n si";
    $("dettaglio").textContent="in piedi da "+d.da+" s, "+d.chieste+
      " richieste servite";
  }catch(e){
    ko++;
    $("stato").textContent="NON RISPONDE"; $("stato").className="n no";
    $("dettaglio").textContent=String(e.message||e);
  }
  $("quante").textContent=ok; $("buche").textContent=ko;
  $("quando").textContent=ultima
    ? Math.round((Date.now()-ultima)/1000)+" s fa" : "mai";
}
batti(); setInterval(batti,1000);
</script>
"""


class Mano(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _manda(self, corpo, tipo):
        b = corpo.encode()
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        CHIESTE[0] += 1
        if self.path.startswith("/vivo"):
            self._manda(
                '{"vivo":true,"da":%d,"chieste":%d}'
                % (int(time.time() - PARTITO), CHIESTE[0]),
                "application/json")
            return
        self._manda(PAGINA, "text/html; charset=utf-8")


# Un server che non si blocca se una richiesta resta appesa: con
# quello a thread singolo, una pagina che interroga ogni secondo
# basta a ingolfarlo.
class Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True


def batte_il_tempo():
    """La prova SENZA browser, ed e' la prova giusta.

    Su iOS Safari si rifiuta di aprire un http:// semplice, quindi la
    pagina del ponte non serve a misurare niente. Ma la domanda non
    riguarda Safari: riguarda a-Shell. Basta stampare l'ora ogni
    secondo, andare via, tornare, e guardare se ci sono BUCHI.

    Nessuna rete, nessun browser, nessun mixed content: solo
    l'orologio e il fatto che questo processo stia girando o no."""
    print("  Stampo l'ora ogni secondo. Adesso:")
    print("   1. VAI VIA da a-Shell - apri Safari, o la schermata Home")
    print("   2. resta fuori un minuto buono")
    print("   3. TORNA qui e guarda le righe")
    print()
    print("  Se le ore sono continue, a-Shell ha continuato a girare in")
    print("  sottofondo, e il telecomando vero si puo' fare.")
    print("  Se c'e' un BUCO - salta da 10:00:05 a 10:01:05 - iOS lo ha")
    print("  sospeso, e non c'e' strada.")
    print()
    n = 0
    while True:
        n += 1
        print("  %s   riga %d" % (time.strftime("%H:%M:%S"), n), flush=True)
        time.sleep(1)


if __name__ == "__main__" or True:
    import sys
    if "--vivo" in " ".join(sys.argv):
        batte_il_tempo()
    else:
        print("  ponte in ascolto su http://127.0.0.1:%d" % PORTA)
        print("  LASCIA a-Shell APERTO, passa a Safari e apri "
              "quell'indirizzo.")
        print("  Se Safari rifiuta l'http, usa invece la prova senza")
        print("  browser:  ...read()) --vivo")
        print("  Per fermarlo: Ctrl-C, oppure chiudi a-Shell.")
        Server(("127.0.0.1", PORTA), Mano).serve_forever()
