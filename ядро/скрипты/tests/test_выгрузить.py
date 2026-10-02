"""Тесты выгрузки на площадку (`выгрузить.py`): собранный сайт → блоки «HTML-код».

Учебный сайт `фикстуры/выгрузка/` — три экрана, картинка в разметке и картинка в стиле,
липкая кнопка, класс на `<body>`, токены в голове и `rem` в стилях. Картинки рисуем здесь,
а не храним в репозитории. Последний класс — живой прогон: образцовая работа собирается
`собрать.py`, выгружается, и браузер сверяет вычисленные стили сайта и блоков.

Запуск из корня репозитория:
    .venv/bin/python -m unittest discover -s ядро/скрипты/tests -t .
"""
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

СКРИПТЫ = Path(__file__).resolve().parent.parent
ФИКСТУРЫ = Path(__file__).resolve().parent / "фикстуры"
sys.path.insert(0, str(СКРИПТЫ))

import выгрузить  # noqa: E402
from находки import ЧИНИТЬ, ПОПРАВИТЬ, К_СВЕДЕНИЮ  # noqa: E402

ПРЯМОЙ = "https://fs.getcourse.ru/fileservice/file/download/a/1/sc/7/h/{}.webp"


def по_имени(находки: list[dict], имя: str) -> dict | None:
    return next((н for н in находки if н["что"] == имя), None)


def стили(html: str) -> str:
    return "\n".join(re.findall(r"<style>(.*?)</style>", html, re.S))


class Работа:
    """Копия учебной работы во временной папке, с нарисованными картинками."""

    def __init__(self):
        from PIL import Image
        self._временная = tempfile.TemporaryDirectory()
        self.работа = Path(self._временная.name) / "выгрузка"
        shutil.copytree(ФИКСТУРЫ / "выгрузка", self.работа)
        (self.работа / "сайт" / "img").mkdir()
        Image.new("RGB", (600, 400), (40, 90, 140)).save(self.работа / "сайт" / "img" / "обложка.webp")
        Image.new("RGB", (60, 60), (200, 170, 120)).save(self.работа / "сайт" / "img" / "фон.webp")

    def ссылки(self, данные: dict) -> Path:
        путь = self.работа / "мои-ссылки.json"
        путь.write_text(json.dumps(данные, ensure_ascii=False), encoding="utf-8")
        return путь

    def закрыть(self):
        self._временная.cleanup()


