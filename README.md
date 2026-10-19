# ⏱ Windows Timer Resolution — Gaming Mode

Utility Python con interfaccia grafica (dark theme) che imposta la risoluzione del timer di sistema Windows a **0.50 ms** tramite `NtSetTimerResolution`, riducendosi nell'**area di notifica** (system tray, accanto al volume).

---

## ✨ Funzionalità

| Funzione | Dettaglio |
|---|---|
| 🎮 Gaming Mode | Imposta il timer a 0.50 ms (da ~15.6 ms default) |
| 🔄 Ripristino | Rilascia la richiesta, Windows torna al valore minimo richiesto dagli altri processi |
| 🔽 System Tray | X o pulsante Minimizza → si nasconde nel tray, continua a girare in background |
| 🔁 Keep-alive | Thread che ri-applica il timer ogni 500 ms (obbligatorio su Win 10 v2004+) |
| 📊 Monitor | Polling ogni 2 s: mostra risoluzione Min / Attuale / Max in tempo reale |
| 🛡️ UAC | Richiede e ottiene automaticamente i privilegi di Amministratore |

---

## 🖥️ Screenshot

> Icona tray **verde** = Gaming Mode attiva · **rossa** = inattivo

---

## 📋 Requisiti

- Windows 10 / 11
- Python 3.9 o superiore
- Librerie (vedi sotto)

---

## 🚀 Installazione

### 1. Clona il repository

```bash
git clone https://github.com/nik8501/TimerResolution-Gaming.git
cd TimerResolution-Gaming
```

### 2. Installa le dipendenze

```bash
pip install -r requirements.txt
```

Le uniche dipendenze esterne sono `pystray` (icona tray) e `Pillow` (generazione icona colorata). `tkinter` è incluso nella distribuzione standard di Python.

### 3. Avvia il programma

```bash
python TimerResolution_Gaming.pyw
```

oppure doppio clic sul file `.pyw` (nessuna finestra console).

> ⚠️ Il programma richiede i **privilegi di Amministratore** — Windows mostrerà il prompt UAC automaticamente.

---

## 🗂️ Struttura del progetto

```
TimerResolution-Gaming/
│
├── TimerResolution_Gaming.pyw   # Programma principale
├── requirements.txt             # Dipendenze Python
├── README.md                    # Questa guida
└── .gitignore                   # File ignorati da Git
```

---

## ⚙️ Come funziona

Windows espone `NtSetTimerResolution` (API non documentata di `ntdll.dll`) che permette di richiedere una risoluzione del timer di sistema più alta del default.

- **Default**: ~15.6 ms (625 tick/s)
- **Gaming Mode**: 0.50 ms (2000 tick/s)

Una risoluzione più alta migliora la precisione delle chiamate `Sleep()` e il tick-rate dello scheduler, riducendo la latenza di input e le micro-stuttering nei giochi.

Da **Windows 10 versione 2004** la risoluzione è **per-processo**: il keep-alive thread ri-applica la richiesta ogni 500 ms per mantenere l'impostazione attiva.

---

## 🔧 Comportamento del Tray

| Azione | Risultato |
|---|---|
| Clic su **X** della finestra | Nasconde nel tray, NON termina |
| Clic su **Minimizza** (−) | Nasconde nel tray, NON termina |
| **Doppio clic** sull'icona tray | Ripristina la finestra |
| Menu tray → **Mostra / Nascondi** | Alterna visibilità finestra |
| Menu tray → **Attiva Gaming Mode** | Attiva senza riaprire la finestra |
| Menu tray → **Ripristina Default** | Disattiva senza riaprire la finestra |
| Menu tray → **Esci** | Chiude pulitamente (chiede se rilasciare il timer) |

---

## 📦 Dipendenze

```
pystray>=0.19.5   — icona nella system tray
Pillow>=10.0.0    — generazione icona colorata (verde/rossa)
```

---

## 📝 Licenza

MIT — libero uso, modifica e distribuzione.

---

## 🙏 Credits

Sviluppato con [Claude](https://claude.ai) (Anthropic).
