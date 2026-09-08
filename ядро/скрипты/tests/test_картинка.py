"""Картинка: вставить и сжать — webp нужной ширины, имя латиницей, карточка 1200×630."""
import sys, tempfile, unittest
from pathlib import Path
from PIL import Image
СКРИПТЫ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(СКРИПТЫ))
import картинка  # noqa: E402


class КартинкаТесты(unittest.TestCase):
    def setUp(self):
        self._д = tempfile.TemporaryDirectory(); self.д = Path(self._д.name); self.addCleanup(self._д.cleanup)
        self.исходник = self.д / "Моё фото.png"
        Image.new("RGB", (3000, 2000), (200, 120, 90)).save(self.исходник)

    def test_сжатие_и_имя(self):
        путь, было, стало = картинка.сжать(self.исходник, self.д / "img")
        self.assertEqual(путь.name, "moyo-foto.webp")
        self.assertEqual(Image.open(путь).size[0], 1600)
        self.assertLess(стало, было)
        self.assertLess(стало, 300 * 1024)

    def test_маленькую_не_растягиваем(self):
        Image.new("RGB", (800, 600), (10, 10, 10)).save(self.исходник)
        путь, _, _ = картинка.сжать(self.исходник, self.д / "img", имя="photo")
        self.assertEqual(Image.open(путь).size, (800, 600))
        self.assertEqual(путь.name, "photo.webp")

    def test_карточка(self):
        путь = картинка.карточка(self.исходник, self.д / "img")
        self.assertEqual(путь.name, "card.jpg")
        self.assertEqual(Image.open(путь).size, (1200, 630))
