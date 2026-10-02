"""Тесты технической приёмки (`проверить.py --техника`, модуль `техника.py`).

Два слоя. Находки считаются из чисел — их проверяем на подложенных числах, без браузера: так
видно каждый порог. А то, что числа вообще снимаются, — один живой прогон по учебной странице
`фикстуры/сайт-техника/`, где каждая беда сделана нарочно. Страница отдаётся локальным сервером
и проверяется как живой адрес: так заодно проверяется вес по сети. В Google отсюда не ходим —
ответ PageSpeed подменяется.

Запуск из корня репозитория:
    .venv/bin/python -m unittest discover -s ядро/скрипты/tests -t .
"""
import io
import json
import shutil
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

СКРИПТЫ = Path(__file__).resolve().parent.parent
ФИКСТУРЫ = Path(__file__).resolve().parent / "фикстуры"
sys.path.insert(0, str(СКРИПТЫ))

import проверить  # noqa: E402
import техника  # noqa: E402
from находки import ЧИНИТЬ, ПОПРАВИТЬ, К_СВЕДЕНИЮ  # noqa: E402


def по_имени(находки: list[dict], имя: str) -> dict | None:
    return next((н for н in находки if н["что"] == имя), None)


def текст(н: dict) -> str:
    return "\n".join([н.get("чем_грозит", "")] + н["строки"])


def скорость(**поля) -> dict:
    """Замер скорости, как его отдаёт `замерить_скорость`, — с подменой нужных полей."""
    замер = {"lcp_с": 1.2, "первым": {"тег": "img", "адрес": "http://x/img/обложка.webp",
                                       "текст": "", "ленивая": False},
             "cls": 0.0, "сдвигались": [], "загрузка_с": 2.0,
             "скачано": {"всего": 500_000, "файлов": 9,
                         "по_типам": {"картинки": 300_000, "стили": 60_000, "шрифты": 90_000}},
             "шрифты": [], "файлы": [{"адрес": "http://x/img/обложка.webp", "тип": "Image",
                                     "байт": 400_000}]}
    замер.update(поля)
    return замер


class ПорогиСкоростиТесты(unittest.TestCase):
    def test_первый_экран_дольше_четырёх_секунд_красное(self):
        н = по_имени(техника.находки_по_скорости(скорость(lcp_с=5.2), True),
                     "Первый экран появляется долго")
        self.assertEqual(н["уровень"], ЧИНИТЬ)
        self.assertIn("5,2 с", текст(н))
        self.assertIn("половина уйдёт", текст(н))

    def test_первый_экран_от_двух_с_половиной_до_четырёх_жёлтое(self):
        н = по_имени(техника.находки_по_скорости(скорость(lcp_с=3.1), True),
                     "Первый экран появляется долго")
        self.assertEqual(н["уровень"], ПОПРАВИТЬ)

    def test_быстрый_первый_экран_молчит(self):
        находки = техника.находки_по_скорости(скорость(lcp_с=2.0), True)
        self.assertIsNone(по_имени(находки, "Первый экран появляется долго"))
        сводка = по_имени(находки, "Как сайт открывается на телефоне")
        self.assertEqual(сводка["уровень"], К_СВЕДЕНИЮ, "сводка скорости звучит всегда")
        self.assertIn("2,0 с", текст(сводка))

    def test_тяжёлая_картинка_первого_экрана_пережать(self):
        н = по_имени(техника.находки_по_скорости(скорость(lcp_с=4.5), True),
                     "Первый экран появляется долго")
        self.assertIn("картинка.py", текст(н))
        self.assertIn("391 КБ", текст(н), "совет называет вес самой картинки")

    def test_лёгкая_картинка_первого_экрана_виноваты_стили_и_шрифты(self):
        лёгкая = [{"адрес": "http://x/img/обложка.webp", "тип": "Image", "байт": 60_000}]
        н = по_имени(техника.находки_по_скорости(скорость(lcp_с=4.5, файлы=лёгкая), True),
                     "Первый экран появляется долго")
        self.assertIn("сама картинка лёгкая", текст(н))
        self.assertIn("шрифты", текст(н))

    def test_ленивая_картинка_первого_экрана_названа(self):
        первым = {"тег": "img", "адрес": "http://x/img/обложка.webp", "текст": "", "ленивая": True}
        н = по_имени(техника.находки_по_скорости(скорость(lcp_с=3.0, первым=первым), True),
                     "Первый экран появляется долго")
        self.assertIn('loading="lazy"', текст(н))

    def test_прыжки_вёрстки_по_порогам(self):
        for cls, уровень in ((0.3, ЧИНИТЬ), (0.15, ПОПРАВИТЬ), (0.05, None)):
            with self.subTest(cls=cls):
                н = по_имени(техника.находки_по_скорости(
                    скорость(cls=cls, сдвигались=["div.вставка"]), True),
                    "Вёрстка прыгает при загрузке")
                if уровень is None:
                    self.assertIsNone(н)
                else:
                    self.assertEqual(н["уровень"], уровень)
                    self.assertIn("div.вставка", текст(н))

    def test_тяжёлые_шрифты_жёлтое(self):
        шрифты = [{"адрес": f"http://x/ш{и}.woff2", "байт": 80_000} for и in range(5)]
        н = по_имени(техника.находки_по_скорости(скорость(шрифты=шрифты), True),
                     "Шрифты весят много")
        self.assertEqual(н["уровень"], ПОПРАВИТЬ)
        self.assertIn("5 файлов", текст(н))

    def test_замер_не_вышел_честная_сводка(self):
        [н] = техника.находки_по_скорости({"не_вышло": "TimeoutError: 90 с"}, True)
        self.assertEqual((н["уровень"], н["что"]), (К_СВЕДЕНИЮ, "Скорость не замерена"))

    def test_папка_честно_говорит_про_сервер_под_боком(self):
        сводка = по_имени(техника.находки_по_скорости(скорость(), False),
                          "Как сайт открывается на телефоне")
        self.assertIn("живому адресу", текст(сводка))


