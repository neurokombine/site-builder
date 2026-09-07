"""Глаза системы: открыть сайт в двух размерах, снять экраны и померить, что меряется.

Отдельная библиотека, а не часть одного скрипта, потому что браузер, размеры экранов и замеры
нужны сразу нескольким местам системы: самопроверке, разбору чужого сайта (`посмотреть_сайт.py`)
и проверке своего (`проверить.py`). Правим здесь — меняется одинаково везде. Руками этот файл
не запускают.

⭐ Меряем только то, что меряется надёжно: шрифты (с проверкой, загрузился свой или подставился
системный) · палитру в hex с долей употребления · кегли и интерлиньяж · долю воздуха по пикселям
снятого экрана · адаптивность (прокрутка вбок, текст мельче 14 px, вылезающие за экран картинки).
⛔ Не меряем и не показываем отступы между секциями и ширину колонки: числа получаются, но врут.
Цвет фона подписан «по разметке» — под фотографией он тоже врёт. Это смотрят глазами по
скриншотам, поэтому скриншот всегда лежит рядом с цифрами.

Размер экрана — не мелочь: ссылку на сайт чаще открывают с телефона, чем с компьютера, а
многие проблемы вёрстки видно только на маленьком экране.
"""
from __future__ import annotations

import json
import math
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

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

МЕЛКИЙ_ТЕКСТ_PX = 14          # мельче этого текст на телефоне читают с прищуром
ТАЙМАУТ_ЗАГРУЗКИ_МС = 35_000  # ждём саму страницу
ТАЙМАУТ_ТИШИНЫ_МС = 8_000     # ждём, пока догрузятся картинки; не критично, если не дождались
ТАЙМАУТ_ДЛИННОГО_СНИМКА_МС = 20_000

# Слова, по которым видно, что нас встретила не страница, а проверка на роботов.
МАРКЕРЫ_СТЕНЫ = [
    "captcha", "доступ ограничен", "доступ запрещ",
    "проверка браузера", "are you a human", "attention required! | cloudflare",
    "just a moment...", "checking your browser before accessing",
    "подозрительная активность", "unusual traffic from your computer",
    "403 forbidden", "ошибка 403", "ваш ip заблокирован", "access denied",
    "smart captcha", "подтвердите, что запросы отправляете вы",
    "проверяем браузер", "что-то не так", "подождите, идёт проверка",
]

# Виды «не пустило» и что человеку с этим делать. Ход везде один — снять экран самому.
ПОДСКАЗКИ = {
    "антибот_стена": (
        "Сайт закрылся от роботов проверкой. Ход везде один — сделайте скриншот сами и покажите "
        "его системе. Если на снятом экране сайт открылся нормально, тревога ложная: замеры "
        "рядом можно читать как есть."
    ),
    "только_компьютер": (
        "С телефона сайт не отдаётся роботу — снимите экран телефона сами и покажите скриншот "
        "системе. Замеры на компьютере при этом верные."
    ),
    "сертификат": (
        "Сайт использует российский сертификат, браузеру системы он незнаком; это не поломка. "
        "Ход тот же — сделайте скриншот сами и покажите его системе."
    ),
    "таймаут": (
        "Сайт не ответил вовремя. Попробуйте ещё раз через минуту, а если повторится — сделайте "
        "скриншот сами и покажите его системе."
    ),
    "ошибка": (
        "Браузер не смог открыть страницу. Проверьте ссылку; если она верна — сделайте скриншот "
        "сами и покажите его системе."
    ),
}
НАЗВАНИЯ_ВИДОВ = {
    "антибот_стена": "проверка на роботов",
    "только_компьютер": "отдаётся только на компьютере",
    "сертификат": "незнакомый сертификат",
    "таймаут": "сайт не ответил вовремя",
    "ошибка": "браузер не смог открыть страницу",
}

