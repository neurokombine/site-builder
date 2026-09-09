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
        self.assertIn('class="кнопка кнопка--главная"', html)   # ровно так: ГЛАВНАЯ_КНОПКА и пульс в стили.css
        self.assertIsNone(н)
        with tempfile.TemporaryDirectory() as д:
            (Path(д) / "виджет.html").write_text("<script>виджет</script>", encoding="utf-8")
            профиль["сайт"]["связь"] = {"способ": "виджет", "адрес": ""}
            html, н = собрать.начинка_связи("Написать", профиль, Path(д))
            self.assertEqual(html, "<script>виджет</script>")
        html, н = собрать.начинка_связи("Написать", None, None)
        self.assertIn("#экран-контакты", html)
        self.assertIn('class="кнопка кнопка--главная"', html)   # запасная — та же главная кнопка, не вторая
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
            self.assertIn('<body class="с-липкой-кнопкой">', html)   # контракт Д: на телефоне кнопка под пальцем
            self.assertIn('<div class="липкая-кнопка"><a class="кнопка кнопка--главная" href="https://t.me/пример">', html)
            self.assertIn('<svg class="иконка"', html)
            self.assertNotIn("<script>", html)   # таймера в образце нет — и JS в сайт не уезжает
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
            import shutil; shutil.copytree(ФИКСТУРЫ / "работа-образец" / "img", работа / "img")   # блоки ссылаются на img/пример.svg
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


class ПравкиРевьюТесты(unittest.TestCase):
    """Правки ревью: 🟡 называет настоящую причину — битый profile.json и пустое поле в поиск.md."""

    def _копия_образца(self, д: str) -> Path:
        import shutil
        работа = Path(д) / "работа"
        shutil.copytree(ФИКСТУРЫ / "работа-образец", работа)
        return работа

    def test_битый_профиль_называет_файл_а_не_шапку(self):
        with tempfile.TemporaryDirectory() as д:
            работа = self._копия_образца(д)
            профиль = Path(д) / "профиль-образец"
            профиль.mkdir()
            (профиль / "profile.json").write_text("{ это не json", encoding="utf-8")
            _, н = собрать.собрать(работа)
            связь = [x for x in н if x["что"] == "Связь не задана"]
            self.assertEqual(len(связь), 1, н)
            строки = " ".join(связь[0]["строки"])
            self.assertIn("profile.json", строки)
            self.assertNotIn("шапке прототипа", строки)

    def test_пустой_заголовок_вкладки_это_жёлтое_с_именем_поля(self):
        with tempfile.TemporaryDirectory() as д:
            работа = self._копия_образца(д)
            поиск = работа / "поиск.md"
            текст = поиск.read_text(encoding="utf-8")
            self.assertIn("Заголовок вкладки: Репетитор по математике — онлайн", текст)
            поиск.write_text(текст.replace("Заголовок вкладки: Репетитор по математике — онлайн",
                                           "Заголовок вкладки:"), encoding="utf-8")
            _, н = собрать.собрать(работа)
            голова = [x for x in н if x["что"] == "Служебная голова не заполнена"]
            self.assertEqual(len(голова), 1, н)
            строки = " ".join(голова[0]["строки"])
            self.assertIn("Заголовок вкладки", строки)
            self.assertNotIn("Описание для поиска", строки)
            self.assertNotIn(находки.ЧИНИТЬ, [x["уровень"] for x in н])


