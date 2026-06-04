"""Desktop-панель керування Discord-ботом (tkinter).

Супервізує бота як підпроцес (запуск/стоп/рестарт + автоперезапуск при падінні),
показує живий лог, статус (зі status.json) і дає редагувати .env.

Запуск:  python panel/app.py   (або panel/start_panel.bat без консолі)
"""
import json
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "discord_bot" / "data"
STATUS_FILE = DATA_DIR / "status.json"
ENV_FILE = ROOT / ".env"
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
RESTART_DELAY = 10  # сек між автоперезапусками

BG = "#10131a"
CARD = "#1a1f2e"
ACCENT = "#00d4ff"
OK = "#22c55e"
DANGER = "#ef4444"
MUTED = "#8b95a7"
TEXT = "#e6e9ef"


class BotPanel(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🎮 Discord Bot — Панель керування")
        self.geometry("900x640")
        self.configure(bg=BG)

        self.proc: subprocess.Popen | None = None
        self._want = False                  # чи має бот працювати
        self._sup_thread: threading.Thread | None = None
        self._logq: queue.Queue[str] = queue.Queue()
        self.auto_restart = tk.BooleanVar(value=True)

        self._build_ui()
        self._poll_logs()
        self._poll_status()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------- UI ----------------

    def _build_ui(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=CARD, foreground=TEXT, padding=(14, 6))
        style.map("TNotebook.Tab", background=[("selected", ACCENT)],
                  foreground=[("selected", "#000000")])

        # Верхня панель статусу
        top = tk.Frame(self, bg=CARD)
        top.pack(fill="x", padx=10, pady=(10, 6))

        self.dot = tk.Label(top, text="●", font=("Segoe UI", 20), bg=CARD, fg=DANGER)
        self.dot.pack(side="left", padx=(12, 6), pady=10)

        info = tk.Frame(top, bg=CARD)
        info.pack(side="left", pady=10)
        self.state_lbl = tk.Label(info, text="ОФЛАЙН", font=("Segoe UI", 14, "bold"),
                                  bg=CARD, fg=TEXT, anchor="w")
        self.state_lbl.pack(anchor="w")
        self.detail_lbl = tk.Label(info, text="Бот не запущено", font=("Segoe UI", 10),
                                   bg=CARD, fg=MUTED, anchor="w")
        self.detail_lbl.pack(anchor="w")

        # Кнопки керування
        btns = tk.Frame(top, bg=CARD)
        btns.pack(side="right", padx=12)
        self.start_btn = self._mkbtn(btns, "▶ Запустити", OK, self.start_bot)
        self.start_btn.pack(side="left", padx=4)
        self.stop_btn = self._mkbtn(btns, "⏹ Зупинити", DANGER, self.stop_bot)
        self.stop_btn.pack(side="left", padx=4)
        self.restart_btn = self._mkbtn(btns, "⟳ Рестарт", ACCENT, self.restart_bot)
        self.restart_btn.pack(side="left", padx=4)
        tk.Checkbutton(btns, text="Авто-рестарт", variable=self.auto_restart,
                       bg=CARD, fg=MUTED, selectcolor=BG, activebackground=CARD,
                       activeforeground=TEXT).pack(side="left", padx=8)

        # Вкладки
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # --- лог ---
        logtab = tk.Frame(nb, bg=BG)
        nb.add(logtab, text="📋 Лог")
        self.log = tk.Text(logtab, bg="#0b0e14", fg=TEXT, insertbackground=ACCENT,
                           relief="flat", wrap="word", font=("Consolas", 10))
        sb = tk.Scrollbar(logtab, command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set, state="disabled")
        sb.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)

        # --- зараз грає ---
        nowtab = tk.Frame(nb, bg=BG)
        nb.add(nowtab, text="🎵 Сервери")
        self.players_box = tk.Text(nowtab, bg="#0b0e14", fg=TEXT, relief="flat",
                                   wrap="word", font=("Segoe UI", 11), state="disabled")
        self.players_box.pack(fill="both", expand=True)

        # --- .env ---
        envtab = tk.Frame(nb, bg=BG)
        nb.add(envtab, text="⚙️ .env")
        self.env_text = tk.Text(envtab, bg="#0b0e14", fg=TEXT, insertbackground=ACCENT,
                                relief="flat", wrap="none", font=("Consolas", 10))
        self.env_text.pack(fill="both", expand=True, padx=4, pady=4)
        envbar = tk.Frame(envtab, bg=BG)
        envbar.pack(fill="x")
        self._mkbtn(envbar, "↻ Перечитати", MUTED, self._load_env).pack(side="left", padx=4, pady=4)
        self._mkbtn(envbar, "💾 Зберегти", OK, self._save_env).pack(side="left", padx=4, pady=4)
        tk.Label(envbar, text="(зміни застосуються після рестарту бота)",
                 bg=BG, fg=MUTED, font=("Segoe UI", 9)).pack(side="left", padx=8)
        self._load_env()

    def _mkbtn(self, parent, text, color, cmd):
        return tk.Button(parent, text=text, command=cmd, bg=color, fg="#000000",
                         relief="flat", bd=0, padx=12, pady=6, cursor="hand2",
                         font=("Segoe UI", 10, "bold"), activebackground=color)

    # ---------------- супервізор ----------------

    def start_bot(self):
        if self._want:
            return
        self._want = True
        self._sup_thread = threading.Thread(target=self._supervise, daemon=True)
        self._sup_thread.start()

    def stop_bot(self):
        self._want = False
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
            except Exception:
                pass
        self._log("--- Зупинка за запитом ---")

    def restart_bot(self):
        if self.proc and self.proc.poll() is None:
            self._log("--- Рестарт ---")
            try:
                self.proc.terminate()  # супервізор підніме знову (якщо _want)
            except Exception:
                pass
        else:
            self.start_bot()

    def _supervise(self):
        py = str(PYTHON) if PYTHON.exists() else sys.executable
        while self._want:
            try:
                self.proc = subprocess.Popen(
                    [py, "run_bot.py"], cwd=str(ROOT),
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace", bufsize=1,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            except Exception as e:
                self._logq.put(f"--- Не вдалося запустити: {e} ---")
                self._want = False
                break
            self._logq.put(f"--- Запуск бота (PID {self.proc.pid}) ---")
            for line in self.proc.stdout:
                self._logq.put(line.rstrip("\n"))
            code = self.proc.wait()
            self.proc = None
            self._logq.put(f"--- Бот завершився (код {code}) ---")
            if not self._want or not self.auto_restart.get():
                break
            for _ in range(RESTART_DELAY):
                if not self._want:
                    break
                time.sleep(1)
        self._want = False
        self._logq.put("--- Супервізор зупинено ---")

    # ---------------- лог / статус ----------------

    def _log(self, msg):
        self._logq.put(msg)

    def _poll_logs(self):
        appended = False
        while not self._logq.empty():
            line = self._logq.get_nowait()
            self.log.configure(state="normal")
            self.log.insert("end", line + "\n")
            self.log.configure(state="disabled")
            appended = True
        if appended:
            self.log.see("end")
        self.after(150, self._poll_logs)

    def _poll_status(self):
        connected = False
        detail = "Бот не запущено"
        players_text = "—"
        if STATUS_FILE.exists():
            try:
                data = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
                fresh = (time.time() - data.get("ts", 0)) < 15
                if data.get("online") and fresh:
                    connected = True
                    detail = (f"{data.get('user', '?')} • {data.get('guilds', 0)} серв. "
                              f"• аптайм {self._fmt(data.get('uptime', 0))}")
                    players = data.get("players", [])
                    if players:
                        players_text = "\n".join(
                            f"🎧 {p['guild']}: "
                            + (f"▶ {p['current']}" if p.get("current") else "—")
                            + (f"  (черга: {p['queue']})" if p.get("queue") else "")
                            for p in players
                        )
                    else:
                        players_text = "Немає активних плеєрів."
            except Exception:
                pass

        proc_running = self.proc is not None and self.proc.poll() is None
        if connected:
            self.dot.config(fg=OK)
            self.state_lbl.config(text="ОНЛАЙН")
        elif proc_running or self._want:
            self.dot.config(fg="#eab308")
            self.state_lbl.config(text="ЗАПУСК...")
            detail = "Процес працює, очікую підключення до Discord..."
        else:
            self.dot.config(fg=DANGER)
            self.state_lbl.config(text="ОФЛАЙН")
        self.detail_lbl.config(text=detail)

        self.players_box.configure(state="normal")
        self.players_box.delete("1.0", "end")
        self.players_box.insert("1.0", players_text)
        self.players_box.configure(state="disabled")

        self.after(2000, self._poll_status)

    @staticmethod
    def _fmt(sec):
        sec = int(sec)
        h, r = divmod(sec, 3600)
        m, s = divmod(r, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    # ---------------- .env ----------------

    def _load_env(self):
        text = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
        self.env_text.delete("1.0", "end")
        self.env_text.insert("1.0", text)

    def _save_env(self):
        try:
            ENV_FILE.write_text(self.env_text.get("1.0", "end-1c"), encoding="utf-8")
            messagebox.showinfo("Збережено", "Файл .env збережено.\nРестартни бота, щоб застосувати.")
        except Exception as e:
            messagebox.showerror("Помилка", f"Не вдалося зберегти .env:\n{e}")

    # ---------------- закриття ----------------

    def _on_close(self):
        if self._want or (self.proc and self.proc.poll() is None):
            if not messagebox.askyesno("Вихід", "Зупинити бота і вийти?"):
                return
            self.stop_bot()
            time.sleep(0.3)
        self.destroy()


if __name__ == "__main__":
    app = BotPanel()
    if "--autostart" in sys.argv:
        app.after(500, app.start_bot)  # одразу піднімати бота (для автозапуску)
    app.mainloop()
