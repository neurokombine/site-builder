"""Контракт карты: всё, что CLAUDE.md и как-работаем.md называют без ⏳, существует на диске.

Иначе нейросеть откроет несуществующий файл и решит, что система сломана.
"""
import re
import unittest
from pathlib import Path

КОРЕНЬ = Path(__file__).resolve().parents[3]
ЯДРО = КОРЕНЬ / "ядро"
ИМЯ = re.compile(r"`([\w\-]+\.(?:md|py))`")
РАБОЧИЕ = {"разведка.md", "референсы.md", "прототип.md", "дизайн.md", "журнал.md",
           "отчёт.md", "замеры.md", "_сводка.md", "profile.json", "README.md",
           "ЕСЛИ-СЛОМАЛОСЬ.md", "CLAUDE.md", "AGENTS.md", "index.html"}


def названные_без_ожидания(текст: str, только_строки=None) -> set[str]:
    имена = set()
    for строка in текст.splitlines():
        if "⏳" in строка:
            continue
        if только_строки and not только_строки(строка):
            continue
        имена.update(ИМЯ.findall(строка))
    return имена


def существует_в_ядре(имя: str) -> bool:
    return (ЯДРО / имя).exists() or (ЯДРО / "скрипты" / имя).exists()


class КартаТесты(unittest.TestCase):
    def test_таблица_маршрута_в_claude_md(self):
        текст = (КОРЕНЬ / "CLAUDE.md").read_text(encoding="utf-8")
        строки_таблицы = lambda с: с.startswith("| ") and с.count("|") >= 5
        for имя in названные_без_ожидания(текст, строки_таблицы) - РАБОЧИЕ:
            with self.subTest(имя=имя):
                self.assertTrue(существует_в_ядре(имя), f"CLAUDE.md называет {имя} без ⏳, а файла нет")

    def test_строки_открыть_в_дороге(self):
        текст = (ЯДРО / "как-работаем.md").read_text(encoding="utf-8")
        открыть = lambda с: с.strip().startswith("- **Открыть:**")
        for имя in названные_без_ожидания(текст, открыть) - РАБОЧИЕ:
            with self.subTest(имя=имя):
                self.assertTrue(существует_в_ядре(имя), f"как-работаем.md велит открыть {имя}, а файла нет")

    def test_каждый_файл_ядра_назван_в_карте(self):
        карта = (КОРЕНЬ / "CLAUDE.md").read_text(encoding="utf-8")
        for файл in ЯДРО.glob("*.md"):
            with self.subTest(файл=файл.name):
                self.assertIn(f"`{файл.name}`", карта, f"{файл.name} лежит в ядре, но CLAUDE.md о нём молчит")


if __name__ == "__main__":
    unittest.main()