class ФиксВолнаТесты(unittest.TestCase):
    """Фикс-волна этапов 6–7: относительный путь, ветки _токены и «нет экранов», сверка 21 имени,
    og:image полным адресом."""

    def _копия_образца(self, д: str) -> Path:
        import shutil
        работа = Path(д) / "работа"
        shutil.copytree(ФИКСТУРЫ / "работа-образец", работа)
        return работа

    def test_относительный_путь_из_чужой_папки(self):
        # п. 1: документированная команда `собрать.py сайты/<имя>` — путь относительный; без
        # resolve() as_uri() падал трейсбеком. Запуск из временной папки, аргумент — «работа».
        with tempfile.TemporaryDirectory() as д:
            self._копия_образца(д)
            р = subprocess.run([sys.executable, str(СКРИПТЫ / "собрать.py"), "работа", "--без-показа"],
                               cwd=д, capture_output=True, text=True, timeout=120)
            self.assertEqual(р.returncode, 0, р.stdout + р.stderr)
            self.assertTrue((Path(д) / "работа" / "сайт" / "index.html").exists())

    def test_нет_решений_при_двух_вариантах_красное(self):
        with tempfile.TemporaryDirectory() as д:
            работа = self._копия_образца(д)
            дизайн = работа / "дизайн.md"
            текст = дизайн.read_text(encoding="utf-8")
            дизайн.write_text(текст[:текст.index("## Решения")], encoding="utf-8")
            _, н = собрать.собрать(работа)
            красные = [x for x in н if x["уровень"] == находки.ЧИНИТЬ]
            self.assertEqual(len(красные), 1, н)
            self.assertIn("Решения", красные[0]["что"])
            self.assertIn("витриной", " ".join(красные[0]["строки"]))

    def test_единственный_вариант_к_сведению(self):
        with tempfile.TemporaryDirectory() as д:
            работа = self._копия_образца(д)
            дизайн = работа / "дизайн.md"
            текст = дизайн.read_text(encoding="utf-8")
            дизайн.write_text(текст[:текст.index("## Вариант 2")], encoding="utf-8")
            путь, н = собрать.собрать(работа)
            self.assertNotIn(находки.ЧИНИТЬ, [x["уровень"] for x in н], н)
            взят = [x for x in н if x["что"] == "Взят единственный вариант"]
            self.assertEqual(len(взят), 1, н)
            self.assertEqual(взят[0]["уровень"], находки.К_СВЕДЕНИЮ)
            self.assertIn("--цвет-акцент", путь.read_text(encoding="utf-8"))

    def test_нет_экранов_красное(self):
        with tempfile.TemporaryDirectory() as д:
            работа = self._копия_образца(д)
            for ф in (работа / "экраны").glob("*.html"):
                ф.unlink()
            _, н = собрать.собрать(работа)
            красные = [x for x in н if x["уровень"] == находки.ЧИНИТЬ]
            self.assertEqual([x["что"] for x in красные], ["Нет ни одного экрана"], н)

    def test_имена_переменных_сверяются_со_стилями(self):
        # п. 12: опечатка в имени раньше молча оставляла блок без цвета.
        self.assertEqual(len(собрать.ПЕРЕМЕННЫЕ), 32)
        with tempfile.TemporaryDirectory() as д:
            работа = self._копия_образца(д)
            дизайн = работа / "дизайн.md"
            текст = дизайн.read_text(encoding="utf-8").replace("--цвет-акцент:", "--цвет-акцен:")
            текст = текст.replace("--ширина: 1120px;", "--ширина: 1120px;  --свой-подложка: var(--цвет-фон-2);")
            дизайн.write_text(текст, encoding="utf-8")
            _, н = собрать.собрать(работа)
            имена = [x for x in н if x["что"] == "Имена переменных расходятся со стили.css"]
            self.assertEqual(len(имена), 1, н)
            self.assertEqual(имена[0]["уровень"], находки.ПОПРАВИТЬ)
            строки = " ".join(имена[0]["строки"])
            self.assertIn("не хватает: --цвет-акцент", строки)
            self.assertIn("лишние: --цвет-акцен", строки)
            self.assertNotIn("--свой-подложка", строки)   # свои переменные — не лишние

    def test_образец_без_жёлтого_про_имена(self):
        with tempfile.TemporaryDirectory() as д:
            _, н = собрать.собрать(ФИКСТУРЫ / "работа-образец", куда=Path(д))
            self.assertNotIn("Имена переменных расходятся со стили.css", [x["что"] for x in н], н)

    def _с_карточкой(self, д: str, адрес: str) -> tuple[str, list[dict]]:
        import shutil
        работа = self._копия_образца(д)
        shutil.copytree(ФИКСТУРЫ / "профиль-образец", Path(д) / "профиль-образец")
        профиль_файл = Path(д) / "профиль-образец" / "profile.json"
        данные = json.loads(профиль_файл.read_text(encoding="utf-8"))
        данные["сайт"]["адрес"] = адрес
        профиль_файл.write_text(json.dumps(данные, ensure_ascii=False), encoding="utf-8")
        поиск = работа / "поиск.md"
        поиск.write_text(поиск.read_text(encoding="utf-8").replace("Картинка карточки: нет",
                                                                    "Картинка карточки: img/card.jpg"),
                         encoding="utf-8")
        путь, н = собрать.собрать(работа)
        return путь.read_text(encoding="utf-8"), н

    def test_карточка_с_адресом_сайта_полным_адресом(self):
        # п. 4: og:image по протоколу — полный адрес; относительный мессенджеры не показывают.
        with tempfile.TemporaryDirectory() as д:
            html, н = self._с_карточкой(д, "https://кто-то.github.io/moyo-delo/")
            self.assertIn('<meta property="og:image" content="https://кто-то.github.io/moyo-delo/img/card.jpg">', html)
            self.assertNotIn("Карточка в мессенджере без адреса сайта", [x["что"] for x in н], н)

    def test_карточка_без_адреса_сайта_жёлтое(self):
        with tempfile.TemporaryDirectory() as д:
            html, н = self._с_карточкой(д, "")
            self.assertIn('<meta property="og:image" content="img/card.jpg">', html)
            жёлтые = [x for x in н if x["что"] == "Карточка в мессенджере без адреса сайта"]
            self.assertEqual(len(жёлтые), 1, н)
            self.assertEqual(жёлтые[0]["уровень"], находки.ПОПРАВИТЬ)
            self.assertIn("сайт.адрес", жёлтые[0]["чем_грозит"])


