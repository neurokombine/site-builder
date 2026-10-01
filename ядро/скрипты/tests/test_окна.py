"""Обложка в первом экране (`окна.py`) и ролик обложки (`обложка.js`).

Две учебные страницы рядом: обложка, которая влезает в каждое окно набора, и та, что не влезает
(высокая секция на компьютере, кнопка под кромкой на телефоне, полоса шире окна). Страницы
собираются здесь же, во временной папке, — в интернет не ходим. Ролик проверяем с подменённым
`play()`: автозапуск отклонён — виден постер того же ролика, первое касание запускает его.

Запуск из корня репозитория:
    .venv/bin/python -m unittest discover -s ядро/скрипты/tests -t .
"""
import sys
import tempfile
import unittest
from pathlib import Path

СКРИПТЫ = Path(__file__).resolve().parent.parent
БЛОКИ = СКРИПТЫ.parent / "блоки"
sys.path.insert(0, str(СКРИПТЫ))

import глаза  # noqa: E402
import окна  # noqa: E402
import проверить  # noqa: E402
from находки import ЧИНИТЬ  # noqa: E402

ОБЛОЖКА = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><style>
body {{ margin: 0; font: 16px/1.4 sans-serif; }}
.блок--первый-экран {{ position: relative; overflow: hidden; min-height: 100vh; box-sizing: border-box; padding: 1rem; }}
.первый-экран__картинка {{ position: absolute; inset: 0; margin: 0; z-index: -1; }}
.первый-экран__картинка img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
.шапка {{ height: 3rem; }}  h1 {{ margin: 0 0 1rem; }}  .кнопка {{ display: inline-block; padding: .8rem 1.5rem; }}
{свои}
</style></head><body>
<section class="блок блок--первый-экран" id="экран-1" data-тип="первый-экран" data-схема="сцена">
  <header class="шапка">Знак дела</header>
  <figure class="картинка первый-экран__картинка"><img src="кадр.svg" alt="кадр"></figure>
  <div class="первый-экран__текст">
    <h1>Заголовок обложки</h1><p class="лид">Лид в одну строку</p>
    <div class="первый-экран__действие"><a class="кнопка кнопка--главная" href="#экран-2">Оставить заявку</a></div>
    <p class="первый-экран__доверие">Лицензия № …</p>
  </div>
</section>
<section class="блок" id="экран-2"><p>Дальше</p></section>
</body></html>"""
КАДР = '<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900"><rect width="1600" height="900" fill="gray"/></svg>'
ВЛЕЗАЕТ = ""
# Высокий лид толкает кнопку и строку доверия под кромку любого окна; полоса шире окна — прокрутка вбок.
НЕ_ВЛЕЗАЕТ = ".лид { height: 70rem; }  #экран-2 { width: 150vw; }"


class ОбложкаВОкнеТесты(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright

        cls._playwright = sync_playwright().start()
        cls.браузер = глаза.запустить_браузер(cls._playwright)
        cls._временная = tempfile.TemporaryDirectory()
        cls.корень = Path(cls._временная.name)
        for имя, свои in (("влезает", ВЛЕЗАЕТ), ("не-влезает", НЕ_ВЛЕЗАЕТ)):
            папка = cls.корень / имя
            папка.mkdir()
            (папка / "index.html").write_text(ОБЛОЖКА.format(свои=свои), encoding="utf-8")
            (папка / "кадр.svg").write_text(КАДР, encoding="utf-8")
        cls.замеры = {}
        with проверить.локальный_сервер(cls.корень) as адрес:
            for имя in ("влезает", "не-влезает"):
                cls.замеры[имя] = окна.снять(cls.браузер, адрес + имя + "/index.html", cls.корень / f"снимки-{имя}")

    @classmethod
    def tearDownClass(cls):
        cls.браузер.close()
        cls._playwright.stop()
        cls._временная.cleanup()

    def test_снято_каждое_окно_набора(self):
        замер = self.замеры["влезает"]
        self.assertEqual(set(замер["компьютер"]), {имя for имя, *_ in окна.ОКНА_КОМПЬЮТЕРА})
        self.assertEqual(set(замер["телефон"]), {имя for имя, *_ in окна.ОКНА_ТЕЛЕФОНА})
        for имя, ширина, высота in окна.ОКНА_ТЕЛЕФОНА:
            self.assertEqual(замер["телефон"][имя]["высота_окна"], высота, имя)
        self.assertEqual(len(окна.снимки(замер)), len(окна.ОКНА_КОМПЬЮТЕРА) + len(окна.ОКНА_ТЕЛЕФОНА))

    def test_влезает_молчит(self):
        self.assertEqual(окна.находки(self.замеры["влезает"]), [])

    def test_не_влезает_три_красных_с_именем_окна(self):
        находки = {н["что"]: н for н in окна.находки(self.замеры["не-влезает"])}
        комп = находки["Обложка не помещается в окно компьютера"]
        тел = находки["Главная кнопка на телефоне ниже первого экрана"]
        вбок = находки["На окнах набора страница ездит вбок"]
        for н in (комп, тел, вбок):
            self.assertEqual(н["уровень"], ЧИНИТЬ)
        self.assertTrue(any(с.startswith("1366 × 625: строка доверия ниже окна на") for с in комп["строки"]), комп["строки"])
        self.assertTrue(any("iPhone SE 375 × 548: «Оставить заявку» ниже окна на" in с for с in тел["строки"]))
        self.assertEqual(len(вбок["строки"]), len(окна.ОКНА_КОМПЬЮТЕРА) + len(окна.ОКНА_ТЕЛЕФОНА))

    def test_окно_ниже_порога_и_уже_брейкпоинта_не_судим(self):
        высокое = {"есть": True, "высота_окна": 560, "ширина_окна": 1280, "ширина_страницы": 1280,
                   "низ_значимого": 900, "низ_кадра": 900}
        узкое = dict(высокое, высота_окна=700, ширина_окна=800, ширина_страницы=800)
        self.assertEqual(окна.находки({"компьютер": {"низко": высокое, "узко": узкое}}), [])

    def test_срезанное_рамкой_тоже_вылезло(self):
        замер = {"есть": True, "высота_окна": 600, "ширина_окна": 1280, "ширина_страницы": 1280,
                 "низ_значимого": 580, "низ_кадра": 600, "срезано_px": 40, "что_срезано": ".первый-экран__действие"}
        н = окна.находки({"компьютер": {"1280 × 600": замер}})
        self.assertEqual(н[0]["строки"], ["1280 × 600: кнопки срезано своей рамкой на 40 px"])

    def test_отчёт_с_числами(self):
        строки = окна.строки_отчёта(self.замеры["влезает"])
        self.assertIn("## Обложка в первом экране", строки)
        self.assertTrue(any(с.startswith("- iPhone 14 390 × 664: низ кнопки") for с in строки))


РОЛИК = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<style>.картинка--постер video {{ display: none; }} .картинка img {{ width: 100px; }}</style></head><body>
<figure class="картинка картинка--видео картинка--постер первый-экран__картинка"><video muted loop playsinline preload="none"
 data-ролик-компьютер="комп.mp4" data-постер-компьютер="комп.jpg" data-ролик-телефон="тел.mp4" data-постер-телефон="тел.jpg"></video>
<picture><source media="(max-width: 899px)" srcset="тел.jpg"><img src="комп.jpg" alt=""></picture></figure>
<div style="height: 300vh"></div>
<script>{скрипт}</script></body></html>"""
# play() отклоняет первый вызов (как встроенный браузер мессенджера) и принимает следующие.
ПОДМЕНА_PLAY = """window.__вызовов = 0;
HTMLMediaElement.prototype.play = function () { window.__вызовов += 1;
  return window.__вызовов === 1 ? Promise.reject(new DOMException("запрещено", "NotAllowedError")) : Promise.resolve(); };"""


