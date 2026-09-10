"""обложка.py: точка лица, кроп 9:16, края выреза; rembg и ffmpeg — необязательные; без сети (GC 24)."""
import contextlib
import io
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "ядро" / "скрипты"))
import обложка  # noqa: E402


def вырез_png(путь: Path, рамка=(100, 60, 300, 560), размер=(400, 600)) -> Path:
    к = Image.new("RGBA", размер, (0, 0, 0, 0))
    к.paste((120, 90, 60, 255), рамка)
    к.save(путь)
    return путь


class Картинка(unittest.TestCase):
    def test_фокус_и_края_выреза(self):
        with tempfile.TemporaryDirectory() as д:
            ф = вырез_png(Path(д) / "figura.png")
            self.assertEqual(обложка.фокус(ф), (50, 25))            # центр по ширине; 60 + 500 · .18 = 150 из 600
            self.assertEqual(обложка.касается_краёв(ф), [])
            у_края = вырез_png(Path(д) / "kray.png", рамка=(0, 0, 300, 560))
            self.assertEqual(обложка.касается_краёв(у_края), ["слева", "сверху"])
            self.assertEqual(обложка.фокус(у_края), (38, 17))
            фото = Path(д) / "foto.jpg"
            Image.new("RGB", (1600, 900), (200, 180, 160)).save(фото)
            self.assertEqual(обложка.фокус(фото), обложка.ФОКУС_ФОТО)
            self.assertEqual(обложка.касается_краёв(фото), ["не вырез"])

    def test_кроп_телефон(self):
        with tempfile.TemporaryDirectory() as д:
            фото = Path(д) / "portret.jpg"
            Image.new("RGB", (1600, 900), (200, 180, 160)).save(фото)
            путь = обложка.кроп_телефон(фото, Path(д) / "img")
            self.assertEqual(путь.name, "portret-telefon.webp")
            with Image.open(путь) as к:
                self.assertEqual(к.size, (506, 899))
            узкое = Path(д) / "uzkoe.png"
            Image.new("RGB", (300, 1000), (1, 2, 3)).save(узкое)
            with Image.open(обложка.кроп_телефон(узкое, Path(д) / "img", (50, 10))) as к:
                self.assertEqual(к.size, (300, 533))

    def test_вырез_без_rembg_none_с_подделкой_файл(self):
        with tempfile.TemporaryDirectory() as д:
            ф = вырез_png(Path(д) / "figura.png")
            with patch.dict(sys.modules, {"rembg": None}):
                self.assertIsNone(обложка.вырез(ф, Path(д) / "img"))
            подделка = types.ModuleType("rembg")
            подделка.remove = lambda к: к
            with patch.dict(sys.modules, {"rembg": подделка}):
                путь = обложка.вырез(ф, Path(д) / "img")
            self.assertEqual(путь.name, "figura-vyrez.png")
            with Image.open(путь) as к:
                self.assertEqual(к.mode, "RGBA")

    def test_обложка_не_тянет_проверить(self):   # GC 17: цикл через картинка → проверить закрыт ленивым импортом
        р = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, 'ядро/скрипты'); import обложка; "
                            "print('проверить' in sys.modules, 'собрать' in sys.modules)"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(р.stdout.strip(), "False False", р.stderr)


class Ролики(unittest.TestCase):
    def test_без_ffmpeg_none(self):
        with patch("обложка.ffmpeg_есть", return_value=None):
            self.assertIsNone(обложка.петля(Path("x.mp4"), Path(".")))
            self.assertIsNone(обложка.альфа_вебм(Path("x.mp4"), Path(".")))

    @unittest.skipUnless(обложка.ffmpeg_есть(), "нет ffmpeg — петля и альфа не проверяются")
    def test_петля_и_альфа(self):
        with tempfile.TemporaryDirectory() as д:
            ролик = Path(д) / "rolik.mp4"
            subprocess.run([обложка.ffmpeg_есть(), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                            "color=c=0x00FF00:s=96x160:d=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(ролик)], check=True)
            итог = обложка.петля(ролик, Path(д) / "video", секунд=1)
            self.assertEqual({итог["webm"].name, итог["mp4"].name, итог["постер"].name}, {"rolik.webm", "rolik.mp4", "rolik-poster.jpg"})
            self.assertLess(итог["мб"], обложка.ПРЕДЕЛ_ВИДЕО_МБ)
            self.assertEqual(обложка.петля(ролик, Path(д) / "video", секунд=1, вертикально=True)["mp4"].name, "rolik-telefon.mp4")
            альфа = обложка.альфа_вебм(ролик, Path(д) / "video", хромакей="00FF00", секунд=1)
            self.assertEqual((альфа["webm"].name, альфа["постер"].name), ("rolik-vyrez.webm", "rolik-vyrez-poster.png"))
            with Image.open(альфа["постер"]) as п:
                self.assertEqual(п.mode, "RGBA")
                self.assertLess(п.getchannel("A").getextrema()[1], 40)   # зелёный фон стал прозрачным


class CLI(unittest.TestCase):
    def test_фокус_кроп_и_честные_отказы(self):
        with tempfile.TemporaryDirectory() as д:
            ф = вырез_png(Path(д) / "figura.png")
            вывод = io.StringIO()
            with contextlib.redirect_stdout(вывод):
                код = обложка.main_с_аргументами([str(ф), "--куда", str(Path(д) / "img"), "--проверить-вырез"])
            self.assertEqual(код, 0)
            self.assertIn("Лицо: 50,25", вывод.getvalue())
            self.assertIn("не касается", вывод.getvalue())
            self.assertTrue((Path(д) / "img" / "figura-telefon.webp").is_file())
            with contextlib.redirect_stdout(вывод), patch.dict(sys.modules, {"rembg": None}):
                self.assertEqual(обложка.main_с_аргументами([str(ф), "--куда", str(Path(д) / "img"), "--вырез"]), 1)
            self.assertIn("remove.bg", вывод.getvalue())
            with contextlib.redirect_stdout(вывод), patch("обложка.ffmpeg_есть", return_value=None):
                self.assertEqual(обложка.main_с_аргументами([str(ф), "--куда", str(Path(д) / "video"), "--петля"]), 1)
            self.assertIn("CapCut", вывод.getvalue())


if __name__ == "__main__":
    unittest.main()
