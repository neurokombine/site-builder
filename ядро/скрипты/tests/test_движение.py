"""Обложка движется и там, где автозапуск запрещён: генерация (`ролик_обложки.py`), разметка рецептов,
скрипт `обложка.js` и замер `движение.py`.

Ролики рисует здесь же ffmpeg (`testsrc`, две секунды) — в репозитории их нет и в интернет мы не ходим.
Нет ffmpeg — классы, которым нужен ролик, пропускаются со словами, а не падают.

Учебные страницы собраны из настоящих стилей первого экрана и настоящего `обложка.js`:
- «движется» — живая обложка с роликом и анимацией у каждого размера: молчит во всех прогонах;
- «стоит» — тот же ролик без анимированной картинки: при запрете автозапуска стоит постер — 🔴;
- «только-webp» — AVIF не открылся (файла нет): страница берёт WebP, обложка движется;
- «мозаика» — два ролика в рамках, у каждой рамки своя картинка: движется без ролика.

Запуск из корня репозитория:
    .venv/bin/python -m unittest discover -s ядро/скрипты/tests -t .
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

СКРИПТЫ = Path(__file__).resolve().parent.parent
БЛОКИ = СКРИПТЫ.parent / "блоки"
sys.path.insert(0, str(СКРИПТЫ))

import движение  # noqa: E402
import ролик_обложки  # noqa: E402
from находки import ЧИНИТЬ  # noqa: E402

FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
НЕТ_FFMPEG = "ffmpeg не найден — ролик для теста нарисовать нечем"


def нарисовать_ролик(путь: Path, ширина: int, высота: int, *доп: str) -> Path:
    """testsrc на две секунды: бегущие цифры и полосы — кадр меняется всегда."""
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    f"testsrc=size={ширина}x{высота}:rate=24:duration=2", *доп, str(путь)], check=True)
    return путь


# ── Генерация ─────────────────────────────────────────────────────────────────────────────

@unittest.skipUnless(FFMPEG, НЕТ_FFMPEG)
class ГенерацияТесты(unittest.TestCase):
    """Компьютерный ролик — High 5.1 со звуком и метаданными в конце: метка уровня переписывается без
    перекодирования. Телефонный — yuv444p: перекодируется. У обоих — постер и анимация в бюджете."""

    @classmethod
    def setUpClass(cls):
        cls._временная = tempfile.TemporaryDirectory()
        корень = Path(cls._временная.name)
        исходники = корень / "исходники"
        исходники.mkdir()
        cls.куда = корень / "video"
        комп = нарисовать_ролик(исходники / "Обложка компьютер.mp4", 320, 180, "-f", "lavfi", "-i",
                                "sine=frequency=440:duration=2", "-shortest", "-c:v", "libx264", "-profile:v", "high",
                                "-level", "5.1", "-pix_fmt", "yuv420p", "-c:a", "aac")
        тел = нарисовать_ролик(исходники / "обложка-телефон.mp4", 180, 320, "-c:v", "libx264", "-pix_fmt", "yuv444p")
        cls.комп = ролик_обложки.приготовить(комп, cls.куда)
        cls.тел = ролик_обложки.приготовить(тел, cls.куда)

    @classmethod
    def tearDownClass(cls):
        cls._временная.cleanup()

    def test_вид_угадан_по_пропорции(self):
        self.assertEqual(self.комп["вид"], "компьютер")
        self.assertEqual(self.тел["вид"], "телефон")

    def test_имена_латиницей_и_от_имени_ролика(self):
        self.assertEqual(self.комп["ролик"]["путь"].name, "oblozhka-kompyuter.mp4")
        for имя in ("oblozhka-kompyuter-poster.jpg", "oblozhka-kompyuter-anim.avif", "oblozhka-kompyuter-anim.webp",
                    "oblozhka-telefon.mp4", "oblozhka-telefon-poster.jpg", "oblozhka-telefon-anim.avif",
                    "oblozhka-telefon-anim.webp"):
            self.assertTrue((self.куда / имя).is_file(), имя)

    def test_метка_уровня_переписана_на_40_а_не_на_4(self):
        self.assertEqual(self.комп["ролик"]["действие"], "метка")
        sps = ролик_обложки.sps(self.комп["ролик"]["путь"])
        self.assertEqual(sps["level_idc"], 40, "фильтр понимает «4.0» как level_idc = 4 — уровня, которого нет")

    def test_ролик_под_ios(self):
        for итог in (self.комп, self.тел):
            р = ролик_обложки.разобрать(итог["ролик"]["путь"])
            self.assertEqual((р["кодек"], р["пиксели"]), ("h264", "yuv420p"))
            self.assertLessEqual(р["уровень"], 40)
            self.assertFalse(р["звук"], "звуковая дорожка осталась")
            self.assertTrue(ролик_обложки.faststart(итог["ролик"]["путь"]), "метаданные не в начале файла")
        self.assertEqual(self.тел["ролик"]["действие"], "перекодировать")

    def test_анимация_движется_в_бюджете_и_начинается_с_постера(self):
        from PIL import Image, ImageChops, ImageStat

        for итог in (self.комп, self.тел):
            постер = Image.open(итог["постер"]).convert("RGB")
            for формат in ("avif", "webp"):
                ф = итог["файлы"][формат]
                self.assertLessEqual(ф["путь"].stat().st_size, ролик_обложки.БЮДЖЕТ_МБ[итог["вид"]] * 1_048_576)
                with Image.open(ф["путь"]) as клип:
                    self.assertGreater(getattr(клип, "n_frames", 1), 10, f"{ф['путь'].name}: не анимация")
                    первый = клип.convert("RGB").resize(постер.size)
                разница = ImageStat.Stat(ImageChops.difference(первый, постер).convert("L")).mean[0]
                self.assertLess(разница, 12, f"{ф['путь'].name}: первый кадр не постер — подмена прыгнет")
                self.assertIn(ф["кадров_в_с"], (15, 12))

    def test_исходник_не_тронут_и_рядом_пишется_ios(self):
        тут = self.куда / "oblozhka-telefon.mp4"
        до = тут.stat().st_size
        повтор = ролик_обложки.под_ios(тут, self.куда)
        self.assertEqual(повтор["действие"], "ничего", "готовый ролик второй раз не трогаем")
        self.assertEqual(тут.stat().st_size, до)

    def test_отчёт_словами(self):
        слова = "\n".join(ролик_обложки.слова(self.комп))
        self.assertIn("переписана метка уровня", слова)
        self.assertIn("Анимация AVIF", слова)
        self.assertIn("{{ВИДЕО}} = oblozhka-kompyuter", слова)


class ПланПодIosТесты(unittest.TestCase):
    """Решение «что делать с роликом» — без ffmpeg, на числах."""

    РОЛИК = {"кодек": "h264", "профиль": "High", "уровень": 50, "пиксели": "yuv420p", "ширина": 1920,
             "высота": 1080, "кадров_в_с": 24.0, "поток_кбит": 2200, "звук": False, "альфа": False}
    SPS_1080 = {"level_idc": 50, "pic_width_in_mbs_minus1": 119, "pic_height_in_map_units_minus1": 67,
                "frame_mbs_only_flag": 1, "max_num_ref_frames": 4, "max_dec_frame_buffering": 4}

    def test_влезает_в_40_значит_метка(self):
        self.assertEqual(ролик_обложки.план_под_ios(self.РОЛИК, self.SPS_1080, True)["действие"], "метка")

    def test_пять_опорных_кадров_у_1080p_значит_перекодировать(self):
        план = ролик_обложки.план_под_ios(self.РОЛИК, dict(self.SPS_1080, max_num_ref_frames=5,
                                                          max_dec_frame_buffering=5), True)
        self.assertEqual(план["действие"], "перекодировать")
        self.assertIn("опорных кадров 5", " ".join(план["причины"]))

    def test_метка_несуществующего_уровня_тоже_правится(self):
        план = ролик_обложки.план_под_ios(self.РОЛИК, dict(self.SPS_1080, level_idc=4), True)
        self.assertEqual(план["действие"], "метка")

    def test_не_h264_и_не_yuv420p_значит_перекодировать(self):
        for правка in ({"кодек": "hevc"}, {"пиксели": "yuv444p"}, {"профиль": "High 10"}):
            self.assertEqual(ролик_обложки.план_под_ios(dict(self.РОЛИК, **правка), self.SPS_1080, True)["действие"],
                             "перекодировать", правка)

    def test_годный_ролик_не_трогаем_а_звук_и_faststart_переупаковкой(self):
        годный = dict(self.РОЛИК, уровень=40)
        sps = dict(self.SPS_1080, level_idc=40)
        self.assertEqual(ролик_обложки.план_под_ios(годный, sps, True)["действие"], "ничего")
        self.assertEqual(ролик_обложки.план_под_ios(dict(годный, звук=True), sps, True)["действие"], "переупаковать")
        self.assertEqual(ролик_обложки.план_под_ios(годный, sps, False)["действие"], "переупаковать")

    def test_нечем_кодировать_говорит_что_поставить(self):
        self.assertIn("avifenc", ролик_обложки.НЕТ_AVIF)
        self.assertIn("img2webp", ролик_обложки.НЕТ_WEBP)
        self.assertIn("brew install ffmpeg", ролик_обложки.НЕТ_FFMPEG)


@unittest.skipUnless(FFMPEG, НЕТ_FFMPEG)
class ВесРоликаТесты(unittest.TestCase):
    """Совместимый с iOS, но тяжёлый ролик пережимается; лёгкий совместимый — не трогается."""

    @classmethod
    def setUpClass(cls):
        cls._временная = tempfile.TemporaryDirectory()
        корень = Path(cls._временная.name)
        cls.куда = корень / "video"
        cls.куда.mkdir()
        общее = ("-c:v", "libx264", "-profile:v", "high", "-level", "4.0", "-pix_fmt", "yuv420p",
                 "-movflags", "+faststart")
        cls.тяжёлый = нарисовать_ролик(корень / "тяжёлый.mp4", 1920, 1080, "-vf", "noise=alls=12:allf=t", *общее,
                                       "-crf", "10")
        cls.лёгкий = нарисовать_ролик(корень / "лёгкий.mp4", 320, 180, *общее, "-crf", "28")

    @classmethod
    def tearDownClass(cls):
        cls._временная.cleanup()

    def test_тяжёлый_совместимый_пережат_и_легче(self):
        до = self.тяжёлый.stat().st_size
        итог = ролик_обложки.под_ios(self.тяжёлый, self.куда, "компьютер")
        self.assertEqual(итог["действие"], "перекодировать")
        self.assertTrue(итог["тяжёлый"])
        self.assertLess(итог["путь"].stat().st_size, до)
        self.assertLess(итог["стало_мб"], итог["было_мб"])
        р = ролик_обложки.разобрать(итог["путь"])
        self.assertEqual((р["кодек"], р["пиксели"], р["ширина"], р["высота"]), ("h264", "yuv420p", 1920, 1080))
        self.assertTrue(ролик_обложки.faststart(итог["путь"]))
        слова = "\n".join(ролик_обложки.слова({"ролик": итог, "постер": итог["путь"], "файлы": {}, "слова": [],
                                              "вид": "компьютер", "имя": "x"}))
        self.assertIn("было", слова)
        self.assertIn("стало", слова)

    def test_лёгкий_не_трогается(self):
        итог = ролик_обложки.под_ios(self.лёгкий, self.куда, "компьютер")
        self.assertEqual(итог["действие"], "ничего")
        self.assertFalse(итог["тяжёлый"])
        self.assertEqual(итог["путь"].read_bytes(), self.лёгкий.read_bytes())

    def test_пороги_на_числах(self):
        р = ПланПодIosТесты.РОЛИК
        self.assertEqual(ролик_обложки.порог_потока(р), 2500)
        self.assertEqual(ролик_обложки.порог_потока(dict(р, ширина=1280, высота=720)), 1500)
        self.assertTrue(ролик_обложки.тяжесть(dict(р, поток_кбит=5400), None, "компьютер"))
        self.assertTrue(ролик_обложки.тяжесть(dict(р, поток_кбит=900), 3_000_000, "компьютер"))
        self.assertFalse(ролик_обложки.тяжесть(dict(р, поток_кбит=900), 1_000_000, "компьютер"))


# ── Разметка рецептов ─────────────────────────────────────────────────────────────────────

class РазметкаРецептовТесты(unittest.TestCase):
    """Атрибуты автозапуска — в разметке с самого начала, а не из скрипта: часть браузеров решает про
    автозапуск по разметке. У каждого ролика — картинка, на которую ляжет анимация того же клипа."""

    def рецепты(self):
        return [п for п in sorted(БЛОКИ.glob("*/01-первый-экран-*.html")) if "<video" in п.read_text(encoding="utf-8")]

    def test_все_ролики_нашлись(self):
        имена = {п.stem.removeprefix("01-первый-экран-") for п in self.рецепты()}
        self.assertEqual(имена, {"живая-обложка", "живая-сцена", "живой-портрет", "мозаика-роликов"})

    def test_атрибуты_автозапуска_в_разметке(self):
        import re

        for путь in self.рецепты():
            for тег in re.findall(r"<video\b[^>]*>", путь.read_text(encoding="utf-8")):
                атрибуты = set(re.findall(r"\s([\w-]+)(?==|\s|>)", тег))
                with self.subTest(рецепт=путь.name):
                    self.assertTrue({"autoplay", "muted", "loop", "playsinline", "webkit-playsinline", "preload"} <= атрибуты,
                                    f"{путь.name}: {тег[:90]}")

    def test_у_каждого_ролика_есть_анимация_в_picture(self):
        import re

        for путь in self.рецепты():
            текст = путь.read_text(encoding="utf-8")
            роликов = текст.count("<video")
            картинок = re.findall(r"<picture>(?:<source[^>]*>)?<img\b[^>]*data-анимация-webp[^>]*>", текст)
            with self.subTest(рецепт=путь.name):
                # мозаика — картинка в каждой рамке, остальные — постер фигуры
                self.assertEqual(len(картинок), роликов if роликов > 1 else 1)
                self.assertIn("-anim.avif", текст)
                self.assertIn("-anim.webp", текст)

    def test_живая_обложка_у_каждого_размера_своя_анимация(self):
        текст = (БЛОКИ / "лендинг" / "01-первый-экран-живая-обложка.html").read_text(encoding="utf-8")
        for атрибут in ('data-анимация-avif-телефон="video/{{ВИДЕО_ТЕЛЕФОН}}-anim.avif"',
                        'data-анимация-webp-компьютер="video/{{ВИДЕО}}-anim.webp"'):
            self.assertIn(атрибут, текст)

    def test_скрипт_ждёт_секунду_и_слушает_всё_что_нужно(self):
        скрипт = (БЛОКИ / "обложка.js").read_text(encoding="utf-8")
        for слово in ("ЖДАТЬ_МС = 1000", "loadedmetadata", "visibilitychange", "pageshow", "suspend", "stalled",
                      "image/avif", "картинка--постер", "в.muted = true", "timeupdate"):
            self.assertIn(слово, скрипт)


# ── Замер «обложка движется» ──────────────────────────────────────────────────────────────

СТРАНИЦА = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><style>{стили}
body {{ margin: 0; }} .блок--первый-экран {{ position: relative; height: 100vh; overflow: hidden; }}
.рамка-телефона {{ display: inline-block; width: 140px; }}
</style></head><body>
<section class="блок блок--первый-экран" id="экран-1" data-тип="первый-экран">
{фигура}
<h1 style="position: relative">Заголовок обложки</h1>
<p class="таймер" style="position: relative" id="часы">0</p>
</section><section class="блок" id="экран-2"><p>Дальше</p></section>
<div style="height: 200vh"></div>
<script>setInterval(function () {{ var ч = document.getElementById("часы"); ч.textContent = +ч.textContent + 1; }}, 200);</script>
<script>{скрипт}</script></body></html>"""
ОБЛОЖКА = ('<figure class="картинка картинка--видео картинка--постер первый-экран__картинка"><video autoplay muted loop '
           'playsinline webkit-playsinline preload="none" poster="video/komp-poster.jpg" data-ролик-компьютер="video/komp.mp4" '
           'data-постер-компьютер="video/komp-poster.jpg" data-ролик-телефон="video/tel.mp4" data-постер-телефон="video/tel-poster.jpg">'
           '</video><picture><source media="(max-width: 899px)" srcset="video/tel-poster.jpg"><img src="video/komp-poster.jpg" '
           'alt="кадр"{анимация}></picture></figure>')
