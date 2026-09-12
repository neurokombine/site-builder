"""обложка.py: рамка выреза, точка лица, кроп 9:16, края выреза; rembg и ffmpeg — необязательные; без сети (GC 24)."""
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

    def test_непрозрачный_png_это_фото(self):   # починка T3: RGBA без единого прозрачного пикселя — фото, не вырез
        with tempfile.TemporaryDirectory() as д:
            фото = Path(д) / "foto.png"
            Image.new("RGBA", (800, 600), (200, 150, 100, 255)).save(фото)
            self.assertEqual(обложка.фокус(фото), обложка.ФОКУС_ФОТО)
            self.assertEqual(обложка.касается_краёв(фото), ["не вырез"])
            ф = вырез_png(Path(д) / "figura.png")                        # настоящий вырез: альфа доезжает до webp кропа
            with Image.open(обложка.кроп_телефон(ф, Path(д) / "img")) as к:
                self.assertEqual(к.mode, "RGBA")
                self.assertEqual(к.getchannel("A").getextrema(), (0, 255))

    def test_обложка_не_тянет_проверить(self):   # GC 17: цикл через картинка → проверить закрыт ленивым импортом
        р = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, 'ядро/скрипты'); import обложка; "
                            "print('проверить' in sys.modules, 'собрать' in sys.modules)"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(р.stdout.strip(), "False False", р.stderr)


