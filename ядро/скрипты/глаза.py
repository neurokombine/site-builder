"""Глаза системы: открыть сайт в двух размерах, снять экраны и померить, что меряется.

Отдельная библиотека, а не часть одного скрипта, потому что браузер, размеры экранов и замеры
нужны сразу нескольким местам системы: самопроверке, разбору чужого сайта (`посмотреть_сайт.py`)
и проверке своего (`проверить.py`). Правим здесь — меняется одинаково везде. Руками этот файл
не запускают.

⭐ Меряем только то, что меряется надёжно: шрифты (с проверкой, загрузился свой или подставился
системный) · палитру в hex с долей употребления · кегли и интерлиньяж · долю воздуха по пикселям
снятого экрана · адаптивность (прокрутка вбок, текст мельче 13 px, вылезающие за экран картинки).
⛔ Не меряем и не показываем отступы между секциями и ширину колонки: числа получаются, но врут.
Цвет фона подписан «по разметке» — под фотографией он тоже врёт. Это смотрят глазами по
скриншотам, поэтому скриншот всегда лежит рядом с цифрами.

Размер экрана — не мелочь: ссылку на сайт чаще открывают с телефона, чем с компьютера, а
многие проблемы вёрстки видно только на маленьком экране.
"""
from __future__ import annotations

import json
import math
import re
import sys
import time
import urllib.parse
import urllib.request
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

# Ещё пять экранов — для технической приёмки (`проверить.py --техника`, модуль `техника.py`).
# В обычной проверке их нет: она обязана оставаться около минуты, а два главных размера выше
# ловят почти всё. Здесь — то, что ломается реже, но у живых людей встречается каждый день:
# маленький телефон, планшет, ноутбук с узким экраном, телефон, повёрнутый набок, и iPhone с
# его собственным движком Safari (WebKit) — Chrome и Safari рисуют одну страницу не одинаково.
IPAD_UA = (
    "Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
)
ЕЩЁ_РАЗМЕРЫ = {
    "телефон-360": dict(viewport={"width": 360, "height": 740}, user_agent=MOBILE_UA,
                        device_scale_factor=3, is_mobile=True, has_touch=True),
    "планшет": dict(viewport={"width": 768, "height": 1024}, user_agent=IPAD_UA,
                    device_scale_factor=2, is_mobile=True, has_touch=True),
    "ноутбук": dict(viewport={"width": 1280, "height": 800}, user_agent=DESKTOP_UA,
                    device_scale_factor=1),
    "телефон-лёжа": dict(viewport={"width": 844, "height": 390}, user_agent=MOBILE_UA,
                         device_scale_factor=3, is_mobile=True, has_touch=True),
    # тот же телефон, что и главный, — но открывается в WebKit, а не в Chromium
    "телефон-safari": dict(РАЗМЕРЫ["телефон"]),
}
ПОДПИСИ_РАЗМЕРОВ = {
    "компьютер": "компьютер 1440 × 900",
    "телефон": "телефон 390 × 844",
    "телефон-360": "маленький телефон 360 × 740",
    "планшет": "планшет 768 × 1024",
    "ноутбук": "ноутбук 1280 × 800",
    "телефон-лёжа": "телефон лёжа 844 × 390",
    "телефон-safari": "iPhone в Safari 390 × 844",
}

# Одно число на систему: канон разрешает мелким служебным строкам 13 px («ядро/канон.md»,
# «Текст и шрифты»), и сторож меряет тем же числом. Раньше их было два — канон 13, сторож 14, —
# и собственная шапка ядра со строкой лицензии (.8125em на телефоне = ровно 13 px) вечно давала
# жёлтую находку, неустранимую без правки обложки.
МЕЛКИЙ_ТЕКСТ_PX = 13          # мельче этого текст на телефоне читают с прищуром
ТАЙМАУТ_ЗАГРУЗКИ_МС = 35_000  # ждём саму страницу
ТАЙМАУТ_ТИШИНЫ_МС = 8_000     # ждём, пока догрузятся картинки; не критично, если не дождались
ТАЙМАУТ_ДЛИННОГО_СНИМКА_МС = 20_000

# Слова, по которым видно, что нас встретила не страница, а проверка на роботов.
# ⚠️ Ищем их только в ВИДИМОМ тексте страницы и в заголовке вкладки — не в разметке. В разметке
# обычного лендинга с формой заявки живёт капча (`recaptcha/api.js`, `smartcaptcha`), и поиск по
# коду объявлял «не пустило» на исправном сайте: вердикт и код выхода менялись на пустом месте.
# По той же причине здесь нет «что-то не так» — это обычная фраза формы, а не примета стены.
МАРКЕРЫ_СТЕНЫ = [
    "captcha", "доступ ограничен", "доступ запрещ",
    "проверка браузера", "are you a human", "attention required! | cloudflare",
    "just a moment...", "checking your browser before accessing",
    "подозрительная активность", "unusual traffic from your computer",
    "403 forbidden", "ошибка 403", "ваш ip заблокирован", "access denied",
    "smart captcha", "подтвердите, что запросы отправляете вы",
    "проверяем браузер", "подождите, идёт проверка",
]