# Замер вычисленных стилей прямо в странице: что реально применилось, а не что написано в CSS.
# ⛔ Отступов между секциями и ширины колонки здесь нет намеренно: эти числа считались,
# но означали не то, что человек видит глазами, — обещать их нельзя.
ЗАМЕР_JS = r"""
() => {
  function rgbToHex(rgbStr) {
    if (!rgbStr) return null;
    const m = rgbStr.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const parts = m[1].split(',').map(s => parseFloat(s.trim()));
    const [r,g,b,a] = parts;
    if (a !== undefined && a === 0) return null;
    const toHex = n => Math.max(0,Math.min(255,Math.round(n||0))).toString(16).padStart(2,'0');
    return '#' + toHex(r) + toHex(g) + toHex(b);
  }
  function isVisible(el) {
    if (!(el instanceof Element)) return false;
    const rect = el.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return false;
    const style = getComputedStyle(el);
    if (style.visibility === 'hidden' || style.display === 'none' || parseFloat(style.opacity) === 0) return false;
    return true;
  }

  // Экран считаем по clientWidth/clientHeight, а не по window.innerWidth: на телефоне
  // страница с чем-нибудь широким внутри «отъезжает» и innerWidth становится шире экрана —
  // тогда вылезающая за край картинка перестаёт считаться вылезающей. clientWidth совпадает
  // с тем, что попадает на снятый экран.
  const vw = document.documentElement.clientWidth || window.innerWidth;
  const vh = document.documentElement.clientHeight || window.innerHeight;

  const fontUsage = {};
  const headingSizes = {};
  const bodySizes = [];
  const lineHeights = [];
  const textColorArea = {};
  const bgColorArea = {};

  // Какой шрифт применился на самом деле: идём по списку из CSS и спрашиваем браузер,
  // есть ли у него такой. Первый общий («sans-serif» и родня) — значит свой не загрузился.
  function resolveFont(stack, sizePx) {
    const names = stack.split(',').map(s => s.trim().replace(/^["']|["']$/g,''));
    const generic = ['serif','sans-serif','monospace','cursive','fantasy','system-ui',
      '-apple-system','blinkmacsystemfont','ui-sans-serif','ui-serif','ui-monospace'];
    for (const n of names) {
      if (generic.includes(n.toLowerCase())) return {resolved: n, isGeneric: true};
      try {
        if (document.fonts.check(`${sizePx}px "${n}"`)) return {resolved: n, isGeneric: false};
      } catch(e) {}
    }
    return {resolved: names[names.length-1] || stack, isGeneric: true};
  }

  const all = Array.from(document.querySelectorAll('body *'));

  // «листовой» текстовый элемент = у него нет дочерних элементов с непустым текстом
  // (сам текст может лежать в текстовом узле ИЛИ во вложенном <span>/<b>) —
  // так заголовки вида <h1><span>Текст</span></h1> тоже находятся
  function isLeafText(el) {
    for (const child of el.children) {
      if (child.textContent.trim().length > 0) return false;
    }
    return el.textContent.trim().length > 0;
  }

  let largestVisibleText = null;

  for (const el of all) {
    if (!isVisible(el)) continue;
    const rect = el.getBoundingClientRect();
    const top = Math.max(0, rect.top), left = Math.max(0, rect.left);
    const bottom = Math.min(vh, rect.bottom), right = Math.min(vw, rect.right);
    const visibleArea = Math.max(0, right-left) * Math.max(0, bottom-top);
    const cs = getComputedStyle(el);
    const tag = el.tagName;
    const isHeadingTag = /^H[1-3]$/.test(tag);

    let ownText = '';
    if (isHeadingTag) {
      ownText = el.textContent.trim();
    } else if (!el.closest('h1,h2,h3') && isLeafText(el)) {
      // всё остальное — только листовые текстовые узлы и не внутри заголовка,
      // иначе текст заголовка задвоится в статистику обычного текста
      ownText = el.textContent.trim();
    }

    if (ownText.length > 0 && visibleArea > 0) {
      const sizePx = parseFloat(cs.fontSize);
      const stack = cs.fontFamily;
      if (!fontUsage[stack]) fontUsage[stack] = {count:0, tags:{}, sizesPx:{}};
      fontUsage[stack].count++;
      fontUsage[stack].tags[tag] = (fontUsage[stack].tags[tag]||0)+1;
      fontUsage[stack].sizesPx[sizePx] = (fontUsage[stack].sizesPx[sizePx]||0)+1;

      if (isHeadingTag) {
        headingSizes[tag] = headingSizes[tag] || [];
        headingSizes[tag].push(sizePx);
      } else if (ownText.length >= 8) {
        bodySizes.push(sizePx);
      }
      const lh = cs.lineHeight;
      if (lh && lh.endsWith('px')) lineHeights.push(parseFloat(lh));

      const hex = rgbToHex(cs.color);
      if (hex) textColorArea[hex] = (textColorArea[hex]||0) + visibleArea;

      if (!largestVisibleText || sizePx > largestVisibleText.sizePx) {
        largestVisibleText = {sizePx, tag, text: ownText.slice(0, 60)};
      }
    }

    const bgHex = rgbToHex(cs.backgroundColor);
    if (bgHex && visibleArea > 400) bgColorArea[bgHex] = (bgColorArea[bgHex]||0) + visibleArea;
  }

  const fontsResolved = Object.entries(fontUsage).map(([stack, data]) => {
    const commonSize = Object.entries(data.sizesPx).sort((a,b)=>b[1]-a[1])[0][0];
    const r = resolveFont(stack, commonSize);
    return {declaredStack: stack, actuallyApplied: r.resolved, isGenericFallback: r.isGeneric,
            elementCount: data.count, tags: data.tags};
  }).sort((a,b) => b.elementCount - a.elementCount);

  const scrollWidth = document.documentElement.scrollWidth;
  const clientWidth = document.documentElement.clientWidth;

  // «вылезает» = картинка частично видна на экране и уходит за его край. Слайды каруселей
  // и скрытые варианты под другой размер лежат за экраном целиком — это не дефект вёрстки.
  const overflowingImgs = [];
  document.querySelectorAll('img,svg,picture,video').forEach(el => {
    if (!isVisible(el)) return;
    const r = el.getBoundingClientRect();
    if (!(r.left < vw && r.right > 0 && r.top < vh && r.bottom > 0)) return;
    const overflowsRight = r.left < vw - 2 && r.right > vw + 3;
    const overflowsLeft = r.right > 2 && r.left < -3;
    if (overflowsRight || overflowsLeft) {
      overflowingImgs.push({tag: el.tagName,
        src: (el.getAttribute('src')||el.getAttribute('data-src')||'').slice(0,120),
        width: Math.round(r.width), left: Math.round(r.left), right: Math.round(r.right)});
    }
  });

  let minBodyFont = null, smallTextCount = 0;
  document.querySelectorAll('p,li,span,a,div').forEach(el=>{
    if (!isVisible(el)) return;
    let t=''; for (const node of el.childNodes) if (node.nodeType===3) t+=node.textContent;
    if (t.trim().length < 15) return;
    const fs = parseFloat(getComputedStyle(el).fontSize);
    if (minBodyFont===null || fs < minBodyFont) minBodyFont = fs;
    if (fs < 14) smallTextCount++;
  });

  return {
    viewport: {w: vw, h: vh},
    fontsResolved, headingSizes, bodySizes, lineHeights, textColorArea, bgColorArea,
    scrollWidth, clientWidth, hasHorizontalScroll: scrollWidth > clientWidth + 3,
    overflowingImgs, minBodyFont, smallTextCount, largestVisibleText,
    pageTitle: document.title,
  };
}
"""


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


