"""Сборка страницы: дизайн, служебная голова, экраны, связь, заглушки — и показ в двух размерах."""
import json, subprocess, sys, tempfile, unittest
from pathlib import Path
СКРИПТЫ = Path(__file__).resolve().parent.parent
ФИКСТУРЫ = Path(__file__).resolve().parent / "фикстуры"
ЯДРО = СКРИПТЫ.parent
sys.path.insert(0, str(СКРИПТЫ))
import находки  # noqa: E402
import собрать  # noqa: E402


class ЧистыеТесты(unittest.TestCase):
    def test_дизайн_варианты_и_решения(self):
        д = собрать.прочитать_дизайн(ФИКСТУРЫ / "работа-образец" / "дизайн.md")
        self.assertEqual([в["номер"] for в in д["варианты"]], [1, 2])
        self.assertIn("--цвет-акцент", д["варианты"][0]["css"])
        self.assertIn(":root", д["решения"])
        self.assertEqual(д["статус"], "выбран")

    def test_поиск_умолчания_без_файла(self):
        п = собрать.прочитать_поиск(None)
        self.assertEqual(п["статус"], "закрыт")
        self.assertFalse(п["есть_файл"])

    def test_шрифты(self):
        css = "--шрифт-заголовков: 'Montserrat', system-ui; --шрифт-текста: 'Open Sans', sans-serif;"
        ссылка = собрать.ссылка_на_шрифты(css)
        self.assertIn("family=Montserrat", ссылка)
        self.assertIn("family=Open+Sans", ссылка)
        self.assertEqual(собрать.ссылка_на_шрифты("--шрифт-заголовков: Arial; --шрифт-текста: Georgia;"), "")

    def test_ссылка_связи(self):
        self.assertEqual(собрать.ссылка_связи("телеграм", "@пример"), "https://t.me/пример")
        self.assertEqual(собрать.ссылка_связи("whatsapp", "+7 (900) 000-00-00"), "https://wa.me/79000000000")
        self.assertEqual(собрать.ссылка_связи("форма", "пример.рф/заказ"), "https://пример.рф/заказ")
        self.assertEqual(собрать.ссылка_связи("почта", "вы@пример.рф"), "mailto:вы@пример.рф")

    def test_начинка_кнопка_и_виджет(self):
        профиль = json.loads((ФИКСТУРЫ / "профиль-образец" / "profile.json").read_text(encoding="utf-8"))
        html, н = собрать.начинка_связи("Написать", профиль, None)
        self.assertIn('href="https://t.me/пример"', html)
        self.assertIsNone(н)
        with tempfile.TemporaryDirectory() as д:
            (Path(д) / "виджет.html").write_text("<script>виджет</script>", encoding="utf-8")
            профиль["сайт"]["связь"] = {"способ": "виджет", "адрес": ""}
            html, н = собрать.начинка_связи("Написать", профиль, Path(д))
            self.assertEqual(html, "<script>виджет</script>")
        html, н = собрать.начинка_связи("Написать", None, None)
        self.assertIn("#экран-контакты", html)
        self.assertEqual(н["уровень"], находки.ПОПРАВИТЬ)

    def test_заглушки(self):
        self.assertEqual(собрать.найти_заглушки("<h1>{{ЗАГОЛОВОК}}</h1>{{СВЯЗЬ:Написать}} {{ЗАГОЛОВОК}}"),
                         ["{{ЗАГОЛОВОК}}", "{{СВЯЗЬ:Написать}}"])

    def test_сборка_образца_чистая(self):
        with tempfile.TemporaryDirectory() as д:
            путь, н = собрать.собрать(ФИКСТУРЫ / "работа-образец", куда=Path(д))
            html = путь.read_text(encoding="utf-8")
            self.assertNotIn(находки.ЧИНИТЬ, [x["уровень"] for x in н], н)
            self.assertIn('content="noindex, nofollow"', html)
            self.assertIn("<title>Репетитор по математике", html)
            self.assertLess(html.index('id="экран-1"'), html.index('id="экран-2"'))
            self.assertIn("--цвет-акцент", html)
            self.assertIn('href="https://t.me/пример"', html)
            self.assertTrue((Path(д) / "style.css").exists())
            self.assertTrue((Path(д) / ".nojekyll").exists())
            self.assertIn("Disallow: /", (Path(д) / "robots.txt").read_text(encoding="utf-8"))

    def test_оставшаяся_заглушка_красная(self):
        with tempfile.TemporaryDirectory() as д:
            работа = Path(д) / "работа"
            import shutil; shutil.copytree(ФИКСТУРЫ / "работа-образец", работа)
            экран = работа / "экраны" / "02-услуги-и-цены.html"
            экран.write_text(экран.read_text(encoding="utf-8").replace("Разбор пробелов", "{{УСЛУГА}}"), encoding="utf-8")
            _, н = собрать.собрать(работа)
            self.assertIn(находки.ЧИНИТЬ, [x["уровень"] for x in н])
            self.assertIn("{{УСЛУГА}}", " ".join(x["что"] + " ".join(x["строки"]) for x in н))


class ПоказТесты(unittest.TestCase):
    def test_1_показ_двух_размеров(self):
        with tempfile.TemporaryDirectory() as д:
            путь, _ = собрать.собрать(ФИКСТУРЫ / "работа-образец", куда=Path(д) / "сайт")
            показ = собрать.показать(путь.parent, Path(д) / "показ", экран=2)
            self.assertTrue((Path(д) / "показ" / "компьютер.png").exists())
            self.assertTrue((Path(д) / "показ" / "телефон.png").exists())
            self.assertIn("Одобрение = одобрение обоих", показ.read_text(encoding="utf-8"))

    def test_2_все_блоки_без_красного(self):
        """Гейт GC 15: страница из всех шестнадцати блоков проходит проверить.py без 🔴."""
        with tempfile.TemporaryDirectory() as д:
            работа = Path(д) / "все"
            (работа / "экраны").mkdir(parents=True)
            for ф in sorted((ФИКСТУРЫ / "экраны-все").glob("*.html")):
                (работа / "экраны" / ф.name).write_text(ф.read_text(encoding="utf-8"), encoding="utf-8")
            for имя in ("дизайн.md", "поиск.md", "прототип.md"):
                (работа / имя).write_text((ФИКСТУРЫ / "работа-образец" / имя).read_text(encoding="utf-8"), encoding="utf-8")
            путь, н = собрать.собрать(работа)
            self.assertNotIn(находки.ЧИНИТЬ, [x["уровень"] for x in н], н)
            р = subprocess.run([sys.executable, str(СКРИПТЫ / "проверить.py"), str(путь.parent)],
                               capture_output=True, text=True, timeout=300)
            self.assertEqual(р.returncode, 0, р.stdout[-3000:])

    def test_3_cli_без_показа(self):
        with tempfile.TemporaryDirectory() as д:
            import shutil; shutil.copytree(ФИКСТУРЫ / "работа-образец", Path(д) / "работа")
            р = subprocess.run([sys.executable, str(СКРИПТЫ / "собрать.py"), str(Path(д) / "работа"), "--без-показа"],
                               capture_output=True, text=True, timeout=120)
            self.assertEqual(р.returncode, 0, р.stdout + р.stderr)
            self.assertTrue((Path(д) / "работа" / "сайт" / "index.html").exists())
