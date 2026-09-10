"""Стили ядра: классы компонентов есть, литералов нет, липкая кнопка есть, scroll-reveal нет нигде."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "ядро" / "скрипты"))
import собрать  # noqa: E402

СТИЛИ = ROOT / "ядро" / "блоки" / "стили.css"
КЛАССЫ = ("блок блок__внутри кнопка кнопка--главная кнопка--контур кнопка--пульс кикер акцент лид карточка "
          "карточка--стекло карточка--главная цифры цифра__значение цифра__подпись фото мокап аватар иконка "
          "список-иконок бейдж разделитель цитата таймер таймер__ячейка липкая-кнопка с-липкой-кнопкой фон--пятна "
          "фон--сетка фон--зерно орбита орбита__спутник первый-экран--разворот первый-экран--орбита "
          "первый-экран--сцена первый-экран--живая-сцена первый-экран--афиша-с-экраном первый-экран--товар-крупно первый-экран--бенто "
          "первый-экран--центр первый-экран--живая-обложка первый-экран--живой-портрет первый-экран--мозаика-роликов "
          "первый-экран__картинка картинка картинка--фото картинка--край картинка--вырез картинка--живой-портрет "
          "картинка--сцена картинка--видео картинка--видео-с-голосом картинка--мокап картинка--товар картинка--мозаика "
          "картинка--постер картинка__бейдж живое опора кольцо парит окно окно__бар окно__адрес бегущая-строка "
          "бегущая-строка__лента рамка-телефона рамка-телефона__экран рамка-телефона__подпись ряд-роликов ряд-роликов__лента "
          "рамка-телефона--дубль бенто бенто__ячейка бенто__ячейка--главная бенто__ячейка--пункты центр__верх центр__бок "
          "сторона--слева звук-блок звук звук__подпись звук__почему звук__почему-длинно звук__почему-коротко "
          "цифра шаг шаг__номер вопрос контакт мелкий пара цитата__кто светлый второй тёмный "
          "первый-экран__текст первый-экран__действие первый-экран__доверие шаги фото--маска").split()
ОБЛОЖКА_JS = ROOT / "ядро" / "блоки" / "обложка.js"
ЗВУК_JS = ROOT / "ядро" / "блоки" / "звук.js"
РОЗОВОЕ = re.compile(r"color-mix\(in srgb, var\(--цвет-акцент\) \d+%, var\(--цвет-(?!акцент)")
ГАСИТСЯ = ("парит", "опора", "кольцо", "окно", "бегущая-строка__лента", "ряд-роликов__лента", "звук",
           "картинка--сцена img", "живое::before", "фон--пятна::before", "бенто__ячейка", "картинка--видео-с-голосом video")
ПЕРЕМЕННЫЕ = ("--радиус-малый --тень --тень-глубокая --плавность --длительность --цвет-стекло --цвет-фон-карточки "
              "--кегль-кикер --кегль-цифра --разрядка-кикера --ширина-колонки").split()


def без_комментариев(css: str) -> str:
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return re.sub(r"@media[^{]*\{", "{", css)   # прелюдия медиазапроса — не свойство


class Стили(unittest.TestCase):
    css = СТИЛИ.read_text(encoding="utf-8")
    тело = без_комментариев(css)

    def test_скрытое_скрыто(self):   # [hidden] сильнее display компонентов: таймер после дедлайна не показывает нули
        self.assertRegex(self.тело, r"\[hidden\]\s*\{\s*display:\s*none\s*!important")

    def test_классы_компонентов_на_месте(self):
        for имя in КЛАССЫ:
            self.assertRegex(self.тело, rf"\.{re.escape(имя)}[\s,.:{{\[>]", имя)
        self.assertRegex(self.тело, r"h1,\s*h2,\s*h3\s*\{[^}]*font-family:\s*var\(--шрифт-заголовков\)",
                         "заголовки без шрифта заголовков")

    def test_ровно_32_переменные_и_новые_среди_них(self):
        self.assertEqual(len(собрать.ПЕРЕМЕННЫЕ), 32)
        for имя in ПЕРЕМЕННЫЕ:
            self.assertIn(имя, собрать.ПЕРЕМЕННЫЕ)

    def test_нет_литералов(self):
        self.assertNotRegex(self.тело, r"#[0-9a-fA-F]{3,8}\b", "hex-цвет в ядре")
        self.assertNotRegex(self.тело, r"\b(?:rgba?|hsla?)\(", "rgb/hsl в ядре")
        self.assertNotRegex(self.тело, r"(?<![\w.-])(?:[5-9]|\d{2,})(?:\.\d+)?px\b", "px ≥ 5 — только токены")
        for м in re.finditer(r"font(?:-family)?\s*:\s*([^;]+);", self.тело):
            self.assertTrue(м.group(1).strip().startswith("var(") or "var(--шрифт" in м.group(1), м.group(0))
        for слово in ("Montserrat", "Open Sans", "Georgia", "nz-", "Натэл"):
            self.assertNotIn(слово, self.css, слово)

    def test_липкая_кнопка_reduced_motion_и_нет_scroll_reveal(self):
        self.assertRegex(self.тело, r"\.липкая-кнопка\s*\{\s*display:\s*none")
        self.assertIn("env(safe-area-inset-bottom)", self.тело)
        self.assertIn("prefers-reduced-motion", self.css)
        self.assertIn("summary::after", self.css[self.css.index("@media (prefers-reduced-motion"):],
                      "плюсик вопроса не выключен при reduced-motion")
        self.assertRegex(self.тело, r"body\.с-липкой-кнопкой\s*\{")
        for файл in (ROOT / "ядро").rglob("*"):
            if файл == Path(__file__).resolve():   # сам список запретов — не нарушение
                continue
            if файл.suffix in (".css", ".js", ".html", ".py", ".md") and файл.is_file():
                текст = файл.read_text(encoding="utf-8", errors="ignore")
                for слово in ("IntersectionObserver", "animation-timeline"):
                    self.assertNotIn(слово, текст, f"{файл}: {слово}")

    def test_нет_розового(self):   # решение 10.09.2026: акцент на тёмном как есть, смешение с белым даёт розовый
        self.assertEqual(РОЗОВОЕ.findall(self.тело), [])
        self.assertRegex(self.тело, r"\.тёмный \.кнопка--главная \{[^}]*background: var\(--цвет-акцент\)")

    def test_картинки_вписаны_и_обложка_js(self):
        self.assertRegex(self.тело, r"\.картинка img, \.картинка video \{[^}]*object-fit: cover")
        self.assertNotIn("object-fit: fill", self.тело)
        self.assertLessEqual(len(self.css.splitlines()), 660)
        js = ОБЛОЖКА_JS.read_text(encoding="utf-8")
        self.assertLessEqual(len(js.splitlines()), 40)
        for слово in ("data-телефон", "prefers-reduced-motion", "canPlayType", "картинка--постер", ".catch("):
            self.assertIn(слово, js)
        звук = ЗВУК_JS.read_text(encoding="utf-8")
        self.assertLessEqual(len(звук.splitlines()), 30)
        for слово in ("muted = false", "loop = false", "currentTime = 0", '"ended"', "visibilitychange", "aria-pressed", "data-звук"):
            self.assertIn(слово, звук)
        self.assertNotIn("Date.now", js + звук)

    def test_reduced_motion_гасит_обложки(self):
        хвост = self.css[self.css.index("@media (prefers-reduced-motion"):]
        for имя in ГАСИТСЯ:
            self.assertIn(имя, хвост, f"{имя} не выключен при reduced-motion")


class ВБраузере(unittest.TestCase):
    """Акцент на тёмном — ровно цвет текста у .акцент и ровно акцент у кнопки: розовый не собирается."""
    @classmethod
    def setUpClass(cls):
        import tempfile
        from playwright.sync_api import sync_playwright
        import глаза
        cls._временная = tempfile.TemporaryDirectory()
        cls._playwright = sync_playwright().start()
        cls.браузер = глаза.запустить_браузер(cls._playwright)
        токены = собрать.прочитать_дизайн(ROOT / "ядро/скрипты/tests/фикстуры/работа-образец/дизайн.md")["решения"]
        cls.путь = Path(cls._временная.name) / "index.html"
        cls.путь.write_text(
            '<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><title>Проба</title>'
            f"<style>{СТИЛИ.read_text(encoding='utf-8')}\n{токены}</style></head><body>"
            '<section class="блок тёмный" id="экран-1"><div class="блок__внутри"><p class="кикер">Кикер</p>'
            '<h1>Заголовок <em class="акцент">с акцентом</em></h1><a class="кнопка кнопка--главная" href="#">Кнопка</a>'
            '<i id="текст" style="color: var(--цвет-тёмный-текст)"></i><i id="акцент" style="color: var(--цвет-акцент)"></i>'
            "</div></section></body></html>", encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.браузер.close()
        cls._playwright.stop()
        cls._временная.cleanup()

    def test_на_тёмном_акцент_не_розовеет(self):
        стр = self.браузер.new_page()
        стр.goto(self.путь.as_uri())
        self.assertEqual(стр.evaluate("s => getComputedStyle(document.querySelector('.акцент')).color"),
                         стр.evaluate("s => getComputedStyle(document.querySelector('#текст')).color"))
        self.assertEqual(стр.evaluate("s => getComputedStyle(document.querySelector('.кнопка--главная')).backgroundColor"),
                         стр.evaluate("s => getComputedStyle(document.querySelector('#акцент')).color"))
        self.assertEqual(стр.evaluate("s => getComputedStyle(document.querySelector('.кикер')).color"),
                         стр.evaluate("s => getComputedStyle(document.querySelector('#текст')).color"))
        стр.close()

if __name__ == "__main__":
    unittest.main()