АНИМАЦИЯ = (' data-анимация-avif-компьютер="video/komp-anim.avif" data-анимация-webp-компьютер="video/komp-anim.webp"'
            ' data-анимация-avif-телефон="video/tel-anim.avif" data-анимация-webp-телефон="video/tel-anim.webp"')
ТОЛЬКО_WEBP = АНИМАЦИЯ.replace("komp-anim.avif", "nety.avif").replace("tel-anim.avif", "nety.avif")
РАМКА = ('<div class="рамка-телефона"><div class="рамка-телефона__экран"><video autoplay muted loop playsinline '
         'webkit-playsinline preload="metadata" poster="video/tel-poster.jpg"><source src="video/tel.mp4" type="video/mp4">'
         '</video><picture><img class="рамка-телефона__анимация" alt="" hidden data-анимация-avif="video/tel-anim.avif" '
         'data-анимация-webp="video/tel-anim.webp"></picture></div></div>')
МОЗАИКА = f'<figure class="картинка картинка--мозаика первый-экран__картинка">{РАМКА}{РАМКА}</figure>'
# Первый вызов play() отклонён (встроенный браузер), следующие — настоящие: так проверяем, что ролик,
# пошедший позже, возвращается на место картинки.
ОТКАЗ_ПОТОМ_ИГРАЕТ = """(() => { const настоящий = HTMLMediaElement.prototype.play; let первый = true;
  document.addEventListener('play', e => { if (первый && e.target.tagName === 'VIDEO') HTMLMediaElement.prototype.pause.call(e.target); }, true);
  HTMLMediaElement.prototype.play = function () { if (первый) return Promise.reject(new DOMException('нет', 'NotAllowedError'));
    return настоящий.call(this); };
  addEventListener('wheel', () => { первый = false; }, {capture: true}); })();"""


