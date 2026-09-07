"""Тесты служебных скриптов: что_уедет, sync_agents, глаза.

Запуск из корня репозитория:
    .venv/bin/python -m unittest discover -s ядро/скрипты/tests -t .
"""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

СКРИПТЫ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(СКРИПТЫ))

import глаза  # noqa: E402
import sync_agents  # noqa: E402
import что_уедет  # noqa: E402


class ЧемОпасенТесты(unittest.TestCase):
    def setUp(self):
        self._временная = tempfile.TemporaryDirectory()
        self.корень = Path(self._временная.name)
        self.addCleanup(self._временная.cleanup)

    def test_ловит_env(self):
        файл = self.корень / ".env"
        файл.write_text("SECRET=1\n", encoding="utf-8")
        причины = что_уедет.чем_опасен(файл, self.корень)
        self.assertTrue(причины, "файл .env должен считаться опасным")

    def test_ловит_профили(self):
        папка = self.корень / "профили" / "клиент-1"
        папка.mkdir(parents=True)
        файл = папка / "profile.json"
        файл.write_text("{}", encoding="utf-8")
        причины = что_уедет.чем_опасен(файл, self.корень)
        self.assertTrue(причины, "профиль с данными клиента должен считаться опасным")

    def test_пропускает_шаблон(self):
        папка = self.корень / "профили" / "_шаблон"
        папка.mkdir(parents=True)
        файл = папка / "profile.json"
        файл.write_text("{}", encoding="utf-8")
        причины = что_уедет.чем_опасен(файл, self.корень)
        self.assertEqual(причины, [], "учебный шаблон уезжает вместе с системой")


class РазобратьТесты(unittest.TestCase):
    def test_парсит_шапку_и_тело(self):
        with tempfile.TemporaryDirectory() as папка:
            файл = Path(папка) / "site-checker.md"
            файл.write_text(
                "---\n"
                "name: site-checker\n"
                "description: проверяющий собранный сайт свежим взглядом\n"
                "tools: Read, Bash\n"
                "---\n"
                "Текст роли для нейросети.\n",
                encoding="utf-8",
            )
            разобранное = sync_agents.разобрать(файл)
            self.assertIsNotNone(разобранное)
            шапка, тело = разобранное
            self.assertEqual(шапка["name"], "site-checker")
            self.assertEqual(шапка["description"], "проверяющий собранный сайт свежим взглядом")
            self.assertEqual(шапка["tools"], "Read, Bash")
            self.assertEqual(тело, "Текст роли для нейросети.")

    def test_без_шапки_возвращает_none(self):
        with tempfile.TemporaryDirectory() as папка:
            файл = Path(папка) / "без-шапки.md"
            файл.write_text("Просто текст, без шапки.\n", encoding="utf-8")
            # разобрать() честно предупреждает в stdout — здесь это ожидаемо, не даём
            # этому шуму попасть в чистый вывод тестов.
            with contextlib.redirect_stdout(io.StringIO()):
                результат = sync_agents.разобрать(файл)
            self.assertIsNone(результат)


class РазмерыТесты(unittest.TestCase):
    def test_оба_размера_на_месте(self):
        self.assertIn("компьютер", глаза.РАЗМЕРЫ)
        self.assertIn("телефон", глаза.РАЗМЕРЫ)

    def test_ширины_экранов(self):
        self.assertEqual(глаза.РАЗМЕРЫ["компьютер"]["viewport"]["width"], 1440)
        self.assertEqual(глаза.РАЗМЕРЫ["компьютер"]["viewport"]["height"], 900)
        self.assertEqual(глаза.РАЗМЕРЫ["телефон"]["viewport"]["width"], 390)
        self.assertEqual(глаза.РАЗМЕРЫ["телефон"]["viewport"]["height"], 844)

    def test_телефон_мобильный_и_с_касанием(self):
        self.assertTrue(глаза.РАЗМЕРЫ["телефон"]["is_mobile"])
        self.assertTrue(глаза.РАЗМЕРЫ["телефон"]["has_touch"])


if __name__ == "__main__":
    unittest.main()
