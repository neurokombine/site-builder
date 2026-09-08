"""Общий модуль находок: уровни, форма находки, отчёт по уровням, код выхода, кодировка вывода.

Плюс охрана от дублей: константы уровней и вывод_в_utf8 живут в одном месте.
"""
import io
import re
import sys
import unittest
from pathlib import Path

СКРИПТЫ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(СКРИПТЫ))
import находки  # noqa: E402


class НаходкиТесты(unittest.TestCase):
    def test_форма_находки(self):
        н = находки.находка(находки.ЧИНИТЬ, "заглушка", ["index.html: «Ваше имя»"], "увидят чужие")
        self.assertEqual(н, {"уровень": "🔴", "что": "заглушка", "чем_грозит": "увидят чужие",
                             "строки": ["index.html: «Ваше имя»"]})

    def test_код_выхода(self):
        красная = [находки.находка(находки.ЧИНИТЬ, "а", [])]
        жёлтая = [находки.находка(находки.ПОПРАВИТЬ, "б", [])]
        self.assertEqual(находки.код_выхода(красная), 1)
        self.assertEqual(находки.код_выхода(жёлтая), 0)
        self.assertTrue(находки.есть_красное(красная + жёлтая))
        self.assertFalse(находки.есть_красное([]))

    def test_заголовки_уровней(self):
        з = находки.заголовки_уровней("вёрстки")
        self.assertEqual(з[находки.ЧИНИТЬ], "Чинить до вёрстки")
        self.assertEqual(находки.заголовки_уровней()[находки.ЧИНИТЬ], "Чинить до показа")
        self.assertEqual(list(з), list(находки.УРОВНИ))

    def test_строки_по_уровням(self):
        н = [находки.находка(находки.ЧИНИТЬ, "Заглушка в тексте", ["«Ваше имя»"], "увидят чужие люди"),
             находки.находка(находки.К_СВЕДЕНИЮ, "Вес страницы", ["120 КБ"], "просто число")]
        строки = находки.строки_по_уровням(н, находки.заголовки_уровней())
        текст = "\n".join(строки)
        self.assertIn("## 🔴 Чинить до показа — 1", текст)
        self.assertIn("### Заглушка в тексте", текст)
        self.assertIn("Чем грозит: увидят чужие люди.", текст)
        self.assertIn("## 🟡 Стоит поправить — 0", текст)
        self.assertIn("Ничего не нашлось.", текст)
        self.assertIn("просто число", текст)
        self.assertNotIn("Чем грозит: просто число", текст)   # ℹ️ ничем не грозит

    def test_вывод_в_utf8_не_падает_на_потоке_без_reconfigure(self):
        подмена = io.StringIO()
        старые = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = подмена
        try:
            находки.вывод_в_utf8()   # у StringIO нет reconfigure — не должно упасть
            print("🔴")
        finally:
            sys.stdout, sys.stderr = старые
        self.assertIn("🔴", подмена.getvalue())


class ОдинДомТесты(unittest.TestCase):
    """Дубли — то, ради чего модуль заведён: их не должно остаться."""
    def _файлы(self):
        return [п for п in СКРИПТЫ.glob("*.py") if п.name != "находки.py"]

    def test_вывод_в_utf8_только_в_находках(self):
        for п in self._файлы():
            with self.subTest(файл=п.name):
                self.assertNotIn("def вывод_в_utf8", п.read_text(encoding="utf-8"))

    def test_уровни_только_в_находках(self):
        for п in self._файлы():
            with self.subTest(файл=п.name):
                self.assertIsNone(re.search(r'^ЧИНИТЬ\s*=\s*"', п.read_text(encoding="utf-8"), re.M))

    def test_скрипты_с_эмодзи_настраивают_вывод(self):
        for имя in ("проверить.py", "проверить_прототип.py", "selftest.py", "ресёрч_ниши.py"):
            with self.subTest(файл=имя):
                self.assertIn("вывод_в_utf8()", (СКРИПТЫ / имя).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
