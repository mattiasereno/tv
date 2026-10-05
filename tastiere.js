// Il percorso sulle tastiere a schermo, in JavaScript.
//
// E' la traduzione di tastiere.py, e vive qui perche' e' LOGICA PURA:
// date una tastiera e un titolo, produce una sequenza di tasti, senza
// toccare la rete. Stando nell'app web si corregge pubblicando, senza
// ricompilare niente e senza i sette giorni del profilo di sviluppo -
// mentre a chi manda i tasti (l'app nativa) resta un compito stabile:
// «premi questi».
//
// Serve perche' nessuna delle app della TV usa l'IME di Tizen: il
// testo iniettato non arriva da nessuna parte, e l'unica strada e'
// muoversi sulla loro tastiera premendo OK su ogni lettera.
//
// LA TRADUZIONE E' VERIFICATA contro il Python, non "sembra giusta":
// prove/confronta_tastiere.py genera le sequenze con tutte e due le
// implementazioni, su tutte le app e molti titoli, e si ferma al primo
// carattere che diverge.

const SPAZIO = " ";
const CANCELLA = "\b";
const ALTRO = "\x00";
const SVUOTA = "\x01";

const DISPOSIZIONI = {
  "netflix": {
    "nome": "Netflix",
    "griglia": [
      "   \b\b\b",
      "abcdef",
      "ghijkl",
      "mnopqr",
      "stuvwx",
      "yz0123",
      "456789"
    ],
    "partenza": [
      1,
      0
    ],
    "azzera": 30,
    "normalizza": [
      "BACK",
      "BACK",
      "BACK",
      "BACK",
      "BACK",
      "OK",
      "BACK",
      "BACK",
      "BACK",
      "BACK",
      "BACK"
    ],
    "strada": [
      "LEFT",
      "OK"
    ],
    "bordi": "girano",
    "ancoraggio": null,
    "larghi": [
      "\b",
      " "
    ]
  },
  "now": {
    "nome": "NOW",
    "griglia": [
      "qwertyuiop",
      "asdfghjkl\b",
      "zxcvbnm\u0000\u0000 "
    ],
    "partenza": [
      0,
      0
    ],
    "bordi": "fermano",
    "larghi": [],
    "ancoraggio": {
      "tasti": [
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "UP",
        "UP",
        "UP",
        "UP",
        "UP"
      ],
      "arrivo": [
        0,
        9
      ]
    },
    "azzera": 30,
    "normalizza": [
      "OK",
      "BACK",
      "BACK",
      "BACK",
      "BACK",
      "BACK",
      "BACK"
    ],
    "strada": [
      "UP",
      "OK",
      "UP",
      "OK"
    ]
  },
  "disney": {
    "nome": "Disney+",
    "griglia": [
      "\b\b\b\b   ",
      "abcdefg",
      "hijklmn",
      "opqrstu",
      "vwxyz12",
      "3456789",
      "0"
    ],
    "partenza": [
      0,
      5
    ],
    "non_scrivibili": [
      " "
    ],
    "bordi": "fermano",
    "larghi": [
      "\b",
      " "
    ],
    "ancoraggio": null,
    "azzera": 30,
    "normalizza": [
      "OK",
      "BACK",
      "BACK",
      "BACK",
      "BACK",
      "BACK",
      "BACK"
    ],
    "strada": [
      "UP",
      "UP",
      "UP",
      "UP",
      "UP",
      "UP",
      "DOWN",
      "OK"
    ]
  },
  "hbomax": {
    "nome": "HBO Max",
    "griglia": [
      "abcdef",
      "ghijkl",
      "mnopqr",
      "stuvwx",
      "yz0123",
      "456789",
      "\b\b  \u0001\u0001"
    ],
    "partenza": [
      0,
      0
    ],
    "bordi": "fermano",
    "larghi": [
      "\u0001",
      "\b",
      " "
    ],
    "ancoraggio": {
      "tasti": [
        "LEFT",
        "LEFT",
        "LEFT",
        "LEFT",
        "LEFT",
        "LEFT",
        "LEFT",
        "LEFT",
        "LEFT",
        "LEFT",
        "RIGHT",
        "UP",
        "UP",
        "UP",
        "UP",
        "UP",
        "UP",
        "UP"
      ],
      "arrivo": [
        0,
        0
      ]
    },
    "azzera": 1,
    "passo": 0.3,
    "normalizza": [
      "OK",
      "BACK",
      "BACK",
      "BACK",
      "BACK",
      "BACK",
      "BACK",
      "BACK",
      "BACK",
      "RIGHT",
      "BACK"
    ],
    "strada": [
      "UP",
      "UP",
      "UP",
      "UP",
      "UP",
      "UP",
      "UP",
      "UP",
      "DOWN",
      "DOWN",
      "OK"
    ]
  },
  "prime": {
    "nome": "Prime Video",
    "griglia": [
      "abcdef",
      "ghijkl",
      "mnopqr",
      "stuvwx",
      "yzàèéì",
      "òù1234",
      "567890",
      "  \b\b\u0001\u0001"
    ],
    "partenza": [
      0,
      0
    ],
    "bordi": "fermano",
    "larghi": [
      "\u0001",
      "\b",
      " "
    ],
    "ancoraggio": {
      "tasti": [
        "LEFT",
        "LEFT",
        "LEFT",
        "LEFT",
        "LEFT",
        "LEFT",
        "LEFT",
        "LEFT",
        "LEFT",
        "LEFT",
        "LEFT",
        "LEFT",
        "RIGHT",
        "UP",
        "UP",
        "UP",
        "UP",
        "UP",
        "UP",
        "UP",
        "UP",
        "UP"
      ],
      "arrivo": [
        0,
        0
      ]
    },
    "azzera": 1,
    "passo": 0.3,
    "normalizza": [
      "OK",
      "BACK",
      "BACK",
      "BACK",
      "BACK",
      "BACK",
      "BACK",
      "BACK",
      "BACK",
      "LEFT",
      "BACK"
    ],
    "strada": [
      "LEFT",
      "UP",
      "UP",
      "UP",
      "UP",
      "UP",
      "UP",
      "UP",
      "UP",
      "DOWN",
      "OK"
    ]
  },
  "infinity": {
    "nome": "Mediaset Infinity",
    "griglia": [
      "abcdefghijklmno\b01234",
      " pqrstuvwxyzàè' 56789"
    ],
    "partenza": [
      0,
      0
    ],
    "bordi": "fermano",
    "larghi": [],
    "ancoraggio": {
      "tasti": [
        "UP",
        "UP",
        "UP",
        "UP",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT",
        "RIGHT"
      ],
      "arrivo": [
        0,
        20
      ]
    },
    "azzera": 30,
    "normalizza": [
      "OK",
      "BACK",
      "BACK",
      "BACK",
      "BACK",
      "BACK",
      "BACK",
      "BACK",
      "BACK",
      "LEFT"
    ],
    "strada": [
      "UP",
      "UP",
      "UP",
      "UP",
      "UP",
      "UP",
      "OK"
    ]
  },
  "prova": {
    "nome": "prova",
    "griglia": [
      "abcdef",
      "ghijkl",
      "mnopqr",
      "stuvwx",
      "yz0123"
    ],
    "partenza": [
      0,
      0
    ],
    "bordi": "fermano",
    "larghi": []
  },
  "discovery": {
    "nome": "Discovery+",
    "griglia": [
      "abcdef",
      "ghijkl",
      "mnopqr",
      "stuvwx",
      "yz0123",
      "456789",
      "\b\b  \u0001\u0001"
    ],
    "partenza": [
      0,
      0
    ],
    "bordi": "fermano",
    "larghi": [
      "\u0001",
      "\b",
      " "
    ],
    "ancoraggio": {
      "tasti": [
        "LEFT",
        "LEFT",
        "LEFT",
        "LEFT",
        "LEFT",
        "LEFT",
        "LEFT",
        "LEFT",
        "LEFT",
        "LEFT",
        "RIGHT",
        "UP",
        "UP",
        "UP",
        "UP",
        "UP",
        "UP",
        "UP"
      ],
      "arrivo": [
        0,
        0
      ]
    },
    "azzera": 1,
    "passo": 0.5,
    "normalizza": [
      "OK",
      "BACK",
      "BACK",
      "BACK",
      "BACK",
      "BACK",
      "BACK",
      "BACK",
      "BACK",
      "RIGHT",
      "BACK"
    ],
    "strada": [
      "UP",
      "UP",
      "UP",
      "UP",
      "UP",
      "UP",
      "UP",
      "UP",
      "DOWN",
      "DOWN",
      "OK"
    ]
  }
};