def фигура_png(путь: Path, кадр=(1024, 1536), макушка=97, голова=210, ширина_головы=272,
               низ=1469, плечи=1.9, центр=512) -> Path:
    """Грубый человек-силуэт: голова кругом, ниже — шея, плечи и корпус. Ровно то, по чему `голова()`
    ищет впадину-шею, и ничего лишнего: тесту нужна геометрия, а не фотография."""
    from PIL import ImageDraw
    к = Image.new("RGBA", кадр, (0, 0, 0, 0))
    р = ImageDraw.Draw(к)
    р.ellipse((центр - ширина_головы // 2, макушка, центр + ширина_головы // 2, макушка + голова), fill=(120, 90, 60, 255))
    шея = макушка + голова
    р.rectangle((центр - ширина_головы // 5, шея - голова // 8, центр + ширина_головы // 5, шея + голова // 10), fill=(120, 90, 60, 255))
    корпус = int(ширина_головы * плечи)
    р.rectangle((центр - корпус // 2, шея + голова // 10, центр + корпус // 2, низ), fill=(120, 90, 60, 255))
    к.save(путь)
    return путь


class РамкаВыреза(unittest.TestCase):
    """Дело фикс-раунда Е: числа кропа в стилях сняты с выреза в полный рост. Ученик принесёт кадр по
    грудь — и схема увеличит его вдвое сильнее нужного. Рамку держит скрипт, а не стиль."""

    def test_три_кадра_одного_человека_встают_одинаково(self):
        with tempfile.TemporaryDirectory() as д:
            д = Path(д)
            рост = фигура_png(д / "rost.png")
            with Image.open(рост) as к:
                по_пояс = к.crop((0, 0, к.width, 850))
                по_грудь = к.crop((120, 40, к.width - 90, 620))
            по_пояс.save(д / "poyas.png")
            по_грудь.save(д / "grud.png")
            до = {имя: обложка.замеры_рамки(д / f"{имя}.png") for имя in ("rost", "poyas", "grud")}
            self.assertGreater(до["grud"]["голова"], до["poyas"]["голова"])      # чем ближе кадр, тем крупнее голова
            self.assertGreater(до["poyas"]["голова"], до["rost"]["голова"])
            после, пути = {}, {}
            for имя in ("rost", "poyas", "grud"):
                итог = обложка.рамка_выреза(д / f"{имя}.png", д / "out" / имя)
                пути[имя] = итог["путь"]
                после[имя] = обложка.замеры_рамки(итог["путь"])
                with Image.open(итог["путь"]) as к:
                    self.assertEqual(к.size, (обложка.ШИРИНА_РАМКИ, обложка.ШИРИНА_РАМКИ * 3 // 2))
                self.assertEqual(обложка.касается_краёв(итог["путь"]), [])       # схема «центр» примет любой из трёх
            for имя, з in после.items():
                self.assertAlmostEqual(з["голова"], обложка.ГОЛОВА_В_РАМКЕ, delta=обложка.ДОПУСК_РАМКИ, msg=имя)
                self.assertAlmostEqual(з["макушка"], обложка.МАКУШКА_В_РАМКЕ, delta=обложка.ДОПУСК_РАМКИ, msg=имя)
                self.assertAlmostEqual(з["лицо_x"], .5, delta=обложка.ДОПУСК_РАМКИ, msg=имя)
                self.assertTrue(з["в_рамке"], имя)
            self.assertEqual(len({обложка.фокус(п) for п in пути.values()}), 1)   # одна точка лица на все три кадра

    def test_кадр_в_рамке_не_трогаем(self):
        with tempfile.TemporaryDirectory() as д:
            рост = фигура_png(Path(д) / "rost.png")
            итог = обложка.рамка_выреза(рост, Path(д) / "out")
            self.assertFalse(итог["приведено"])
            self.assertEqual(итог["путь"], рост)              # лишнего пережатия чужого файла не делаем

    def test_фотография_с_мягким_краем_не_вырез(self):
        """`картинка--край` растворяет низ фото прямо в файле — прозрачные пиксели есть, а вырезом это не стало."""
        with tempfile.TemporaryDirectory() as д:
            фото = Path(д) / "portret.png"
            к = Image.new("RGBA", (800, 1150), (200, 150, 100, 255))
            к.putalpha(Image.linear_gradient("L").resize((800, 1150)).point(lambda а: 255 - а))
            к.save(фото)
            self.assertIsNone(обложка.силуэт(фото))
            self.assertIsNone(обложка.замеры_рамки(фото))
            self.assertEqual(обложка.фокус(фото), обложка.ФОКУС_ФОТО)
            self.assertFalse(обложка.рамка_выреза(фото, Path(д) / "out")["приведено"])

    def test_пример_ядра_лежит_ровно_в_рамке(self):
        """Контракт: макеты рисовались на этом вырезе, и он же — эталон рамки. Разъедется — разъедутся и числа стилей."""
        з = обложка.замеры_рамки(ROOT / "ядро/обложки/пример-студия/img/portret-vyrez.webp")
        self.assertIsNotNone(з)
        self.assertTrue(з["в_рамке"], з)

    def test_широкую_фигуру_ужимаем_и_говорим(self):
        with tempfile.TemporaryDirectory() as д:
            широкий = фигура_png(Path(д) / "shirokiy.png", кадр=(1200, 900), макушка=20, голова=90,
                                 ширина_головы=110, низ=880, плечи=9, центр=600)
            итог = обложка.рамка_выреза(широкий, Path(д) / "out")
            self.assertTrue(итог["приведено"])
            self.assertIn("шире рамки", итог["предупреждение"])
            self.assertEqual(обложка.касается_краёв(итог["путь"]), [])


class КрупностьИВид(unittest.TestCase):
    """Фикс-раунд Ж. Дело 1: два замера кадра уезжают в стиль переменными, а не процентами, снятыми
    с нашего файла. Дело 2: близкий кадр подводит плашку «имя · опора» к подбородку — об этом надо
    предупредить до сборки. Дело 3: вырез не человека рамку не получает — и об этом надо сказать
    словами, а не промолчать."""

    def test_крупность_меряет_кадр_а_без_замера_отдаёт_эталон(self):
        with tempfile.TemporaryDirectory() as д:
            д = Path(д)
            рост = фигура_png(д / "rost.png")
            голова_доля, макушка_доля = обложка.крупность(рост)
            self.assertAlmostEqual(голова_доля, обложка.ГОЛОВА_В_РАМКЕ, delta=обложка.ДОПУСК_РАМКИ)
            self.assertAlmostEqual(макушка_доля, обложка.МАКУШКА_В_РАМКЕ, delta=обложка.ДОПУСК_РАМКИ)
            with Image.open(рост) as к:
                к.crop((120, 40, к.width - 90, 620)).save(д / "grud.png")
            крупнее = обложка.крупность(д / "grud.png")[0]
            self.assertGreater(крупнее, голова_доля * 1.5)      # тот же человек ближе — голова крупнее, и стиль об этом узнает
            фото = д / "foto.jpg"
            Image.new("RGB", (800, 1200), (200, 180, 160)).save(фото)
            self.assertEqual(обложка.крупность(фото), (обложка.ГОЛОВА_В_РАМКЕ, обложка.МАКУШКА_В_РАМКЕ))
            self.assertEqual(обложка.крупность(фото, (обложка.ГОЛОВА_В_РОЛИКЕ, обложка.МАКУШКА_В_РОЛИКЕ)),
                             (обложка.ГОЛОВА_В_РОЛИКЕ, обложка.МАКУШКА_В_РОЛИКЕ))   # живому портрету — эталон его макета
            (д / "zaglushka.svg").write_text("<svg/>", encoding="utf-8")   # витрина подставляет svg — не поломка, а «не картинка»
            self.assertEqual(обложка.крупность(д / "zaglushka.svg"), (обложка.ГОЛОВА_В_РАМКЕ, обложка.МАКУШКА_В_РАМКЕ))
            self.assertIn("{{ГОЛОВА_В_КАДРЕ}}", обложка.слоты_крупности(рост))

    def test_что_видно_называет_увиденное(self):
        with tempfile.TemporaryDirectory() as д:
            д = Path(д)
            self.assertIn("вырез человека", обложка.что_видно(фигура_png(д / "rost.png")))
            коробка = вырез_png(д / "korobka.png")                     # прямоугольник: вырез, но не человек
            self.assertIn("вырез без человека", обложка.что_видно(коробка))
            фото = д / "foto.jpg"
            Image.new("RGB", (800, 600), (200, 180, 160)).save(фото)
            self.assertIn("обычная фотография", обложка.что_видно(фото))
            (д / "zaglushka.svg").write_text("<svg/>", encoding="utf-8")
            self.assertIn("не картинка", обложка.что_видно(д / "zaglushka.svg"))

    def test_вырез_не_человека_не_проходит_молча(self):
        """Дело 3: раньше на все случаи была одна глухая строка. Теперь сказано, что увидели и чего ждали."""
        with tempfile.TemporaryDirectory() as д:
            итог = обложка.рамка_выреза(вырез_png(Path(д) / "korobka.png"), Path(д) / "out")
            self.assertFalse(итог["приведено"])
            self.assertEqual(итог["вид"], "вырез-без-головы")
            self.assertIn("вырез без человека", итог["предупреждение"])
            self.assertIn("считается от головы", итог["предупреждение"])
            self.assertIn("схему, которой вырез не нужен", итог["предупреждение"])

    def test_близкий_кадр_говорит_замером_а_на_фото_просит_проверить(self):
        with tempfile.TemporaryDirectory() as д:
            д = Path(д)
            рост = фигура_png(д / "rost.png")
            self.assertLess(обложка.подбородок_в_кадре(рост), обложка.ПОРОГ_ПОДБОРОДКА)
            self.assertEqual(обложка.близкий_кадр(рост), "")
            with Image.open(рост) as к:
                к.crop((120, 40, к.width - 90, 620)).save(д / "blizko.png")   # «голова и плечи во весь кадр»
            self.assertGreater(обложка.подбородок_в_кадре(д / "blizko.png"), обложка.ПОРОГ_ПОДБОРОДКА)
            сказано = обложка.близкий_кадр(д / "blizko.png")
            self.assertIn("кадр слишком близкий", сказано)
            self.assertIn("запасом над головой", сказано)
            фото = д / "foto.jpg"
            Image.new("RGB", (800, 1200), (200, 180, 160)).save(фото)
            self.assertIsNone(обложка.подбородок_в_кадре(фото))
            self.assertIn("Проверьте кадр сами", обложка.близкий_кадр(фото))   # силуэта нет — не молчим, а просим проверить


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


class РамкаРолика(unittest.TestCase):
    """Живой портрет держит ролик с прозрачным фоном. Его мы не перекадрируем — меряем и говорим, что не так."""

    def test_говорит_что_не_так(self):
        with tempfile.TemporaryDirectory() as д:
            ровный = фигура_png(Path(д) / "kadr.png")
            self.assertIn("Кадр в рамке", обложка.рамка_ролика(ровный))
            крупный = фигура_png(Path(д) / "krupno.png", кадр=(720, 960), макушка=41, голова=239,
                                 ширина_головы=261, низ=960, центр=369)
            текст = обложка.рамка_ролика(крупный)
            self.assertIn("не в рамке", текст)
            self.assertIn("не перекадрируем", текст)
            пусто = Path(д) / "pusto.png"
            Image.new("RGBA", (400, 600), (0, 0, 0, 0)).save(пусто)
            self.assertIn("головы на первом кадре не видно", обложка.рамка_ролика(пусто))


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


class СветлотаИДобор(unittest.TestCase):
    """Фикс-раунд И, замечание 1. Затемнение кадра под текстом считается от светлоты самого кадра:
    макетные остановки — для кадра такой же светлоты, как в макете; кадр светлее — поверх ложится
    вуаль. Тест закрепляет три вещи: тёмному кадру добора нет вовсе, белому — не больше предела,
    и наши собственные примеры дают ровно те числа, из которых выведен шаг."""

    def test_тёмному_кадру_добора_нет_белому_предел(self):
        with tempfile.TemporaryDirectory() as д:
            тёмный = Path(д) / "temno.jpg"
            Image.new("RGB", (1600, 900), (18, 22, 30)).save(тёмный)
            белый = Path(д) / "belo.jpg"
            Image.new("RGB", (1600, 900), (252, 252, 250)).save(белый)
            self.assertLess(обложка.светлота_под_текстом(тёмный), обложка.СВЕТЛОТА_МАКЕТА)
            self.assertEqual(обложка.добор_затемнения(тёмный), 0)
            self.assertGreater(обложка.светлота_под_текстом(белый), обложка.СВЕТЛОТА_МАКЕТА)
            self.assertEqual(обложка.добор_затемнения(белый), обложка.ПРЕДЕЛ_ДОБОРА)
            # добор всегда в границах: ни отрицательным, ни гуще предела он не бывает
            for файл in (тёмный, белый):
                self.assertTrue(0 <= обложка.добор_затемнения(файл) <= обложка.ПРЕДЕЛ_ДОБОРА)

    def test_светлота_меряется_полосой_под_текстом_а_не_всем_кадром(self):
        # Кадр, где тёмная половина слева от полосы, а сама полоса белая: по всему кадру он средний,
        # по полосе — светлый. Меряем именно полосу, иначе светлый фон за человеком теряется в среднем.
        with tempfile.TemporaryDirectory() as д:
            кадр = Image.new("RGB", (1000, 600), (10, 10, 12))
            л, п, верх, низ = обложка.ПОЛОСА_ТЕКСТА
            кадр.paste((250, 250, 250), (int(1000 * л), int(600 * верх), int(1000 * п), int(600 * низ)))
            файл = Path(д) / "polosa.png"
            кадр.save(файл)
            self.assertGreater(обложка.светлота_под_текстом(файл), .9)
            self.assertEqual(обложка.добор_затемнения(файл), обложка.ПРЕДЕЛ_ДОБОРА)

    def test_не_картинка_не_ломает_замер(self):
        with tempfile.TemporaryDirectory() as д:
            битый = Path(д) / "bityi.webp"
            битый.write_text("это не картинка", encoding="utf-8")
            self.assertIsNone(обложка.светлота_под_текстом(битый))
            self.assertEqual(обложка.добор_затемнения(битый), 0)

    def test_наши_примеры_дают_числа_из_которых_выведен_шаг(self):
        пример = ROOT / "ядро" / "обложки" / "пример-студия"
        сцена = пример / "img" / "stsena-16x9.webp"          # кадр, по которому рисовался макет сцены
        живая = пример / "video" / "golos-poster.jpg"        # светлая студийная стена
        self.assertAlmostEqual(обложка.светлота_под_текстом(сцена), обложка.СВЕТЛОТА_МАКЕТА, delta=.02)
        self.assertEqual(обложка.добор_затемнения(сцена), 0, "на макетном кадре схема обязана встать без вуали")
        self.assertGreater(обложка.добор_затемнения(живая), .2, "светлый кадр остался без добора — текст на нём потеряется")


class ФотографияИлиВырез(unittest.TestCase):
    """Фикс-раунд И, замечание 4. Обратная находка к той, что завёл фикс-раунд Ж: раньше система
    говорила «схеме нужен вырез, а дали фотографию», теперь и наоборот — схемам, которые растворяют
    прямоугольный кадр виньеткой, вырез не годится."""

    def test_вырез_под_схему_с_фотографией_называется_словами(self):
        with tempfile.TemporaryDirectory() as д:
            фигура = вырез_png(Path(д) / "figura.png")
            найдено = обложка.находки_кадра("разворот", "фото", фигура, наш_пример=True)
            про_вырез = [н for н in найдено if "нужна фотография" in н["что"]]
            self.assertEqual(len(про_вырез), 1, найдено)
            self.assertIn("прозрачный фон занимает", про_вырез[0]["строки"][0])
            self.assertIn("фон подбирают, а не вырезают", про_вырез[0]["чем_грозит"])

    def test_фотография_под_ту_же_схему_молчит(self):
        with tempfile.TemporaryDirectory() as д:
            фото = Path(д) / "foto.jpg"
            Image.new("RGB", (800, 1067), (180, 170, 160)).save(фото)
            найдено = обложка.находки_кадра("разворот", "фото", фото, наш_пример=True)
            self.assertEqual([н for н in найдено if "нужна фотография" in н["что"]], [])

    def test_вырезу_под_свою_схему_эта_находка_не_приходит(self):
        with tempfile.TemporaryDirectory() as д:
            фигура = вырез_png(Path(д) / "figura.png")
            найдено = обложка.находки_кадра("центр", "вырез", фигура, наш_пример=True)
            self.assertEqual([н for н in найдено if "нужна фотография" in н["что"]], [])

    def test_наш_пример_разворота_больше_не_вырез(self):
        # Замечание 4 целиком: у схемы «разворот» в примере ядра лежал файл с прозрачным фоном.
        кадр = ROOT / "ядро" / "обложки" / "пример-студия" / "img" / "portret-3x4.webp"
        self.assertEqual(обложка.доля_прозрачного(кадр), 0, "в примере разворота снова вырез, а не фотография")


if __name__ == "__main__":
    unittest.main()