# Виды «не пустило» и что человеку с этим делать. Человек — ПОСЛЕДНИЙ шаг лестницы: сначала
# система сама пробует видимое окно и копию из веб-архива (`подняться_для_размера`), и только
# если обе ступени не дали нормальной страницы, звучит этот совет — снять экран самому.
ПОДСКАЗКИ = {
    "антибот_стена": (
        "Сайт закрылся от роботов проверкой. Система уже пробовала сама (видимое окно, копия из "
        "веб-архива) — остался последний шаг, за человеком: сделайте скриншот сами и покажите "
        "его системе. Если на снятом экране сайт открылся нормально, тревога ложная: замеры "
        "рядом можно читать как есть."
    ),
    "только_компьютер": (
        "С телефона сайт не отдаётся роботу, и система уже пробовала обойти это сама. Остался "
        "последний шаг, за человеком: снимите экран телефона сами и покажите скриншот системе. "
        "Замеры на компьютере при этом верные."
    ),
    "сертификат": (
        "Сайт использует российский сертификат, браузеру системы он незнаком; это не поломка. "
        "Открывать его в обход проверки система не станет — это вопрос безопасности; копию из "
        "веб-архива она уже искала. Остался последний шаг, за человеком: сделайте скриншот сами "
        "и покажите его системе."
    ),
    "таймаут": (
        "Сайт не ответил вовремя, даже когда система подождала дольше и открыла видимое окно. "
        "Попробуйте ещё раз через минуту, а если повторится — сделайте скриншот сами и покажите "
        "его системе."
    ),
    "ошибка": (
        "Браузер не смог открыть страницу. Проверьте ссылку; если она верна — сделайте скриншот "
        "сами и покажите его системе."
    ),
}
# Коды, которыми браузер называет беду именно с сертификатом.
# ⛔ По словам «cert» и «ssl» судить нельзя: в текст ошибки браузер вписывает сам адрес, и у
# сайта, у которого эти буквы стоят в домене, любая беда — хоть «такого сайта не нашли» —
# получала уверенное и неверное объяснение «незнакомый сертификат». Врать увереннее, чем
# молчать, здесь хуже всего: человек пойдёт чинить сертификат вместо опечатки в адресе.
КОДЫ_СЕРТИФИКАТА = ("ERR_CERT", "ERR_SSL", "SSL_ERROR", "CERT_")

НАЗВАНИЯ_ВИДОВ = {
    "антибот_стена": "проверка на роботов",
    "только_компьютер": "отдаётся только на компьютере",
    "сертификат": "незнакомый сертификат",
    "таймаут": "сайт не ответил вовремя",
    "ошибка": "браузер не смог открыть страницу",
}

# Три вещи, которые нужны в браузере и здесь, и при разборе разметки в `проверить.РАЗБОР_JS`:
# разобрать цвет, понять, видно ли элемент, и понять, его ли это текст. Держим их в одном
# месте и подклеиваем в оба замера — иначе одна и та же функция живёт в двух файлах двумя
# слегка разными копиями, и правка в одной тихо расходится с другой.
ОБЩИЙ_JS = r"""
  // 'rgba(17, 17, 17, 0.8)' → {r, g, b, a}. Прозрачность, которой в строке нет, считаем
  // полной: 'rgb(...)' — это непрозрачный цвет.
  function parseRgb(строка) {
    if (!строка) return null;
    const m = String(строка).match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const ч = m[1].split(',').map(s => parseFloat(s.trim()));
    return {r: ч[0] || 0, g: ч[1] || 0, b: ч[2] || 0, a: ч.length > 3 ? ч[3] : 1};
  }
  // Цвет в hex. Принимает и строку браузера, и уже разобранный цвет: из вычисленных стилей
  // приходит строка, а из расчёта контраста — цвет, положенный на фон. Полностью прозрачное
  // цветом не считаем вовсе: в палитре ему делать нечего.
  function rgbToHex(значение) {
    const c = (значение && typeof значение === 'object') ? значение : parseRgb(значение);
    if (!c || c.a === 0) return null;
    const toHex = n => Math.max(0,Math.min(255,Math.round(n||0))).toString(16).padStart(2,'0');
    return '#' + toHex(c.r) + toHex(c.g) + toHex(c.b);
  }
  function isVisible(el) {
    if (!(el instanceof Element)) return false;
    const rect = el.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return false;
    const style = getComputedStyle(el);
    if (style.visibility === 'hidden' || style.display === 'none' || parseFloat(style.opacity) === 0) return false;
    return true;
  }
  // «Листовой» текстовый элемент = у него нет детей с непустым текстом (сам текст может
  // лежать в текстовом узле ИЛИ во вложенном <span>/<b>) — так заголовки вида
  // <h1><span>Текст</span></h1> тоже находятся, а текст ребёнка не задваивается в родителе.
  function isLeafText(el) {
    for (const child of el.children) {
      if (child.textContent.trim().length > 0) return false;
    }
    return el.textContent.trim().length > 0;
  }
"""