/// Dove sta ogni carattere. Per i tasti larghi vince la cella piu' a
/// sinistra; il centro lo calcola `campata`.
function posizioni(griglia) {
  const dove = new Map();
  griglia.forEach((riga, r) => {
    for (let c = 0; c < riga.length; c++) {
      if (!dove.has(riga[c])) dove.set(riga[c], [r, c]);
    }
  });
  return dove;
}

/// Da dove a dove arriva il tasto che occupa questa cella. Un tasto
/// largo e' una fila di celle con la stessa etichetta.
function campata(griglia, riga, colonna) {
  const t = griglia[riga], ch = t[colonna];
  let a = colonna, b = colonna;
  while (a > 0 && t[a - 1] === ch) a--;
  while (b < t.length - 1 && t[b + 1] === ch) b++;
  return [a, b];
}

/// La colonna centrale del tasto. MISURATO su Netflix: scendendo da
/// CANCELLA (colonne 3-5) si arriva su "e", colonna 4.
function centro(griglia, riga, colonna) {
  const [a, b] = campata(griglia, riga, colonna);
  return Math.floor((a + b) / 2);
}

/// Un passo. `bordi` e' la cosa piu' difficile da sapere di una
/// tastiera: "fermano" = a fondo corsa il cursore resta, "girano" =
/// ricompare dall'altro lato. Netflix GIRA, misurato.
function muovi(griglia, da, verso, bordi = "fermano") {
  let [r, c] = da;
  const alte = griglia.length;
  if (verso === "UP" || verso === "DOWN") {
    const passo = verso === "UP" ? -1 : 1;
    if (verso === "DOWN") c = centro(griglia, r, c);
    r = bordi === "girano"
      ? ((r + passo) % alte + alte) % alte        // il modulo di JS tiene il segno
      : Math.max(0, Math.min(alte - 1, r + passo));
  } else {
    const passo = verso === "LEFT" ? -1 : 1;
    const larga = griglia[r].length;
    c = bordi === "girano"
      ? ((c + passo) % larga + larga) % larga
      : Math.max(0, Math.min(larga - 1, c + passo));
  }
  return [r, Math.min(c, griglia[r].length - 1)];
}

