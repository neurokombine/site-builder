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
          "фон--сетка фон--зерно орбита орбита__спутник первый-экран--разворот первый-экран--постер "
          "первый-экран--фото первый-экран--орбита "
          "цифра шаг шаг__номер вопрос контакт мелкий пара цитата__кто орбита__центр светлый второй тёмный "
          "первый-экран__текст первый-экран__фото первый-экран__действие первый-экран__доверие шаги фото--маска").split()
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

if __name__ == "__main__":
    unittest.main()
