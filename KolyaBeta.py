import tkinter as tk
from tkinter import ttk, messagebox, font, Canvas
import time
import pyautogui
import keyboard
import threading
import json
import os
import sys
from datetime import datetime
import math
import random


class UltraModernMinecraftGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🎮 Minecraft Auto Commander ULTRA PRO 🚀")
        self.root.geometry("1000x700")
        self.root.resizable(True, True)
        self.root.configure(bg='#000000')

        # Конфігурація
        self.config_file = "specs/minecraft_auto_config.json"
        self.default_config = {
            "command": "/htc10",
            "interval": 10,
            "hotkeys": {
                "toggle": "f8",
                "stop": "f9",
                "test": "f10"
            }
        }
        self.load_config()

        # Стан програми
        self.running = False
        self.thread = None
        self.commands_sent = 0
        self.start_time = None
        self.particles = []
        self.command_history = []

        # Кольори та стилі
        self.colors = {
            'bg_primary': '#0a0a0f',
            'bg_secondary': '#1a1a2e',
            'bg_card': '#16213e',
            'bg_input': '#0f172a',
            'accent_primary': '#00ff88',
            'accent_secondary': '#00d4ff',
            'accent_purple': '#a855f7',
            'accent_pink': '#ec4899',
            'danger': '#ff3366',
            'warning': '#ffcc00',
            'success': '#22ff22',
            'text_primary': '#ffffff',
            'text_secondary': '#94a3b8',
            'text_muted': '#64748b',
            'glow': '#00ff8844'
        }

        self.setup_styles()
        self.create_background_canvas()
        self.create_gui()
        self.setup_hotkeys()
        self.update_status()
        self.animate_effects()
        self.create_particles()

    def setup_styles(self):
        # Встановлення шрифтів
        self.fonts = {
            'title': font.Font(family="Segoe UI", size=28, weight="bold"),
            'subtitle': font.Font(family="Segoe UI", size=14, weight="normal"),
            'header': font.Font(family="Segoe UI", size=18, weight="bold"),
            'normal': font.Font(family="Segoe UI", size=12, weight="normal"),
            'button': font.Font(family="Segoe UI", size=13, weight="bold"),
            'mono': font.Font(family="Consolas", size=11, weight="normal"),
            'small': font.Font(family="Segoe UI", size=10, weight="normal")
        }

    def create_background_canvas(self):
        """Створює анімований фон з ефектами"""
        self.bg_canvas = Canvas(
            self.root,
            highlightthickness=0,
            bg=self.colors['bg_primary']
        )
        self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)

        # Анімований градієнт
        self.animation_frame = 0

    def create_particles(self):
        """Створює систему частинок"""
        for _ in range(50):
            self.particles.append({
                'x': random.randint(0, 1000),
                'y': random.randint(0, 700),
                'vx': random.uniform(-1, 1),
                'vy': random.uniform(-1, 1),
                'size': random.uniform(1, 3),
                'alpha': random.uniform(0.2, 0.8)
            })

    def animate_particles(self):
        """Анімує частинки на фоні"""
        self.bg_canvas.delete("particle")

        for particle in self.particles:
            particle['x'] += particle['vx']
            particle['y'] += particle['vy']

            # Відбивання від стінок
            if particle['x'] <= 0 or particle['x'] >= 1000:
                particle['vx'] *= -1
            if particle['y'] <= 0 or particle['y'] >= 700:
                particle['vy'] *= -1

            # Обмеження позиції
            particle['x'] = max(0, min(1000, particle['x']))
            particle['y'] = max(0, min(700, particle['y']))

            # Малюємо частинку
            alpha = int(particle['alpha'] * 255)
            color = f"#{alpha:02x}{alpha:02x}{alpha // 2:02x}"

            self.bg_canvas.create_oval(
                particle['x'], particle['y'],
                particle['x'] + particle['size'],
                particle['y'] + particle['size'],
                fill=color, outline="", tags="particle"
            )

    def create_gui(self):
        # Головний контейнер з прозорістю
        self.main_frame = tk.Frame(
            self.root,
            bg=self.colors['bg_primary'],
            relief='flat'
        )
        self.main_frame.place(relx=0.05, rely=0.02, relwidth=0.9, relheight=0.96)

        # Заголовок з ефектами
        self.create_header()

        # Основний контент
        self.create_main_content()

    def create_header(self):
        """Створює заголовок з ефектами"""
        header_frame = tk.Frame(
            self.main_frame,
            bg=self.colors['bg_primary'],
            height=120
        )
        header_frame.pack(fill='x', pady=(0, 20))
        header_frame.pack_propagate(False)

        # Анімований заголовок
        self.title_canvas = Canvas(
            header_frame,
            height=80,
            bg=self.colors['bg_primary'],
            highlightthickness=0
        )
        self.title_canvas.pack(fill='x', pady=10)

        # Підзаголовок
        subtitle_frame = tk.Frame(header_frame, bg=self.colors['bg_primary'])
        subtitle_frame.pack(fill='x')

        tk.Label(
            subtitle_frame,
            text="🚀 Professional Command Automation Suite",
            font=self.fonts['subtitle'],
            bg=self.colors['bg_primary'],
            fg=self.colors['text_secondary']
        ).pack()

        version_label = tk.Label(
            subtitle_frame,
            text="v3.0 Ultra Edition • Made with ❤️ for Minecraft",
            font=self.fonts['small'],
            bg=self.colors['bg_primary'],
            fg=self.colors['text_muted']
        )
        version_label.pack()

    def create_main_content(self):
        """Створює основний контент"""
        # Скроловане вікно
        canvas = Canvas(
            self.main_frame,
            bg=self.colors['bg_primary'],
            highlightthickness=0
        )
        scrollbar = ttk.Scrollbar(self.main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.colors['bg_primary'])

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Статусна панель
        self.create_status_dashboard(scrollable_frame)

        # Налаштування
        self.create_settings_section(scrollable_frame)

        # Гарячі клавіші
        self.create_hotkeys_section(scrollable_frame)

        # Управління
        self.create_control_section(scrollable_frame)

        # Статистика
        self.create_statistics_section(scrollable_frame)

        # Лог подій
        self.create_log_section(scrollable_frame)

    def create_glass_card(self, parent, title, height=None):
        """Створює карточку зі скляним ефектом"""
        card = tk.Frame(
            parent,
            bg=self.colors['bg_card'],
            relief='raised',
            bd=1
        )

        if height:
            card.config(height=height)
            card.pack_propagate(False)

        card.pack(fill='x', padx=10, pady=10)

        # Заголовок карточки
        header = tk.Frame(card, bg=self.colors['bg_card'])
        header.pack(fill='x', padx=15, pady=(15, 5))

        title_label = tk.Label(
            header,
            text=title,
            font=self.fonts['header'],
            bg=self.colors['bg_card'],
            fg=self.colors['accent_primary']
        )
        title_label.pack(side='left')

        # Декоративна лінія
        line = tk.Frame(card, bg=self.colors['accent_primary'], height=2)
        line.pack(fill='x', padx=15)

        return card

    def create_status_dashboard(self, parent):
        """Створює статусну панель"""
        card = self.create_glass_card(parent, "📊 System Dashboard", 120)

        content = tk.Frame(card, bg=self.colors['bg_card'])
        content.pack(fill='both', expand=True, padx=15, pady=10)

        # Лівий блок - статус
        left_frame = tk.Frame(content, bg=self.colors['bg_card'])
        left_frame.pack(side='left', fill='y')

        status_container = tk.Frame(left_frame, bg=self.colors['bg_card'])
        status_container.pack(anchor='w')

        self.status_indicator = tk.Label(
            status_container,
            text="●",
            font=('Segoe UI', 24),
            bg=self.colors['bg_card'],
            fg=self.colors['danger']
        )
        self.status_indicator.pack(side='left')

        status_text = tk.Frame(status_container, bg=self.colors['bg_card'])
        status_text.pack(side='left', padx=(10, 0), fill='y')

        self.status_label = tk.Label(
            status_text,
            text="SYSTEM OFFLINE",
            font=self.fonts['header'],
            bg=self.colors['bg_card'],
            fg=self.colors['text_primary'],
            anchor='w'
        )
        self.status_label.pack(anchor='w')

        self.status_desc = tk.Label(
            status_text,
            text="Ready to start automation",
            font=self.fonts['normal'],
            bg=self.colors['bg_card'],
            fg=self.colors['text_secondary'],
            anchor='w'
        )
        self.status_desc.pack(anchor='w')

        # Правий блок - статистика
        right_frame = tk.Frame(content, bg=self.colors['bg_card'])
        right_frame.pack(side='right', fill='y')

        self.uptime_label = tk.Label(
            right_frame,
            text="⏱️ Uptime: 00:00:00",
            font=self.fonts['normal'],
            bg=self.colors['bg_card'],
            fg=self.colors['text_secondary']
        )
        self.uptime_label.pack(anchor='e')

        self.next_cmd_label = tk.Label(
            right_frame,
            text="🎯 Next command: --",
            font=self.fonts['normal'],
            bg=self.colors['bg_card'],
            fg=self.colors['text_secondary']
        )
        self.next_cmd_label.pack(anchor='e')

    def create_settings_section(self, parent):
        """Створює секцію налаштувань"""
        card = self.create_glass_card(parent, "⚙️ Configuration Settings")

        content = tk.Frame(card, bg=self.colors['bg_card'])
        content.pack(fill='x', padx=15, pady=10)

        # Команда
        cmd_frame = tk.Frame(content, bg=self.colors['bg_card'])
        cmd_frame.pack(fill='x', pady=10)

        tk.Label(
            cmd_frame,
            text="🎯 Command:",
            font=self.fonts['normal'],
            bg=self.colors['bg_card'],
            fg=self.colors['text_primary']
        ).pack(side='left')

        self.command_var = tk.StringVar(value=self.command)
        cmd_entry_frame = tk.Frame(cmd_frame, bg=self.colors['bg_input'], relief='solid', bd=1)
        cmd_entry_frame.pack(side='right', fill='x', expand=True, padx=(10, 0))

        self.command_entry = tk.Entry(
            cmd_entry_frame,
            textvariable=self.command_var,
            font=self.fonts['mono'],
            bg=self.colors['bg_input'],
            fg=self.colors['text_primary'],
            insertbackground=self.colors['accent_primary'],
            relief='flat',
            bd=8
        )
        self.command_entry.pack(fill='x', padx=2, pady=2)

        # Інтервал
        interval_frame = tk.Frame(content, bg=self.colors['bg_card'])
        interval_frame.pack(fill='x', pady=10)

        tk.Label(
            interval_frame,
            text="⏱️ Interval:",
            font=self.fonts['normal'],
            bg=self.colors['bg_card'],
            fg=self.colors['text_primary']
        ).pack(side='left')

        interval_container = tk.Frame(interval_frame, bg=self.colors['bg_card'])
        interval_container.pack(side='right')

        self.interval_var = tk.StringVar(value=str(self.interval))
        interval_entry_frame = tk.Frame(interval_container, bg=self.colors['bg_input'], relief='solid', bd=1)
        interval_entry_frame.pack(side='left')

        self.interval_entry = tk.Entry(
            interval_entry_frame,
            textvariable=self.interval_var,
            font=self.fonts['mono'],
            bg=self.colors['bg_input'],
            fg=self.colors['text_primary'],
            insertbackground=self.colors['accent_primary'],
            relief='flat',
            bd=8,
            width=8
        )
        self.interval_entry.pack(padx=2, pady=2)

        tk.Label(
            interval_container,
            text=" seconds",
            font=self.fonts['normal'],
            bg=self.colors['bg_card'],
            fg=self.colors['text_secondary']
        ).pack(side='left', padx=(5, 0))

    def create_hotkeys_section(self, parent):
        """Створює секцію гарячих клавіш"""
        card = self.create_glass_card(parent, "🎹 Hotkey Configuration")

        content = tk.Frame(card, bg=self.colors['bg_card'])
        content.pack(fill='x', padx=15, pady=10)

        # Пояснення
        info_frame = tk.Frame(content, bg=self.colors['bg_secondary'], relief='solid', bd=1)
        info_frame.pack(fill='x', pady=(0, 15))

        tk.Label(
            info_frame,
            text="💡 Click on hotkey button to change it. Press ESC to cancel.",
            font=self.fonts['small'],
            bg=self.colors['bg_secondary'],
            fg=self.colors['text_secondary']
        ).pack(pady=8)

        # Гарячі клавіші
        hotkeys_data = [
            ("🚀 Toggle Automation", "toggle", "Start/Stop automation"),
            ("🛑 Force Stop", "stop", "Emergency stop"),
            ("🧪 Test Command", "test", "Send test command")
        ]

        self.hotkey_vars = {}
        self.hotkey_buttons = {}

        for title, key, desc in hotkeys_data:
            hk_frame = tk.Frame(content, bg=self.colors['bg_card'])
            hk_frame.pack(fill='x', pady=8)

            # Опис
            desc_frame = tk.Frame(hk_frame, bg=self.colors['bg_card'])
            desc_frame.pack(side='left', fill='x', expand=True)

            tk.Label(
                desc_frame,
                text=title,
                font=self.fonts['normal'],
                bg=self.colors['bg_card'],
                fg=self.colors['text_primary'],
                anchor='w'
            ).pack(anchor='w')

            tk.Label(
                desc_frame,
                text=desc,
                font=self.fonts['small'],
                bg=self.colors['bg_card'],
                fg=self.colors['text_muted'],
                anchor='w'
            ).pack(anchor='w')

            # Кнопка гарячої клавіші
            self.hotkey_vars[key] = tk.StringVar(value=self.hotkeys.get(key, "f8").upper())

            hotkey_btn = tk.Button(
                hk_frame,
                textvariable=self.hotkey_vars[key],
                font=self.fonts['button'],
                bg=self.colors['accent_secondary'],
                fg='black',
                relief='flat',
                bd=0,
                padx=20,
                pady=8,
                cursor='hand2',
                command=lambda k=key: self.change_hotkey(k)
            )
            hotkey_btn.pack(side='right')
            self.hotkey_buttons[key] = hotkey_btn

    def create_control_section(self, parent):
        """Створює секцію управління"""
        card = self.create_glass_card(parent, "🎮 Control Center")

        content = tk.Frame(card, bg=self.colors['bg_card'])
        content.pack(fill='x', padx=15, pady=15)

        # Головна кнопка
        main_btn_frame = tk.Frame(content, bg=self.colors['bg_card'])
        main_btn_frame.pack(fill='x', pady=(0, 15))

        self.main_btn = tk.Button(
            main_btn_frame,
            text="🚀 START AUTOMATION",
            font=('Segoe UI', 16, 'bold'),
            bg=self.colors['accent_primary'],
            fg='black',
            relief='flat',
            bd=0,
            padx=40,
            pady=20,
            command=self.toggle_automation,
            cursor='hand2'
        )
        self.main_btn.pack(expand=True)

        # Додаткові кнопки
        buttons_frame = tk.Frame(content, bg=self.colors['bg_card'])
        buttons_frame.pack(fill='x')

        buttons_data = [
            ("💾 SAVE", self.save_settings, self.colors['accent_secondary']),
            ("🧪 TEST", self.test_command, self.colors['warning']),
            ("🗑️ CLEAR LOG", self.clear_log, self.colors['text_muted']),
            ("📊 RESET STATS", self.reset_stats, self.colors['danger'])
        ]

        for i, (text, command, color) in enumerate(buttons_data):
            btn = tk.Button(
                buttons_frame,
                text=text,
                font=self.fonts['button'],
                bg=color,
                fg='black' if color != self.colors['text_muted'] else 'white',
                relief='flat',
                bd=0,
                padx=15,
                pady=10,
                command=command,
                cursor='hand2'
            )
            btn.pack(side='left', padx=5, fill='x', expand=True)

    def create_statistics_section(self, parent):
        """Створює секцію статистики"""
        card = self.create_glass_card(parent, "📈 Performance Analytics")

        content = tk.Frame(card, bg=self.colors['bg_card'])
        content.pack(fill='x', padx=15, pady=10)

        # Статистика у вигляді карточок
        stats_grid = tk.Frame(content, bg=self.colors['bg_card'])
        stats_grid.pack(fill='x', pady=10)

        # Перший рядок статистики
        row1 = tk.Frame(stats_grid, bg=self.colors['bg_card'])
        row1.pack(fill='x', pady=5)

        self.create_stat_card(row1, "📤", "Commands Sent", "0", self.colors['accent_primary'])
        self.create_stat_card(row1, "⚡", "Success Rate", "100%", self.colors['success'])
        self.create_stat_card(row1, "🕐", "Average Interval", "10s", self.colors['accent_secondary'])

        # Другий рядок статистики
        row2 = tk.Frame(stats_grid, bg=self.colors['bg_card'])
        row2.pack(fill='x', pady=5)

        self.create_stat_card(row2, "📊", "Session Time", "00:00:00", self.colors['accent_purple'])
        self.create_stat_card(row2, "🎯", "Last Command", "--", self.colors['accent_pink'])
        self.create_stat_card(row2, "⏳", "Next In", "--", self.colors['warning'])

    def create_stat_card(self, parent, icon, title, value, color):
        """Створює карточку статистики"""
        card = tk.Frame(parent, bg=self.colors['bg_secondary'], relief='solid', bd=1)
        card.pack(side='left', fill='x', expand=True, padx=3, pady=2)

        # Іконка
        tk.Label(
            card,
            text=icon,
            font=('Segoe UI', 20),
            bg=self.colors['bg_secondary'],
            fg=color
        ).pack(pady=(8, 0))

        # Значення
        value_label = tk.Label(
            card,
            text=value,
            font=self.fonts['header'],
            bg=self.colors['bg_secondary'],
            fg=self.colors['text_primary']
        )
        value_label.pack()

        # Заголовок
        tk.Label(
            card,
            text=title,
            font=self.fonts['small'],
            bg=self.colors['bg_secondary'],
            fg=self.colors['text_muted']
        ).pack(pady=(0, 8))

        # Зберігаємо посилання для оновлення
        if not hasattr(self, 'stat_labels'):
            self.stat_labels = {}

        key = title.lower().replace(' ', '_')
        self.stat_labels[key] = value_label

    def create_log_section(self, parent):
        """Створює секцію логів"""
        card = self.create_glass_card(parent, "📋 System Event Log", 250)

        content = tk.Frame(card, bg=self.colors['bg_card'])
        content.pack(fill='both', expand=True, padx=15, pady=10)

        # Лог з прокруткою
        log_container = tk.Frame(content, bg=self.colors['bg_input'], relief='solid', bd=1)
        log_container.pack(fill='both', expand=True)

        self.log_text = tk.Text(
            log_container,
            font=self.fonts['mono'],
            bg=self.colors['bg_input'],
            fg=self.colors['text_primary'],
            insertbackground=self.colors['accent_primary'],
            relief='flat',
            bd=8,
            wrap='word',
            selectbackground=self.colors['accent_primary'],
            selectforeground='black'
        )

        log_scroll = tk.Scrollbar(log_container, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)

        log_scroll.pack(side='right', fill='y')
        self.log_text.pack(side='left', fill='both', expand=True)

        # Початкові логи
        self.add_log("🚀 Minecraft Auto Commander ULTRA initialized!")
        self.add_log(f"⚙️ Loaded config: command='{self.command}', interval={self.interval}s")
        self.add_log("🎹 Hotkeys configured and ready")
        self.add_log("💡 System ready for automation")

    def change_hotkey(self, hotkey_type):
        """Змінює гарячу клавішу"""
        btn = self.hotkey_buttons[hotkey_type]
        btn.configure(text="Press key...", bg=self.colors['warning'])

        def on_key_event(e):
            if e.name == 'esc':
                btn.configure(
                    text=self.hotkey_vars[hotkey_type].get(),
                    bg=self.colors['accent_secondary']
                )
                keyboard.unhook_all()
                return

            # Оновлюємо гарячу клавішу
            new_key = e.name.upper()
            self.hotkeys[hotkey_type] = e.name
            self.hotkey_vars[hotkey_type].set(new_key)
            btn.configure(text=new_key, bg=self.colors['success'])

            # Зберігаємо та перенастроюємо гарячі клавіші
            self.save_config()
            keyboard.unhook_all()
            self.setup_hotkeys()

            self.add_log(f"🎹 Hotkey changed: {hotkey_type} -> {new_key}")

            # Повертаємо оригінальний колір через секунду
            self.root.after(1000, lambda: btn.configure(bg=self.colors['accent_secondary']))

        keyboard.on_press(on_key_event)

    def clear_log(self):
        """Очищує лог"""
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, 'end')
        self.log_text.config(state='disabled')
        self.add_log("🗑️ Log cleared")

    def reset_stats(self):
        """Скидає статистику"""
        if messagebox.askyesno("Reset Statistics", "Are you sure you want to reset all statistics?"):
            self.commands_sent = 0
            self.start_time = None
            self.command_history.clear()
            self.add_log("📊 Statistics reset")

    def load_config(self):
        """Завантажує конфігурацію"""
        config_path = self.get_config_path()
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.command = config.get("command", self.default_config["command"])
                self.interval = config.get("interval", self.default_config["interval"])
                self.hotkeys = config.get("hotkeys", self.default_config["hotkeys"])
            else:
                self.command = self.default_config["command"]
                self.interval = self.default_config["interval"]
                self.hotkeys = self.default_config["hotkeys"]
                self.save_config()
        except Exception:
            self.command = self.default_config["command"]
            self.interval = self.default_config["interval"]
            self.hotkeys = self.default_config["hotkeys"]

    def save_config(self):
        """Зберігає конфігурацію"""
        config_path = self.get_config_path()
        try:
            config = {
                "command": self.command,
                "interval": self.interval,
                "hotkeys": self.hotkeys
            }
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_config_path(self):
        """Отримує шлях до конфігурації"""
        if getattr(sys, 'frozen', False):
            return os.path.join(os.path.dirname(sys.executable), self.config_file)
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), self.config_file)

    def setup_hotkeys(self):
        """Налаштовує гарячі клавіші"""
        try:
            keyboard.unhook_all()
            keyboard.add_hotkey(self.hotkeys.get('toggle', 'f8'), self.toggle_automation)
            keyboard.add_hotkey(self.hotkeys.get('stop', 'f9'), self.stop_automation)
            keyboard.add_hotkey(self.hotkeys.get('test', 'f10'), self.test_command)
        except Exception as e:
            self.add_log(f"⚠️ Hotkey setup error: {e}")

    def send_command(self):
        """Відправляє команду"""
        try:
            pyautogui.press('t')
            time.sleep(0.2)
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.1)
            keyboard.write(self.command)
            time.sleep(0.1)
            pyautogui.press('enter')

            self.commands_sent += 1
            self.command_history.append({
                'command': self.command,
                'timestamp': datetime.now(),
                'success': True
            })

            self.add_log(f"✅ Command sent: '{self.command}' (#{self.commands_sent})")

        except Exception as e:
            self.add_log(f"❌ Command failed: {e}")
            self.command_history.append({
                'command': self.command,
                'timestamp': datetime.now(),
                'success': False,
                'error': str(e)
            })

    def auto_send_loop(self):
        """Основний цикл автоматичного відправлення"""
        countdown = self.interval
        while self.running:
            if countdown <= 0:
                self.send_command()
                countdown = self.interval
            else:
                # Оновлення UI з countdown
                self.root.after(0, self.update_countdown, countdown)
                countdown -= 1

            time.sleep(1)

    def update_countdown(self, countdown):
        """Оновлює відлік"""
        if hasattr(self, 'stat_labels') and 'next_in' in self.stat_labels:
            self.stat_labels['next_in'].configure(text=f"{countdown}s")

    def toggle_automation(self):
        """Перемикає автоматизацію"""
        if not self.running:
            self.start_automation()
        else:
            self.stop_automation()

    def start_automation(self):
        """Запускає автоматизацію"""
        if not self.save_settings():
            return

        self.running = True
        self.start_time = datetime.now()
        self.thread = threading.Thread(target=self.auto_send_loop)
        self.thread.daemon = True
        self.thread.start()

        # Оновлення UI
        self.main_btn.configure(
            text="🛑 STOP AUTOMATION",
            bg=self.colors['danger']
        )

        self.status_indicator.configure(fg=self.colors['success'])
        self.status_label.configure(text="SYSTEM ONLINE", fg=self.colors['success'])
        self.status_desc.configure(text="Automation running...")

        self.add_log(f"🚀 Automation started! Command: '{self.command}', interval: {self.interval}s")

    def stop_automation(self):
        """Зупиняє автоматизацію"""
        self.running = False

        # Оновлення UI
        self.main_btn.configure(
            text="🚀 START AUTOMATION",
            bg=self.colors['accent_primary']
        )

        self.status_indicator.configure(fg=self.colors['danger'])
        self.status_label.configure(text="SYSTEM OFFLINE", fg=self.colors['text_primary'])
        self.status_desc.configure(text="Ready to start automation")

        if hasattr(self, 'stat_labels') and 'next_in' in self.stat_labels:
            self.stat_labels['next_in'].configure(text="--")

        self.add_log("⏹️ Automation stopped")

    def test_command(self):
        """Тестує команду"""
        if self.save_settings():
            self.add_log("🧪 Testing command...")
            threading.Thread(target=lambda: (time.sleep(1), self.send_command()), daemon=True).start()

    def save_settings(self):
        """Зберігає налаштування"""
        try:
            new_command = self.command_var.get().strip()
            new_interval = int(self.interval_var.get().strip())

            if not new_command:
                messagebox.showerror("Error", "Command cannot be empty!")
                return False

            if new_interval <= 0:
                messagebox.showerror("Error", "Interval must be greater than 0!")
                return False

            self.command = new_command
            self.interval = new_interval
            self.save_config()

            self.add_log(f"💾 Settings saved: command='{self.command}', interval={self.interval}s")
            return True

        except ValueError:
            messagebox.showerror("Error", "Interval must be a number!")
            return False
        except Exception as e:
            messagebox.showerror("Error", f"Save error: {e}")
            return False

    def add_log(self, message):
        """Додає запис до логу"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"

        self.log_text.config(state='normal')
        self.log_text.insert('end', log_entry)
        self.log_text.config(state='disabled')
        self.log_text.see('end')

    def animate_title(self):
        """Анімує заголовок"""
        self.title_canvas.delete("all")

        # Анімований текст з градієнтом
        text = "🎮 MINECRAFT AUTO COMMANDER ULTRA 🚀"
        x = self.title_canvas.winfo_width() // 2 if self.title_canvas.winfo_width() > 1 else 400
        y = 40

        # Ефект свічення
        glow_colors = ['#ff0080', '#0080ff', '#80ff00', '#ff8000']
        glow_color = glow_colors[int(self.animation_frame / 20) % len(glow_colors)]

        # Тіні для глибини
        for offset in [(2, 2), (1, 1)]:
            self.title_canvas.create_text(
                x + offset[0], y + offset[1],
                text=text,
                font=self.fonts['title'],
                fill='#000000',
                anchor='center'
            )

        # Основний текст з градієнтом
        self.title_canvas.create_text(
            x, y,
            text=text,
            font=self.fonts['title'],
            fill=glow_color,
            anchor='center'
        )

    def animate_effects(self):
        """Головна функція анімації"""
        self.animation_frame += 1

        # Анімація заголовка
        self.animate_title()

        # Анімація частинок
        self.animate_particles()

        # Анімація статусного індикатора
        if self.running:
            brightness = int(100 + 155 * abs(math.sin(self.animation_frame * 0.2)))
            status_color = f"#{brightness:02x}ff{brightness // 3:02x}"
            self.status_indicator.configure(fg=status_color)

        # Продовження анімації
        self.root.after(50, self.animate_effects)

    def update_status(self):
        """Оновлює статус та статистику"""
        # Оновлення статистики
        if hasattr(self, 'stat_labels'):
            if 'commands_sent' in self.stat_labels:
                self.stat_labels['commands_sent'].configure(text=str(self.commands_sent))

            if 'success_rate' in self.stat_labels and self.command_history:
                successful = sum(1 for cmd in self.command_history if cmd['success'])
                rate = int((successful / len(self.command_history)) * 100)
                self.stat_labels['success_rate'].configure(text=f"{rate}%")

            if 'average_interval' in self.stat_labels:
                self.stat_labels['average_interval'].configure(text=f"{self.interval}s")

            if 'last_command' in self.stat_labels and self.command_history:
                last_cmd = self.command_history[-1]['command']
                display_cmd = last_cmd[:10] + "..." if len(last_cmd) > 10 else last_cmd
                self.stat_labels['last_command'].configure(text=display_cmd)

        # Оновлення часу роботи
        if self.start_time and self.running:
            uptime = datetime.now() - self.start_time
            hours, remainder = divmod(int(uptime.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            self.uptime_label.configure(text=f"⏱️ Uptime: {uptime_str}")

            if hasattr(self, 'stat_labels') and 'session_time' in self.stat_labels:
                self.stat_labels['session_time'].configure(text=uptime_str)
        else:
            self.uptime_label.configure(text="⏱️ Uptime: 00:00:00")
            if hasattr(self, 'stat_labels') and 'session_time' in self.stat_labels:
                self.stat_labels['session_time'].configure(text="00:00:00")

        # Продовження оновлення
        self.root.after(1000, self.update_status)

    def on_closing(self):
        """Обробка закриття вікна"""
        if self.running:
            if messagebox.askokcancel("Exit", "Stop automation and exit?"):
                self.stop_automation()
                keyboard.unhook_all()
                self.root.destroy()
        else:
            keyboard.unhook_all()
            self.root.destroy()

    def run(self):
        """Запускає програму"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Обробка зміни розміру вікна для адаптивності
        def on_configure(event):
            if event.widget == self.root:
                # Оновлюємо розміри canvas
                self.bg_canvas.config(width=event.width, height=event.height)
                # Оновлюємо частинки під новий розмір
                for particle in self.particles:
                    if particle['x'] > event.width:
                        particle['x'] = event.width - 10
                    if particle['y'] > event.height:
                        particle['y'] = event.height - 10

        self.root.bind('<Configure>', on_configure)
        self.root.mainloop()


def main():
    """Головна функція"""
    try:
        app = UltraModernMinecraftGUI()
        app.run()
    except Exception as e:
        messagebox.showerror("Critical Error", f"Application startup failed: {e}")
        import traceback
        print(traceback.format_exc())


if __name__ == "__main__":
    main()