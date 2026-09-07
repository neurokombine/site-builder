#!/usr/bin/env bash
# Разовая установка окружения для системы «Сборщик сайтов».
# Идемпотентно: можно запускать повторно. Создаёт .venv (изолированно), ставит playwright
# и pillow, доустанавливает браузер Chromium. Запуск: bash ядро/скрипты/setup.sh
set -euo pipefail
cd "$(dirname "$0")/../.."

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

# 3. зависимости — только то, что нужно этапам 1–3: браузер и обработка картинок
echo "[setup] зависимости…"
"$VPY" -m pip install -q --upgrade pip
"$VPY" -m pip install -q playwright pillow

# 4. Chromium (в общий кэш, быстро если уже скачан)
# Установка изредка зависает намертво — например, когда Chromium уже в кэше, а команда всё
# равно ждёт сеть. Поэтому ограничиваем время и НЕ роняем установку: остальные шаги важнее,
# а браузер можно доставить отдельной командой.
echo "[setup] Chromium…"
CHROMIUM_TIMEOUT=${CHROMIUM_TIMEOUT:-600}
if command -v timeout >/dev/null 2>&1; then
  timeout "$CHROMIUM_TIMEOUT" "$VPY" -m playwright install chromium || CHROMIUM_FAILED=1
elif command -v gtimeout >/dev/null 2>&1; then
  gtimeout "$CHROMIUM_TIMEOUT" "$VPY" -m playwright install chromium || CHROMIUM_FAILED=1
else
  "$VPY" -m playwright install chromium || CHROMIUM_FAILED=1
fi
if [ "${CHROMIUM_FAILED:-0}" = "1" ]; then
  echo "[setup] ⚠️  браузер не доустановился (долго или нет сети) — остальное поставлю."
  echo "[setup]     Доставить потом: .venv/bin/python -m playwright install chromium"
fi

echo "[setup] Готово. Дальше: .venv/bin/python ядро/скрипты/selftest.py"