class РоликОбложкиТесты(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright

        cls._playwright = sync_playwright().start()
        cls.браузер = глаза.запустить_браузер(cls._playwright)
        cls._временная = tempfile.TemporaryDirectory()
        папка = Path(cls._временная.name)
        скрипт = (БЛОКИ / "обложка.js").read_text(encoding="utf-8")
        (папка / "index.html").write_text(РОЛИК.format(скрипт=скрипт), encoding="utf-8")
        cls.итог = {}
        with проверить.локальный_сервер(папка) as адрес:
            for вид, окно in (("компьютер", {"width": 1280, "height": 800}), ("телефон", {"width": 390, "height": 664})):
                контекст = cls.браузер.new_context(viewport=окно, is_mobile=вид == "телефон", has_touch=вид == "телефон")
                контекст.add_init_script(ПОДМЕНА_PLAY)
                страница = контекст.new_page()
                запросы = []
                страница.on("request", lambda з, запросы=запросы: запросы.append(з.url))
                страница.goto(адрес + "index.html")
                страница.wait_for_timeout(300)
                до = страница.evaluate("""() => { const в = document.querySelector('video'), ф = в.closest('figure');
                  return {постер: в.getAttribute('poster'), src: в.getAttribute('src'), ждёт: ф.classList.contains('картинка--постер'),
                          вызовов: window.__вызовов}; }""")
                страница.mouse.wheel(0, 400)
                страница.wait_for_timeout(300)
                после = страница.evaluate("""() => ({ждёт: document.querySelector('figure').classList.contains('картинка--постер'),
                                                     вызовов: window.__вызовов})""")
                cls.итог[вид] = {"до": до, "после": после, "запросы": " ".join(запросы)}
                контекст.close()

    @classmethod
    def tearDownClass(cls):
        cls.браузер.close()
        cls._playwright.stop()
        cls._временная.cleanup()

    def test_каждый_размер_берёт_свой_ролик(self):
        self.assertTrue(self.итог["компьютер"]["до"]["src"].endswith("комп.mp4"))
        self.assertTrue(self.итог["телефон"]["до"]["src"].endswith("тел.mp4"))
        self.assertNotIn("%D1%82%D0%B5%D0%BB.mp4", self.итог["компьютер"]["запросы"], "компьютер качал телефонный ролик")
        self.assertNotIn("%D0%BA%D0%BE%D0%BC%D0%BF.mp4", self.итог["телефон"]["запросы"], "телефон качал компьютерный ролик")

    def test_отказ_автозапуска_оставляет_постер_того_же_ролика(self):
        for вид, постер in (("компьютер", "комп.jpg"), ("телефон", "тел.jpg")):
            до = self.итог[вид]["до"]
            self.assertTrue(до["постер"].endswith(постер), вид)
            self.assertTrue(до["ждёт"], f"{вид}: после отказа play() должен стоять постер")
            self.assertEqual(до["вызовов"], 1)

    def test_первая_прокрутка_запускает_ролик(self):
        for вид in ("компьютер", "телефон"):
            после = self.итог[вид]["после"]
            self.assertEqual(после["вызовов"], 2, вид)
            self.assertFalse(после["ждёт"], f"{вид}: ролик пошёл — постер снят")


if __name__ == "__main__":
    unittest.main()