# Замер вычисленных стилей прямо в странице: что реально применилось, а не что написано в CSS.
# ⛔ Отступов между секциями и ширины колонки здесь нет намеренно: эти числа считались,
# но означали не то, что человек видит глазами, — обещать их нельзя.
ЗАМЕР_JS = "() => {" + ОБЩИЙ_JS + r"""
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
  // Картинку, которую обрезает предок с `overflow: hidden` в пределах экрана, человек видит
  // целой рамкой: кадр обложки «cover» шире окна на ноутбуке 1280 — не дефект, а замысел.
  function clippedInside(el) {
    for (let p = el.parentElement; p && p !== document.documentElement; p = p.parentElement) {
      const ox = getComputedStyle(p).overflowX;
      if (ox !== 'hidden' && ox !== 'clip') continue;
      const pr = p.getBoundingClientRect();
      if (pr.left >= -3 && pr.right <= vw + 3) return true;
    }
    return false;
  }
  const overflowingImgs = [];
  document.querySelectorAll('img,svg,picture,video').forEach(el => {
    if (!isVisible(el)) return;
    const r = el.getBoundingClientRect();
    if (!(r.left < vw && r.right > 0 && r.top < vh && r.bottom > 0)) return;
    const overflowsRight = r.left < vw - 2 && r.right > vw + 3;
    const overflowsLeft = r.right > 2 && r.left < -3;
    if ((overflowsRight || overflowsLeft) && !clippedInside(el)) {
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
    if (fs < __ПОРОГ_МЕЛКОГО__) smallTextCount++;
  });

  return {
    viewport: {w: vw, h: vh},
    fontsResolved, headingSizes, bodySizes, lineHeights, textColorArea, bgColorArea,
    scrollWidth, clientWidth, hasHorizontalScroll: scrollWidth > clientWidth + 3,
    overflowingImgs, minBodyFont, smallTextCount, largestVisibleText,
    pageTitle: document.title,
  };
}
""".replace("__ПОРОГ_МЕЛКОГО__", str(МЕЛКИЙ_ТЕКСТ_PX))  # порог живёт в одном месте — в константе


def запустить_браузер(playwright):
    """Headless Chromium, готовый смотреть на чужие и свои сайты.

    Флаг `--disable-blink-features=AutomationControlled` — чтобы сайты с защитой от ботов не
    блокировали нас с порога. Если обычный запуск не удался (так бывает в песочнице, которой
    не разрешены вспомогательные процессы браузера) — пробуем второй раз в запасном режиме.

    ⚠️ Запасной режим — без песочницы браузера, а этим браузером мы открываем чужие сайты.
    Ловим любую ошибку запуска намеренно: на машинах учеников их набор непредсказуем, и
    сузить условие значит оставить часть людей вовсе без работающей системы. Но раз защита
    ослаблена — говорим об этом вслух, а не молча.
    """
    аргументы = ["--disable-blink-features=AutomationControlled"]
    try:
        return playwright.chromium.launch(headless=True, args=аргументы)
    except Exception:
        браузер = playwright.chromium.launch(
            headless=True,
            args=аргументы + ["--single-process", "--no-zygote", "--no-sandbox"],
        )
        print("Браузер запущен в запасном режиме без песочницы: чужие сайты открываются "
              "с меньшей защитой. Это не поломка.", file=sys.stderr)
        return браузер


def контекст(browser, размер, **доп):
    """Новый контекст браузера под размер: два главных — «компьютер» и «телефон» — или один из
    дополнительных для технической приёмки (`ЕЩЁ_РАЗМЕРЫ`)."""
    все = {**РАЗМЕРЫ, **ЕЩЁ_РАЗМЕРЫ}
    if размер not in все:
        raise ValueError(f"Неизвестный размер «{размер}» — есть только {list(все)}")
    параметры = {"locale": "ru-RU", **все[размер], **доп}
    return browser.new_context(**параметры)


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