/// I tasti per andare da una cella all'altra: prima in verticale, poi
/// in orizzontale, a delta esatto. Un percorso a delta esatto non
/// tocca mai un bordo, quindi vale con entrambi i modelli.
function percorso(griglia, da, a, bordi = "fermano") {
  const passi = [];
  let pos = da;
  const tetto = griglia.length + Math.max(...griglia.map(r => r.length)) + 2;
  for (let i = 0; i < tetto && pos[0] !== a[0]; i++) {
    passi.push(a[0] > pos[0] ? "DOWN" : "UP");
    pos = muovi(griglia, pos, passi[passi.length - 1], bordi);
  }
  for (let i = 0; i < tetto && pos[1] !== a[1]; i++) {
    passi.push(a[1] > pos[1] ? "RIGHT" : "LEFT");
    pos = muovi(griglia, pos, passi[passi.length - 1], bordi);
  }
  if (pos[0] !== a[0] || pos[1] !== a[1]) {
    throw new Error(`disposizione incoerente: da ${da} non si arriva a ${a}`);
  }
  return [passi, pos];
}

/// I tasti per arrivare su un tasto largo. Ci si arriva SOLO da sotto:
/// muoversi in orizzontale sulla riga dei tasti larghi salterebbe fra
/// i due in un modo che il modello a celle non sa contare.
function percorsoLargo(griglia, da, ch, bordi = "fermano") {
  const dove = posizioni(griglia);
  if (!dove.has(ch)) throw new Error(`${JSON.stringify(ch)} non e' su questa tastiera`);
  const rigaLarga = dove.get(ch)[0];
  const [a, b] = campata(griglia, rigaLarga, dove.get(ch)[1]);
  const colonna = Math.floor((a + b) / 2);
  const passi = [];
  let pos = da;
  if (pos[0] === rigaLarga) {
    // due tasti larghi di fila: «Amori & incantesimi» ha due spazi
    // vicini perche' la & viene saltata. Si scende e si risale.
    const via = rigaLarga === 0 ? "DOWN" : "UP";
    passi.push(via);
    pos = muovi(griglia, pos, via, bordi);
  }
  for (let i = 0; i < griglia[pos[0]].length + 1 && pos[1] !== colonna; i++) {
    passi.push(colonna > pos[1] ? "RIGHT" : "LEFT");
    pos = muovi(griglia, pos, passi[passi.length - 1], bordi);
  }
  for (let i = 0; i < griglia.length + 1 && pos[0] !== rigaLarga; i++) {
    // la direzione dipende da DOVE STA quella riga: sopra le lettere su
    // Netflix e Disney+, SOTTO su HBO Max. Darla per scontata rompeva HBO.
    const via = rigaLarga > pos[0] ? "DOWN" : "UP";
    passi.push(via);
    pos = muovi(griglia, pos, via, bordi);
  }
  if (griglia[pos[0]][pos[1]] !== ch) {
    throw new Error(`non arrivo su ${JSON.stringify(ch)}: sono su ` +
                    JSON.stringify(griglia[pos[0]][pos[1]]));
  }
  return [passi, pos];
}

