"""
Скрипт для компіляції GUI версії Minecraft Auto Command Sender в .exe файл
"""

import subprocess
import sys
import os


def create_icon():
    """Створює простий ICO файл для програми"""
    icon_content = '''
    AAABAAEAEBAAAAAAAABoBAAAFgAAACgAAAAQAAAAIAAAAAEAIAAAAAAAQAQAAAAAAAAAAAAAAAAAAAAAAAAA
    AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
    AAAAAAAA////////AAAA//8AAAD//wAAAP//AAAA//8AAAD//wAAAP//AAAA//8AAAD//wAAAP//AAAA//8AAAAA
    AAAA////////AAAA//8AAAD//wAAAP//AAAA//8AAAD//wAAAP//AAAA//8AAAD//wAAAP//AAAA//8AAAAAAAAA
    AAAA////////AAAA//8AAAD//wAAAP//AAAA//8AAAD//wAAAP//AAAA//8AAAD//wAAAP//AAAA//8AAAAAAAAA
    AAAA////////AAAA//8AAAD//wAAAP//AAAA//8AAAD//wAAAP//AAAA//8AAAD//wAAAP//AAAA//8AAAAAAAAA
    '''

    try:
        # Створюємо базову іконку (це буде працювати не ідеально, але краще ніж нічого)
        with open('specs/app_icon.ico', 'wb') as f:
            # Створюємо мінімальний ICO файл
            ico_header = b'\x00\x00\x01\x00\x01\x00\x10\x10\x00\x00\x01\x00\x20\x00\x68\x04\x00\x00\x16\x00\x00\x00'
            f.write(ico_header)
            # Додаємо білий квадрат 16x16
            for i in range(16 * 16):
                f.write(b'\xFF\xFF\xFF\xFF')  # Білий піксель з альфа-каналом
        return True
    except:
        return False


def install_requirements():
    """Встановлює необхідні пакети"""
    requirements = [
        'pyinstaller',
        'pyautogui',
        'keyboard'
    ]

    print("🔧 Встановлення необхідних пакетів...")
    for req in requirements:
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', req])
            print(f"✅ {req} встановлено")
        except subprocess.CalledProcessError:
            print(f"❌ Помилка встановлення {req}")
            return False
    return True


def build_gui_exe():
    """Компілює GUI програму в .exe файл"""
    script_name = "MinecraftAutoCmd_GUI.py"

    if not os.path.exists(script_name):
        print(f"❌ Файл {script_name} не знайдено!")
        print("Переконайся, що файл знаходиться в тій же папці")
        return False

    print("🚀 Початок компіляції GUI версії...")

    # Створюємо іконку
    has_icon = create_icon()

    # Параметри для PyInstaller
    cmd = [
        'pyinstaller',
        '--onefile',  # Один exe файл
        '--windowed',  # Без консольного вікна
        '--name=MinecraftAutoCmd_Pro',  # Ім'я exe файла
        '--distpath=./dist_gui',  # Папка для результату
        '--workpath=./build_gui',  # Тимчасова папка
        '--specpath=./specs',  # Папка для spec файлів
        '--clean',
        '--noupx',
        script_name
    ]

    # Додаємо іконку якщо вдалося створити
    if has_icon:
        cmd.insert(-1, '--icon=app_icon.ico')

    # Додаємо додаткові параметри для кращої сумісності
    cmd.extend([
        '--add-data', 'minecraft_auto_config.json;.',
        '--hidden-import', 'tkinter',
        '--hidden-import', 'tkinter.ttk',
        '--hidden-import', 'tkinter.font',
        '--collect-submodules', 'pyautogui',
        '--collect-submodules', 'keyboard'
    ])

    try:
        subprocess.check_call(cmd)
        print("✅ Компіляція завершена успішно!")
        print("📁 .exe файл знаходиться в папці 'dist_gui/'")
        print("📋 Файл називається: MinecraftAutoCmd_Pro.exe")

        # Очищення тимчасових файлів
        if has_icon and os.path.exists('specs/app_icon.ico'):
            os.remove('specs/app_icon.ico')

        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Помилка компіляції: {e}")
        return False


