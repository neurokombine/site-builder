"""Витрина: первый экран из прототипа в каждом варианте дизайн-системы — три композиции, в двух видах."""
import subprocess, sys, tempfile, unittest, shutil
from pathlib import Path
СКРИПТЫ = Path(__file__).resolve().parent.parent
ФИКСТУРЫ = Path(__file__).resolve().parent / "фикстуры"
sys.path.insert(0, str(СКРИПТЫ))
import витрина, глаза, находки, собрать  # noqa: E402


def _скопировать_образец(д: Path) -> Path:
    """Копия работа-образец в д/работа и профиль-образец рядом — как selftest._прогнать_сборку:
    так слот связи получает настоящую кнопку, а не запасную с 🟡."""
    shutil.copytree(ФИКСТУРЫ / "работа-образец", д / "работа")
    shutil.copytree(ФИКСТУРЫ / "профиль-образец", д / "профиль-образец")
    return д / "работа"


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
        self.assertIn("Композиция: постер · тёмная · пятна · иконки плотные", текст)
        self.assertIn("вариант-2/телефон.png", текст)
        self.assertIn("Снято", текст)


class ФиксВолнаТесты(unittest.TestCase):
    """Фикс-волна: относительный путь из чужой папки."""

    def test_относительный_путь_из_чужой_папки(self):
        # п. 1: `витрина.py сайты/<имя> --без-показа` падал ValueError в as_uri() — снимки идут до показа.
        with tempfile.TemporaryDirectory() as д:
            shutil.copytree(ФИКСТУРЫ / "работа-образец", Path(д) / "работа")
            р = subprocess.run([sys.executable, str(СКРИПТЫ / "витрина.py"), "работа", "--без-показа"],
                               cwd=д, capture_output=True, text=True, timeout=180)
            self.assertEqual(р.returncode, 0, р.stdout + р.stderr)
            self.assertTrue((Path(д) / "работа" / "витрина" / "витрина.html").exists())


class ИзПрототипаТесты(unittest.TestCase):
    """Витрина строит первый экран из прототипа и рецепта концепции варианта, а не из экраны/:
    три варианта — три разные композиции, на телефоне липкая кнопка, иконки инлайн, заглушек нет."""

    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls._playwright = sync_playwright().start()
        cls.браузер = глаза.запустить_браузер(cls._playwright)

    @classmethod
    def tearDownClass(cls):
        cls.браузер.close()
        cls._playwright.stop()

    def test_тексты_первого_экрана_из_прототипа(self):
        т = витрина.тексты_первого_экрана(ФИКСТУРЫ / "работа-образец")
        self.assertEqual((т["пресет"], т["заголовок"], т["акцент"]), ("визитка", "Математика без паники за три", "месяца"))
        self.assertEqual((len(т["пункты"]), т["кнопка"], т["фото"]), (3, "Написать про занятия", "пример.svg"))
        self.assertEqual(т["цифры"], [("6", "лет занятий"), ("40", "учеников закончили год без троек")])
        self.assertTrue(т["кикер"].startswith("родитель восьмиклассника"))

    def test_три_композиции(self):
        with tempfile.TemporaryDirectory() as д:
            работа = _скопировать_образец(Path(д))   # копия работа-образец + профиль-образец рядом
            shutil.rmtree(работа / "экраны")           # витрине экраны/ не нужны: первый экран — из прототипа
            дизайн = работа / "дизайн.md"
            текст = дизайн.read_text(encoding="utf-8")
            третий = ("\n## Вариант 3 · Орбита\nЧем отличается: тёмный экран с четырьмя карточками вокруг\n"
                      "- Концепция первого экрана: орбита\n- Доминанта: тёмная\n- Атмосфера: сетка\n- Иконки: плотные\n\n"
                      "```css\n" + текст.split("```css\n")[1].split("```")[0] + "```\n")
            дизайн.write_text(текст.replace("\n## Решения", третий + "\n## Решения"), encoding="utf-8")
            итог, н = витрина.витрина(работа, куда=Path(д) / "витрина", браузер=self.браузер)
            self.assertFalse(находки.есть_красное(н), н)
            страницы = {н: (Path(д) / "витрина" / f"вариант-{н}" / "index.html").read_text(encoding="utf-8") for н in (1, 2, 3)}
            for номер, концепция, темно in ((1, "разворот", False), (2, "постер", True), (3, "орбита", True)):
                self.assertIn(f'data-концепция="{концепция}"', страницы[номер])
                self.assertEqual(" тёмный" in страницы[номер].split("</section>")[0], темно)
                for кусок in ('class="липкая-кнопка"', '<svg class="иконка"', 'href="https://t.me/пример"'):
                    self.assertIn(кусок, страницы[номер])
                self.assertNotIn("{{", страницы[номер])
            self.assertIn("фон--пятна", страницы[2]); self.assertIn("орбита__спутник", страницы[3])
            self.assertIn('stroke-width="1.5"', страницы[1]); self.assertIn('stroke-width="2"', страницы[3])
            self.assertTrue((Path(д) / "витрина" / "вариант-3" / "телефон.png").is_file())
            self.assertIn("Композиция: орбита · тёмная · сетка · иконки плотные", итог.read_text(encoding="utf-8"))

    def test_нет_прототипа_красное(self):
        with tempfile.TemporaryDirectory() as д:
            работа = _скопировать_образец(Path(д))
            (работа / "прототип.md").unlink()
            _, н = витрина.витрина(работа, куда=Path(д) / "витрина", браузер=self.браузер)
            self.assertEqual(н[-1]["что"], "Нет первого экрана в прототипе")
            self.assertFalse((Path(д) / "витрина" / "витрина.html").exists())

    def test_без_концепции_жёлтое_и_повтор_к_сведению(self):
        with tempfile.TemporaryDirectory() as д:
            работа = _скопировать_образец(Path(д))
            дизайн = работа / "дизайн.md"
            текст = дизайн.read_text(encoding="utf-8").replace("- Концепция первого экрана: постер\n", "")
            дизайн.write_text(текст, encoding="utf-8")
            _, н = витрина.витрина(работа, куда=Path(д) / "витрина", браузер=self.браузер)
            self.assertFalse(находки.есть_красное(н), н)
            по_имени = {x["что"]: x for x in н}
            self.assertIn("взят разворот", " ".join(по_имени["Вариант без концепции первого экрана"]["строки"]))
            self.assertEqual(по_имени["Вариант без концепции первого экрана"]["уровень"], находки.ПОПРАВИТЬ)
            self.assertEqual(по_имени["Два варианта с одной концепцией"]["уровень"], находки.К_СВЕДЕНИЮ)
            self.assertIn("разворот", " ".join(по_имени["Два варианта с одной концепцией"]["строки"]))
            вторая = (Path(д) / "витрина" / "вариант-2" / "index.html").read_text(encoding="utf-8")
            self.assertIn('data-концепция="разворот"', вторая)
            self.assertIn(" тёмный", вторая.split("</section>")[0])   # доминанта варианта 2 всё равно применилась


if __name__ == "__main__":
    unittest.main()
