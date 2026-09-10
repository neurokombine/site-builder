"""обложки.py: подбор картинок под тип, все схемы набора на текстах, палитре и картинке; каталог без копий медиа."""
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "ядро" / "скрипты"))
import витрина  # noqa: E402
import глаза  # noqa: E402
import находки  # noqa: E402
import обложки  # noqa: E402

ФИКСТУРЫ = ROOT / "ядро" / "скрипты" / "tests" / "фикстуры"
ВИЗИТКА = ("разворот", "орбита", "сцена", "живая-сцена", "товар-крупно", "бенто", "центр", "живой-портрет")


def _скопировать_образец(д: Path) -> Path:
    shutil.copytree(ФИКСТУРЫ / "работа-образец", д / "работа")
    shutil.copytree(ФИКСТУРЫ / "профиль-образец", д / "профиль-образец")
    return д / "работа"


def _материалы(работа: Path) -> None:
    """Файлы по контракту З: фото 3:4, вырез, кадр 16:9, экран, товар 9:16, голос, живая, портрет-вырез, три ролика."""
    img, video = работа / "img", работа / "video"
    for имя in ("portret-3x4.webp", "stsena-16x9.webp", "ekran.webp", "tovar-9x16.webp"):
        Image.new("RGB", (40, 30), (9, 9, 9)).save(img / имя)
    вырез = Image.new("RGBA", (40, 60), (0, 0, 0, 0))
    вырез.paste((1, 2, 3, 255), (10, 6, 30, 56))
    вырез.save(img / "portret-vyrez.png")
    for имя in ("golos.mp4", "golos-poster.jpg", "zhivaya.mp4", "zhivaya.webm", "zhivaya-telefon.mp4", "zhivaya-poster.jpg",
                "zhivaya-telefon-poster.jpg", "portret-vyrez.webm", "portret-vyrez-poster.png",
                "rolik-1.mp4", "rolik-1-poster.jpg", "rolik-2.mp4", "rolik-2-poster.jpg", "rolik-3.mp4"):
        (video / имя).write_bytes(b"")


