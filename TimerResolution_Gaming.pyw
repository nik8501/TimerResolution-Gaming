"""
Windows Timer Resolution — Gaming Mode
Imposta la risoluzione del timer di sistema a 0.50 ms via NtSetTimerResolution.
Richiede privilegi amministratore (UAC).

v2.0 — System Tray:
  • X o minimizza → si nasconde nell'area di notifica (accanto al volume)
  • Doppio clic sull'icona tray → riapre la finestra
  • Menu tray: Mostra/Nascondi · Attiva/Ripristina · Esci
  • Icona verde = Gaming Mode ATTIVA · icona rossa = Inattivo
  • Il keep-alive thread continua a girare anche da minimizzato
"""

import ctypes
import sys
import os
import threading
import tkinter as tk
from tkinter import messagebox

# ── Dipendenze opzionali per il tray (auto-installazione se mancano) ─────────
import subprocess

TRAY_ERR = ""      # dettaglio errore, mostrato nel log se il tray non parte


def _try_import_tray() -> bool:
    global pystray, Image, ImageDraw, ImageFont
    import importlib
    importlib.invalidate_caches()
    import pystray                                   # noqa: F811
    from PIL import Image, ImageDraw, ImageFont      # noqa: F811
    return True


def _auto_install_tray() -> str:
    """Installa pystray e Pillow con pip. Ritorna "" se ok, altrimenti l'errore."""
    exe = sys.executable
    # Con pythonw.exe non c'è console: usa python.exe affiancato per pip
    py = os.path.join(os.path.dirname(exe), "python.exe")
    if not os.path.exists(py):
        py = exe
    try:
        r = subprocess.run(
            [py, "-m", "pip", "install", "--user", "--upgrade", "pystray", "Pillow"],
            capture_output=True, text=True, timeout=300,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if r.returncode != 0:
            return (r.stderr or r.stdout or "pip ha restituito un errore").strip()[-600:]
        return ""
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


try:
    TRAY_OK = _try_import_tray()
except ImportError as _e:
    TRAY_ERR = f"Import fallito: {_e}"
    _pip_err = _auto_install_tray()
    if _pip_err:
        TRAY_ERR += f"\n   pip: {_pip_err}"
        TRAY_OK = False
    else:
        try:
            TRAY_OK = _try_import_tray()
        except ImportError as _e2:
            TRAY_ERR += f"\n   Dopo l'installazione: {_e2}"
            TRAY_OK = False


# ── UAC ──────────────────────────────────────────────────────────────────────

def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def elevate() -> None:
    """Rilancia il processo con privilegi di amministratore (UAC)."""
    script  = os.path.abspath(sys.argv[0])
    params  = " ".join(f'"{a}"' for a in sys.argv[1:])
    exe     = sys.executable
    pythonw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = exe          # fallback: python.exe (mostra la console)
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", pythonw, f'"{script}" {params}', None, 1
    )
    sys.exit(0)


# ── ntdll wrappers ────────────────────────────────────────────────────────────

_ntdll = ctypes.WinDLL("ntdll")


def query_timer_resolution() -> tuple:
    """NtQueryTimerResolution → (min, max, current) in unità 100ns."""
    mn  = ctypes.c_ulong()
    mx  = ctypes.c_ulong()
    cur = ctypes.c_ulong()
    _ntdll.NtQueryTimerResolution(ctypes.byref(mn), ctypes.byref(mx), ctypes.byref(cur))
    return mn.value, mx.value, cur.value


def set_timer_resolution(desired_100ns: int) -> tuple:
    """NtSetTimerResolution(Set=TRUE) → (NTSTATUS, actual_100ns)."""
    cur    = ctypes.c_ulong()
    status = _ntdll.NtSetTimerResolution(
        ctypes.c_ulong(desired_100ns),
        ctypes.c_ubyte(1),
        ctypes.byref(cur),
    )
    return status, cur.value