class ЭкраныИSafariТесты(unittest.TestCase):
    def экран(self, **поля) -> dict:
        у = {"статус": "ок", "прокрутка_вбок": {"есть": False}, "вылезающие_картинки": [],
             "мелкий_текст": {"минимум_px": 16, "элементов_мельче_порога": 0}}
        у.update(поля)
        return у

    def test_ездит_вбок_на_маленьком_телефоне_красное(self):
        экраны = {"телефон-360": self.экран(прокрутка_вбок={"есть": True, "ширина_страницы": 370,
                                                             "ширина_экрана": 360})}
        н = по_имени(техника.находки_по_экранам(экраны), "На других экранах вёрстка ломается")
        self.assertEqual(н["уровень"], ЧИНИТЬ)
        self.assertIn("маленький телефон 360", текст(н))

    def test_safari_не_открыл_это_поломка(self):
        экраны = {техника.SAFARI: {"статус": "ошибка",
                                   "не_пустило": {"вид": "ошибка", "признак": "сбой движка"}}}
        н = по_имени(техника.находки_по_экранам(экраны), "На других экранах вёрстка ломается")
        self.assertIn("iPhone в Safari", текст(н))

    def test_мелкий_текст_главного_телефона_не_повторяем(self):
        телефон = {"мелкий_текст": {"минимум_px": 12, "элементов_мельче_порога": 2}}
        тот_же = {"планшет": self.экран(мелкий_текст={"минимум_px": 12, "элементов_мельче_порога": 2})}
        self.assertIsNone(по_имени(техника.находки_по_экранам(тот_же, телефон),
                                   "На других экранах есть текст мельче 13 px"))
        хуже = {"телефон-360": self.экран(мелкий_текст={"минимум_px": 11, "элементов_мельче_порога": 5})}
        н = по_имени(техника.находки_по_экранам(хуже, телефон),
                     "На других экранах есть текст мельче 13 px")
        self.assertEqual(н["уровень"], ПОПРАВИТЬ)

    def test_нет_webkit_это_сведение_с_командой(self):
        class БезWebkit:
            class webkit:
                @staticmethod
                def launch(**_):
                    raise RuntimeError("Executable doesn't exist at /нет/webkit")

        итог = техника.снять_safari(БезWebkit(), "http://x/", Path(tempfile.gettempdir()), 0.1)
        self.assertEqual(итог["статус"], "нет_движка")
        н = по_имени(техника.находки_по_экранам({техника.SAFARI: итог}), "Safari не проверен")
        self.assertEqual(н["уровень"], К_СВЕДЕНИЮ)
        self.assertIn(техника.ПОСТАВИТЬ_SAFARI, текст(н))


ОТВЕТ_GOOGLE = {
    "lighthouseResult": {
        "categories": {"performance": {"score": 0.37}},
        "audits": {"largest-contentful-paint": {"numericValue": 6120.0},
                   "cumulative-layout-shift": {"numericValue": 0.02},
                   "total-byte-weight": {"numericValue": 2_400_000}},
    },
    "loadingExperience": {"metrics": {"LARGEST_CONTENTFUL_PAINT_MS": {"percentile": 3400}}},
}