class Правила(unittest.TestCase):
    def test_рекомендации(self):
        т = {"фото": "a.jpg", "видео": "", "цифры": [1, 2, 3]}
        self.assertEqual(list(обложки.рекомендации(т, "визитка")), ["разворот"])
        self.assertEqual(list(обложки.рекомендации(т, "лендинг")), ["разворот", "орбита"])
        self.assertEqual(list(обложки.рекомендации({**т, "видео": "v"}, "лендинг")), ["живая-обложка", "разворот"])
        self.assertEqual(list(обложки.рекомендации({**т, "видео": "v", "голос": "g"}, "визитка")), ["живая-сцена", "разворот"])
        self.assertEqual(list(обложки.рекомендации({"фото": "", "видео": "", "цифры": []}, "визитка")), ["сцена"])
        for почему in обложки.рекомендации(т, "лендинг").values():
            self.assertGreater(len(почему), 30)

    def test_схемы_набора(self):
        self.assertEqual(tuple(обложки.схемы_набора("визитка")), ВИЗИТКА)
        self.assertEqual(len(обложки.схемы_набора("лендинг")), 11)
        self.assertEqual(tuple(обложки.схемы_набора("нет-такого")), ВИЗИТКА)

    def test_подбор_картинок_под_тип(self):
        with tempfile.TemporaryDirectory() as д:
            работа = _скопировать_образец(Path(д))
            _материалы(работа)
            к = обложки.картинки_для_схем(работа, "лендинг", {"фото": "пример.svg", "видео": "", "постер": ""})
            self.assertEqual(к["разворот"]["фото"], "portret-3x4.webp")
            self.assertEqual(к["сцена"]["фото"], "stsena-16x9.webp")
            self.assertEqual(к["бенто"]["фото"], "stsena-16x9.webp")
            self.assertEqual((к["орбита"]["фото"], к["центр"]["лицо"]), ("portret-vyrez.png", "50,25"))
            self.assertEqual(к["афиша-с-экраном"]["фото"], "ekran.webp")
            self.assertEqual(к["товар-крупно"]["фото"], "tovar-9x16.webp")
            self.assertEqual((к["живая-сцена"]["видео"], к["живая-сцена"]["постер"]), ("golos", "golos-poster.jpg"))
            self.assertEqual((к["живая-обложка"]["видео"], к["живая-обложка"]["видео_телефон"], к["живая-обложка"]["постер_телефон"]),
                             ("zhivaya", "zhivaya-telefon", "zhivaya-telefon-poster.jpg"))
            self.assertEqual((к["живой-портрет"]["видео"], к["живой-портрет"]["постер"]), ("portret-vyrez", "portret-vyrez-poster.png"))
            self.assertEqual(к["мозаика-роликов"]["ролики"], [("rolik-1", "rolik-1-poster.jpg"), ("rolik-2", "rolik-2-poster.jpg"), ("rolik-3", "кадр.svg")])
            пусто = обложки.картинки_для_схем(работа / "нет", "визитка", {"фото": "", "видео": "", "постер": ""})
            self.assertEqual((пусто["разворот"]["фото"], пусто["живой-портрет"]["видео"], пусто["орбита"]["лицо"]), ("", "", "50,22"))
            self.assertEqual(tuple(обложки.картинки_для_схем(работа, "нет-такого", {"фото": "", "видео": "", "постер": ""})), ВИЗИТКА)   # чужой пресет → визитка, не FileNotFoundError

    def test_каталог_заглушки_ведут_в_ядро(self):
        """В каталоге медиа — по ссылке в папку работы, а силуэт и кадр — в ядро/блоки/заглушки: в папке примера их нет."""
        with tempfile.TemporaryDirectory() as д:
            работа = _скопировать_образец(Path(д))
            своя = Path(д) / "каталог" / "обложка-разворот"
            своя.mkdir(parents=True)
            html = обложки._в_каталог('<img src="img/пример.svg"><img src="img/силуэт.svg"><video poster="video/кадр.svg">'
                                      '<source src="video/пример.mp4"><img src="video/кадр.svg">', работа, своя)
            self.assertIn('src="../../работа/img/пример.svg"', html)
            self.assertIn('src="../../работа/video/пример.mp4"', html)
            self.assertNotIn("работа/img/силуэт.svg", html)
            self.assertNotIn("работа/video/кадр.svg", html)
            ссылки = re.findall(r'"([^"]*(?:силуэт|кадр)\.svg)"', html)
            self.assertEqual(len(ссылки), 3)
            for ссылка in ссылки:
                self.assertTrue((своя / ссылка).resolve().is_file(), ссылка)
                self.assertEqual((своя / ссылка).resolve().parent, витрина.ЗАГЛУШКИ.resolve())

    def test_без_палитры_красное(self):
        with tempfile.TemporaryDirectory() as д:
            работа = _скопировать_образец(Path(д))
            дизайн = работа / "дизайн.md"
            дизайн.write_text(дизайн.read_text(encoding="utf-8").split("## Решения")[0], encoding="utf-8")
            путь, н = обложки.обложки(работа, куда=Path(д) / "витрина")
            self.assertEqual([x["что"] for x in н if x["уровень"] == находки.ЧИНИТЬ], ["Палитра ещё не выбрана"])
            self.assertFalse(путь.exists())