def слаг(имя: str) -> str:
    """Любая строка — в имя папки: строчными, без пробелов и знаков. «Моё Дело!» → «моё-дело»."""
    буквы = [с if (с.isalnum() or с == "-") else "-" for с in имя.lower()]
    имя = "".join(буквы).strip("-")
    while "--" in имя:
        имя = имя.replace("--", "-")
    return имя or "сайт"


def слаг_из(адрес: str) -> str:
    """Короткое имя папки по адресу: `https://пример.ру/цены` → `пример-ру`."""
    from urllib.parse import unquote, urlparse

    разбор = urlparse(адрес)
    if разбор.scheme == "file":
        # путь к локальной папке приходит процентно-закодированным: без unquote кириллическое
        # имя превратится в «d1-80-d0-b5-…», и человек не узнает свою же папку
        имя = Path(unquote(разбор.path)).parent.name or "сайт"
    else:
        имя = разбор.netloc or адрес
        if имя.startswith("www."):
            имя = имя[4:]
    return слаг(имя)


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
    """Первое слово из МАРКЕРЫ_СТЕНЫ, найденное в видимом тексте или заголовке вкладки.

    Разметку сюда не передаём: `<script src=".../recaptcha/api.js">` в форме заявки —
    признак обычного лендинга, а не стены.
    """
    склеено = " ".join((т or "").lower() for т in тексты)
    for маркер in МАРКЕРЫ_СТЕНЫ:
        if маркер in склеено:
            return маркер
    return None


def подсказка_по_виду(вид: str) -> str:
    """Что человеку делать, если сайт не пустил."""
    return ПОДСКАЗКИ.get(вид, ПОДСКАЗКИ["ошибка"])


def вид_по_ошибке(текст: str) -> str:
    """«сертификат» или просто «ошибка» — по коду, которым браузер назвал беду.

    Судим по коду, а не по словам в строке: строка содержит и сам адрес, поэтому у сайта с
    «ssl» или «cert» в домене «такого сайта не нашли» превращалось в «незнакомый сертификат».
    """
    верх = текст.upper()
    return "сертификат" if any(код in верх for код in КОДЫ_СЕРТИФИКАТА) else "ошибка"


def открыть(страница, адрес: str, таймаут_мс: int | None = None) -> bool:
    """Открыть адрес и дождаться «загрузилась». True — дождались; False — событие не пришло за
    таймаут, но страница уже на экране (в ней есть текст): так бывает на площадках, где чужой
    скрипт — счётчик, чат, проверка — не отвечает минутами. Мерим то, что открылось, а не
    объявляем страницу неоткрывшейся. Не открылось совсем — ошибка браузера летит дальше."""
    from playwright.sync_api import TimeoutError as ТаймаутБраузера

    try:
        страница.goto(адрес, wait_until="load", timeout=таймаут_мс or ТАЙМАУТ_ЗАГРУЗКИ_МС)
        return True
    except ТаймаутБраузера:
        try:
            есть = страница.evaluate(
                "() => !!document.body && document.body.innerText.trim().length > 0")
        except Exception:   # noqa: BLE001 — страница не отвечает вовсе
            есть = False
        if not есть:
            raise
        return False


