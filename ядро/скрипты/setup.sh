#!/usr/bin/env bash
# Разовая установка окружения для системы «Сборщик сайтов».
# Идемпотентно: можно запускать повторно. Создаёт .venv (изолированно), ставит playwright,
# pillow и rembg, доустанавливает браузер Chromium. Запуск: bash ядро/скрипты/setup.sh
set -euo pipefail
cd "$(dirname "$0")/../.."

# 0. Цена входа — вслух и ЗАРАНЕЕ, а не посреди установки (CLAUDE.md § 7).
# Числа настоящие, замерены на этой системе: браузер ≈ 700 МБ, rembg ≈ 430 МБ в окружении,
# модель выреза ≈ 170 МБ скачивается отдельно и при первом вырезе, а не сейчас.
echo "[setup] Ставлю окружение. Один раз и надолго; вот сколько это стоит:"
echo "[setup]   · браузер — около четырёх минут и примерно 700 мегабайт;"
echo "[setup]   · rembg (вырез фона у фотографий) — около двух минут и примерно 430 мегабайт;"
echo "[setup]     ещё примерно 170 мегабайт — сама модель выреза, она скачается позже,"
echo "[setup]     когда вы первый раз попросите убрать фон, и тоже один раз."
echo "[setup]   · картинки система просит у ChatGPT в браузере — для этого нужен ваш"
echo "[setup]     Google Chrome и один вход руками. Chrome мы не качаем, места он не займёт,"
echo "[setup]     и отдельных денег это не стоит: рисуем по той подписке ChatGPT, которая"
echo "[setup]     у вас уже есть. Окно с вашим входом лежит в папке браузер/ и наружу"
echo "[setup]     не уезжает никогда."
echo "[setup]   Полоска подолгу стоит на месте — так и должно быть. Повторный запуск"
echo "[setup]   ничего не качает заново: уже готовое пропускается."

# 1. Выбрать базовый python со стабильными колёсами (3.10–3.13; системный 3.14 — без них)
pick_python() {
  for c in python3.12 python3.11 python3.13 python3.10 python python3; do
    command -v "$c" >/dev/null 2>&1 || continue
    ver=$("$c" -c 'import sys;print(sys.version_info[0]*100+sys.version_info[1])' 2>/dev/null || echo 0)
    if [ "$ver" -ge 310 ] && [ "$ver" -lt 314 ]; then echo "$c"; return; fi
  done
  for c in python python3; do command -v "$c" >/dev/null 2>&1 && { echo "$c"; return; }; done
}

# 2. venv
# ⚠️ Windows кладёт python в .venv/Scripts/, а не в .venv/bin/ — а все команды системы
# написаны через .venv/bin/python. Поэтому на Windows мы создаём .venv/bin/python как
# маленькую обёртку к .venv/Scripts/python.exe: один файл вместо правки всей документации,
# и одинаковая команда на обеих системах.
venv_python() {
  if [ -x .venv/bin/python ]; then echo .venv/bin/python
  elif [ -x .venv/Scripts/python.exe ]; then echo .venv/Scripts/python.exe
  elif [ -f .venv/Scripts/python.exe ]; then echo .venv/Scripts/python.exe
  fi
}

if [ -z "$(venv_python)" ]; then
  BASE=$(pick_python)
  if [ -z "${BASE:-}" ]; then
    echo "[setup] ❌ не нашёл Python. Поставьте Python 3.12 и запустите установку снова."
    exit 1
  fi
  echo "[setup] базовый python: $BASE ($($BASE --version 2>&1))"
  "$BASE" -m venv .venv
fi

REAL=$(venv_python)
if [ -z "${REAL:-}" ]; then
  echo "[setup] ❌ окружение создалось, но python в нём не найден (ни .venv/bin, ни .venv/Scripts)."
  exit 1
fi

# Мостик для Windows: .venv/bin/python → .venv/Scripts/python.exe
if [ ! -e .venv/bin/python ] && [ -e .venv/Scripts/python.exe ]; then
  echo "[setup] Windows: делаю .venv/bin/python мостиком к .venv/Scripts/python.exe"
  mkdir -p .venv/bin
  printf '#!/bin/sh\nexec "$(dirname "$0")/../Scripts/python.exe" "$@"\n' > .venv/bin/python
  chmod +x .venv/bin/python
fi