class ВБраузере(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls._playwright = sync_playwright().start()
        cls.браузер = глаза.запустить_браузер(cls._playwright)

    @classmethod
    def tearDownClass(cls):
        cls.браузер.close()
        cls._playwright.stop()

    def test_восемь_обложек_образца(self):
        with tempfile.TemporaryDirectory() as д:
            работа = _скопировать_образец(Path(д))
            путь, н = обложки.обложки(работа, куда=Path(д) / "витрина", браузер=self.браузер, сторона="слева")
            self.assertFalse(находки.есть_красное(н), н)
            self.assertNotIn("Картинки первого экрана ещё нет", [x["что"] for x in н])
            текст = путь.read_text(encoding="utf-8")
            for номер, схема in enumerate(ВИЗИТКА, 1):
                папка = Path(д) / "витрина" / f"обложка-{схема}"
                страница = (папка / "index.html").read_text(encoding="utf-8")
                self.assertIn(f'data-схема="{схема}"', страница)
                self.assertIn("сторона--слева", страница.split("</section>")[0])
                self.assertIn('data-лицо="50,22"', страница)
                self.assertNotIn("{{", страница)
                self.assertIn("--цвет-акцент", страница)                       # палитра из Решений
                for файл in ("компьютер.jpg", "телефон.jpg", "style.css", "img/пример.svg", "video/пример.webm", "img/силуэт.svg"):
                    self.assertTrue((папка / файл).is_file(), файл)
                self.assertIn(f"{номер} · {схема}", текст)
                self.assertIn(f"обложка-{схема}/index.html", текст)
            живая = (Path(д) / "витрина" / "обложка-живая-сцена" / "index.html").read_text(encoding="utf-8")
            self.assertEqual(живая.count("<script>"), 2)                       # обложка.js + звук.js
            self.assertIn("рекомендую", текст)
            self.assertIn("номер · сторона", текст)
            self.assertIn("слева", текст.split("Что ответить")[1])

    def test_каталог_без_копий_медиа(self):
        with tempfile.TemporaryDirectory() as д:
            работа = _скопировать_образец(Path(д))
            путь, н = обложки.обложки(работа, куда=Path(д) / "каталог", браузер=self.браузер, каталог=True)
            self.assertFalse(находки.есть_красное(н), н)
            папка = Path(д) / "каталог" / "обложка-разворот"
            страница = (папка / "index.html").read_text(encoding="utf-8")
            self.assertIn('src="../../работа/img/пример.svg"', страница)
            self.assertFalse((папка / "img").exists())
            self.assertIn('poster="../../работа/video/', (Path(д) / "каталог" / "обложка-живая-сцена" / "index.html").read_text(encoding="utf-8"))
            self.assertTrue((папка / "компьютер.jpg").is_file())
            for схема in ВИЗИТКА:   # заглушки никогда не ведут в папку работы; если есть — файл существует
                своя = Path(д) / "каталог" / f"обложка-{схема}"
                html = (своя / "index.html").read_text(encoding="utf-8")
                self.assertNotIn("работа/img/силуэт.svg", html)
                self.assertNotIn("работа/video/кадр.svg", html)
                for ссылка in re.findall(r'"([^"]*(?:силуэт|кадр)\.svg)"', html):
                    self.assertTrue((своя / ссылка).resolve().is_file(), ссылка)
            текст = путь.read_text(encoding="utf-8")
            self.assertIn("Каталог схем первого экрана", текст)
            self.assertIn("обложки.py сайты/", текст)

    def test_без_картинки_силуэт_и_жёлтое(self):
        with tempfile.TemporaryDirectory() as д:
            работа = _скопировать_образец(Path(д))
            shutil.rmtree(работа / "img")
            путь, н = обложки.обложки(работа, куда=Path(д) / "витрина", браузер=self.браузер)
            self.assertIn("Картинки первого экрана ещё нет", [x["что"] for x in н])
            self.assertFalse(находки.есть_красное(н), н)
            self.assertIn('src="img/силуэт.svg"', (Path(д) / "витрина" / "обложка-разворот" / "index.html").read_text(encoding="utf-8"))
            self.assertIn("силуэт", путь.read_text(encoding="utf-8"))

    def test_cli_без_показа(self):
        with tempfile.TemporaryDirectory() as д:
            работа = _скопировать_образец(Path(д))
            р = subprocess.run([sys.executable, str(ROOT / "ядро/скрипты/обложки.py"), str(работа), "--сторона", "справа", "--без-показа"],
                               capture_output=True, text=True, timeout=300)
            self.assertEqual(р.returncode, 0, р.stdout[-2000:] + р.stderr[-2000:])
            self.assertIn("# Обложки:", р.stdout)
            self.assertTrue((работа / "витрина" / "обложки.html").is_file())


if __name__ == "__main__":
    unittest.main()