def снять_размер(браузер, адрес: str, размер: str, папка: Path, ждать_сек: float,
                 таймаут_мс: int | None = None, доп_контекст: dict | None = None,
                 скрыть_css: str | None = None, ответы: list | None = None) -> dict:
    """Открыть сайт в одном размере, снять два экрана и померить вычисленные стили.

    Необязательное — для ступеней лестницы (`подняться_для_размера`): `таймаут_мс` — ждать
    страницу дольше обычного; `доп_контекст` — свои параметры окна (user agent, пояс);
    `скрыть_css` — стиль, прячущий чужую обвязку (панель веб-архива); `ответы` — список, куда
    складываем (тип ресурса, код ответа), чтобы понять, подтянулись ли стили."""
    from playwright.sync_api import TimeoutError as ТаймаутБраузера

    итог: dict = {"статус": "ок", "не_пустило": None, "скриншоты": {}}
    таймаут_загрузки = таймаут_мс or ТАЙМАУТ_ЗАГРУЗКИ_МС
    контекст_размера = контекст(браузер, размер, **(доп_контекст or {}))
    страница = контекст_размера.new_page()
    if ответы is not None:
        страница.on("response", lambda о: ответы.append((о.request.resource_type, о.status)))
    экран = папка / f"{размер}.png"
    вся_страница = папка / f"{размер}-вся-страница.png"
    начало = time.time()
    try:
        try:
            страница.goto(адрес, wait_until="load", timeout=таймаут_загрузки)
        except ТаймаутБраузера:
            итог["статус"] = "таймаут"
            итог["не_пустило"] = {
                "вид": "таймаут",
                "признак": f"страница не загрузилась за {таймаут_загрузки // 1000} секунд",
            }
        except Exception as ошибка:
            текст = f"{type(ошибка).__name__}: {ошибка}".split("\n")[0]
            вид = вид_по_ошибке(текст)
            итог["статус"] = "не_пустило" if вид == "сертификат" else "ошибка"
            итог["не_пустило"] = {"вид": вид, "признак": текст}
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
        if скрыть_css:
            try:
                страница.add_style_tag(content=скрыть_css)
            except Exception:
                pass
        if ответы is not None:
            try:
                итог["_стилей_в_разметке"] = страница.evaluate(
                    "() => document.querySelectorAll('link[rel~=\"stylesheet\"]').length")
            except Exception:
                итог["_стилей_в_разметке"] = 0
        итог["время_загрузки_сек"] = round(time.time() - начало, 2)

        видимый_текст, заголовок = "", ""
        try:
            видимый_текст = страница.evaluate(
                "() => (document.body ? document.body.innerText : '').slice(0, 8000)")
        except Exception:
            pass
        try:
            заголовок = страница.title()
        except Exception:
            pass
        итог["заголовок_вкладки"] = заголовок
        маркер = маркер_стены(видимый_текст, заголовок)
        if маркер:
            # стена важнее таймаута: если её видно, вид назван точнее
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

        # Страница не сказала «загрузилась», но экран снялся и замеры вышли — это не «не пустило»,
        # а живой сайт с висящим трекером или чатом. Считаем размер снятым и пишем пометку.
        if (итог["статус"] == "таймаут" and "экран" in итог["скриншоты"]
                and "замер_не_вышел" not in итог):
            итог["статус"] = "ок"
            итог["не_пустило"] = None
            итог["предупреждение"] = (
                f"страница не сообщила о полной загрузке за {таймаут_загрузки // 1000} с, "
                "замеры сняты с того, что успело открыться"
            )
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
            "элементов_мельче_порога": замер.get("smallTextCount", 0),
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


# ── Лестница при «не пустило»: машина пробует сама, человек — последний шаг ──────────────────
# 1) повтор подольше (только для «не ответил вовремя»); 2) видимое окно Chromium с обычным
# пользовательским профилем; 3) копия из веб-архива, с честной пометкой «снято с копии».
# Незнакомый сертификат в обход не открываем никогда — только архив. Отказ любой ступени
# не роняет скрипт: говорим словами и идём к следующей.
ТАЙМАУТ_ПОВТОРА_МС = 70_000
АРХИВ_ОТВЕТ_СЕК = 25
АРХИВ_API = "https://archive.org/wayback/available?url="
СКРЫТЬ_ПАНЕЛЬ_АРХИВА = "#wm-ipp-base, #wm-ipp, #donato { display: none !important; }"
ОКНО_ЧЕЛОВЕКА = dict(timezone_id="Europe/Moscow")


def выбрать_ступени(вид, другой_размер_ок: bool = False) -> list[str]:
    """Какие ступени и в каком порядке пробуем для этого вида «не пустило».

    «повтор» — подождать дольше · «окно» — видимый браузер · «архив» — копия из веб-архива.
    Сертификат — только архив. Что не из списка (опечатка в адресе, DNS) — лестницы нет."""
    if вид == "таймаут":
        return ["повтор", "окно", "архив"]
    if вид in ("антибот_стена", "доступ_запрещён"):
        return ["окно", "архив"]
    if вид == "сертификат":
        return ["архив"]
    if вид == "ошибка" and другой_размер_ок:   # компьютер открылся, телефон — нет
        return ["окно", "архив"]
    return []


