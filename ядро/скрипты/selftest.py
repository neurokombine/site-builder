"""Самопроверка системы: всё ли на месте и открывается ли браузер.

Проверяет по шагам: своё ли окружение запущено, стоят ли playwright и pillow, установлен ли
сам браузер, умеет ли он открыть страницу и сфотографировать её в двух размерах — на компьютере
и на телефоне. Если профиль уже настроен — заодно сверяет и его.

Запуск:  .venv/bin/python ядро/скрипты/selftest.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
PY = sys.executable
ПАПКА = ROOT / "сайты" / "_самопроверка"

sys.path.insert(0, str(Path(__file__).resolve().parent))
import глаза  # noqa: E402

СТРАНИЦА = """<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"><title>Самопроверка</title></head>
<body style="font-family:sans-serif;max-width:640px;margin:60px auto;padding:0 24px;">
<h1>Система работает</h1>
<p>Это тестовая страница для самопроверки: если браузер её открыл и сфотографировал —
значит окружение и браузер на месте.</p>
<button type="button">Кнопка для проверки</button>
</body></html>
"""


def шаг(описание, функция):
    print(f"→ {описание}")
    try:
        return функция()
    except Exception as ошибка:
        print(f"\n⛔ Не прошло: {описание}")
        for строка in str(ошибка).splitlines():
            print(f"   {строка}")
        print("   Что делать — в ЕСЛИ-СЛОМАЛОСЬ.md.\n")
        sys.exit(1)


def проверить_окружение():
    """sys.executable должен быть внутри .venv — иначе это чужой, системный python.

    ⚠️ Сравнивать нужно по sys.prefix, а не по резолву sys.executable: внутри .venv python —
    это цепочка символических ссылок (python → python3.12 → .../miniconda3/...), и полный
    resolve() уводит проверку на системный интерпретатор, даже когда запуск честно был через
    `.venv/bin/python`.
    """
    venv = (ROOT / ".venv").resolve()
    if Path(sys.prefix).resolve() != venv:
        raise RuntimeError(
            f"Запущено не своим окружением: {PY}.\nНужно: bash ядро/скрипты/setup.sh, "
            "затем .venv/bin/python ядро/скрипты/selftest.py"
        )


def проверить_библиотеки():
    import importlib
    for имя, подсказка in (("playwright", "playwright"), ("PIL", "pillow")):
        try:
            importlib.import_module(имя)
        except ImportError:
            raise RuntimeError(
                f"Библиотека «{подсказка}» не установлена.\nЗапустите: bash ядро/скрипты/setup.sh"
            )


def проверить_браузер(playwright):
    путь = Path(playwright.chromium.executable_path)
    if not путь.exists():
        raise RuntimeError(
            "Браузер не установлен.\n"
            "Поставьте командой: .venv/bin/python -m playwright install chromium"
        )


def снять_скриншоты(браузер, страница_путь):
    ПАПКА.mkdir(parents=True, exist_ok=True)
    for размер, имя_файла in (("компьютер", "компьютер.png"), ("телефон", "телефон.png")):
        контекст = глаза.контекст(браузер, размер)
        страница = контекст.new_page()
        страница.goto(страница_путь.as_uri())
        страница.screenshot(path=str(ПАПКА / имя_файла))
        контекст.close()


def проверить_профиль():
    """Профиль появится в следующей задаче — пока честно пропускаем этот шаг."""
    скрипт = ROOT / "ядро" / "скрипты" / "профиль.py"
    if not скрипт.exists():
        print("→ проверка профиля: профиль.py ещё не сделан — пропускаю, это нормально")
        return
    папка_профили = ROOT / "профили"
    профили = [
        д for д in папка_профили.iterdir()
        if д.is_dir() and not д.name.startswith("_") and (д / "profile.json").exists()
    ] if папка_профили.exists() else []
    if not профили:
        print("→ проверка профиля: профиля ещё нет — пропускаю")
        return
    шаг("проверяю профиль", lambda: subprocess.run(
        [PY, str(скрипт), "--проверить"], cwd=ROOT, check=True,
    ))


def main():
    шаг("проверяю, что запускаюсь из своего окружения (.venv)", проверить_окружение)
    шаг("проверяю, что playwright и pillow на месте", проверить_библиотеки)

    from playwright.sync_api import sync_playwright

    временный_файл = Path(tempfile.gettempdir()) / "site-builder-самопроверка.html"
    шаг("готовлю тестовую страницу",
        lambda: временный_файл.write_text(СТРАНИЦА, encoding="utf-8"))

    try:
        with sync_playwright() as p:
            шаг("проверяю, что браузер (Chromium) установлен", lambda: проверить_браузер(p))
            браузер = шаг("запускаю браузер", lambda: глаза.запустить_браузер(p))
            try:
                шаг(
                    "открываю тестовую страницу — на компьютере и на телефоне",
                    lambda: снять_скриншоты(браузер, временный_файл),
                )
            finally:
                браузер.close()
    finally:
        временный_файл.unlink(missing_ok=True)

    проверить_профиль()

    print("\n✅ Всё работает.")
    print(f"   Скриншоты: {ПАПКА.relative_to(ROOT).as_posix()}/компьютер.png, "
          f"{ПАПКА.relative_to(ROOT).as_posix()}/телефон.png")
    print("   Дальше: скажите, чей сайт собираем, — или /setup.")


if __name__ == "__main__":
    main()