class БезСсылокТесты(unittest.TestCase):
    """Первый запуск: блоки, список картинок, шаблон ссылок, красное про неготовые блоки."""

    @classmethod
    def setUpClass(cls):
        cls.р = Работа()
        cls.итог = выгрузить.выгрузить(cls.р.работа, "getcourse")
        cls.куда = cls.итог["куда"]
        cls.блоки = cls.итог["блоки"]

    @classmethod
    def tearDownClass(cls):
        cls.р.закрыть()

    def test_три_экрана_три_блока_по_порядку(self):
        self.assertEqual([б["файл"].name for б in self.блоки],
                         ["01-первый-экран.НЕ-ГОТОВ.html", "02-отзывы.НЕ-ГОТОВ.html", "03-подвал.html"])
        self.assertEqual(self.куда, (self.р.работа / "на-площадку" / "getcourse").resolve())
        for б in self.блоки:
            self.assertTrue(б["файл"].is_file())

    def test_плейсхолдеры_вместо_своих_файлов(self):
        первый, второй, _ = (б["html"] for б in self.блоки)
        self.assertIn('src="{{КАРТИНКА:img/обложка.webp}}"', первый)
        self.assertIn("url('{{КАРТИНКА:img/фон.webp}}')", второй)
        self.assertNotIn('src="img/', первый)
        self.assertIn('href="#экран-3"', первый, "якоря — не файлы, их не трогаем")

    def test_красное_про_неготовые_блоки(self):
        н = по_имени(self.итог["находки"], "Блоки не готовы: картинки без адреса")
        self.assertEqual(н["уровень"], ЧИНИТЬ)
        self.assertEqual(len(н["строки"]), 2)
        self.assertIn("img/обложка.webp", н["строки"][0])
        self.assertEqual(выгрузить.main_с_аргументами([str(self.р.работа), "--getcourse"]), 1)

    def test_список_картинок_с_весом_и_шаблон_ссылок(self):
        список = (self.куда / "картинки-залить.md").read_text(encoding="utf-8")
        self.assertLess(список.index("img/обложка.webp"), список.index("img/фон.webp"))
        self.assertRegex(список, r"`img/обложка.webp` \| \d+ КБ \| 01 \|")
        self.assertIn("/pl/fileindex/file/index", список)
        шаблон = json.loads((self.куда / "ссылки.json").read_text(encoding="utf-8"))
        self.assertEqual(шаблон, {"img/обложка.webp": "", "img/фон.webp": ""})

    def test_инструкция_и_примерка_рядом(self):
        инструкция = (self.куда / "ИНСТРУКЦИЯ.md").read_text(encoding="utf-8")
        for слово in ("Файловое хранилище", "Вставка → HTML", "Значение", "Сохранить и закрыть",
                      "Опубликовать изменения", "Липкая кнопка", "одна боевая копия",
                      "Мастерская у реки — лодки и вёсла"):
            with self.subTest(слово=слово):
                self.assertIn(слово.lower(), инструкция.lower())
        примерка = (self.куда / "примерка.html").read_text(encoding="utf-8")
        self.assertIn("html{font-size:10px}", примерка)
        self.assertIn('class="container text-center"', примерка)
        self.assertIn('src="../../сайт/img/обложка.webp"', примерка, "до заливки картинки берутся из папки сайта")


