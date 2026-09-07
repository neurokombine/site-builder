"""Глаза системы: как открыть браузер и в каком размере смотреть на страницу.

Отдельная библиотека, а не часть какого-то одного скрипта, потому что запуск браузера и
размеры экранов нужны сразу нескольким местам системы: самопроверке, разбору чужого сайта
и проверке своего. Правим настройки здесь — и они одинаковые везде. Руками этот файл не
запускают: сам по себе он ничего не открывает и не меряет — это готовит следующая часть
системы, эта только запускает браузер и раздаёт ему нужный размер экрана.

Размер экрана — не мелочь: ссылку на сайт чаще открывают с телефона, чем с компьютера, а
многие проблемы вёрстки видно только на маленьком экране.
"""
from __future__ import annotations

import sys
from datetime import timedelta, timezone

МСК = timezone(timedelta(hours=3))

# User-agent'ы как у настоящих браузеров. Без них некоторые сайты отдают на компьютере и на
# телефоне одну и ту же вёрстку — или вовсе показывают страницу «обновите браузер».
DESKTOP_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
)

# Параметры для browser.new_context() — два размера, в которых мы всегда показываем сайт
# человеку: «одобрение = одобрение обоих» (правило системы, CLAUDE.md § 4).
РАЗМЕРЫ = {
    "компьютер": dict(
        viewport={"width": 1440, "height": 900},
        user_agent=DESKTOP_UA,
        device_scale_factor=1,
    ),
    "телефон": dict(
        viewport={"width": 390, "height": 844},
        user_agent=MOBILE_UA,
        device_scale_factor=3,
        is_mobile=True,
        has_touch=True,
    ),
}


def запустить_браузер(playwright):
    """Headless Chromium, готовый смотреть на чужие и свои сайты.

    Флаг `--disable-blink-features=AutomationControlled` — чтобы сайты с защитой от ботов не
    блокировали нас с порога. Если обычный запуск не удался (так бывает в песочнице, которой
    не разрешены вспомогательные процессы браузера) — пробуем второй раз в однопроцессном
    режиме и предупреждаем об этом в консоли.
    """
    аргументы = ["--disable-blink-features=AutomationControlled"]
    try:
        return playwright.chromium.launch(headless=True, args=аргументы)
    except Exception:
        print("браузер запущен однопроцессным режимом", file=sys.stderr)
        return playwright.chromium.launch(
            headless=True,
            args=аргументы + ["--single-process", "--no-zygote", "--no-sandbox"],
        )


def контекст(browser, размер):
    """Новый контекст браузера под один из двух размеров — «компьютер» или «телефон»."""
    if размер not in РАЗМЕРЫ:
        raise ValueError(f"Неизвестный размер «{размер}» — есть только {list(РАЗМЕРЫ)}")
    return browser.new_context(locale="ru-RU", **РАЗМЕРЫ[размер])
