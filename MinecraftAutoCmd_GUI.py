import tkinter as tk
from tkinter import ttk, messagebox, font
import time
import pyautogui
import keyboard
import threading
import json
import os
import sys
from datetime import datetime
import math


class ModernMinecraftGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Minecraft Auto Command Sender Pro")
        self.root.geometry("800x600")
        self.root.resizable(False, False)

        # Конфігурація
        self.config_file = "specs/minecraft_auto_config.json"
        self.default_config = {"command": "/htc10", "interval": 10}
        self.load_config()

        # Стан програми
        self.running = False
        self.thread = None
        self.commands_sent = 0
        self.start_time = None

        # Кольори та стилі
        self.colors = {
            'bg': '#0a0a0a',
            'secondary': '#1a1a1a',
            'accent': '#00ff88',
            'accent_hover': '#00cc6a',
            'danger': '#ff4444',
            'danger_hover': '#cc3333',
            'text': '#ffffff',
            'text_secondary': '#aaaaaa',
            'success': '#44ff44',
            'warning': '#ffaa00'
        }

        self.setup_styles()
        self.create_gui()
        self.setup_hotkeys()
        self.update_status()

        # Анімація
        self.animation_step = 0
        self.animate_background()

    def get_config_path(self):
        if getattr(sys, 'frozen', False):
            return os.path.join(os.path.dirname(sys.executable), self.config_file)
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), self.config_file)

    def load_config(self):
        config_path = self.get_config_path()
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.command = config.get("command", self.default_config["command"])
                self.interval = config.get("interval", self.default_config["interval"])
            else:
                self.command = self.default_config["command"]
                self.interval = self.default_config["interval"]
                self.save_config()
        except Exception:
            self.command = self.default_config["command"]
            self.interval = self.default_config["interval"]

    def save_config(self):
        config_path = self.get_config_path()
        try:
            config = {"command": self.command, "interval": self.interval}
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def setup_styles(self):
        self.root.configure(bg=self.colors['bg'])

        # Кастомні шрифти
        self.font_title = font.Font(family="Segoe UI", size=24, weight="bold")
        self.font_header = font.Font(family="Segoe UI", size=16, weight="bold")
        self.font_normal = font.Font(family="Segoe UI", size=12)
        self.font_small = font.Font(family="Segoe UI", size=10)

        # Стилі для ttk
        style = ttk.Style()
        style.theme_use('clam')

        # Кнопки
        style.configure('Accent.TButton',
                        background=self.colors['accent'],
                        foreground='black',
                        font=('Segoe UI', 12, 'bold'),
                        focuscolor='none',
                        borderwidth=0,
                        relief='flat')

        style.map('Accent.TButton',
                  background=[('active', self.colors['accent_hover'])])

        style.configure('Danger.TButton',
                        background=self.colors['danger'],
                        foreground='white',
                        font=('Segoe UI', 12, 'bold'),
                        focuscolor='none',
                        borderwidth=0,
                        relief='flat')

    def create_gui(self):
        # Головний контейнер
        main_frame = tk.Frame(self.root, bg=self.colors['bg'])
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Заголовок з анімацією
        self.title_frame = tk.Frame(main_frame, bg=self.colors['bg'])
        self.title_frame.pack(fill='x', pady=(0, 30))

        # Анімований заголовок
        self.title_label = tk.Label(
            self.title_frame,
            text="🎮 MINECRAFT AUTO COMMANDER 🚀",
            font=self.font_title,
            bg=self.colors['bg'],
            fg=self.colors['accent']
        )
        self.title_label.pack()

        subtitle = tk.Label(
            self.title_frame,
            text="Professional Command Automation Tool",
            font=self.font_small,
            bg=self.colors['bg'],
            fg=self.colors['text_secondary']
        )
        subtitle.pack(pady=(5, 0))

        # Основний контент
        content_frame = tk.Frame(main_frame, bg=self.colors['secondary'], relief='raised', bd=2)
        content_frame.pack(fill='both', expand=True, padx=10, pady=10)

        # Верхня панель зі статусом
        self.create_status_panel(content_frame)

        # Панель налаштувань
        self.create_settings_panel(content_frame)

        # Панель управління
        self.create_control_panel(content_frame)

        # Панель статистики
        self.create_stats_panel(content_frame)

        # Панель логів
        self.create_log_panel(content_frame)

    def create_status_panel(self, parent):
        status_frame = tk.Frame(parent, bg=self.colors['secondary'])
        status_frame.pack(fill='x', padx=20, pady=(20, 10))

        # Індикатор статусу
        self.status_indicator = tk.Label(
            status_frame,
            text="●",
            font=('Segoe UI', 20),
            bg=self.colors['secondary'],
            fg=self.colors['danger']
        )
        self.status_indicator.pack(side='left')

        self.status_label = tk.Label(
            status_frame,
            text="ЗУПИНЕНО",
            font=self.font_header,
            bg=self.colors['secondary'],
            fg=self.colors['text']
        )
        self.status_label.pack(side='left', padx=(10, 0))

        # Час роботи
        self.uptime_label = tk.Label(
            status_frame,
            text="Час роботи: 00:00:00",
            font=self.font_normal,
            bg=self.colors['secondary'],
            fg=self.colors['text_secondary']
        )
        self.uptime_label.pack(side='right')

    def create_settings_panel(self, parent):
        settings_frame = tk.LabelFrame(
            parent,
            text="⚙️ Налаштування",
            font=self.font_header,
            bg=self.colors['secondary'],
            fg=self.colors['accent'],
            relief='flat',
            bd=2
        )
        settings_frame.pack(fill='x', padx=20, pady=10)

        # Команда
        cmd_frame = tk.Frame(settings_frame, bg=self.colors['secondary'])
        cmd_frame.pack(fill='x', padx=15, pady=10)

        tk.Label(
            cmd_frame,
            text="🎯 Команда:",
            font=self.font_normal,
            bg=self.colors['secondary'],
            fg=self.colors['text']
        ).pack(side='left')

        self.command_var = tk.StringVar(value=self.command)
        self.command_entry = tk.Entry(
            cmd_frame,
            textvariable=self.command_var,
            font=self.font_normal,
            bg='#2a2a2a',
            fg=self.colors['text'],
            insertbackground=self.colors['accent'],
            relief='flat',
            bd=5,
            width=30
        )
        self.command_entry.pack(side='left', padx=(10, 0), fill='x', expand=True)

        # Інтервал
        interval_frame = tk.Frame(settings_frame, bg=self.colors['secondary'])
        interval_frame.pack(fill='x', padx=15, pady=(0, 10))

        tk.Label(
            interval_frame,
            text="⏱️ Інтервал:",
            font=self.font_normal,
            bg=self.colors['secondary'],
            fg=self.colors['text']
        ).pack(side='left')

        self.interval_var = tk.StringVar(value=str(self.interval))
        self.interval_entry = tk.Entry(
            interval_frame,
            textvariable=self.interval_var,
            font=self.font_normal,
            bg='#2a2a2a',
            fg=self.colors['text'],
            insertbackground=self.colors['accent'],
            relief='flat',
            bd=5,
            width=10
        )
        self.interval_entry.pack(side='left', padx=(10, 0))

        tk.Label(
            interval_frame,
            text="секунд",
            font=self.font_normal,
            bg=self.colors['secondary'],
            fg=self.colors['text_secondary']
        ).pack(side='left', padx=(5, 0))

    def create_control_panel(self, parent):
        control_frame = tk.Frame(parent, bg=self.colors['secondary'])
        control_frame.pack(fill='x', padx=20, pady=20)

        # Кнопка запуску/зупинки
        self.main_btn = tk.Button(
            control_frame,
            text="🚀 ЗАПУСТИТИ",
            font=('Segoe UI', 14, 'bold'),
            bg=self.colors['accent'],
            fg='black',
            relief='flat',
            bd=0,
            padx=30,
            pady=15,
            command=self.toggle_automation,
            cursor='hand2'
        )
        self.main_btn.pack(side='left', padx=(0, 10))

        # Кнопка збереження
        save_btn = tk.Button(
            control_frame,
            text="💾 ЗБЕРЕГТИ",
            font=('Segoe UI', 12, 'bold'),
            bg='#4a4a4a',
            fg=self.colors['text'],
            relief='flat',
            bd=0,
            padx=20,
            pady=10,
            command=self.save_settings,
            cursor='hand2'
        )
        save_btn.pack(side='left', padx=5)

        # Кнопка тестування
        test_btn = tk.Button(
            control_frame,
            text="🧪 ТЕСТ",
            font=('Segoe UI', 12, 'bold'),
            bg='#4a4a4a',
            fg=self.colors['text'],
            relief='flat',
            bd=0,
            padx=20,
            pady=10,
            command=self.test_command,
            cursor='hand2'
        )
        test_btn.pack(side='left', padx=5)

    def create_stats_panel(self, parent):
        stats_frame = tk.LabelFrame(
            parent,
            text="📊 Статистика",
            font=self.font_header,
            bg=self.colors['secondary'],
            fg=self.colors['accent'],
            relief='flat',
            bd=2
        )
        stats_frame.pack(fill='x', padx=20, pady=10)

        stats_inner = tk.Frame(stats_frame, bg=self.colors['secondary'])
        stats_inner.pack(fill='x', padx=15, pady=10)

        # Відправлено команд
        self.commands_label = tk.Label(
            stats_inner,
            text=f"📤 Відправлено команд: {self.commands_sent}",
            font=self.font_normal,
            bg=self.colors['secondary'],
            fg=self.colors['text']
        )
        self.commands_label.pack(side='left')

        # Наступна команда через
        self.next_cmd_label = tk.Label(
            stats_inner,
            text="⏳ Наступна команда через: --",
            font=self.font_normal,
            bg=self.colors['secondary'],
            fg=self.colors['text_secondary']
        )
        self.next_cmd_label.pack(side='right')

    def create_log_panel(self, parent):
        log_frame = tk.LabelFrame(
            parent,
            text="📋 Лог подій",
            font=self.font_header,
            bg=self.colors['secondary'],
            fg=self.colors['accent'],
            relief='flat',
            bd=2
        )
        log_frame.pack(fill='both', expand=True, padx=20, pady=(10, 20))

        # Текстове поле для логів
        self.log_text = tk.Text(
            log_frame,
            font=('Consolas', 10),
            bg='#1a1a1a',
            fg=self.colors['text'],
            insertbackground=self.colors['accent'],
            relief='flat',
            bd=10,
            height=8,
            wrap='word'
        )

        # Скролбар
        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side='right', fill='y')
        self.log_text.pack(side='left', fill='both', expand=True, padx=(15, 0), pady=10)

        # Початковий лог
        self.add_log("🚀 Minecraft Auto Commander запущено!")
        self.add_log(f"⚙️ Завантажено налаштування: команда='{self.command}', інтервал={self.interval}с")

    def add_log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"

        self.log_text.config(state='normal')
        self.log_text.insert('end', log_entry)
        self.log_text.config(state='disabled')
        self.log_text.see('end')

    def animate_background(self):
        # Анімація заголовка
        self.animation_step += 0.1
        brightness = int(127 + 127 * math.sin(self.animation_step))
        color = f"#{brightness:02x}ff{brightness // 2:02x}"
        self.title_label.configure(fg=color)

        # Анімація індикатора статусу
        if self.running:
            pulse = int(100 + 155 * abs(math.sin(self.animation_step * 2)))
            status_color = f"#{pulse:02x}{pulse:02x}44"
            self.status_indicator.configure(fg=status_color)

        self.root.after(50, self.animate_background)

    def setup_hotkeys(self):
        try:
            keyboard.add_hotkey('f8', self.toggle_automation)
            keyboard.add_hotkey('f9', self.stop_automation)
            keyboard.add_hotkey('f10', self.test_command)
            self.add_log("🎹 Гарячі клавіші налаштовано (F8-старт/стоп, F9-стоп, F10-тест)")
        except Exception as e:
            self.add_log(f"⚠️ Помилка налаштування гарячих клавіш: {e}")

    def send_command(self):
        try:
            # Відкриваємо чат
            pyautogui.press('t')
            time.sleep(0.2)

            # Очищуємо поле чату
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.1)

            # Вводимо команду
            keyboard.write(self.command)
            time.sleep(0.1)

            # Відправляємо
            pyautogui.press('enter')

            self.commands_sent += 1
            self.add_log(f"✅ Команда '{self.command}' відправлена ({self.commands_sent})")

        except Exception as e:
            self.add_log(f"❌ Помилка відправки команди: {e}")

    def auto_send_loop(self):
        countdown = self.interval
        while self.running:
            if countdown <= 0:
                self.send_command()
                countdown = self.interval
            else:
                # Оновлення лічильника
                self.root.after(0, lambda: self.next_cmd_label.configure(
                    text=f"⏳ Наступна команда через: {countdown}с"))
                countdown -= 1

            time.sleep(1)

    def toggle_automation(self):
        if not self.running:
            self.start_automation()
        else:
            self.stop_automation()

    def start_automation(self):
        if not self.save_settings():
            return

        self.running = True
        self.start_time = datetime.now()
        self.thread = threading.Thread(target=self.auto_send_loop)
        self.thread.daemon = True
        self.thread.start()

        self.main_btn.configure(
            text="🛑 ЗУПИНИТИ",
            bg=self.colors['danger']
        )

        self.status_indicator.configure(fg=self.colors['success'])
        self.status_label.configure(text="ПРАЦЮЄ", fg=self.colors['success'])

        self.add_log(f"🚀 Автоматичне відправлення запущено! Команда: '{self.command}', інтервал: {self.interval}с")

    def stop_automation(self):
        self.running = False

        self.main_btn.configure(
            text="🚀 ЗАПУСТИТИ",
            bg=self.colors['accent']
        )

        self.status_indicator.configure(fg=self.colors['danger'])
        self.status_label.configure(text="ЗУПИНЕНО", fg=self.colors['text'])
        self.next_cmd_label.configure(text="⏳ Наступна команда через: --")

        self.add_log("⏹️ Автоматичне відправлення зупинено")

    def test_command(self):
        if self.save_settings():
            self.add_log("🧪 Тестування команди...")
            threading.Thread(target=lambda: (time.sleep(1), self.send_command()), daemon=True).start()

    def save_settings(self):
        try:
            new_command = self.command_var.get().strip()
            new_interval = int(self.interval_var.get().strip())

            if not new_command:
                messagebox.showerror("Помилка", "Команда не може бути пустою!")
                return False

            if new_interval <= 0:
                messagebox.showerror("Помилка", "Інтервал має бути більше 0!")
                return False

            self.command = new_command
            self.interval = new_interval
            self.save_config()

            self.add_log(f"💾 Налаштування збережено: команда='{self.command}', інтервал={self.interval}с")
            return True

        except ValueError:
            messagebox.showerror("Помилка", "Інтервал має бути числом!")
            return False
        except Exception as e:
            messagebox.showerror("Помилка", f"Помилка збереження: {e}")
            return False

    def update_status(self):
        # Оновлення статистики
        self.commands_label.configure(text=f"📤 Відправлено команд: {self.commands_sent}")

        # Оновлення часу роботи
        if self.start_time and self.running:
            uptime = datetime.now() - self.start_time
            hours, remainder = divmod(int(uptime.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            self.uptime_label.configure(text=f"Час роботи: {hours:02d}:{minutes:02d}:{seconds:02d}")
        else:
            self.uptime_label.configure(text="Час роботи: 00:00:00")

        self.root.after(1000, self.update_status)

    def on_closing(self):
        if self.running:
            if messagebox.askokcancel("Вихід", "Зупинити автоматичне відправлення та вийти?"):
                self.stop_automation()
                self.root.destroy()
        else:
            self.root.destroy()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()


def main():
    try:
        app = ModernMinecraftGUI()
        app.run()
    except Exception as e:
        messagebox.showerror("Критична помилка", f"Помилка запуску програми: {e}")


if __name__ == "__main__":
    main()