def разобрать_ответ_архива(ответ) -> dict | None:
    """Ответ `archive.org/wayback/available` → ближайший снимок или None.

    Возвращает {"метка": "20260512103000", "дата": "12.05.2026"} (дата — по МСК, метка архива в UTC). Снимок с ошибкой сервера
    (4xx/5xx) за копию не считаем — там записана не страница, а отказ."""
    if not isinstance(ответ, dict):
        return None
    снимок = ((ответ.get("archived_snapshots") or {}).get("closest")) or {}
    if not isinstance(снимок, dict) or not снимок.get("available"):
        return None
    метка = str(снимок.get("timestamp") or "")
    if not re.fullmatch(r"\d{14}", метка):
        return None
    if str(снимок.get("status") or "200")[:1] in ("4", "5"):
        return None
    # Метка архива — UTC; дату показываем по Москве (граница суток — московская полночь).
    try:
        момент = datetime.strptime(метка, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return {"метка": метка, "дата": момент.astimezone(МСК).strftime("%d.%m.%Y")}


def адреса_копии(адрес: str, метка: str) -> tuple[str, str]:
    """(исходная страница без панели `id_`, обычная копия с панелью) для снимка архива."""
    return (f"https://web.archive.org/web/{метка}id_/{адрес}",
            f"https://web.archive.org/web/{метка}/{адрес}")


def стили_подтянулись(ответы, стилей_в_разметке) -> bool:
    """Подтянулись ли стили у копии `id_`: на странице есть таблицы стилей, а ответили ≥ половины.
    Нет таблиц вовсе (стили внутри страницы) — считаем, что всё в порядке."""
    if not стилей_в_разметке:
        return True
    живых = sum(1 for тип, код in ответы if тип == "stylesheet" and код < 400)
    return живых >= max(1, половина_стилей(стилей_в_разметке))


def половина_стилей(число: int) -> int:
    return (число + 1) // 2


def _получить_json(адрес: str):
    запрос = urllib.request.Request(
        адрес, headers={"User-Agent": DESKTOP_UA, "Accept": "application/json"})
    with urllib.request.urlopen(запрос, timeout=АРХИВ_ОТВЕТ_СЕК) as отклик:
        return json.loads(отклик.read().decode("utf-8", "replace"))


def найти_копию(адрес: str, получить=None) -> tuple[dict | None, str | None]:
    """(снимок, причина_отказа). Сеть — через `получить(url) -> json`, чтобы тесты её не трогали."""
    получить = получить or _получить_json
    try:
        ответ = получить(АРХИВ_API + urllib.parse.quote(адрес, safe=":/?&=%"))
    except Exception as ошибка:   # noqa: BLE001 — архив не ответил: это отказ ступени, не беда скрипта
        return None, f"архив не ответил ({type(ошибка).__name__})"
    снимок = разобрать_ответ_архива(ответ)
    return (снимок, None) if снимок else (None, "копии этого сайта в архиве нет")


def _нормальная(итог_размера) -> bool:
    return bool(итог_размера) and итог_размера.get("статус") == "ок" and not итог_размера.get("не_пустило")


def _запустить_видимый(движок):
    return движок.chromium.launch(
        headless=False, args=["--disable-blink-features=AutomationControlled"])


def _отметить_копию(итог_размера: dict, дата: str, адрес_копии: str) -> dict:
    итог_размера["источник"] = "копия_архива"
    итог_размера["дата_копии"] = дата
    итог_размера["адрес_копии"] = адрес_копии
    итог_размера["предупреждение"] = (
        f"снято с копии веб-архива от {дата} — сайт мог измениться")
    return итог_размера


def подняться_для_размера(размер, итог_размера, адрес, папка, ждать_сек, браузер, движок=None,
                          другой_размер_ок=False, получить=None, принудительно_вид=None,
                          сказать=print, кэш=None) -> dict:
    """Лестница для одного размера. Возвращает нормальный итог размера (с ключом «ступени» —
    что пробовали словами) или прежний итог с тем же ключом, если ни одна ступень не помогла."""
    вид = принудительно_вид or (итог_размера.get("не_пустило") or {}).get("вид")
    план = выбрать_ступени(вид, другой_размер_ок)
    if not план:
        return итог_размера
    кэш = кэш if кэш is not None else {}
    слова: list[str] = []

    def говорю(текст):
        слова.append(текст)
        сказать("   " + текст)

    говорю(f"Сайт не пустил робота на {размер} ({НАЗВАНИЯ_ВИДОВ.get(вид, вид)}). "
           "Пробую сам, человека пока не зову.")

    for ступень in план:
        новый = None
        if ступень == "повтор":
            говорю(f"Шаг: подождать подольше — до {ТАЙМАУТ_ПОВТОРА_МС // 1000} секунд.")
            try:
                новый = снять_размер(браузер, адрес, размер, папка, ждать_сек,
                                     таймаут_мс=ТАЙМАУТ_ПОВТОРА_МС)
            except Exception as ошибка:   # noqa: BLE001
                говорю(f"Не вышло: {type(ошибка).__name__}.")
        elif ступень == "окно":
            if движок is None:
                говорю("Шаг: видимое окно браузера — здесь недоступно, пропускаю.")
                continue
            доп = dict(ОКНО_ЧЕЛОВЕКА)
            подпись = "Шаг: открываю сайт видимым окном браузера, как это делает человек."
            if размер == "телефон" and другой_размер_ок:
                доп["user_agent"] = DESKTOP_UA
                подпись += (" Экран телефонный, но браузер представится компьютером — "
                            "мобильной вёрстки в замерах может не быть.")
            говорю(подпись)
            видимый = None
            try:
                видимый = _запустить_видимый(движок)
                новый = снять_размер(видимый, адрес, размер, папка, ждать_сек,
                                     таймаут_мс=ТАЙМАУТ_ПОВТОРА_МС, доп_контекст=доп)
            except Exception as ошибка:   # noqa: BLE001 — нет экрана, окно не поднялось и т. п.
                говорю(f"Не вышло: окно не открылось ({type(ошибка).__name__}).")
            finally:
                if видимый is not None:
                    try:
                        видимый.close()
                    except Exception:   # noqa: BLE001
                        pass
            if новый is not None and _нормальная(новый):
                говорю("Получилось: в видимом окне страница открылась.")
                новый["ступени"] = слова
                новый["ступень"] = "окно"
                return новый
            if новый is not None:
                говорю("Не вышло: и видимое окно сайт не пускает.")
            continue
        elif ступень == "архив":
            говорю("Шаг: ищу копию сайта в веб-архиве.")
            if "снимок" not in кэш:
                кэш["снимок"] = найти_копию(адрес, получить)
            снимок, причина = кэш["снимок"]
            if not снимок:
                говорю(f"Не вышло: {причина}.")
                continue
            говорю(f"Нашёл копию от {снимок['дата']}. Снимаю её — это не живой сайт, он мог измениться.")
            без_панели, с_панелью = адреса_копии(адрес, снимок["метка"])
            ответы: list = []
            try:
                новый = снять_размер(браузер, без_панели, размер, папка, ждать_сек,
                                     таймаут_мс=ТАЙМАУТ_ПОВТОРА_МС, ответы=ответы)
                стилей = новый.pop("_стилей_в_разметке", 0)
                if _нормальная(новый) and not стили_подтянулись(ответы, стилей):
                    говорю("У копии без панели не подтянулись стили — беру обычную копию архива "
                           "и прячу его панель.")
                    новый = None
                if новый is None or not _нормальная(новый):
                    новый = снять_размер(браузер, с_панелью, размер, папка, ждать_сек,
                                         таймаут_мс=ТАЙМАУТ_ПОВТОРА_МС,
                                         скрыть_css=СКРЫТЬ_ПАНЕЛЬ_АРХИВА)
                    новый.pop("_стилей_в_разметке", None)
                    адрес_копии = с_панелью
                else:
                    адрес_копии = без_панели
            except Exception as ошибка:   # noqa: BLE001
                говорю(f"Не вышло: копия не открылась ({type(ошибка).__name__}).")
                новый = None
            if новый is not None and _нормальная(новый):
                _отметить_копию(новый, снимок["дата"], адрес_копии)
                говорю(f"Получилось: замеры сняты с копии веб-архива от {снимок['дата']}. "
                       "Помечаю это в отчёте.")
                новый["ступени"] = слова
                новый["ступень"] = "архив"
                return новый
            if новый is not None:
                говорю("Не вышло: копия в архиве тоже оказалась проверкой или пустой.")
            continue
        if новый is not None and _нормальная(новый):
            говорю("Получилось: со второй попытки страница открылась.")
            новый["ступени"] = слова
            новый["ступень"] = "повтор"
            return новый

    говорю("Машина сделала всё, что могла. Остался последний шаг — за человеком.")
    итог_размера["ступени"] = слова
    return итог_размера


def подняться(замеры: dict, адрес, папка, размеры, ждать_сек, браузер, движок=None,
              получить=None, принудительно_вид=None, сказать=print) -> bool:
    """Лестница по всем размерам сайта; обновляет `замеры` и пересчитывает вердикт.
    `принудительно_вид` — когда снаружи уже знают, что это стена, а замер этого не увидел.
    True — хотя бы одна ступень что-то изменила."""
    изменилось = False
    кэш: dict = {}
    for размер in размеры:
        у = замеры["устройства"].get(размер)
        if у is None:
            continue
        если_нормальный = _нормальная(у) and not принудительно_вид
        if если_нормальный:
            continue
        другой_ок = any(
            _нормальная(д) for имя, д in замеры["устройства"].items() if имя != размер)
        новый = подняться_для_размера(
            размер, у, адрес, Path(папка), ждать_сек, браузер, движок,
            другой_размер_ок=другой_ок, получить=получить,
            принудительно_вид=принудительно_вид, сказать=сказать, кэш=кэш)
        if новый is not у:
            изменилось = True
        замеры["устройства"][размер] = новый
    замеры["итог"] = подвести_итог(замеры["устройства"], размеры)
    ступени = [с for д in замеры["устройства"].values() for с in (д.get("ступени") or [])]
    if ступени:
        замеры["итог"]["ступени"] = ступени
    копии = {д["дата_копии"] for д in замеры["устройства"].values() if д.get("дата_копии")}
    if копии:
        замеры["итог"]["копия_архива"] = {
            "дата": sorted(копии)[0],
            "пометка": f"снято с копии веб-архива от {sorted(копии)[0]} — сайт мог измениться",
        }
    return изменилось


def посмотреть(адрес, папка, размеры=("компьютер", "телефон"), ждать_сек=3.5, браузер=None,
               движок=None, лестница=False) -> dict:
    """Открыть сайт в двух размерах, снять экраны, померить и сложить всё в папку.

    Кладёт рядом: `компьютер.png` и `телефон.png` (первый экран), `…-вся-страница.png`,
    `замеры.json` (все числа) и `замеры.md` (то же словами). Возвращает те же замеры словарём.
    `браузер` можно передать свой — тогда скрипт не будет открывать ещё один; вместе с ним
    стоит передать `движок` (объект playwright), иначе ступень «видимое окно» недоступна.
    `лестница=True` (чужие сайты при разведке: `посмотреть_сайт.py`, `ресёрч_ниши.py`) — если
    сайт не пустил, сама поднимается по ступеням (повтор · видимое окно · копия из веб-архива,
    `подняться`), человек — последний шаг. Для своих сайтов (`проверить.py`) она выключена:
    своя страница в архив не ходит.
    """
    папка = Path(папка)
    папка.mkdir(parents=True, exist_ok=True)
    замеры = {
        "адрес": адрес,
        "снято": datetime.now(МСК).strftime("%d.%m.%Y %H:%M МСК"),
        "устройства": {},
        "итог": {},
    }

    def обойти(бр, дв):
        for размер in размеры:
            замеры["устройства"][размер] = снять_размер(бр, адрес, размер, папка, ждать_сек)
        if лестница:
            подняться(замеры, адрес, папка, размеры, ждать_сек, бр, дв)

    if браузер is not None:
        обойти(браузер, движок)
    else:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as движок:
            свой = запустить_браузер(движок)
            try:
                обойти(свой, движок)
            finally:
                свой.close()

    if not замеры["итог"]:
        замеры["итог"] = подвести_итог(замеры["устройства"], размеры)
    записать_замеры(замеры, папка)
    return замеры


def записать_замеры(замеры: dict, папка) -> None:
    папка = Path(папка)
    (папка / "замеры.json").write_text(
        json.dumps(замеры, ensure_ascii=False, indent=2), encoding="utf-8")
    (папка / "замеры.md").write_text(сводка(замеры), encoding="utf-8")


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

    итог_сайта = замеры.get("итог") or {}
    копия = итог_сайта.get("копия_архива")
    if копия:
        строки += ["", f"⚠️ {копия['пометка'][0].upper()}{копия['пометка'][1:]}. "
                   "Это не живой сайт: цвета, шрифты и тексты могли поменяться."]
    if итог_сайта.get("ступени"):
        строки += ["", "Что система пробовала сама:"]
        строки += [f"- {с}" for с in итог_сайта["ступени"]]

    не_пустило = итог_сайта.get("не_пустило")
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
    if у.get("предупреждение"):
        строки.append(f"- Пометка: {у['предупреждение']}")
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
        сколько = мелкий.get("элементов_мельче_порога") or 0
        if сколько:
            куски.append(f"текста мельче {МЕЛКИЙ_ТЕКСТ_PX} px — {сколько} шт., "
                         f"самый мелкий {мелкий.get('минимум_px')} px")
        else:
            куски.append(f"текста мельче {МЕЛКИЙ_ТЕКСТ_PX} px нет")
        куски.append(f"картинок за экран вылезает: {len(картинки)}" if картинки
                     else "картинки за экран не вылезают")
        # Две цифры считаются по-разному, и без оговорки их читают как одну мерку:
        # мелкий текст ищется по всей странице, вылезающие картинки — только на первом экране.
        строки.append("- Адаптивность: " + " · ".join(куски)
                      + " (текст — по всей странице, картинки — по первому экрану)")
    if у.get("самый_крупный_текст"):
        к = у["самый_крупный_текст"]
        строки.append(f"- Самый крупный текст: {к['px']} px — «{к['текст']}»")
    экраны = [п for п in (у.get("скриншоты") or {}).values() if str(п).endswith(".png")]
    if экраны:
        строки.append("- Экраны: " + " · ".join(Path(п).name for п in экраны))
    if у.get("замер_не_вышел"):
        строки.append(f"- Померить стили не вышло: {у['замер_не_вышел']}")
    return строки or ["- Мерить нечего: страница не открылась."]