class GoogleТесты(unittest.TestCase):
    def test_ответ_разбирается_в_числа(self):
        разбор = техника.разобрать_google(ОТВЕТ_GOOGLE)
        self.assertEqual(разбор["оценка"], 37)
        self.assertEqual(разбор["lcp_с"], 6.1)
        self.assertEqual(разбор["живые_люди"], {"lcp_с": 3.4})

    def test_низкая_оценка_жёлтое_плюс_сведение(self):
        находки = техника.находки_по_google(техника.разобрать_google(ОТВЕТ_GOOGLE), True)
        self.assertEqual(по_имени(находки, "Оценка скорости от Google низкая")["уровень"], ПОПРАВИТЬ)
        self.assertIn("37 из 100", текст(по_имени(находки, "Оценка Google PageSpeed")))

    def test_лимит_без_ключа_это_сведение_а_не_падение(self):
        ошибка = urllib.error.HTTPError("https://x", 429, "Too Many Requests", {}, io.BytesIO(b"{}"))
        with patch.object(техника.urllib.request, "urlopen", side_effect=ошибка):
            ответ = техника.спросить_google("https://пример.рф/")
        [н] = техника.находки_по_google(ответ, True)
        self.assertEqual((н["уровень"], н["что"]), (К_СВЕДЕНИЮ, "PageSpeed не ответил"))
        self.assertIn("лимит", текст(н))
        self.assertIn("pagespeed.web.dev", текст(н))

    def test_нет_сети_это_сведение(self):
        with patch.object(техника.urllib.request, "urlopen", side_effect=OSError("нет сети")):
            ответ = техника.спросить_google("https://пример.рф/")
        self.assertIn("не достучались", ответ["не_вышло"])

    def test_папку_google_не_спрашиваем(self):
        self.assertEqual(техника.находки_по_google(None, False), [])


class ВесПоСетиТесты(unittest.TestCase):
    def test_живой_адрес_вес_по_сети(self):
        сеть = [{"адрес": "https://x/img/обложка.jpg", "тип": "image", "байт": 1_500_000},
                {"адрес": "https://x/img/работа.jpg", "тип": "image", "байт": 400_000},
                {"адрес": "https://x/app.js", "тип": "script", "байт": 1_400_000}]
        находки = проверить.находки_по_весу_сети(сеть)
        self.assertEqual(по_имени(находки, "Тяжёлые картинки")["уровень"], ЧИНИТЬ)
        self.assertIn("обложка.jpg", текст(по_имени(находки, "Тяжёлые картинки")))
        self.assertIn("по сети", текст(по_имени(находки, "Картинки, которые стоит сжать")))
        self.assertIn("3,1 МБ", текст(по_имени(находки, "Страница весит много")))

    def test_лёгкая_страница_молчит(self):
        self.assertEqual(проверить.находки_по_весу_сети(
            [{"адрес": "https://x/i.webp", "тип": "image", "байт": 90_000}]), [])