@unittest.skipUnless(FFMPEG, НЕТ_FFMPEG)
class ЗамерДвиженияТесты(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright

        import глаза
        import проверить

        cls._временная = tempfile.TemporaryDirectory()
        корень = Path(cls._временная.name)
        исходники = корень / "исходники"
        исходники.mkdir()
        видео = корень / "общее-video"
        for имя, ш, в in (("komp", 320, 180), ("tel", 180, 320)):
            ролик_обложки.приготовить(нарисовать_ролик(исходники / f"{имя}.mp4", ш, в, "-c:v", "libx264",
                                                        "-pix_fmt", "yuv420p"), видео)
        стили = "\n".join((БЛОКИ / имя).read_text(encoding="utf-8") for имя in
                          ("стили-база.css", "стили-первый-экран.css", "стили-первый-экран-кадр.css"))
        скрипт = (БЛОКИ / "обложка.js").read_text(encoding="utf-8")
        страницы = {"движется": ОБЛОЖКА.format(анимация=АНИМАЦИЯ), "стоит": ОБЛОЖКА.format(анимация=""),
                    "только-webp": ОБЛОЖКА.format(анимация=ТОЛЬКО_WEBP), "мозаика": МОЗАИКА}
        cls.папки = {}
        for имя, фигура in страницы.items():
            папка = корень / имя
            shutil.copytree(видео, папка / "video")
            (папка / "index.html").write_text(СТРАНИЦА.format(стили=стили, фигура=фигура, скрипт=скрипт), encoding="utf-8")
            cls.папки[имя] = папка
        cls.замеры = {}
        with sync_playwright() as движок:
            браузер = глаза.запустить_браузер(движок)
            try:
                for имя, папка in cls.папки.items():
                    with проверить.локальный_сервер(папка) as адрес:
                        cls.замеры[имя] = движение.снять(браузер, адрес + "index.html", корень / f"снимки-{имя}",
                                                         движок=движок if имя == "движется" else None)
                with проверить.локальный_сервер(cls.папки["движется"]) as адрес:
                    cls.вернулся = cls._ролик_вернулся(браузер, адрес + "index.html")
            finally:
                браузер.close()

    @staticmethod
    def _ролик_вернулся(браузер, адрес: str) -> dict:
        контекст = браузер.new_context(viewport={"width": 1280, "height": 800})
        контекст.add_init_script(ОТКАЗ_ПОТОМ_ИГРАЕТ)
        страница = контекст.new_page()
        страница.goto(адрес, wait_until="load")
        страница.wait_for_timeout(1600)
        состояние = """() => { const ф = document.querySelector('figure'), и = ф.querySelector('img');
          return {постер: ф.classList.contains('картинка--постер'), картинка: и.currentSrc.split('/').pop(),
                  источников: ф.querySelectorAll('source').length}; }"""
        до = страница.evaluate(состояние)
        страница.mouse.wheel(0, 300)
        страница.wait_for_timeout(1500)
        после = страница.evaluate(состояние)
        контекст.close()
        return {"до": до, "после": после}

    @classmethod
    def tearDownClass(cls):
        cls._временная.cleanup()

    def красные(self, имя):
        return [н for н in движение.находки(self.замеры[имя], self.папки[имя]) if н["уровень"] == ЧИНИТЬ]

    def test_ролик_с_анимацией_молчит_во_всех_прогонах(self):
        замер = self.замеры["движется"]
        self.assertTrue(замер["есть"])
        режимы = {(п["движок"], п["размер"], п["режим"]) for п in замер["прогоны"] if "доля" in п}
        self.assertTrue({("Chromium", р, м) for р in ("компьютер", "телефон") for м in ("обычный", "отказ", "вечно", "уменьшение", "уменьшение-отказ")}
                        <= режимы, режимы)
        self.assertEqual(self.красные("движется"), [])

    def test_при_запрете_на_месте_анимированная_картинка(self):
        for п in self.замеры["движется"]["прогоны"]:
            if п.get("режим") in ("отказ", "вечно") and "доля" in п:
                with self.subTest(п=(п["движок"], п["размер"], п["режим"])):
                    self.assertFalse(п["ролик_шёл"])
                    self.assertTrue(any(к.endswith("-anim.avif") for к in п["картинки"]), п["картинки"])
                    self.assertGreaterEqual(п["доля"], движение.ПОРОГ_ДОЛИ)

    def test_при_уменьшении_движения_обложка_движется(self):
        """prefers-reduced-motion: reduce — ролик играет, а с запретом play() — анимированная картинка."""
        обычные = [п for п in self.замеры["движется"]["прогоны"] if п.get("режим") == "уменьшение" and "доля" in п]
        self.assertTrue(обычные)
        for п in обычные:
            with self.subTest(п=(п["движок"], п["размер"])):
                self.assertGreaterEqual(п["доля"], движение.ПОРОГ_ДОЛИ)
                self.assertTrue(п["ролик_шёл"], п)
        запрет = [п for п in self.замеры["движется"]["прогоны"] if п.get("режим") == "уменьшение-отказ" and "доля" in п]
        self.assertTrue(запрет)
        for п in запрет:
            self.assertTrue(any(к.endswith("-anim.avif") for к in п["картинки"]), п["картинки"])
            self.assertGreaterEqual(п["доля"], движение.ПОРОГ_ДОЛИ)

    def test_остановка_при_уменьшении_называется_красным(self):
        стоит = {"есть": True, "прогоны": [{"движок": "Chromium", "размер": "телефон", "режим": "уменьшение",
                                            "доля": 0.0, "картинки": ["komp-poster.jpg"], "анимация": ["a.avif"]}]}
        красные = [н for н in движение.находки(стоит) if н["уровень"] == ЧИНИТЬ]
        self.assertEqual([н["что"] for н in красные], ["Обложка стоит, когда автозапуск запрещён"])
        self.assertTrue(any("включено уменьшение движения" in с for с in красные[0]["строки"]), красные[0]["строки"])
        self.assertFalse(any("нет data-анимация" in с for с in красные[0]["строки"]), "причина тут не анимация")

    def test_в_обычном_прогоне_идёт_ролик(self):
        for п in self.замеры["движется"]["прогоны"]:
            if п.get("режим") == "обычный" and п.get("движок") == "Chromium":
                self.assertTrue(п["ролик_шёл"], п)

    def test_без_анимации_красное_с_причиной(self):
        находки = self.красные("стоит")
        self.assertEqual([н["что"] for н in находки], ["Обложка стоит, когда автозапуск запрещён"])
        строки = находки[0]["строки"]
        self.assertTrue(any("компьютер, Chromium, play() отклонён: два снимка через 1 с одинаковые" in с for с in строки), строки)
        self.assertTrue(any("play() завис" in с for с in строки))
        self.assertTrue(any("нет data-анимация" in с for с in строки), строки)

    def test_avif_не_открылся_берёт_webp(self):
        self.assertEqual(self.красные("только-webp"), [])
        запрет = [п for п in self.замеры["только-webp"]["прогоны"] if п.get("режим") == "отказ"]
        self.assertTrue(запрет and all(any(к.endswith("-anim.webp") for к in п["картинки"]) for п in запрет), запрет)

    def test_мозаика_движется_картинками_рамок(self):
        self.assertEqual(self.красные("мозаика"), [])

    def test_ролик_пошёл_позже_возвращается(self):
        до, после = self.вернулся["до"], self.вернулся["после"]
        self.assertTrue(до["постер"])
        self.assertEqual(до["картинка"], "komp-anim.avif")
        self.assertFalse(после["постер"], "ролик пошёл — постер и картинка уходят")
        self.assertEqual(после["картинка"], "komp-poster.jpg", "картинка вернулась к постеру из разметки")
        self.assertEqual(после["источников"], 1, "источник постера телефона вернулся на место")

    def test_safari_прогнан_или_сказано_почему(self):
        замер = self.замеры["движется"]
        if замер.get("safari") == "проверен":
            self.assertTrue(any(п.get("движок") == "Safari" and "доля" in п for п in замер["прогоны"]))
        else:
            имена = [н["что"] for н in движение.находки(замер, self.папки["движется"])]
            self.assertIn("Движение обложки в Safari не проверено", имена)

    def test_без_ролика_замер_молчит_и_не_тратит_время(self):
        self.assertEqual(движение.находки({"есть": False}), [])
        self.assertEqual(движение.строки_отчёта({"есть": False}), [])

    def test_отчёт_и_снимки(self):
        строки = "\n".join(движение.строки_отчёта(self.замеры["движется"]))
        self.assertIn("## Обложка движется", строки)
        self.assertIn("play() завис: движется картинка", строки)
        self.assertTrue(движение.снимки(self.замеры["движется"]))


class ОстальноеДвижениеПриУменьшенииТесты(unittest.TestCase):
    """При reduce прочие CSS-анимации выключены, а ролик обложки и кнопка звука на месте и видны."""

    def test_парение_гаснет_а_ролик_и_звук_остаются(self):
        from playwright.sync_api import sync_playwright

        import глаза

        стили = "\n".join((БЛОКИ / имя).read_text(encoding="utf-8") for имя in (
            "стили-база.css", "стили-первый-экран.css", "стили-первый-экран-кадр.css", "стили-первый-экран-компьютер.css"))
        страница = (f'<!doctype html><meta charset="utf-8"><style>{стили}</style>'
                    '<span class="парит" id="п">чип</span>'
                    '<figure class="картинка картинка--видео-с-голосом" style="width:200px;height:200px;position:relative">'
                    '<video id="в" muted loop playsinline></video><img id="к" alt="" src="data:image/gif;base64,'
                    'R0lGODlhAQABAAAAACw="></figure><div class="звук-блок" id="з">звук</div>')
        результат = {}
        with sync_playwright() as движок:
            браузер = глаза.запустить_браузер(движок)
            try:
                for режим in ("no-preference", "reduce"):
                    контекст = браузер.new_context(viewport={"width": 1440, "height": 900}, reduced_motion=режим)
                    п = контекст.new_page()
                    п.set_content(страница)
                    результат[режим] = п.evaluate("""() => ({
                      парит: getComputedStyle(document.getElementById('п')).animationName,
                      видео: getComputedStyle(document.getElementById('в')).display,
                      звук: getComputedStyle(document.getElementById('з')).display})""")
                    контекст.close()
            finally:
                браузер.close()
        self.assertNotEqual(результат["no-preference"]["парит"], "none", "без reduce парение должно идти")
        self.assertEqual(результат["reduce"]["парит"], "none", "при reduce парение обязано гаснуть")
        self.assertNotEqual(результат["reduce"]["видео"], "none", "ролик обложки при reduce прятать нельзя")
        self.assertNotEqual(результат["reduce"]["звук"], "none", "кнопка звука при reduce остаётся")


if __name__ == "__main__":
    unittest.main()