def release_timer_resolution(desired_100ns: int) -> int:
    """NtSetTimerResolution(Set=FALSE) → ritorna la risoluzione corrente dopo il rilascio."""
    cur = ctypes.c_ulong()
    _ntdll.NtSetTimerResolution(
        ctypes.c_ulong(desired_100ns),
        ctypes.c_ubyte(0),
        ctypes.byref(cur),
    )
    return cur.value


# ── Costanti ──────────────────────────────────────────────────────────────────

TARGET_100NS = 5_000                     # 0.50 ms → 5000 × 100 ns
TARGET_MS    = TARGET_100NS / 10_000     # 0.5

# Palette dark (coerente con PC_Cleaner)
BG     = "#1a1a2e"
BG2    = "#16213e"
ACCENT = "#0f3460"
GREEN  = "#00d084"
RED    = "#ff4757"
YELLOW = "#ffa502"
FG     = "#e0e0e0"
FG_DIM = "#888888"


# ── Applicazione ──────────────────────────────────────────────────────────────

class TimerApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Windows Timer Resolution — Gaming Mode")
        self.geometry("520x640")
        self.minsize(520, 500)
        self.resizable(True, True)
        self.configure(bg=BG)

        # Intercetta il tasto X della finestra
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._active   = False          # True → Gaming Mode attiva
        self._running  = True           # False → ferma il loop di refresh
        self._stop_evt = threading.Event()
        self._tray     = None           # istanza pystray.Icon
        self._hiding   = False          # guard per evitare withdraw ricorsivo

        self._build_ui()
        self._schedule_refresh()

        # Avvia tray (se le librerie sono disponibili)
        if TRAY_OK:
            self._setup_tray()
            # Intercetta il pulsante minimizza → nascondi al tray
            self.bind("<Unmap>", self._on_unmap)
        else:
            self._log(
                "⚠️  pystray o Pillow non disponibili — tray non attivo.\n"
                f"   Python: {sys.executable}\n"
                f"   {TRAY_ERR}\n"
                "   Prova a mano:  python -m pip install pystray Pillow\n"
                "   Il programma funziona normalmente senza tray."
            )
            # Senza tray il btn Nascondi non ha senso: lo disabilita
            self.btn_tray.config(state="disabled", text="🔽  Tray non disponibile")

    # ─────────────────────────────────────────────────────────────────────────
    # TRAY — Creazione icona
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _make_icon(active: bool) -> "Image.Image":
        """
        Icona 64×64 px:
          sfondo blu scuro · cerchio verde (attivo) o rosso (inattivo)
          · lancetta orologio · punto centrale
        """
        ring  = (0, 208, 132, 255)  if active else (255, 71, 87, 255)
        bg_c  = (22, 33, 62, 255)

        img  = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Sfondo circolare
        draw.ellipse([2, 2, 62, 62], fill=bg_c, outline=ring, width=4)

        # Lancetta "12 → centro" (ticker)
        cx, cy = 32, 32
        draw.line([cx, cy - 16, cx, cy], fill=ring, width=3)
        draw.line([cx, cy, cx + 10, cy + 4], fill=ring, width=2)

        # Punto centrale
        draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=ring)

        return img

    # ─────────────────────────────────────────────────────────────────────────
    # TRAY — Setup
    # ─────────────────────────────────────────────────────────────────────────

    def _setup_tray(self):
        """Costruisce e avvia l'icona nella system tray in un thread daemon."""
        menu = pystray.Menu(
            pystray.MenuItem(
                "Mostra / Nascondi",
                self._tray_toggle_window,
                default=True,       # azione al doppio clic
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "🎮  Attiva Gaming Mode",
                lambda icon, item: self.after(0, self._activate),
            ),
            pystray.MenuItem(
                "🔄  Ripristina Default",
                lambda icon, item: self.after(0, self._restore),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "❌  Esci",
                lambda icon, item: self.after(0, self._tray_exit),
            ),
        )

        self._tray = pystray.Icon(
            name  = "TimerResolutionGaming",
            icon  = self._make_icon(False),
            title = "Timer Resolution — Inattivo",
            menu  = menu,
        )

        # Avvia in thread daemon: si ferma automaticamente quando il processo esce
        threading.Thread(target=self._tray.run, daemon=True).start()

    def _update_tray_icon(self):
        """Aggiorna colore icona e tooltip del tray in base allo stato."""
        if not (TRAY_OK and self._tray):
            return
        try:
            self._tray.icon  = self._make_icon(self._active)
            self._tray.title = (
                "⚡ Gaming Mode ATTIVA — 0.50 ms"
                if self._active
                else "Timer Resolution — Inattivo"
            )
        except Exception:
            pass    # il tray potrebbe non essere ancora pronto

    # ─────────────────────────────────────────────────────────────────────────
    # TRAY — Azioni
    # ─────────────────────────────────────────────────────────────────────────

    def _tray_toggle_window(self, icon=None, item=None):
        """Mostra o nasconde la finestra principale (chiamato dal thread tray)."""
        if self.wm_state() == "withdrawn":
            self.after(0, self._show_window)
        else:
            self.after(0, self._hide_to_tray)

    def _show_window(self):
        """Ripristina e porta in primo piano la finestra."""
        self._hiding = False
        self.deiconify()
        self.lift()
        self.focus_force()

    def _hide_to_tray(self):
        """Nasconde la finestra senza terminare il processo."""
        if self._hiding:
            return
        self._hiding = True
        self.withdraw()
        self._log("💾 Nascosto nel tray. Doppio clic sull'icona per riaprire.")

    def _tray_exit(self):
        """Uscita pulita tramite menu tray."""
        if self._active:
            ans = messagebox.askyesno(
                "Esci",
                "La Gaming Mode è ancora attiva.\n"
                "Ripristinare la risoluzione di default prima di uscire?",
            )
            if ans:
                self._stop_keepalive()
                release_timer_resolution(TARGET_100NS)
        self._running = False
        self._stop_keepalive()
        if self._tray:
            try:
                self._tray.stop()
            except Exception:
                pass
        self.destroy()

    # ─────────────────────────────────────────────────────────────────────────
    # Intercettazione tasto Minimizza della barra del titolo
    # ─────────────────────────────────────────────────────────────────────────

    def _on_unmap(self, event):
        """
        <Unmap> scatta quando la finestra viene rimossa dallo schermo.
        Se lo stato è "iconic" significa che è stata premuta la freccia
        minimizza → sostituiamo iconify con withdraw (nascondi al tray).
        Guard _hiding evita ricorsioni se withdraw() ri-triggera Unmap.
        """
        if event.widget is not self or self._hiding:
            return
        # Piccolo ritardo: tkinter aggiorna wm_state() in modo asincrono
        self.after(20, self._check_iconic)

    def _check_iconic(self):
        if self.wm_state() == "iconic":
            self._hide_to_tray()

    # ─────────────────────────────────────────────────────────────────────────
    # Costruzione interfaccia
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Header ───────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=ACCENT, pady=14)
        hdr.pack(fill="x")
        tk.Label(
            hdr, text="⏱  Windows Timer Resolution",
            font=("Segoe UI", 14, "bold"), bg=ACCENT, fg=FG,
        ).pack()
        tk.Label(
            hdr,
            text="Ottimizzazione timer di sistema per il gaming  •  Target: 0.50 ms",
            font=("Segoe UI", 9), bg=ACCENT, fg=FG_DIM,
        ).pack()

        # ── Card stato ───────────────────────────────────────────────────────
        card = tk.Frame(self, bg=BG2, padx=20, pady=16)
        card.pack(fill="x", padx=16, pady=12)

        self.lbl_val = tk.Label(
            card, text="—",
            font=("Segoe UI", 28, "bold"), bg=BG2, fg=YELLOW,
        )
        self.lbl_val.pack()
        tk.Label(
            card, text="Risoluzione attuale",
            font=("Segoe UI", 9), bg=BG2, fg=FG_DIM,
        ).pack()

        # Riga Min / Max
        row = tk.Frame(card, bg=BG2)
        row.pack(pady=(8, 0))
        tk.Label(row, text="Min:", font=("Segoe UI", 9),
                 bg=BG2, fg=FG_DIM).grid(row=0, column=0, padx=(8, 2))
        self.lbl_min = tk.Label(row, text="—", font=("Segoe UI", 9, "bold"),
                                bg=BG2, fg=FG)
        self.lbl_min.grid(row=0, column=1, padx=(0, 8))
        tk.Label(row, text="│", font=("Segoe UI", 9),
                 bg=BG2, fg=FG_DIM).grid(row=0, column=2)
        tk.Label(row, text="Max:", font=("Segoe UI", 9),
                 bg=BG2, fg=FG_DIM).grid(row=0, column=3, padx=(8, 2))
        self.lbl_max = tk.Label(row, text="—", font=("Segoe UI", 9, "bold"),
                                bg=BG2, fg=FG)
        self.lbl_max.grid(row=0, column=4, padx=(0, 8))

        # Badge stato
        self.lbl_status = tk.Label(
            card, text="⬤  Inattivo",
            font=("Segoe UI", 10, "bold"), bg=BG2, fg=RED,
        )
        self.lbl_status.pack(pady=(10, 0))

        # ── Pulsanti ─────────────────────────────────────────────────────────
        bf = tk.Frame(self, bg=BG)
        bf.pack(fill="x", padx=16, pady=4)

        self.btn_on = tk.Button(
            bf,
            text="🎮  Attiva Gaming Mode  (0.50 ms)",
            font=("Segoe UI", 10, "bold"),
            bg=GREEN, fg="#000000",
            activebackground="#00b870", activeforeground="#000000",
            relief="flat", pady=10, cursor="hand2",
            command=self._activate,
        )
        self.btn_on.pack(fill="x", pady=(0, 6))

        self.btn_off = tk.Button(
            bf,
            text="🔄  Ripristina Default  (~15.6 ms)",
            font=("Segoe UI", 10, "bold"),
            bg=ACCENT, fg=FG,
            activebackground="#1a4080", activeforeground=FG,
            relief="flat", pady=10, cursor="hand2",
            state="disabled",
            command=self._restore,
        )
        self.btn_off.pack(fill="x", pady=(0, 6))

        # Pulsante "Nascondi nel Tray"
        self.btn_tray = tk.Button(
            bf,
            text="🔽  Nascondi nel Tray",
            font=("Segoe UI", 9),
            bg=BG2, fg=FG_DIM,
            activebackground=ACCENT, activeforeground=FG,
            relief="flat", pady=6, cursor="hand2",
            command=self._hide_to_tray,
        )
        self.btn_tray.pack(fill="x")

        # ── Info box ─────────────────────────────────────────────────────────
        info = tk.Frame(self, bg=BG2, padx=14, pady=10)
        info.pack(fill="x", padx=16, pady=10)
        tk.Label(
            info,
            text=(
                "ℹ️  La risoluzione del timer influisce sulla precisione delle chiamate\n"
                "Sleep() e sul tick-rate dello scheduler di Windows.\n"
                "0.50 ms = latenza minima, ideale per il gaming.\n"
                "⚠️  La modalità rimane attiva anche quando nascosto nel tray."
            ),
            font=("Segoe UI", 9), bg=BG2, fg=FG_DIM, justify="left",
        ).pack(anchor="w")

        # ── Log ──────────────────────────────────────────────────────────────
        tk.Label(
            self, text="Log", font=("Segoe UI", 9, "bold"),
            bg=BG, fg=FG_DIM, anchor="w",
        ).pack(fill="x", padx=16)

        self.log = tk.Text(
            self, height=10,
            bg="#0d0d1a", fg=FG,
            font=("Consolas", 9), relief="flat",
            state="disabled", padx=8, pady=6,
        )
        self.log.pack(fill="both", expand=True, padx=16, pady=(2, 12))

    # ─────────────────────────────────────────────────────────────────────────
    # Azioni principali
    # ─────────────────────────────────────────────────────────────────────────

    def _activate(self):
        status, actual = set_timer_resolution(TARGET_100NS)
        actual_ms = actual / 10_000
        if status == 0:
            self._active = True
            self._log(
                f"✅ Timer impostato: {actual_ms:.4f} ms "
                f"(richiesto {TARGET_MS:.2f} ms)"
            )
            self._start_keepalive()
        else:
            self._log(f"❌ NtSetTimerResolution fallito — NTSTATUS: 0x{status:08X}")
        self._update_ui()

    def _restore(self):
        self._stop_keepalive()
        cur_after = release_timer_resolution(TARGET_100NS)
        self._active = False
        self._log(
            f"🔄 Timer rilasciato. Risoluzione corrente: "
            f"{cur_after / 10_000:.4f} ms"
        )
        self._update_ui()

    # ─────────────────────────────────────────────────────────────────────────
    # Keep-alive (obbligatorio su Windows 10 v2004+ — timer per-processo)
    # ─────────────────────────────────────────────────────────────────────────

    def _start_keepalive(self):
        self._stop_evt.clear()
        threading.Thread(target=self._keepalive_worker, daemon=True).start()
        self._log("🔁 Keep-alive thread avviato (Win 10 2004+ per-process mode).")

    def _stop_keepalive(self):
        self._stop_evt.set()

    def _keepalive_worker(self):
        """
        Ri-applica NtSetTimerResolution ogni 500 ms.
        _stop_evt.wait(0.5): dorme 0.5 s oppure si sveglia subito se
        l'evento viene settato (True = settato → uscita loop).
        """
        cur = ctypes.c_ulong()
        while not self._stop_evt.wait(0.5):
            try:
                _ntdll.NtSetTimerResolution(
                    ctypes.c_ulong(TARGET_100NS),
                    ctypes.c_ubyte(1),
                    ctypes.byref(cur),
                )
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────────────────────
    # Aggiornamento UI
    # ─────────────────────────────────────────────────────────────────────────

    def _update_ui(self):
        try:
            mn, mx, cur = query_timer_resolution()
            self.lbl_val.config(
                text=f"{cur / 10_000:.4f} ms",
                fg=GREEN if self._active else YELLOW,
            )
            self.lbl_min.config(text=f"{mn / 10_000:.4f} ms")
            self.lbl_max.config(text=f"{mx / 10_000:.4f} ms")
        except Exception as exc:
            self._log(f"⚠️  Errore lettura risoluzione: {exc}")

        if self._active:
            self.lbl_status.config(text="⬤  Gaming Mode ATTIVA", fg=GREEN)
            self.btn_on.config(state="disabled")
            self.btn_off.config(state="normal")
        else:
            self.lbl_status.config(text="⬤  Inattivo", fg=RED)
            self.btn_on.config(state="normal")
            self.btn_off.config(state="disabled")

        self._update_tray_icon()

    def _schedule_refresh(self):
        """Polling ogni 2 secondi. Continua anche quando la finestra è nascosta."""
        if self._running:
            self._update_ui()
            self.after(2000, self._schedule_refresh)

    def _log(self, msg: str):
        """Thread-safe: usa self.after per scrivere nel log dal thread GUI."""
        def _write():
            self.log.config(state="normal")
            self.log.insert("end", f"{msg}\n")
            self.log.see("end")
            self.log.config(state="disabled")
        self.after(0, _write)

    # ─────────────────────────────────────────────────────────────────────────
    # Chiusura
    # ─────────────────────────────────────────────────────────────────────────

    def _on_close(self):
        """
        Tasto X della finestra:
          - Se il tray è disponibile → nascondi (NON termina il processo).
          - Se il tray non è disponibile → chiede conferma ed esce.
        """
        if TRAY_OK and self._tray:
            self._hide_to_tray()
        else:
            self._tray_exit()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not is_admin():
        elevate()
    TimerApp().mainloop()