class ДизайнV2Тесты(unittest.TestCase):
    """Дизайн v2: четыре поля варианта, их проверка (🟡, не 🔴), светлота и атмосфера первого экрана из
    полей, липкая кнопка и таймер в сборке, 🟡 когда экран 1 свёрстан не по той концепции."""

    def test_дизайн_v2_поля_варианта_и_решений(self):
        д = собрать.прочитать_дизайн(ФИКСТУРЫ / "работа-образец" / "дизайн.md")
        self.assertEqual(д["варианты"][0]["концепция"], "разворот")
        self.assertEqual(д["варианты"][1]["доминанта"], "тёмная")
        self.assertEqual(д["решения_поля"], {"концепция": "разворот", "доминанта": "светлая",
                                             "атмосфера": "чисто", "иконки": "тонкие"})
        self.assertIn(":root", д["решения"])

    def test_проверить_поля(self):
        ок = {"концепция": "разворот", "доминанта": "светлая", "атмосфера": "чисто", "иконки": "тонкие"}
        self.assertEqual(собрать.проверить_поля(ок, "Решения"), [])
        н = собрать.проверить_поля({**ок, "концепция": "коллаж", "доминанта": ""}, "Вариант 2")
        self.assertEqual((len(н), н[0]["что"], len(н[0]["строки"])), (1, "В дизайн.md поле не заполнено", 2))
        self.assertIn("Вариант 2 · концепция: «коллаж» — можно: разворот, постер, фото, орбита", н[0]["строки"][0])
        self.assertEqual(н[0]["уровень"], находки.ПОПРАВИТЬ)   # собирать не мешает

    def test_применить_вариант(self):
        html = ('<section class="блок блок--первый-экран первый-экран--постер светлый фон--сетка" '
                'id="экран-1" data-тип="первый-экран" data-концепция="постер"><div>x</div></section>')
        итог = собрать.применить_вариант(html, {"доминанта": "тёмная", "атмосфера": "пятна"})
        self.assertIn('class="блок блок--первый-экран первый-экран--постер тёмный фон--пятна"', итог)
        итог = собрать.применить_вариант(итог, {"доминанта": "светлая", "атмосфера": "чисто"})
        self.assertIn('class="блок блок--первый-экран первый-экран--постер светлый"', итог)
        self.assertEqual(собрать.применить_вариант(html, {}), html)

    def test_липкая_кнопка_и_скрипт_таймера(self):
        связь = '<a class="кнопка кнопка--главная" href="https://t.me/пример">Написать</a>'
        html = "<html><body>\n<section>" + связь + "</section>\n</body></html>"
        итог = собрать.липкая_кнопка(html, связь)
        self.assertIn('<body class="с-липкой-кнопкой">', итог)
        self.assertIn('<div class="липкая-кнопка">' + связь + "</div>\n</body>", итог)
        self.assertEqual(собрать.липкая_кнопка(html, "<script>виджет</script>"), html)
        # атрибуты <body> остаются, чужой класс — тоже (ревью, minor 4)
        self.assertIn('<body class="с-липкой-кнопкой" lang="ru">',
                      собрать.липкая_кнопка(html.replace("<body>", '<body lang="ru">'), связь))
        self.assertIn('<body class="с-липкой-кнопкой свой" lang="ru">',
                      собрать.липкая_кнопка(html.replace("<body>", '<body class="свой" lang="ru">'), связь))
        self.assertEqual(собрать.скрипт_таймера(html), html)
        с_таймером = собрать.скрипт_таймера(html.replace("<section>", '<section data-дедлайн="2030-12-31T23:59:00+03:00">'))
        self.assertIn("<script>", с_таймером)
        self.assertIn("data-дедлайн", с_таймером.split("<script>")[1])

    def test_первый_экран_не_той_концепции_жёлтое(self):
        with tempfile.TemporaryDirectory() as д:
            работа = Path(д) / "работа"
            import shutil; shutil.copytree(ФИКСТУРЫ / "работа-образец", работа)
            дизайн = работа / "дизайн.md"
            голова, решения = дизайн.read_text(encoding="utf-8").split("## Решения", 1)
            дизайн.write_text(голова + "## Решения" + решения.replace(
                "Концепция первого экрана: разворот", "Концепция первого экрана: постер"), encoding="utf-8")
            _, н = собрать.собрать(работа)
            self.assertNotIn(находки.ЧИНИТЬ, [x["уровень"] for x in н], н)
            не_та = [x for x in н if x["что"] == "Первый экран не той концепции"]
            self.assertEqual(len(не_та), 1, н)
            self.assertIn("«разворот»", не_та[0]["строки"][0])
            self.assertIn("«постер»", не_та[0]["строки"][0])
            self.assertIn("в дизайн.md → Решения", не_та[0]["строки"][0])
            self.assertIn("01-первый-экран-постер.html", не_та[0]["чем_грозит"])
            # без «Решений» сравниваем с вариантом 1 — и так и говорим (ревью, minor 7)
            текст = дизайн.read_text(encoding="utf-8")
            дизайн.write_text(текст[:текст.index("## Решения")].replace(
                "Концепция первого экрана: разворот", "Концепция первого экрана: постер", 1), encoding="utf-8")
            _, н = собрать.собрать(работа)
            не_та = [x for x in н if x["что"] == "Первый экран не той концепции"]
            self.assertEqual(len(не_та), 1, н)
            self.assertIn("в дизайн.md → Вариант 1", не_та[0]["строки"][0])
            _, н = собрать.собрать(ФИКСТУРЫ / "работа-образец", куда=Path(д) / "сайт")
            self.assertNotIn("Первый экран не той концепции", [x["что"] for x in н], н)
            self.assertNotIn("В дизайн.md поле не заполнено", [x["что"] for x in н], н)

    def test_без_дизайна_нет_второй_находки_о_полях(self):
        # ревью, minor 8: нет файла — 🔴 от _токены уже есть, 🟡 «поле не заполнено» поверх не нужна
        with tempfile.TemporaryDirectory() as д:
            работа = Path(д) / "работа"
            import shutil; shutil.copytree(ФИКСТУРЫ / "работа-образец", работа)
            (работа / "дизайн.md").unlink()
            _, н = собрать.собрать(работа)
            self.assertIn(находки.ЧИНИТЬ, [x["уровень"] for x in н], н)
            self.assertNotIn("В дизайн.md поле не заполнено", [x["что"] for x in н], н)