def адрес_из(аргумент) -> str:
    """Ссылка, путь к папке с сайтом или голый домен — приводим к адресу, который поймёт браузер."""
    строка = str(аргумент).strip().strip('"').strip("'")
    if not строка:
        raise ValueError("Не сказано, какой сайт смотреть — нужна ссылка или папка с сайтом.")
    if строка.startswith(("http://", "https://", "file://")):
        return строка
    путь = Path(строка).expanduser()
    if путь.exists():
        if путь.is_dir():
            индекс = путь / "index.html"
            if not индекс.exists():
                raise ValueError(f"В папке «{путь}» нет index.html — открывать нечего.")
            путь = индекс
        return путь.resolve().as_uri()
    return "https://" + строка.lstrip("/")


def слаг_из(адрес: str) -> str:
    """Короткое имя папки по адресу: `https://пример.ру/цены` → `пример-ру`."""
    from urllib.parse import urlparse

    разбор = urlparse(адрес)
    if разбор.scheme == "file":
        имя = Path(разбор.path).parent.name or "сайт"
    else:
        имя = разбор.netloc or адрес
        if имя.startswith("www."):
            имя = имя[4:]
    буквы = [с if (с.isalnum() or с == "-") else "-" for с in имя.lower()]
    имя = "".join(буквы).strip("-")
    while "--" in имя:
        имя = имя.replace("--", "-")
    return имя or "сайт"