VPY=$(venv_python)
[ -x .venv/bin/python ] && VPY=.venv/bin/python

# 3. зависимости — браузер и обработка картинок
# Без сети pip падает сам, и падает многословно. Своё слово добавляем сверху: человеку нужно
# не «ERROR: Could not find a version», а что именно не встало и что с этим делать.
echo "[setup] зависимости…"
"$VPY" -m pip install -q --upgrade pip || true
if ! "$VPY" -m pip install -q playwright pillow; then
  echo "[setup] ❌ не поставились playwright и pillow — без них система не соберёт ни одной страницы."
  echo "[setup]    Чаще всего это пропавший интернет: проверьте связь и запустите установку ещё раз,"
  echo "[setup]    bash ядро/скрипты/setup.sh. Повторный запуск безопасен."
  exit 1
fi

# 3-bis. rembg — вырез фона (схемы «орбита», «центр», «живой портрет»).
# Решение владелицы 13.09.2026: ставим вместе с системой, а не «если понадобится». Раньше это
# была необязательная зависимость, и система молча не умела мерить голову на обычной фотографии.
# Не роняем установку, как и на браузере: остальное важнее, а доставить можно одной командой.
# Модель (~170 МБ) отсюда НЕ качается — её скачает сам rembg при первом вырезе.
run_limited() {   # запустить с ограничением по времени, если в системе есть чем ограничить
  if command -v timeout >/dev/null 2>&1; then timeout "$1" "${@:2}"
  elif command -v gtimeout >/dev/null 2>&1; then gtimeout "$1" "${@:2}"
  else "${@:2}"; fi
}
echo "[setup] rembg (вырез фона)… примерно 430 мегабайт, около двух минут"
REMBG_TIMEOUT=${REMBG_TIMEOUT:-900}
run_limited "$REMBG_TIMEOUT" "$VPY" -m pip install -q "rembg[cpu]" || REMBG_FAILED=1
if [ "${REMBG_FAILED:-0}" = "1" ]; then
  echo "[setup] ⚠️  rembg не поставился (долго или нет сети) — остальное поставлю."
  echo "[setup]     Без него система не умеет убирать фон с фотографии: схемы «орбита», «центр»"
  echo "[setup]     и «живой портрет» попросят готовый PNG с прозрачностью. Доставить потом:"
  echo "[setup]     .venv/bin/pip install 'rembg[cpu]'"
fi

# 4. Chromium (в общий кэш, быстро если уже скачан)
# Установка изредка зависает намертво — например, когда Chromium уже в кэше, а команда всё
# равно ждёт сеть. Поэтому ограничиваем время и НЕ роняем установку: остальные шаги важнее,
# а браузер можно доставить отдельной командой.
echo "[setup] Chromium… примерно 700 мегабайт, около четырёх минут"
CHROMIUM_TIMEOUT=${CHROMIUM_TIMEOUT:-600}
run_limited "$CHROMIUM_TIMEOUT" "$VPY" -m playwright install chromium || CHROMIUM_FAILED=1
if [ "${CHROMIUM_FAILED:-0}" = "1" ]; then
  echo "[setup] ⚠️  браузер не доустановился (долго или нет сети) — остальное поставлю."
  echo "[setup]     Доставить потом: .venv/bin/python -m playwright install chromium"
fi

# 5. Канал до генератора картинок: свой Chrome и один вход руками.
# Chrome мы НЕ качаем и не ставим — это чужой установщик и лишние сотни мегабайт, а нужен
# именно тот браузер, в котором человек живёт: чужой профиль сайт узнаёт как автоматику.
# Не нашли — говорим, что поставить, и идём дальше: канал необязателен ровно как rembg,
# сайт собирается и без картинок. Поэтому весь блок обязан пережить любой свой провал.
channel_report() {
  echo "[setup] канал до генератора картинок…"
  if "$VPY" ядро/скрипты/кисть.py --канал 2>/dev/null | sed 's/^/[setup]   /'; then
    return 0
  fi
  echo "[setup]   ⚠️  не смог посмотреть канал — скажет самопроверка:"
  echo "[setup]      .venv/bin/python ядро/скрипты/кисть.py --канал"
  echo "[setup]      Установку это не ломает: картинки необязательны, сайт собирается без них."
}
channel_report || true

echo "[setup] Готово. Дальше: .venv/bin/python ядро/скрипты/selftest.py"