class СтилиВнутриБлокаТесты(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.р = Работа()
        cls.блоки = выгрузить.выгрузить(cls.р.работа, "getcourse")["блоки"]

    @classmethod
    def tearDownClass(cls):
        cls.р.закрыть()

    def test_каждое_правило_под_своим_префиксом(self):
        for б in self.блоки:
            префикс = f".сб-выгрузка-{б['номер']:02d}"
            with self.subTest(блок=б["номер"]):
                self.assertIn(f'class="сб-выгрузка сб-выгрузка-{б["номер"]:02d}"', б["html"])
                for правило in re.finditer(r"(?:^|[}\n])([^{}@\n][^{}]*)\{", стили(б["html"])):
                    for селектор in выгрузить.разделить_селекторы(правило.group(1)):
                        if not селектор or селектор.startswith(("from", "to", "50%")):
                            continue
                        снаружи = re.match(r"body\.[\w-]+(?: " + re.escape(префикс) + r"(?![\w-]).*)?$", селектор)
                        self.assertTrue(селектор.startswith(префикс) or снаружи,
                                        f"селектор без префикса: {селектор}")

    def test_токены_головы_на_обёртке_а_не_на_корне(self):
        css = стили(self.блоки[0]["html"])
        self.assertIn(".сб-выгрузка-01{--шрифт-заголовков", css.replace(" ", ""))
        self.assertNotIn(":root", css)

    def test_rem_в_пикселях(self):
        css = стили(self.блоки[0]["html"])
        self.assertIn("font-size: 40px", css, "2.5rem экрана при корне 16 px")
        self.assertNotRegex(css, r"\d+(\.\d+)?rem\b")
        self.assertIn("padding: 24px", self.блоки[1]["html"], "rem в style= тоже")

    def test_в_блоке_только_нужные_правила(self):
        первый, второй, третий = (стили(б["html"]) for б in self.блоки)
        self.assertIn(".отзыв", второй)
        self.assertNotIn(".отзыв", первый)
        self.assertNotIn(".таблица-цен", первый + второй + третий, "такого класса нет ни в одном экране")
        self.assertIn("@keyframes пульс", первый)
        self.assertNotIn("никому-не-нужна", первый + второй + третий)

    def test_грабли_площадки_в_обёртке(self):
        css = стили(self.блоки[1]["html"])
        self.assertIn("text-align:start", css, "GetCourse оборачивает блок в text-center")
        self.assertRegex(css, r"\.сб-выгрузка-02 :is\([^)]*blockquote[^)]*\)\{[^}]*border:revert",
                         "тема красит blockquote — сбрасываем к виду браузера")
        self.assertIn("font-size:16px", css)

    def test_классы_body_ставит_сам_блок(self):
        for б in self.блоки:
            self.assertIn('document.body.classList.add(к)', б["html"])
        третий = стили(self.блоки[2]["html"])
        self.assertIn("body.главная-на-виду .сб-выгрузка-03 .липкая-кнопка", третий)
        self.assertIn("body.с-липкой-кнопкой{", третий.replace(" {", "{"))

    def test_липкая_кнопка_в_последнем_блоке_и_спрятана_в_редакторе(self):
        первый, _, третий = self.блоки
        self.assertIn('class="липкая-кнопка"', третий["html"])
        self.assertTrue(третий["липкий"])
        self.assertIn("/pl/cms/page/editor", третий["html"])
        self.assertIn("body.сб-в-редакторе .сб-выгрузка-03 .липкая-кнопка{display:none!important}", третий["html"],
                      "в редакторе прячет правило по метке — на любой ширине, а не разовый скрипт")
        self.assertNotIn('class="липкая-кнопка"', первый["html"])

    def test_скрипт_едет_туда_где_его_кнопка(self):
        первый, _, третий = self.блоки
        self.assertIn("главная-на-виду", первый["html"].split("</div>")[-1])
        self.assertNotIn("addEventListener", третий["html"])

    def test_скрипт_головы_работает_с_обёрткой_а_не_с_корнем(self):
        for б in self.блоки:
            with self.subTest(блок=б["номер"]):
                self.assertIn(f'document.querySelector(".сб-выгрузка-{б["номер"]:02d}").setAttribute("data-очко"', б["html"])
                self.assertNotIn("document.documentElement", б["html"])


class РазметкаКтоЭтоТесты(unittest.TestCase):
    """JSON-LD «кто это» на площадку не едет: ни в хвост блока, ни в общий список скриптов."""

    def test_ld_json_не_попадает_в_скрипты(self):
        html = ('<html><head><script type="application/ld+json">{"@type":"Person","url":"https://x.github.io/a/"}'
                '</script><script>var a=1;</script></head><body><section>1</section><section>2</section>'
                '<script type="application/ld+json">{"@type":"Person"}</script><script>var b=2;</script></body></html>')
        страница = выгрузить.разобрать_страницу(html, Path("."))
        вместе = "\n".join(страница["скрипты"] + страница["скрипты_головы"])
        self.assertNotIn("Person", вместе)
        self.assertIn("var a=1;", вместе)
        self.assertIn("var b=2;", вместе)

    def test_инструкция_говорит_про_разметку_и_адрес_оригинал(self):
        р = Работа()
        try:
            итог = выгрузить.выгрузить(р.работа, "getcourse")
            текст = (итог["куда"] / "ИНСТРУКЦИЯ.md").read_text(encoding="utf-8")
            self.assertIn("JSON-LD", текст)
            self.assertIn("адрес-оригинал на площадке ставит сама площадка", текст)
        finally:
            р.закрыть()


class КлассыИзСкриптаЭкранаТесты(unittest.TestCase):
    """Класс-состояние, который ставит только скрипт самого экрана (<script> внутри секции), в
    разметке не виден. Выгрузка выбрасывала его правило — так ролик обложки на площадке был
    невидим. Слова из скрипта экрана теперь держат такие правила в блоке."""

    @classmethod
    def setUpClass(cls):
        cls.р = Работа()
        страница = cls.р.работа / "сайт" / "index.html"
        html = страница.read_text(encoding="utf-8")
        начало = html.index('<section class="блок блок--отзывы')
        конец = html.index("</section>", начало)
        вставка = ('<style>#экран-02 .отзыв.раскрыт { opacity: .5; } #экран-02 .нигде-нет { opacity: .4; }</style>'
                   '<script>document.querySelector("#экран-02 .отзыв").classList.add("раскрыт");</script>')
        страница.write_text(html[:конец] + вставка + html[конец:], encoding="utf-8")
        cls.блоки = выгрузить.выгрузить(cls.р.работа, "getcourse")["блоки"]

    @classmethod
    def tearDownClass(cls):
        cls.р.закрыть()

    def test_правило_класса_из_скрипта_экрана_остаётся(self):
        второй = стили(self.блоки[1]["html"])
        self.assertIn(".раскрыт", второй)
        self.assertNotIn(".нигде-нет", второй, "класса нет ни в разметке, ни в скрипте — правило уходит, как раньше")

    def test_слова_из_скриптов(self):
        слова = выгрузить.слова_из_скриптов(['a.classList.add("картинка--постер"); b.className = "x y";',
                                             "q('#экран-1 .ролик.ждёт');"])
        self.assertTrue({"картинка--постер", "x", "y", "ролик", "ждёт"} <= слова)


class АнимацияОбложкиТесты(unittest.TestCase):
    """Запасной ход ролика обложки на площадке: анимированная картинка лежит в data-анимация-…, а не в src —
    выгрузка обязана увидеть её файлы, поставить плейсхолдеры и не выбросить правила состояний подмены
    (`картинка--постер` ставит обложка.js, `img[hidden]` держит картинку рамки до отказа ролика)."""

    ФАЙЛЫ = ("video/x.mp4", "video/x-poster.jpg", "video/x-anim.avif", "video/x-anim.webp",
             "video/t-poster.jpg", "video/t-anim.avif", "video/t-anim.webp")

    @classmethod
    def setUpClass(cls):
        cls.р = Работа()
        сайт = cls.р.работа / "сайт"
        (сайт / "video").mkdir()
        for имя in cls.ФАЙЛЫ:
            (сайт / имя).write_bytes(b"0" * 64)
        страница = сайт / "index.html"
        html = страница.read_text(encoding="utf-8")
        старое = '<figure class="картинка"><img src="img/обложка.webp" alt="Лодка у причала" width="600" height="400"></figure>'
        новое = ('<figure class="картинка картинка--видео первый-экран__картинка"><video autoplay muted loop playsinline '
                 'webkit-playsinline preload="none" data-ролик-компьютер="video/x.mp4" data-постер-компьютер="video/x-poster.jpg"></video>'
                 '<picture><source media="(max-width: 899px)" srcset="video/t-poster.jpg"><img src="video/x-poster.jpg" alt="кадр" '
                 'data-анимация-avif-компьютер="video/x-anim.avif" data-анимация-webp-компьютер="video/x-anim.webp" '
                 'data-анимация-avif-телефон="video/t-anim.avif" data-анимация-webp-телефон="video/t-anim.webp"></picture></figure>')
        assert старое in html
        скрипт = "<script>\n" + (СКРИПТЫ.parent / "блоки" / "обложка.js").read_text(encoding="utf-8") + "\n</script>\n"
        html = html.replace(старое, новое).replace("</body>", скрипт + "</body>")
        страница.write_text(html, encoding="utf-8")
        with open(сайт / "style.css", "a", encoding="utf-8") as ф:
            ф.write("\n.картинка--постер video { display: none; }\n.картинка img[hidden] { display: none; }\n")
        cls.итог = выгрузить.выгрузить(cls.р.работа, "getcourse")
        cls.первый = cls.итог["блоки"][0]

    @classmethod
    def tearDownClass(cls):
        cls.р.закрыть()

    def test_файлы_анимации_в_списке_заливки(self):
        for имя in self.ФАЙЛЫ:
            self.assertIn(имя, self.первый["файлы"])
        список = (self.р.работа / "на-площадку" / "getcourse" / "картинки-залить.md").read_text(encoding="utf-8")
        for имя in ("x-anim.avif", "x-anim.webp", "t-anim.avif", "t-anim.webp", "x-poster.jpg"):
            self.assertIn(имя, список)

    def test_плейсхолдеры_в_data_атрибутах(self):
        html = self.первый["html"]
        self.assertIn('data-анимация-avif-телефон="{{КАРТИНКА:video/t-anim.avif}}"', html)
        self.assertIn('data-анимация-webp-компьютер="{{КАРТИНКА:video/x-anim.webp}}"', html)
        self.assertNotIn('="video/', html, "свой файл остался относительным адресом — на площадке его нет")

    def test_правила_состояний_подмены_остались(self):
        css = стили(self.первый["html"])
        self.assertIn(".картинка--постер video", css, "класс ставит обложка.js — правило выбрасывать нельзя")
        self.assertIn("img[hidden]", css)


class СоСсылкамиТесты(unittest.TestCase):
    def setUp(self):
        self.р = Работа()

    def tearDown(self):
        self.р.закрыть()

    def test_все_адреса_есть_блоки_готовы(self):
        путь = self.р.ссылки({"img/обложка.webp": ПРЯМОЙ.format("a1"), "img/фон.webp": ПРЯМОЙ.format("b2")})
        итог = выгрузить.выгрузить(self.р.работа, "getcourse", путь)
        self.assertNotIn(ЧИНИТЬ, [н["уровень"] for н in итог["находки"]])
        self.assertEqual([б["файл"].name for б in итог["блоки"]],
                         ["01-первый-экран.html", "02-отзывы.html", "03-подвал.html"])
        self.assertIn(f'src="{ПРЯМОЙ.format("a1")}"', итог["блоки"][0]["html"])
        self.assertIn(f"url('{ПРЯМОЙ.format('b2')}')", итог["блоки"][1]["html"])
        self.assertFalse(any("{{КАРТИНКА" in б["html"] for б in итог["блоки"]))
        self.assertFalse(list(итог["куда"].glob("*НЕ-ГОТОВ*")), "старые неготовые блоки убраны")
        шаблон = json.loads((итог["куда"] / "ссылки.json").read_text(encoding="utf-8"))
        self.assertEqual(шаблон["img/обложка.webp"], ПРЯМОЙ.format("a1"))

    def test_ответ_загрузчика_по_имени_файла_и_хост_шарда(self):
        путь = self.р.ссылки({
            "обложка.webp": {"url": "https://fs16.getcourse.ru/fileservice/file/download/a/1/sc/7/h/a1.webp", "ok": True},
            "фон.webp": {"url": ПРЯМОЙ.format("b2"), "ok": True}})
        итог = выгрузить.выгрузить(self.р.работа, "getcourse", путь)
        self.assertIn('src="https://fs.getcourse.ru/fileservice/', итог["блоки"][0]["html"])
        self.assertNotIn("fs16.", итог["блоки"][0]["html"])

    def test_невыставленная_картинка_красное_и_блок_не_отдан(self):
        путь = self.р.ссылки({"img/обложка.webp": ПРЯМОЙ.format("a1"), "img/фон.webp": ""})
        итог = выгрузить.выгрузить(self.р.работа, "getcourse", путь)
        н = по_имени(итог["находки"], "Блоки не готовы: картинки без адреса")
        self.assertEqual(н["строки"], ["02-отзывы.НЕ-ГОТОВ.html: нет адреса для img/фон.webp"])
        self.assertTrue((итог["куда"] / "01-первый-экран.html").is_file())
        self.assertFalse((итог["куда"] / "02-отзывы.html").exists())

    def test_адрес_из_админки_это_красное(self):
        путь = self.р.ссылки({"img/обложка.webp": "https://school.ru/pl/fileservice/user/file/download/h/a1.webp",
                              "img/фон.webp": ПРЯМОЙ.format("b2")})
        итог = выгрузить.выгрузить(self.р.работа, "getcourse", путь)
        н = по_имени(итог["находки"], "Адрес из админки GetCourse, а не прямая ссылка")
        self.assertEqual(н["уровень"], ЧИНИТЬ)
        self.assertIn("01-первый-экран.НЕ-ГОТОВ.html", [б["файл"].name for б in итог["блоки"]])

    def test_относительный_адрес_это_красное(self):
        путь = self.р.ссылки({"img/обложка.webp": "img/обложка.webp", "img/фон.webp": ПРЯМОЙ.format("b2")})
        итог = выгрузить.выгрузить(self.р.работа, "getcourse", путь)
        self.assertEqual(по_имени(итог["находки"], "Адрес файла не прямой")["уровень"], ЧИНИТЬ)


class ТильдаТесты(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.р = Работа()
        путь = cls.р.ссылки({"img/обложка.webp": ПРЯМОЙ.format("a1"), "img/фон.webp": ПРЯМОЙ.format("b2")})
        cls.итог = выгрузить.выгрузить(cls.р.работа, "tilda", путь)

    @classmethod
    def tearDownClass(cls):
        cls.р.закрыть()

    def test_те_же_блоки_в_своей_папке(self):
        self.assertEqual(self.итог["куда"], (self.р.работа / "на-площадку" / "tilda").resolve())
        self.assertEqual(len(self.итог["блоки"]), 3)
        self.assertIn("text-align:start", self.итог["блоки"][0]["html"])

    def test_грабли_getcourse_не_едут_в_тильду(self):
        self.assertFalse(any("/pl/cms/page/editor" in б["html"] for б in self.итог["блоки"]))

    def test_инструкция_тильды(self):
        текст = (self.итог["куда"] / "ИНСТРУКЦИЯ.md").read_text(encoding="utf-8")
        for слово in ("T123", "текстом", "Запретить поисковикам индексировать страницу", "SEO"):
            with self.subTest(слово=слово):
                self.assertIn(слово, текст)
        список = (self.итог["куда"] / "картинки-залить.md").read_text(encoding="utf-8")
        self.assertIn("своего хранилища для HTML-блока у Тильды нет", список)


class РазборТесты(unittest.TestCase):
    def test_префикс_головы_селектора(self):
        п = ".сб-x-01"
        случаи = {
            ":root": ".сб-x-01",
            "html": ".сб-x-01",
            "body": ".сб-x-01",
            "body .лид": ".сб-x-01 .лид",
            "body.с-липкой-кнопкой": "body.с-липкой-кнопкой",
            "body.главная-на-виду .липкая-кнопка": "body.главная-на-виду .сб-x-01 .липкая-кнопка",
            ".блок > .x": ".сб-x-01 .блок > .x",
            "*::before": ".сб-x-01 *::before",
            "#экран-1 h1": ".сб-x-01 #экран-1 h1",
            "bodyless": ".сб-x-01 bodyless",
        }
        for было, стало in случаи.items():
            with self.subTest(было=было):
                self.assertEqual(выгрузить.с_префиксом(было, п), стало)

    def test_нужное_селектору_не_считает_скобки(self):
        классы, ids = выгрузить.нужное_селектору(".блок:not(.блок--первый-экран) #экран-2 [data-x='.y'] .z:has(.w)")
        self.assertEqual(классы, {"блок", "z"})
        self.assertEqual(ids, {"экран-2"})

    def test_rem_в_px(self):
        self.assertEqual(выгрузить.rem_в_px("margin: -1.5rem .5rem 0 2rem; --x2rem: 1"),
                         "margin: -24px 8px 0 32px; --x2rem: 1")

    def test_разбор_групп_и_как_есть(self):
        дерево = выгрузить.разобрать_css("@import url(x.css);@media (min-width: 9px){.a{b:c}}"
                                         "@font-face{font-family:Q}.d{content:'}'}")
        self.assertEqual([у[0] for у in дерево], ["строка", "группа", "как_есть", "правило"])
        self.assertEqual(дерево[3], ("правило", ".d", "content:'}'"))

    def test_локальный_файл(self):
        self.assertEqual(выгрузить.локальный_файл("./img/a.webp?v=2"), "img/a.webp")
        for чужое in ("https://x.ru/a.webp", "#экран-2", "data:image/png;base64,AA", "mailto:a@b.c",
                      "страница.html", "/img/a.webp", "{{КАРТИНКА:img/a.webp}}"):
            with self.subTest(чужое=чужое):
                self.assertIsNone(выгрузить.локальный_файл(чужое))

    def test_нет_собранного_сайта(self):
        with tempfile.TemporaryDirectory() as д:
            self.assertEqual(выгрузить.main_с_аргументами([д, "--getcourse"]), 2)


class ОбразцоваяРаботаВживуюТесты(unittest.TestCase):
    """Настоящая сборка `собрать.py` → выгрузка → браузер: у каждого элемента каждого экрана в
    блоке те же вычисленные стили, что на сайте, — и внутри «враждебной» примерки площадки."""

    СВОЙСТВА = ("fontSize", "fontWeight", "lineHeight", "marginTop", "marginBottom", "paddingTop",
                "paddingLeft", "textAlign", "color", "backgroundColor", "borderLeftWidth", "width")

    @classmethod
    def setUpClass(cls):
        import собрать
        from playwright.sync_api import sync_playwright

        cls._временная = tempfile.TemporaryDirectory()
        работа = Path(cls._временная.name) / "образец"
        shutil.copytree(ФИКСТУРЫ / "работа-образец", работа)
        собрать.собрать(работа)
        cls.итог = выгрузить.выгрузить(работа, "getcourse")
        cls.работа = работа
        замер = """() => [...document.querySelectorAll('%s')].map(с => [...с.querySelectorAll('*')]
            .filter(э => !['STYLE', 'SCRIPT'].includes(э.tagName) && !э.closest('svg'))
            .map(э => { const cs = getComputedStyle(э); return [э.tagName, %s]; }))"""
        свойства = ", ".join(f"cs.{с}" for с in cls.СВОЙСТВА)
        with sync_playwright() as движок:
            браузер = движок.chromium.launch()
            страница = браузер.new_page(viewport={"width": 1280, "height": 900})
            страница.goto((работа / "сайт" / "index.html").as_uri())
            страница.wait_for_timeout(300)
            cls.сайт = страница.evaluate(замер % ("body > section", свойства))
            страница.goto((cls.итог["куда"] / "примерка.html").as_uri())
            страница.wait_for_timeout(300)
            cls.блоки = страница.evaluate(замер % ("[data-экран] > section", свойства))
            браузер.close()

    @classmethod
    def tearDownClass(cls):
        cls._временная.cleanup()

    def test_блок_на_экран(self):
        self.assertEqual(len(self.итог["блоки"]), len(self.сайт))
        self.assertGreaterEqual(len(self.сайт), 4)

    def test_вычисленные_стили_как_на_сайте(self):
        for номер, (экран, блок) in enumerate(zip(self.сайт, self.блоки), 1):
            with self.subTest(экран=номер):
                self.assertEqual(len(экран), len(блок))
                различия = [(э[0], св, э[1 + i], б[1 + i]) for э, б in zip(экран, блок)
                            for i, св in enumerate(self.СВОЙСТВА) if э[1 + i] != б[1 + i]]
                self.assertEqual(различия, [])


if __name__ == "__main__":
    unittest.main()