def доли_по_площади(площади: dict, сколько: int = 6) -> list[dict]:
    """Цвета по занятой площади → список hex с долей в процентах."""
    всего = sum(площади.values()) or 1
    верх = sorted(площади.items(), key=lambda пара: -пара[1])[:сколько]
    return [{"hex": цвет, "доля": round(100 * площадь / всего, 1)} for цвет, площадь in верх]


def мода_px(значения) -> dict | None:
    """Самый частый размер в пикселях — и сколько всего разных встретилось."""
    if not значения:
        return None
    счёт = Counter(round(з) for з in значения)
    значение, сколько = счёт.most_common(1)[0]
    return {"px": значение, "элементов": сколько, "разных_значений": len(счёт)}


def воздух_по_скриншоту(путь, шаг: int = 16, порог: int = 26, макс_сторона: int = 480) -> dict:
    """Доля «воздуха» — пикселей фона — на снятом первом экране.

    Считаем по картинке, а не по разметке: находим самый частый цвет и считаем, сколько
    пикселей от него почти не отличаются. Остальное (текст, картинки, кнопки, тени) — контент.
    """
    from PIL import Image

    картинка = Image.open(путь).convert("RGB")
    масштаб = min(1.0, макс_сторона / картинка.width)
    мелкая = картинка.resize((max(1, int(картинка.width * масштаб)),
                              max(1, int(картинка.height * масштаб))))
    сырьё = мелкая.tobytes()          # три байта на пиксель, без предупреждений Pillow
    пиксели = [(сырьё[i], сырьё[i + 1], сырьё[i + 2]) for i in range(0, len(сырьё) - 2, 3)]

    def квант(п):
        return (п[0] // шаг * шаг, п[1] // шаг * шаг, п[2] // шаг * шаг)

    частый = Counter(квант(п) for п in пиксели).most_common(1)[0][0]
    ведро = [п for п in пиксели if квант(п) == частый]
    сред = [sum(п[и] for п in ведро) / len(ведро) for и in (0, 1, 2)]
    фоновых = sum(
        1 for п in пиксели
        if math.sqrt(sum((п[и] - сред[и]) ** 2 for и in (0, 1, 2))) < порог
    )
    return {
        "доля": round(100.0 * фоновых / len(пиксели), 1),
        "фон_скриншота_hex": "#%02x%02x%02x" % tuple(round(с) for с in сред),
        "как_считали": (
            f"первый экран уменьшен до {макс_сторона} px по ширине; берём самый частый цвет "
            f"(шаг квантования {шаг}) и считаем пиксели, отличающиеся от него меньше чем на "
            f"{порог} по RGB; их доля и есть воздух"
        ),
    }


def маркер_стены(*тексты) -> str | None:
    """Первое слово из МАРКЕРЫ_СТЕНЫ, найденное в коде или заголовке страницы."""
    склеено = " ".join((т or "").lower() for т in тексты)
    for маркер in МАРКЕРЫ_СТЕНЫ:
        if маркер in склеено:
            return маркер
    return None


def подсказка_по_виду(вид: str) -> str:
    """Что человеку делать, если сайт не пустил."""
    return ПОДСКАЗКИ.get(вид, ПОДСКАЗКИ["ошибка"])


def снять_размер(браузер, адрес: str, размер: str, папка: Path, ждать_сек: float) -> dict:
    """Открыть сайт в одном размере, снять два экрана и померить вычисленные стили."""
    from playwright.sync_api import TimeoutError as ТаймаутБраузера

    итог: dict = {"статус": "ок", "не_пустило": None, "скриншоты": {}}
    контекст_размера = контекст(браузер, размер)
    страница = контекст_размера.new_page()
    экран = папка / f"{размер}.png"
    вся_страница = папка / f"{размер}-вся-страница.png"
    начало = time.time()
    try:
        try:
            страница.goto(адрес, wait_until="load", timeout=ТАЙМАУТ_ЗАГРУЗКИ_МС)
        except ТаймаутБраузера:
            итог["статус"] = "таймаут"
            итог["не_пустило"] = {
                "вид": "таймаут",
                "признак": f"страница не загрузилась за {ТАЙМАУТ_ЗАГРУЗКИ_МС // 1000} секунд",
            }
        except Exception as ошибка:
            текст = f"{type(ошибка).__name__}: {ошибка}".split("\n")[0]
            сертификат = any(с in текст.lower() for с in ("cert", "ssl"))
            итог["статус"] = "не_пустило" if сертификат else "ошибка"
            итог["не_пустило"] = {"вид": "сертификат" if сертификат else "ошибка", "признак": текст}
            итог["время_загрузки_сек"] = round(time.time() - начало, 2)
            return итог

        try:
            страница.wait_for_load_state("networkidle", timeout=ТАЙМАУТ_ТИШИНЫ_МС)
        except Exception:
            pass  # многие сайты не затихают никогда (трекеры, чаты) — это не беда
        try:
            страница.evaluate("document.fonts.ready.then(() => true)")
        except Exception:
            pass
        time.sleep(ждать_сек)  # даём догрузиться ленивым картинкам и шрифтам
        итог["время_загрузки_сек"] = round(time.time() - начало, 2)

        код, заголовок = "", ""
        try:
            код = страница.content()
        except Exception:
            pass
        try:
            заголовок = страница.title()
        except Exception:
            pass
        итог["заголовок_вкладки"] = заголовок
        маркер = маркер_стены(код, заголовок)
        if маркер and итог["не_пустило"] is None:
            итог["статус"] = "не_пустило"
            итог["не_пустило"] = {"вид": "антибот_стена", "признак": маркер}

        try:
            страница.screenshot(path=str(экран), full_page=False)
            итог["скриншоты"]["экран"] = str(экран)
        except Exception as ошибка:
            итог["скриншоты"]["экран_не_снялся"] = str(ошибка).split("\n")[0]
        try:
            страница.screenshot(path=str(вся_страница), full_page=True,
                                timeout=ТАЙМАУТ_ДЛИННОГО_СНИМКА_МС)
            итог["скриншоты"]["вся_страница"] = str(вся_страница)
        except Exception as ошибка:
            итог["скриншоты"]["вся_страница_не_снялась"] = str(ошибка).split("\n")[0]

        try:
            замер = страница.evaluate(ЗАМЕР_JS)
            итог.update(разобрать_замер(замер))
        except Exception as ошибка:
            итог["замер_не_вышел"] = f"{type(ошибка).__name__}: {ошибка}".split("\n")[0]

        if "экран" in итог["скриншоты"]:
            try:
                итог["воздух"] = воздух_по_скриншоту(итог["скриншоты"]["экран"])
            except Exception as ошибка:
                итог["воздух"] = {"не_посчитан": str(ошибка).split("\n")[0]}
    finally:
        контекст_размера.close()
    return итог


def разобрать_замер(замер: dict) -> dict:
    """Сырые числа из браузера — в русские ключи, которыми дальше пользуется вся система."""
    шрифты = [
        {
            "объявлен": ш.get("declaredStack"),
            "применён": ш.get("actuallyApplied"),
            "запасной_ли": bool(ш.get("isGenericFallback")),
            "элементов": ш.get("elementCount"),
            "теги": ш.get("tags", {}),
        }
        for ш in замер.get("fontsResolved", [])[:8]
    ]
    заголовочный = текстовый = None
    for ш in шрифты:
        теги = ш.get("теги") or {}
        if заголовочный is None and any(т in теги for т in ("H1", "H2", "H3")):
            заголовочный = ш["применён"]
        if текстовый is None and any(т in теги for т in ("P", "SPAN", "DIV", "A", "LI")):
            текстовый = ш["применён"]

    # набор ключей одинаковый всегда: пусто значит «такого заголовка на странице не нашлось»
    кегли = {"h1": None, "h2": None, "h3": None}
    for тег, значения in замер.get("headingSizes", {}).items():
        кегли[тег.lower()] = мода_px(значения)
    кегли["текст"] = мода_px(замер.get("bodySizes", []))
    крупный = замер.get("largestVisibleText") or None
    return {
        "шрифты": шрифты,
        "шрифт_заголовков": заголовочный,
        "шрифт_текста": текстовый,
        "кегли": кегли,
        "интерлиньяж": мода_px(замер.get("lineHeights", [])),
        "цвета_текста": доли_по_площади(замер.get("textColorArea", {})),
        "фон_по_разметке": доли_по_площади(замер.get("bgColorArea", {})),
        "прокрутка_вбок": {
            "есть": bool(замер.get("hasHorizontalScroll")),
            "ширина_страницы": замер.get("scrollWidth"),
            "ширина_экрана": замер.get("clientWidth"),
        },
        "мелкий_текст": {
            "минимум_px": замер.get("minBodyFont"),
            "элементов_мельче_14": замер.get("smallTextCount", 0),
        },
        "вылезающие_картинки": [
            {"тег": к.get("tag"), "адрес": к.get("src"), "ширина": к.get("width"),
             "слева": к.get("left"), "справа": к.get("right")}
            for к in замер.get("overflowingImgs", [])
        ],
        "самый_крупный_текст": (
            {"px": round(крупный["sizePx"]), "тег": крупный["tag"], "текст": крупный["text"]}
            if крупный else None
        ),
    }


def подвести_итог(устройства: dict, размеры) -> dict:
    """Один вердикт на весь сайт: пустило или нет, и если нет — какого рода стена."""
    виды = [у["не_пустило"]["вид"] for у in устройства.values() if у.get("не_пустило")]
    где = {}
    for имя, у in устройства.items():
        if у.get("не_пустило"):
            где.setdefault(у["не_пустило"]["вид"], []).append(имя)

    вид = признак = None
    if "антибот_стена" in виды:
        вид = "антибот_стена"
    elif "сертификат" in виды:
        вид = "сертификат"
    elif (
        "компьютер" in размеры and "телефон" in размеры
        and устройства.get("компьютер", {}).get("статус") == "ок"
        and устройства.get("телефон", {}).get("статус") != "ок"
    ):
        вид = "только_компьютер"
    elif виды:
        вид = "таймаут" if "таймаут" in виды else виды[0]

    if вид and вид != "только_компьютер":
        for у in устройства.values():
            помеха = у.get("не_пустило") or {}
            if помеха.get("вид") == вид:
                признак = помеха.get("признак")
                break
    if вид == "только_компьютер":
        помеха = (устройства.get("телефон", {}).get("не_пустило") or {}).get("признак")
        признак = помеха or "телефон не показал страницу"
        где["только_компьютер"] = ["телефон"]

    есть_ок = any(у.get("статус") == "ок" for у in устройства.values())
    return {
        "статус": "ок" if есть_ок else "не_пустило",
        "не_пустило": None if вид is None else {
            "вид": вид,
            "признак": признак,
            "где": где.get(вид, []),
            "подсказка": подсказка_по_виду(вид),
        },
    }


def посмотреть(адрес, папка, размеры=("компьютер", "телефон"), ждать_сек=3.5, браузер=None) -> dict:
    """Открыть сайт в двух размерах, снять экраны, померить и сложить всё в папку.

    Кладёт рядом: `компьютер.png` и `телефон.png` (первый экран), `…-вся-страница.png`,
    `замеры.json` (все числа) и `замеры.md` (то же словами). Возвращает те же замеры словарём.
    `браузер` можно передать свой — тогда скрипт не будет открывать ещё один.
    """
    папка = Path(папка)
    папка.mkdir(parents=True, exist_ok=True)
    замеры = {
        "адрес": адрес,
        "снято": datetime.now(МСК).strftime("%d.%m.%Y %H:%M МСК"),
        "устройства": {},
        "итог": {},
    }

    def обойти(бр):
        for размер in размеры:
            замеры["устройства"][размер] = снять_размер(бр, адрес, размер, папка, ждать_сек)

    if браузер is not None:
        обойти(браузер)
    else:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as движок:
            свой = запустить_браузер(движок)
            try:
                обойти(свой)
            finally:
                свой.close()

    замеры["итог"] = подвести_итог(замеры["устройства"], размеры)
    (папка / "замеры.json").write_text(
        json.dumps(замеры, ensure_ascii=False, indent=2), encoding="utf-8")
    (папка / "замеры.md").write_text(сводка(замеры), encoding="utf-8")
    return замеры


def процент(число) -> str:
    """Число с одним знаком после запятой — и запятая, а не точка: текст читает человек."""
    return f"{число:.1f}".replace(".", ",")


def цвета_строкой(цвета, сколько=4) -> str:
    """Палитра одной строкой: цвет и сколько места он занимает."""
    return " · ".join(f"{ц['hex']} — {процент(ц['доля'])} %" for ц in (цвета or [])[:сколько]) or "—"


def сводка(замеры: dict) -> str:
    """Человеческий текст по замерам: он же ложится в `замеры.md` рядом со скриншотами."""
    строки = ["# Замеры сайта", "", f"Адрес: {замеры.get('адрес', '')}"]
    заголовок = next(
        (у.get("заголовок_вкладки") for у in замеры.get("устройства", {}).values()
         if у.get("заголовок_вкладки")), None)
    if заголовок:
        строки.append(f"Заголовок вкладки: {заголовок}")
    if замеры.get("снято"):
        строки.append(f"Снято: {замеры['снято']}")

    не_пустило = (замеры.get("итог") or {}).get("не_пустило")
    if не_пустило:
        где = ", ".join(не_пустило.get("где") or []) or "оба размера"
        строки += [
            "",
            f"⚠️ Не пустило: {НАЗВАНИЯ_ВИДОВ.get(не_пустило['вид'], не_пустило['вид'])} ({где})",
            f"   Признак: {не_пустило.get('признак')}",
            f"   {не_пустило.get('подсказка')}",
        ]

    for размер, у in замеры.get("устройства", {}).items():
        строки += ["", f"## {размер.capitalize()} — {состояние_словами(у)}", ""]
        строки += описать_размер(у)

    экраны = " · ".join(
        у["скриншоты"]["экран"] for у in замеры.get("устройства", {}).values()
        if (у.get("скриншоты") or {}).get("экран")
    )
    строки += [
        "",
        "Что не меряется: отступы между секциями, ширина колонки, фон под фотографией. "
        "Это — глазами по скриншотам: " + (экраны or "экраны снять не удалось"),
        "Числа — не приговор: скриншот всегда рядом с цифрами.",
        "",
    ]
    return "\n".join(строки)


def состояние_словами(устройство: dict) -> str:
    """«ок» или «не пустило: …» — заголовок раздела про один размер."""
    if устройство.get("статус") == "ок":
        return "ок"
    вид = (устройство.get("не_пустило") or {}).get("вид", устройство.get("статус", "ошибка"))
    return f"не пустило: {НАЗВАНИЯ_ВИДОВ.get(вид, вид)}"


def описать_размер(у: dict) -> list[str]:
    """Замеры одного размера — строчками, как человек их читает."""
    строки = []
    if у.get("не_пустило"):
        строки.append(f"- Признак: {у['не_пустило'].get('признак')}")
    if у.get("шрифты"):
        def подпись(имя):
            """Имя шрифта плюс главное про него: свой загрузился или подставился системный."""
            свои = [ш for ш in у["шрифты"] if ш["применён"] == имя]
            if not имя or not свои:
                return имя or "не нашлись"
            запасной = all(ш["запасной_ли"] for ш in свои)
            return f"{имя} (запасной системный)" if запасной else f"{имя} (загрузился)"
        строки.append(f"- Шрифты: заголовки — {подпись(у.get('шрифт_заголовков'))} · "
                      f"текст — {подпись(у.get('шрифт_текста'))}")
        # один и тот же шрифт может прийти из разных объявлений в CSS — складываем
        сколько_у_кого = {}
        for ш in у["шрифты"]:
            имя = ш["применён"]
            сколько_у_кого[имя] = сколько_у_кого.get(имя, 0) + (ш["элементов"] or 0)
        наборы = sorted(сколько_у_кого.items(), key=lambda пара: -пара[1])[:4]
        строки.append("- Употребление шрифтов: "
                      + " · ".join(f"{имя} — {сколько}" for имя, сколько in наборы))
    кегли = у.get("кегли") or {}
    померенные = [f"{тег} {к['px']} px" for тег, к in кегли.items() if к]
    if померенные:
        разных = (кегли.get("текст") or {}).get("разных_значений")
        хвост = f" · разных размеров текста: {разных}" if разных else ""
        строки.append("- Кегли: " + " · ".join(померенные) + хвост)
    if у.get("интерлиньяж"):
        строки.append(f"- Интерлиньяж текста: {у['интерлиньяж']['px']} px")
    if у.get("цвета_текста"):
        строки.append(f"- Цвет текста: {цвета_строкой(у['цвета_текста'])}")
    if у.get("фон_по_разметке"):
        строки.append(f"- Фон по разметке: {цвета_строкой(у['фон_по_разметке'])}"
                      "  (по разметке: под фотографией это число врёт)")
    воздух = у.get("воздух") or {}
    if "доля" in воздух:
        строки.append(f"- Воздух: {процент(воздух['доля'])} % первого экрана "
                      f"(фон экрана {воздух['фон_скриншота_hex']})")
    прокрутка = у.get("прокрутка_вбок") or {}
    мелкий = у.get("мелкий_текст") or {}
    картинки = у.get("вылезающие_картинки") or []
    if прокрутка or мелкий:
        куски = []
        if прокрутка.get("есть"):
            куски.append(f"прокрутка вбок — да ({прокрутка.get('ширина_страницы')} px "
                         f"при экране {прокрутка.get('ширина_экрана')} px)")
        else:
            куски.append("прокрутки вбок нет")
        сколько = мелкий.get("элементов_мельче_14") or 0
        if сколько:
            куски.append(f"текста мельче {МЕЛКИЙ_ТЕКСТ_PX} px — {сколько} шт., "
                         f"самый мелкий {мелкий.get('минимум_px')} px")
        else:
            куски.append(f"текста мельче {МЕЛКИЙ_ТЕКСТ_PX} px нет")
        куски.append(f"картинок за экран вылезает: {len(картинки)}" if картинки
                     else "картинки за экран не вылезают")
        строки.append("- Адаптивность: " + " · ".join(куски))
    if у.get("самый_крупный_текст"):
        к = у["самый_крупный_текст"]
        строки.append(f"- Самый крупный текст: {к['px']} px — «{к['текст']}»")
    экраны = [п for п in (у.get("скриншоты") or {}).values() if str(п).endswith(".png")]
    if экраны:
        строки.append("- Экраны: " + " · ".join(Path(п).name for п in экраны))
    if у.get("замер_не_вышел"):
        строки.append(f"- Померить стили не вышло: {у['замер_не_вышел']}")
    return строки or ["- Мерить нечего: страница не открылась."]