class ТехприёмкаВживуюТесты(unittest.TestCase):
    """Один прогон по учебной странице как по живому адресу: числа снимаются, беды находятся."""

    @classmethod
    def setUpClass(cls):
        from PIL import Image
        from playwright.sync_api import sync_playwright

        cls._временная = tempfile.TemporaryDirectory()
        корень = Path(cls._временная.name)
        сайт = корень / "сайт"
        shutil.copytree(ФИКСТУРЫ / "сайт-техника", сайт)
        (сайт / "img").mkdir()
        # Картинки рисуем здесь, а не храним в репозитории: одноцветные, лёгкие, нужного размера.
        Image.new("RGB", (3000, 1500), (40, 90, 140)).save(сайт / "img" / "большая.png")
        Image.new("RGB", (1500, 60), (200, 170, 120)).save(сайт / "img" / "полоса.png")
        Image.new("RGB", (400, 300), (90, 140, 60)).save(сайт / "img" / "ниже.png")

        cls._playwright = sync_playwright().start()
        cls.браузер = проверить.глаза.запустить_браузер(cls._playwright)
        with patch.object(техника, "спросить_google", return_value=техника.разобрать_google(ОТВЕТ_GOOGLE)), \
                проверить.локальный_сервер(сайт) as адрес:
            cls.итог = проверить.проверить(None, корень / "проверка", адрес=адрес,
                                           браузер=cls.браузер, ждать_сек=0.2,
                                           техприёмка=True, движок=cls._playwright)
        cls.находки = cls.итог["находки"]

    @classmethod
    def tearDownClass(cls):
        cls.браузер.close()
        cls._playwright.stop()
        cls._временная.cleanup()

    def test_картинка_крупнее_показа(self):
        н = по_имени(self.находки, "Картинка крупнее, чем показывается")
        self.assertEqual(н["уровень"], ПОПРАВИТЬ)
        self.assertIn("«большая.png» — в файле 3000 px", текст(н))
        self.assertNotIn("ниже.png", текст(н))

    def test_ленивая_загрузка_в_обе_стороны(self):
        н = по_имени(self.находки, "Ленивая загрузка не там, где нужно")
        self.assertIn("«ниже.png» ниже первого экрана", текст(н))
        self.assertIn("«большая.png» на первом экране", текст(н))

    def test_без_размеров_только_та_что_без_размеров(self):
        н = по_имени(self.находки, "Картинки без размеров")
        self.assertIn("ниже.png", текст(н))
        self.assertNotIn("большая.png", текст(н))
        self.assertNotIn("полоса.png", текст(н))

    def test_маленький_телефон_ездит_вбок_а_обрезанная_рамкой_картинка_не_беда(self):
        н = по_имени(self.находки, "На других экранах вёрстка ломается")
        self.assertEqual(н["уровень"], ЧИНИТЬ)
        self.assertIn("маленький телефон 360", текст(н))
        self.assertNotIn("ноутбук", текст(н))
        self.assertNotIn("полоса.png", текст(н), "кадр в рамке с overflow: hidden не вылезает")

    def test_вёрстка_прыгает(self):
        н = по_имени(self.находки, "Вёрстка прыгает при загрузке")
        self.assertIsNotNone(н, "поздняя вставка сверху обязана сдвинуть вёрстку")
        self.assertIn(н["уровень"], (ЧИНИТЬ, ПОПРАВИТЬ))

    def test_сводка_скорости_и_вес_по_сети(self):
        сводка = по_имени(self.находки, "Как сайт открывается на телефоне")
        self.assertIn("первый экран показался через", текст(сводка))
        сеть = self.итог["разметка"]["сеть"]
        self.assertTrue(any(з["тип"] == "image" and з["байт"] > 0 for з in сеть),
                        "по живому адресу вес картинок считается по сети")

    def test_google_в_отчёте(self):
        self.assertIsNotNone(по_имени(self.находки, "Оценка скорости от Google низкая"))

    def test_снимки_дополнительных_экранов_рядом_с_отчётом(self):
        куда = self.итог["куда"]
        for размер in техника.ДОП_ЭКРАНЫ:
            with self.subTest(размер=размер):
                self.assertTrue((куда / f"{размер}.png").is_file())
        self.assertIn("## Техника: ещё пять экранов", self.итог["отчёт"])
        safari = self.итог["замеры"]["техника"]["экраны"][техника.SAFARI]
        if safari.get("статус") == "нет_движка":
            self.assertIsNotNone(по_имени(self.находки, "Safari не проверен"))
        else:
            self.assertTrue((куда / f"{техника.SAFARI}.png").is_file())
        json.loads((куда / "замеры.json").read_text(encoding="utf-8"))