/// I tasti per portarsi in un punto CERTO, e dove si finisce. Non e'
/// una formula: e' un fatto misurato, scritto nella disposizione.
function ancoraggio(app = "netflix") {
  const d = DISPOSIZIONI[app];
  const anc = d.ancoraggio;
  if (!anc) {
    throw new Error(`${d.nome}: nessun ancoraggio. I bordi non bloccano, ` +
      "quindi a fondo corsa il cursore non si ferma: serve sapere da dove " +
      "parte, e aprire la ricerca da zero.");
  }
  return [[...anc.tasti], [...anc.arrivo]];
}

/// La sequenza di tasti per scrivere un testo dentro l'app.
/// Torna { tasti, saltati }: i caratteri che non stanno sulla tastiera
/// si dichiarano invece di sparire in silenzio.
function digita(testo, app = "netflix", azzera = 0, ancora = null) {
  const d = DISPOSIZIONI[app];
  const griglia = d.griglia, larghi = d.larghi || [];
  const bordi = d.bordi || "fermano";
  const dove = posizioni(griglia);
  const nonScrivibili = new Set(d.non_scrivibili || []);
  let pos = [...d.partenza];
  let tasti = [];
  const saltati = [];

  if (ancora === null) ancora = !!d.ancoraggio;
  if (ancora) {
    const [passi, p] = ancoraggio(app);
    tasti = tasti.concat(passi);
    pos = p;
  }

  // prima si toglie quello che non si puo' scrivere, POI si accorpano
  // gli spazi: senza, «Amori & incantesimi» diventava «amori  incantesimi»
  const pulito = [];
  for (const ch of testo.toLowerCase()) {
    if (dove.has(ch) && ch !== CANCELLA && !nonScrivibili.has(ch)) {
      if (ch === SPAZIO && (pulito.length === 0 || pulito[pulito.length - 1] === SPAZIO)) continue;
      pulito.push(ch);
    } else {
      saltati.push(ch);
      // un buco resta un buco: al posto del saltato ci va uno spazio,
      // ma solo se lo spazio si puo' scrivere
      if (pulito.length && pulito[pulito.length - 1] !== SPAZIO
          && dove.has(SPAZIO) && !nonScrivibili.has(SPAZIO)) {
        pulito.push(SPAZIO);
      }
    }
  }
  while (pulito.length && pulito[pulito.length - 1] === SPAZIO) pulito.pop();
  const scritto = pulito.join("");

  const vai = (carattere) => larghi.includes(carattere)
    ? percorsoLargo(griglia, pos, carattere, bordi)
    : percorso(griglia, pos, dove.get(carattere), bordi);

  if (azzera) {
    if (dove.has(SVUOTA)) {
      const [passi, p] = vai(SVUOTA); pos = p;
      tasti = tasti.concat(passi, ["OK"]);
    } else if (dove.has(CANCELLA)) {
      const [passi, p] = vai(CANCELLA); pos = p;
      tasti = tasti.concat(passi, Array(azzera).fill("OK"));
    } else {
      throw new Error(`${d.nome}: non so dov'e' il tasto cancella`);
    }
  }

  for (const ch of scritto) {
    const [passi, p] = vai(ch); pos = p;
    tasti = tasti.concat(passi, ["OK"]);
  }

  return { tasti, saltati };
}

// per il confronto da riga di comando con node
if (typeof module !== "undefined" && module.exports) {
  module.exports = { DISPOSIZIONI, digita, posizioni, campata, centro,
                     muovi, percorso, percorsoLargo, ancoraggio,
                     SPAZIO, CANCELLA, ALTRO, SVUOTA };
}
