"""Единый список засечных гарнитур: распознавание и замена. Сам список используют и
ресёрч_ниши.py (доноры), и сторож ядра (test_шрифты_без_засечек.py, документы и фикстуры)."""
import sys
import unittest
from pathlib import Path

СКРИПТЫ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(СКРИПТЫ))

import гарнитуры  # noqa: E402


class ЗасечнаяТесты(unittest.TestCase):
    def test_известные_антиквы_ловятся(self):
        for имя in ("Georgia", "'Times New Roman', serif", "PT Serif", "Playfair Display",
                    "Cormorant Garamond", "Noto Serif", "Roboto Slab"):
            with self.subTest(имя=имя):
                self.assertTrue(гарнитуры.засечная(имя), имя)

    def test_родовое_имя_serif_тоже_ловится(self):
        self.assertTrue(гарнитуры.засечная("serif"))
        self.assertTrue(гарнитуры.засечная("ui-serif"))

    def test_гротески_не_ловятся(self):
        for имя in ("Montserrat", "'Open Sans', system-ui, sans-serif", "Arial", "Tahoma", ""):
            with self.subTest(имя=имя):
                self.assertFalse(гарнитуры.засечная(имя), имя)

    def test_пустое_и_отсутствующее_имя_не_засечное(self):
        self.assertFalse(гарнитуры.засечная(None))
        self.assertFalse(гарнитуры.засечная(""))

    def test_регистр_и_кавычки_не_мешают(self):
        self.assertTrue(гарнитуры.засечная("\"GEORGIA\", Serif"))

    def test_гротеск_с_антиквой_внутри_имени_не_ловится(self):
        """Обрывок слова — не имя. «Explora» содержит «Lora», «Montserrat» содержит «serif»
        внутри «sans-serif», и оба гротески: имя сверяется целиком, иначе система заменит
        человеку его же гротеск и скажет, что спасла от засечек."""
        for имя in ("Explora", "Explora, sans-serif", "Montserrat, sans-serif",
                    "Inter, ui-sans-serif", "PT Sans", "Roboto"):
            with self.subTest(имя=имя):
                self.assertFalse(гарнитуры.засечная(имя), имя)

    def test_та_же_антиква_в_другом_начертании_ловится(self):
        for имя in ("Georgia Pro", "Lora Italic"):
            with self.subTest(имя=имя):
                self.assertTrue(гарнитуры.засечная(имя), имя)


class БлижайшийГротескТесты(unittest.TestCase):
    def test_умолчание_нейтральный_гротеск(self):
        self.assertEqual(гарнитуры.ближайший_гротеск("Georgia"), гарнитуры.ГРОТЕСК_ПО_УМОЛЧАНИЮ)
        self.assertEqual(гарнитуры.ближайший_гротеск("PT Serif"), гарнитуры.ГРОТЕСК_ПО_УМОЛЧАНИЮ)

    def test_афишным_антиквам_своя_замена(self):
        self.assertEqual(гарнитуры.ближайший_гротеск("Playfair Display"), "Montserrat")
        self.assertEqual(гарнитуры.ближайший_гротеск("Cormorant Garamond"), "Montserrat")

    def test_замена_никогда_не_засечная(self):
        for имя in гарнитуры.ЗАСЕЧНЫЕ:
            with self.subTest(имя=имя):
                self.assertFalse(гарнитуры.засечная(гарнитуры.ближайший_гротеск(имя)))


if __name__ == "__main__":
    unittest.main()