class ПлощадкаСЧужимиСкриптамиТесты(unittest.TestCase):
    """Страница на площадке (GetCourse, Тильда) тянет чужие скрипты — счётчики, чаты, проверки, —
    и какой-нибудь из них не отвечает вовсе: событие «загрузилась» не наступает минутами, хотя
    сама страница давно на экране. Техприёмка по такому адресу не имеет права упасть или
    объявить страницу неоткрывшейся: мерим то, что открылось, а про висящее говорим ℹ️."""

    ВИСИТ_СЕК = 20

    @classmethod
    def setUpClass(cls):
        import http.server
        import threading
        import time
        from functools import partial
        from playwright.sync_api import sync_playwright

        cls._временная = tempfile.TemporaryDirectory()
        корень = Path(cls._временная.name)
        сайт = корень / "сайт"
        сайт.mkdir()
        висит = cls.ВИСИТ_СЕК

        class Площадка(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *аргументы):
                pass

            def do_GET(self):
                if self.path.startswith("/vendor/"):
                    time.sleep(висит)          # чужой скрипт площадки, который не отвечает
                    try:
                        self.send_response(204)
                        self.end_headers()
                    except OSError:
                        pass
                    return
                super().do_GET()

        cls._сервер = http.server.ThreadingHTTPServer(("127.0.0.1", 0), partial(Площадка, directory=str(сайт)))
        cls._сервер.daemon_threads = True
        threading.Thread(target=cls._сервер.serve_forever, daemon=True).start()
        порт = cls._сервер.server_port
        (сайт / "index.html").write_text(
            "<!DOCTYPE html><html lang=\"ru\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            "<meta name=\"robots\" content=\"noindex\">"
            "<title>Страница на площадке</title>"
            f"<script async src=\"http://127.0.0.1:{порт}/vendor/counter.js\"></script>"
            "<style>body{margin:0;font:18px/1.5 Arial,sans-serif;color:#1a1a1a;background:#fff}"
            ".блок{padding:40px 16px}</style></head><body>"
            "<section class=\"блок\"><h1>Мастерская у реки</h1><p>Чиним лодки и делаем вёсла.</p></section>"
            f"<script>setInterval(function(){{fetch('http://127.0.0.1:{порт}/vendor/ping').catch(function(){{}})}}, 300);"
            "</script></body></html>", encoding="utf-8")

        cls._playwright = sync_playwright().start()
        cls.браузер = проверить.глаза.запустить_браузер(cls._playwright)
        with patch.object(проверить.глаза, "ТАЙМАУТ_ЗАГРУЗКИ_МС", 3000), \
                patch.object(проверить.глаза, "ТАЙМАУТ_ТИШИНЫ_МС", 500), \
                patch.object(техника, "ТАЙМАУТ_МЕДЛЕННОЙ_ЗАГРУЗКИ_МС", 4000), \
                patch.object(техника, "ТАЙМАУТ_ТИШИНЫ_МС", 500), \
                patch.object(техника, "спросить_google", return_value=техника.разобрать_google(ОТВЕТ_GOOGLE)):
            cls.итог = проверить.проверить(None, корень / "проверка", адрес=f"http://127.0.0.1:{порт}/",
                                           браузер=cls.браузер, ждать_сек=0.2,
                                           техприёмка=True, движок=None)
        cls.находки = cls.итог["находки"]

    @classmethod
    def tearDownClass(cls):
        cls.браузер.close()
        cls._playwright.stop()
        cls._сервер.shutdown()
        cls._сервер.server_close()
        cls._временная.cleanup()

    def test_страница_считается_открывшейся(self):
        for н in self.находки:
            self.assertFalse(н["что"].startswith("Страница не открылась"), н)
        self.assertIsNone(по_имени(self.находки, "Разметку прочитать не вышло"),
                          "висящий чужой скрипт не повод бросать разбор разметки")

    def test_висящее_это_сведение_а_не_красное(self):
        красные = [н["что"] for н in self.находки if н["уровень"] == ЧИНИТЬ]
        self.assertEqual(красные, [], красные)

    def test_скорость_замерена_и_честная_оговорка(self):
        сводка = по_имени(self.находки, "Как сайт открывается на телефоне")
        self.assertIsNotNone(сводка, "первый экран на экране — значит, его можно измерить")
        self.assertEqual(сводка["уровень"], К_СВЕДЕНИЮ)
        self.assertIn("чужие скрипты", текст(сводка))


class ЖиваяГоловаТесты(unittest.TestCase):
    """Консоль и несуществующий адрес: находки считаются из чисел, браузера не нужно."""

    def test_ошибка_консоли_это_жёлтое(self):
        [н] = техника.находки_по_живой_голове(
            {"ошибки_консоли": ["Uncaught ReferenceError: x is not defined"], "код_несуществующего": 404})
        self.assertEqual((н["что"], н["уровень"]), ("Страница ругается в консоли браузера", ПОПРАВИТЬ))

    def test_ответ_200_на_несуществующий_адрес_это_жёлтое(self):
        [н] = техника.находки_по_живой_голове(
            {"ошибки_консоли": [], "код_несуществующего": 200, "несуществующий_адрес": "https://x/нет"})
        self.assertEqual((н["что"], н["уровень"]), ("Несуществующий адрес не отвечает 404", ПОПРАВИТЬ))
        self.assertIn("200", текст(н))

    def test_чисто_и_404_молчат(self):
        self.assertEqual(техника.находки_по_живой_голове(
            {"ошибки_консоли": [], "код_несуществующего": 404}), [])

    def test_замер_не_вышел_молчим(self):
        self.assertEqual(техника.находки_по_живой_голове({"не_вышло": "TimeoutError"}), [])
        self.assertEqual(техника.находки_по_живой_голове(None), [])

    def test_локально_эти_находки_не_зовутся(self):
        голова = {"ошибки_консоли": ["ошибка"], "код_несуществующего": 200}
        итог = техника.находки({"живой": False, "живая_голова": голова})
        self.assertIsNone(по_имени(итог, "Страница ругается в консоли браузера"))
        self.assertIsNone(по_имени(итог, "Несуществующий адрес не отвечает 404"))


if __name__ == "__main__":
    unittest.main()
