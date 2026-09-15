"""Помощник верстальщика: что открыть перед экраном этого типа. Ничего не пишет — только печатает."""
import io
import contextlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

СКРИПТЫ = Path(__file__).resolve().parent.parent
ФИКСТУРЫ = Path(__file__).resolve().parent / "фикстуры"
sys.path.insert(0, str(СКРИПТЫ))

import экран  # noqa: E402

ПОТОЛОК_СТРОК = 120   # подсказка для слабых моделей, а не второй скрипт сборки


def _вывод(argv) -> tuple[int, str]:
    поток = io.StringIO()
    with contextlib.redirect_stdout(поток):
        код = экран.main_с_аргументами(argv)
    return код, поток.getvalue()


class ПодсказкаТесты(unittest.TestCase):
    def test_печатает_инструкцию_примеры_и_напоминание(self):
        with tempfile.TemporaryDirectory() as д:
            работа = Path(д) / "работа"
            shutil.copytree(ФИКСТУРЫ / "работа-образец", работа)
            код, текст = _вывод(["отзывы", "--работа", str(работа)])
        self.assertEqual(код, 0, текст)
        self.assertIn("ядро/экраны/отзывы.md", текст)
        self.assertIn("галерея/примеры/отзывы/лендинг", текст)
        self.assertIn("галерея/примеры/отзывы/визитка", текст)
        self.assertIn("страница-целиком", текст)
        self.assertIn("дизайн.md", текст)
        self.assertIn("Контракт", текст)

    def test_беру_из_референсов_работы(self):
        with tempfile.TemporaryDirectory() as д:
            работа = Path(д) / "работа"
            shutil.copytree(ФИКСТУРЫ / "работа-образец", работа)
            (работа / "референсы.md").write_text(
                "# Референсы\n\n## Беру\n\n- [x] ленту шагов с цифрами\n"
                "- [ ] тёмный первый экран\n- [X] отбивку итога цветом\n", encoding="utf-8")
            _, текст = _вывод(["отзывы", "--работа", str(работа)])
        self.assertIn("ленту шагов с цифрами", текст)
        self.assertIn("отбивку итога цветом", текст)
        self.assertNotIn("тёмный первый экран", текст)

    def test_без_раздела_беру_так_и_говорим(self):
        with tempfile.TemporaryDirectory() as д:
            работа = Path(д) / "работа"
            shutil.copytree(ФИКСТУРЫ / "работа-образец", работа)
            _, текст = _вывод(["отзывы", "--работа", str(работа)])
        self.assertIn("«Беру»", текст)
        self.assertIn("нет", текст.lower())

    def test_незнакомый_тип_называет_все(self):
        with tempfile.TemporaryDirectory() as д:
            работа = Path(д) / "работа"
            shutil.copytree(ФИКСТУРЫ / "работа-образец", работа)
            код, текст = _вывод(["витрина-роликов", "--работа", str(работа)])
        self.assertEqual(код, 2)
        self.assertIn("отзывы", текст)
        self.assertIn("первый-экран", текст)

    def test_работа_не_обязательна(self):
        код, текст = _вывод(["боль"])
        self.assertEqual(код, 0, текст)
        self.assertIn("ядро/экраны/боль.md", текст)

    def test_скрипт_запускается_командой(self):
        р = subprocess.run([sys.executable, str(СКРИПТЫ / "экран.py"), "отзывы"],
                           capture_output=True, text=True, timeout=120)
        self.assertEqual(р.returncode, 0, р.stdout + р.stderr)
        self.assertIn("отзывы.md", р.stdout)

    def test_помощник_не_растёт(self):
        сколько = len((СКРИПТЫ / "экран.py").read_text(encoding="utf-8").splitlines())
        self.assertLessEqual(сколько, ПОТОЛОК_СТРОК,
                             f"экран.py на {сколько} строк при потолке {ПОТОЛОК_СТРОК}")


if __name__ == "__main__":
    unittest.main()