def create_startup_script():
    """Створює bat файл для зручного запуску"""
    bat_content = '''@echo off
title Minecraft Auto Commander Pro
echo.
echo  ╔═══════════════════════════════════════╗
echo  ║    Minecraft Auto Commander Pro       ║
echo  ║           Запуск програми...          ║
echo  ╚═══════════════════════════════════════╝
echo.

REM Запуск програми
start "" "MinecraftAutoCmd_Pro.exe"

REM Закриття bat файлу через 2 секунди
timeout /t 2 /nobreak >nul
exit
'''

    try:
        with open('./dist_gui/Запустити_MinecraftAutoCmd.bat', 'w', encoding='utf-8') as f:
            f.write(bat_content)
        print("✅ Створено зручний bat файл для запуску")
    except:
        pass


def create_readme():
    """Створює README файл з інструкціями"""
    readme_content = '''# 🎮 Minecraft Auto Commander Pro

## 🚀 Як користуватися:

### Запуск програми:
- Подвійний клік на MinecraftAutoCmd_Pro.exe
- Або використай Запустити_MinecraftAutoCmd.bat

### Налаштування:
1. 🎯 Введи команду яку потрібно автоматично відправляти (наприклад: /htc10)
2. ⏱️ Встанови інтервал в секундах між відправленнями
3. 💾 Натисни "ЗБЕРЕГТИ" щоб зберегти налаштування

### Управління:
- 🚀 "ЗАПУСТИТИ" - починає автоматичне відправлення команд
- 🛑 "ЗУПИНИТИ" - зупиняє автоматичне відправлення
- 🧪 "ТЕСТ" - відправляє команду один раз для тестування

### Гарячі клавіші:
- F8 - Запустити/Зупинити автоматичне відправлення
- F9 - Зупинити автоматичне відправлення
- F10 - Тестувати команду

### Важливо:
- Minecraft повинен бути запущений і активним
- Переконайся що можеш писати в чат на сервері
- Налаштування автоматично зберігаються в файл minecraft_auto_config.json

### Статистика:
- Програма показує кількість відправлених команд
- Час роботи програми
- Відлік до наступної команди

## 🎨 Особливості:
- Сучасний темний інтерфейс
- Анімовані елементи
- Автоматичне збереження налаштувань
- Детальний лог всіх подій
- Статистика роботи

## 💡 Поради:
- Використовуй розумні інтервали (не менше 5 секунд)
- Перевіряй команди за допомогою кнопки "ТЕСТ"
- Слідкуй за логом для відстеження роботи

Розроблено для автоматизації Minecraft команд з професійним підходом!
'''

    try:
        with open('./dist_gui/README.txt', 'w', encoding='utf-8') as f:
            f.write(readme_content)
        print("✅ Створено README.txt з інструкціями")
    except:
        pass


def main():
    print("=== Minecraft Auto Command Builder GUI ===")
    print("Цей скрипт скомпілює красиву GUI версію програми в .exe файл")

    # Встановлюємо залежності
    if not install_requirements():
        print("❌ Не вдалося встановити всі залежності")
        input("Натисни Enter для виходу...")
        return

    # Компілюємо
    if build_gui_exe():
        create_startup_script()
        create_readme()

        print("\n🎉 Готово! Тепер ти маєш:")
        print("📁 Папка 'dist_gui' з готовою програмою:")
        print("   📦 MinecraftAutoCmd_Pro.exe - головна програма")
        print("   🚀 Запустити_MinecraftAutoCmd.bat - зручний запуск")
        print("   📖 README.txt - інструкції по використанню")
        print("\n✨ Особливості GUI версії:")
        print("   🎨 Сучасний темний дизайн")
        print("   ✨ Анімації та ефекти")
        print("   📊 Статистика та моніторинг")
        print("   📋 Детальний лог подій")
        print("   💾 Автоматичне збереження")
        print("   🎹 Гарячі клавіші")

        print("\n🚀 Можеш скопіювати всю папку 'dist_gui' на будь-який комп'ютер!")
    else:
        print("❌ Компіляція не вдалася")

    input("\nНатисни Enter для виходу...")


if __name__ == "__main__":
    main()