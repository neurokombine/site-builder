"""Витрина: первый экран в каждом варианте дизайн-системы, рядом в двух видах."""
import subprocess, sys, tempfile, unittest, shutil
from pathlib import Path
СКРИПТЫ = Path(__file__).resolve().parent.parent
ФИКСТУРЫ = Path(__file__).resolve().parent / "фикстуры"
sys.path.insert(0, str(СКРИПТЫ))
import витрина, находки, собрать  # noqa: E402


class ВитринаТесты(unittest.TestCase):
    def test_варианты_и_перекраска(self):
        д = собрать.прочитать_дизайн(ФИКСТУРЫ / "работа-образец" / "дизайн.md")
        в = витрина.варианты_из(д)
        self.assertEqual(len(в), 2)
        html = "<html><head><style>\n:root{--а:1}\n</style></head><body></body></html>"
        self.assertIn("--цвет-акцент", витрина.перекрасить(html, в[1]["css"]))
        self.assertNotIn("--а:1", витрина.перекрасить(html, в[1]["css"]))

    def test_1_витрина_двух_вариантов(self):
        with tempfile.TemporaryDirectory() as д:
            shutil.copytree(ФИКСТУРЫ / "работа-образец", Path(д) / "работа")
            путь, н = витрина.витрина(Path(д) / "работа")
            self.assertNotIn(находки.ЧИНИТЬ, [x["уровень"] for x in н], н)
            for n in (1, 2):
                папка = Path(д) / "работа" / "витрина" / f"вариант-{n}"
                self.assertTrue((папка / "index.html").exists())
                self.assertTrue((папка / "компьютер.png").exists())
                self.assertTrue((папка / "телефон.png").exists())
            текст = путь.read_text(encoding="utf-8")
            self.assertIn("Вариант 1", текст)
            self.assertIn("Вариант 2", текст)
            self.assertIn("тот же прототип стал другой страницей", текст)

    def test_2_один_вариант_красный(self):
        with tempfile.TemporaryDirectory() as д:
            shutil.copytree(ФИКСТУРЫ / "работа-образец", Path(д) / "работа")
            дизайн = Path(д) / "работа" / "дизайн.md"
            текст = дизайн.read_text(encoding="utf-8")
            дизайн.write_text(текст[:текст.index("## Вариант 2")] + текст[текст.index("## Решения"):], encoding="utf-8")
            р = subprocess.run([sys.executable, str(СКРИПТЫ / "витрина.py"), str(Path(д) / "работа"), "--без-показа"],
                               capture_output=True, text=True, timeout=120)
            self.assertEqual(р.returncode, 1, р.stdout)
            self.assertIn("две-три на выбор", р.stdout)


class ЧемОтличаетсяТесты(unittest.TestCase):
    """Строка «Чем отличается» доезжает из дизайн.md до витрины: без неё человек сравнивает вслепую."""

    def test_строка_из_дизайна_попадает_на_витрину(self):
        д = собрать.прочитать_дизайн(ФИКСТУРЫ / "работа-образец" / "дизайн.md")
        self.assertEqual(д["варианты"][0]["чем_отличается"],
                         "белый лист и один синий акцент — как чистая страница в тетради")
        текст = витрина._страница_витрины("проба", витрина.варианты_из(д))
        self.assertIn("Чем отличается: белый лист и один синий акцент", текст)
        self.assertIn("вариант-2/телефон.png", текст)
        self.assertIn("Снято", текст)


class ФиксВолнаТесты(unittest.TestCase):
    """Фикс-волна: относительный путь и 🔴 «нет первого экрана»."""

    def test_относительный_путь_из_чужой_папки(self):
        # п. 1: `витрина.py сайты/<имя> --без-показа` падал ValueError в as_uri() — снимки идут до показа.
        with tempfile.TemporaryDirectory() as д:
            shutil.copytree(ФИКСТУРЫ / "работа-образец", Path(д) / "работа")
            р = subprocess.run([sys.executable, str(СКРИПТЫ / "витрина.py"), "работа", "--без-показа"],
                               cwd=д, capture_output=True, text=True, timeout=180)
            self.assertEqual(р.returncode, 0, р.stdout + р.stderr)
            self.assertTrue((Path(д) / "работа" / "витрина" / "витрина.html").exists())

    def test_нет_первого_экрана_красное(self):
        with tempfile.TemporaryDirectory() as д:
            shutil.copytree(ФИКСТУРЫ / "работа-образец", Path(д) / "работа")
            for ф in (Path(д) / "работа" / "экраны").glob("01-*.html"):
                ф.unlink()
            путь, н = витрина.витрина(Path(д) / "работа")
            красные = [x for x in н if x["уровень"] == находки.ЧИНИТЬ]
            self.assertEqual([x["что"] for x in красные], ["Нет первого экрана"], н)
            self.assertFalse(путь.exists())


if __name__ == "__main__":
    unittest.main()
