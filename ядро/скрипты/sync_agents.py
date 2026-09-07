"""Одно описание роли — три инструмента.

Роли живут в `.claude/agents/*.md` (это источник истины). Отсюда собираются те же роли
в форматах других инструментов, чтобы система работала одинаково везде:

    .claude/agents/<имя>.md      ← пишем руками (markdown + шапка)
    .codex/agents/<имя>.toml     ← собирается (TOML, поля Codex)
    .kimi-code/agents/<имя>.md   ← собирается (markdown + шапка Kimi)
    .codex/config.toml           ← собирается (регистрация ролей и лимиты)

Запуск:
    .venv/bin/python ядро/скрипты/sync_agents.py            # собрать
    .venv/bin/python ядро/скрипты/sync_agents.py --проверить # только сверить, ничего не писать

Зачем: описания ролей разъезжаются молча. Разъехались — и на одном инструменте документ
собирается по одним правилам, на другом по другим. Поэтому правим ОДИН файл и пересобираем.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ИСТОЧНИК = ROOT / ".claude" / "agents"
CODEX = ROOT / ".codex" / "agents"
KIMI = ROOT / ".kimi-code" / "agents"
CODEX_CONFIG = ROOT / ".codex" / "config.toml"

ШАПКА = "<!-- Собрано из .claude/agents/{имя}.md — правьте там и пересоберите: ядро/скрипты/sync_agents.py -->"

# Инструменты Claude → инструменты Kimi (имена отличаются)
ИНСТРУМЕНТЫ_KIMI = {
    "Read": "Read",
    "Write": "Write",
    "Edit": "Edit",
    "Bash": "Bash",
    "Grep": "Grep",
    "Glob": "Glob",
    "WebFetch": "WebFetch",
}
# Роли, которым нельзя писать в файлы: у Codex это отдельный режим песочницы (`read-only`).
# Пусто и, скорее всего, останется пустым: даже приёмщик, который «ничего не чинит», запускает
# скрипты, а те кладут экраны, замеры и отчёт в папку работы. Запрет на запись сломал бы его
# первой же командой — роль обязана работать одинаково во всех трёх инструментах.
ТОЛЬКО_ЧТЕНИЕ: set[str] = set()


def разобрать(файл):
    """Достать шапку и тело из markdown-описания роли."""
    текст = файл.read_text(encoding="utf-8")
    совпадение = re.match(r"^---\n(.*?)\n---\n(.*)$", текст, re.S)
    if not совпадение:
        print(f"⚠️  {файл.name}: нет шапки между --- --- , пропускаю")
        return None
    шапка_текст, тело = совпадение.groups()
    шапка = {}
    ключ = None
    for строка in шапка_текст.split("\n"):
        если_поле = re.match(r"^([a-zA-Z_]+):\s*(.*)$", строка)
        if если_поле:
            ключ, значение = если_поле.groups()
            шапка[ключ] = значение.strip()
        elif ключ and строка.strip():
            шапка[ключ] += " " + строка.strip()
    шапка.setdefault("name", файл.stem)
    return шапка, тело.strip()


def экранировать(текст):
    return текст.replace("\\", "\\\\").replace('"', '\\"')


def собрать_codex(имя, шапка, тело):
    строки = [
        f"# Роль «{имя}» для Codex. Собрано из .claude/agents/{имя}.md — правьте там.",
        f'name = "{имя}"',
        f'description = "{экранировать(шапка.get("description", ""))}"',
    ]
    if имя in ТОЛЬКО_ЧТЕНИЕ:
        строки.append('sandbox_mode = "read-only"')
    строки += ['developer_instructions = """', тело, '"""', ""]
    return "\n".join(строки)


def собрать_kimi(имя, шапка, тело):
    инструменты = [
        ИНСТРУМЕНТЫ_KIMI.get(и.strip(), и.strip())
        for и in шапка.get("tools", "").split(",")
        if и.strip()
    ]
    строки = ["---", f"name: {имя}", f"description: {шапка.get('description', '')}"]
    if инструменты:
        строки.append("tools:")
        строки += [f"  - {и}" for и in инструменты]
    строки += ["---", "", ШАПКА.format(имя=имя), "", тело, ""]
    return "\n".join(строки)


def собрать_конфиг(роли):
    строки = [
        "# Настройки Codex для этой системы. Собрано ядро/скрипты/sync_agents.py — правьте роли,",
        "# а не этот файл.",
        "",
        "[agents]",
        "enabled = true",
        "max_concurrent_threads_per_session = 3",
        "max_depth = 1",
        "",
    ]
    for имя, шапка in роли:
        строки += [
            f"[agents.{имя.replace('-', '_')}]",
            f'description = "{экранировать(шапка.get("description", ""))}"',
            f'config_file = "./agents/{имя}.toml"',
            "",
        ]
    return "\n".join(строки)


def main():
    только_проверить = "--проверить" in sys.argv or "--check" in sys.argv
    файлы = sorted(ИСТОЧНИК.glob("*.md"))
    if not файлы:
        print("⛔ В .claude/agents/ нет ни одного описания роли.")
        sys.exit(1)

    CODEX.mkdir(parents=True, exist_ok=True)
    KIMI.mkdir(parents=True, exist_ok=True)

    роли, расхождения = [], []
    for файл in файлы:
        разобранное = разобрать(файл)
        if not разобранное:
            continue
        шапка, тело = разобранное
        имя = файл.stem
        роли.append((имя, шапка))

        для_записи = {
            CODEX / f"{имя}.toml": собрать_codex(имя, шапка, тело),
            KIMI / f"{имя}.md": собрать_kimi(имя, шапка, тело),
        }
        for путь, содержимое in для_записи.items():
            старое = путь.read_text(encoding="utf-8") if путь.exists() else None
            if старое == содержимое:
                continue
            расхождения.append(путь.relative_to(ROOT))
            if not только_проверить:
                путь.write_text(содержимое, encoding="utf-8")

    конфиг = собрать_конфиг(роли)
    старый = CODEX_CONFIG.read_text(encoding="utf-8") if CODEX_CONFIG.exists() else None
    if старый != конфиг:
        расхождения.append(CODEX_CONFIG.relative_to(ROOT))
        if not только_проверить:
            CODEX_CONFIG.write_text(конфиг, encoding="utf-8")

    print(f"Ролей в системе: {len(роли)} — " + ", ".join(и for и, _ in роли))
    if только_проверить:
        if расхождения:
            print("\n⚠️  Разъехались (пересоберите ядро/скрипты/sync_agents.py):")
            for п in расхождения:
                print(f"   {п}")
            sys.exit(1)
        print("✅ Все три формата совпадают.")
        return
    if расхождения:
        print(f"\n✅ Пересобрано файлов: {len(расхождения)}")
        for п in расхождения:
            print(f"   {п}")
    else:
        print("✅ Всё уже совпадало, менять нечего.")


if __name__ == "__main__":
    main()
