"""Кисть: разбор ответов ChatGPT, диагностика входа, замок, поиск Chrome.

Живой браузер здесь не поднимается и в интернет тесты не ходят: проверяем ровно ту логику,
на которой система принимает решения — что считать нарисованной картинкой, когда она готова,
вошли мы или нет, свой это браузер или чужой, и не завёлся ли где-нибудь путь через API.
"""
import contextlib
import io
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

СКРИПТЫ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(СКРИПТЫ))
import кисть  # noqa: E402


def снимок(src="https://files.oaiusercontent.com/a.png", w=1024, h=1024,
           inForm=False, inUser=False):
    return {"src": src, "naturalWidth": w, "naturalHeight": h,
            "inForm": inForm, "inUser": inUser}


class КартинкиЛенты(unittest.TestCase):
    def test_нормальная_годится(self):
        self.assertTrue(кисть.картинка_ленты_годится(снимок()))

    def test_мелкая_не_годится(self):
        # Значки и миниатюры в ленту не считаем: порог — больше 500 px по обеим сторонам.
        # (Иконки сайдбара ровно 512×512 порог проходят — их отсекает сам зонд: он смотрит
        # только внутрь <main>, а сайдбар вне его.)
        self.assertFalse(кисть.картинка_ленты_годится(снимок(w=480, h=1024)))
        self.assertFalse(кисть.картинка_ленты_годится(снимок(w=1024, h=500)))

    def test_аватар_не_годится(self):
        self.assertFalse(кисть.картинка_ленты_годится(снимок(src="https://x/avatar-1.png")))

    def test_blob_не_годится(self):
        # blob: — превью вложения в композере, а не ответ.
        self.assertFalse(кисть.картинка_ленты_годится(снимок(src="blob:https://chatgpt.com/1")))

    def test_внутри_формы_не_годится(self):
        self.assertFalse(кисть.картинка_ленты_годится(снимок(inForm=True)))

    def test_наше_вложение_в_реплике_человека_не_годится(self):
        # Главная защита от «на диск уехал приложенный референс вместо нарисованного кадра».
        self.assertFalse(кисть.картинка_ленты_годится(снимок(inUser=True)))

    def test_пустое_и_без_адреса(self):
        self.assertFalse(кисть.картинка_ленты_годится(None))
        self.assertFalse(кисть.картинка_ленты_годится({"src": ""}))
        self.assertFalse(кисть.картинка_ленты_годится({"src": "https://x/a.png"}))  # нет размеров

    def test_адреса_по_порядку_без_повторов(self):
        снимки = [снимок(src="https://x/1.png"), снимок(src="https://x/2.png"),
                  снимок(src="https://x/1.png"), снимок(src="blob:zz"),
                  снимок(src="https://x/3.png", inUser=True)]
        self.assertEqual(кисть.адреса_ленты(снимки), ["https://x/1.png", "https://x/2.png"])

    def test_пустой_вход(self):
        self.assertEqual(кисть.адреса_ленты(None), [])


class ГотовностьКартинки(unittest.TestCase):
    def шаг(self, состояние, адреса, цель, время):
        return кисть.шаг_готовности(состояние, {"адреса": адреса, "цель": цель,
                                                "прошло_мс": время, "сейчас": время})

    def test_картинок_ещё_мало(self):
        итог = self.шаг(None, [], 1, 60_000)
        self.assertFalse(итог["готово"])

    def test_рано_даже_если_картинка_есть(self):
        # Раньше минимального ожидания «готово» не бывает — бывает недорисованное.
        итог = self.шаг(None, ["https://x/1.png"], 1, 5_000)
        self.assertFalse(итог["готово"])

    def test_новый_адрес_становится_кандидатом(self):
        итог = self.шаг(None, ["https://x/1.png"], 1, 40_000)
        self.assertFalse(итог["готово"])
        self.assertEqual(итог["состояние"]["кандидат"], "https://x/1.png")
        self.assertEqual(итог["состояние"]["кандидат_с"], 40_000)

    def test_адрес_постоял_и_готово(self):
        первый = self.шаг(None, ["https://x/1.png"], 1, 40_000)
        второй = self.шаг(первый["состояние"], ["https://x/1.png"], 1, 55_000)
        self.assertTrue(второй["готово"])
        self.assertEqual(второй["адрес"], "https://x/1.png")

    def test_адрес_сменился_отсчёт_заново(self):
        первый = self.шаг(None, ["https://x/1.png"], 1, 40_000)
        второй = self.шаг(первый["состояние"], ["https://x/1.png", "https://x/2.png"], 1, 45_000)
        self.assertFalse(второй["готово"])
        self.assertEqual(второй["состояние"]["кандидат"], "https://x/2.png")
        третий = self.шаг(второй["состояние"], ["https://x/1.png", "https://x/2.png"], 1, 60_000)
        self.assertTrue(третий["готово"])
        self.assertEqual(третий["адрес"], "https://x/2.png")

    def test_ждём_две_картинки_а_есть_одна(self):
        self.assertFalse(self.шаг(None, ["https://x/1.png"], 2, 90_000)["готово"])


class СвободаКомпозера(unittest.TestCase):
    def test_снимок_не_прочитался(self):
        self.assertFalse(кисть.композер_свободен(None))
        self.assertFalse(кисть.композер_свободен("что-то не то"))

    def test_страница_ещё_не_готова(self):
        self.assertFalse(кисть.композер_свободен({"composer": False, "stop": 0, "streaming": 0}))

    def test_ответ_пишется(self):
        self.assertFalse(кисть.композер_свободен({"composer": True, "stop": 1, "streaming": 0}))
        self.assertFalse(кисть.композер_свободен({"composer": True, "stop": 0, "streaming": 1}))

    def test_свободен(self):
        # Пустой композер с погашенной кнопкой отправки — это свободное состояние.
        self.assertTrue(кисть.композер_свободен(
            {"composer": True, "stop": 0, "streaming": 0, "send": 1, "sendDisabled": True}))


class СостояниеВхода(unittest.TestCase):
    def test_вошли(self):
        что = кисть.разобрать_состояние({"композер": 1, "кнопки_входа": 0, "заголовок": "ChatGPT"})
        self.assertEqual(что["вход"], "есть")

    def test_не_вошли(self):
        что = кисть.разобрать_состояние({"композер": 0, "кнопки_входа": 2, "заголовок": "ChatGPT"})
        self.assertEqual(что["вход"], "нет")

    def test_молчат_оба_признака_говорим_непонятно(self):
        # Ложный вызов «войдите заново» стоит доверия — лучше честное «непонятно».
        что = кисть.разобрать_состояние({"композер": 0, "кнопки_входа": 0, "заголовок": "Just a moment"})
        self.assertEqual(что["вход"], "непонятно")
        self.assertIn("повторить позже", что["подсказка"])

    def test_кнопка_входа_главнее_поля_для_вопроса(self):
        # chatgpt.com показывает поле для вопроса и НЕ вошедшему: само по себе оно ничего
        # не доказывает, а «Войти» на странице вошедшего человека не висит.
        что = кисть.разобрать_состояние({"композер": 1, "кнопки_входа": 1, "заголовок": ""})
        self.assertEqual(что["вход"], "нет")

    def test_заголовок_обрезается(self):
        что = кисть.разобрать_состояние({"композер": 1, "заголовок": "я" * 200})
        self.assertEqual(len(что["заголовок"]), 80)


class ЧужиеИСвоиБраузеры(unittest.TestCase):
    def test_разбор_строк_запуска(self):
        строки = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome "
            "--remote-debugging-port=9500 --user-data-dir=/тут/браузер/профиль-chatgpt --no-first-run",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome "
            "--remote-debugging-port=9222 --user-data-dir=/цех/auth/chrome-auto-profile",
            "лишняя строка без порта",
        ]
        self.assertEqual(кисть.разобрать_порты(строки),
                         {9500: "профиль-chatgpt", 9222: "chrome-auto-profile"})

    def test_дочерние_процессы_не_считаются(self):
        строки = ["chrome --type=renderer --remote-debugging-port=9500 --user-data-dir=/a/чужой"]
        self.assertEqual(кисть.разобрать_порты(строки), {})

    def test_путь_в_кавычках_и_обратными_слешами(self):
        строки = ['chrome.exe --remote-debugging-port=9501 '
                  '--user-data-dir="C:\\Users\\Аня\\site-builder\\браузер\\профиль-chatgpt"']
        self.assertEqual(кисть.разобрать_порты(строки), {9501: "профиль-chatgpt"})

    def test_к_чужому_профилю_не_подключаемся(self):
        # ⚠️ Порт живой, но его держит «Визуальный цех» — своим он не считается.
        порт = кисть.наш_живой_порт(порты=(9500,), живой=lambda п: True,
                                    команды=lambda: ["chrome --remote-debugging-port=9500 "
                                                     "--user-data-dir=/цех/chrome-auto-profile"])
        self.assertIsNone(порт)

    def test_свой_живой_порт_находится(self):
        порт = кисть.наш_живой_порт(порты=(9500, 9501), живой=lambda п: п == 9501,
                                    команды=lambda: ["chrome --remote-debugging-port=9501 "
                                                     "--user-data-dir=/тут/профиль-chatgpt"])
        self.assertEqual(порт, 9501)

    def test_запомненный_порт_проверяется_первым(self):
        спрошено = []

        def живой(п):
            спрошено.append(п)
            return True

        команды = lambda: ["chrome --remote-debugging-port=9500 --user-data-dir=/a/профиль-chatgpt",
                           "chrome --remote-debugging-port=9503 --user-data-dir=/a/профиль-chatgpt"]
        self.assertEqual(кисть.наш_живой_порт(живой=живой, команды=команды, запомненный=9503), 9503)
        self.assertEqual(спрошено[0], 9503)

    def test_свободный_порт(self):
        self.assertEqual(кисть.свободный_порт((9500, 9501), живой=lambda п: п == 9500), 9501)

    def test_все_порты_заняты_говорим_что_делать(self):
        with self.assertRaises(кисть.БедаКисти) as беда:
            кисть.свободный_порт((9500, 9501), живой=lambda п: True)
        self.assertIn("закройте лишние окна", str(беда.exception).lower())


class ГдеChrome(unittest.TestCase):
    def test_переменная_перебивает_поиск(self):
        # Ручка старше списка кандидатов — но только если по её пути действительно есть файл.
        путь = кисть.найти_chrome(платформа="linux", окружение={"CHROME_BIN": "/свой/chrome"},
                                  есть=lambda п: п == "/свой/chrome")
        self.assertEqual(путь, "/свой/chrome")

    def test_путь_из_переменной_проверяется_как_свои_кандидаты(self):
        # Путь в переменной человек вводит руками и по памяти: взять его на слово — значит
        # проглотить опечатку и показать зелёную галочку тому, у кого канала нет.
        with self.assertRaises(кисть.ПутьМимоБраузера) as беда:
            кисть.найти_chrome(платформа="darwin", окружение={"CHROME_BIN": "/нет/такого"},
                               есть=lambda п: True if п != "/нет/такого" else False)
        self.assertEqual(беда.exception.путь, "/нет/такого")
        self.assertIn("/нет/такого", str(беда.exception))

    def test_опечатка_в_пути_не_ищет_chrome_дальше_по_списку(self):
        # Иначе человек получил бы «✅ Chrome найден» — но не тот, который он назвал.
        with self.assertRaises(кисть.ПутьМимоБраузера):
            кисть.найти_chrome(платформа="darwin", окружение={"CHROME_BIN": "/нет/такого"},
                               есть=lambda п: п.endswith("Google Chrome"))

    def test_пустая_переменная_за_ручку_не_считается(self):
        # CHROME_BIN= (или пробелы) — это не «браузер вот здесь», это ничего.
        for пусто in ("", "   "):
            путь = кисть.найти_chrome(платформа="linux", окружение={"CHROME_BIN": пусто},
                                      есть=lambda п: п == "/usr/bin/google-chrome")
            self.assertEqual(путь, "/usr/bin/google-chrome")

    def test_находит_на_маке(self):
        путь = кисть.найти_chrome(
            платформа="darwin", окружение={},
            есть=lambda п: п == "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        self.assertTrue(путь.endswith("Google Chrome"))

    def test_находит_на_windows(self):
        путь = кисть.найти_chrome(
            платформа="win32", окружение={},
            есть=lambda п: п == r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        self.assertTrue(путь.endswith("chrome.exe"))

    def test_не_нашёлся_говорим_человеческим_языком(self):
        with self.assertRaises(кисть.БедаКисти) as беда:
            кисть.найти_chrome(платформа="linux", окружение={}, есть=lambda п: False)
        текст = str(беда.exception)
        self.assertIn("google.com/chrome", текст)
        self.assertIn("CHROME_BIN", текст)

    def test_незнакомая_система_не_роняет_разбор(self):
        with self.assertRaises(кисть.БедаКисти):
            кисть.найти_chrome(платформа="freebsd13", окружение={}, есть=lambda п: True)


class Замок(unittest.TestCase):
    def setUp(self):
        self._д = tempfile.TemporaryDirectory()
        self.addCleanup(self._д.cleanup)
        self.замок = Path(self._д.name) / "браузер" / ".замок"

    def test_занять_и_отпустить(self):
        self.assertTrue(кисть.занять_замок(self.замок))
        self.assertEqual(self.замок.read_text(encoding="utf-8"), str(os.getpid()))
        кисть.отпустить_замок(self.замок)
        self.assertFalse(self.замок.exists())

    def test_второй_прогон_не_проходит(self):
        self.assertTrue(кисть.занять_замок(self.замок))
        self.assertFalse(кисть.занять_замок(self.замок))

    def test_мёртвый_замок_подбираем(self):
        # Упавший прогон не должен запирать систему навсегда.
        self.замок.parent.mkdir(parents=True, exist_ok=True)
        self.замок.write_text("999999", encoding="utf-8")
        self.assertTrue(кисть.занять_замок(self.замок))
        self.assertEqual(self.замок.read_text(encoding="utf-8"), str(os.getpid()))

    def test_битый_замок_подбираем(self):
        self.замок.parent.mkdir(parents=True, exist_ok=True)
        self.замок.write_text("не число", encoding="utf-8")
        self.assertTrue(кисть.занять_замок(self.замок))

    def test_отпустить_несуществующий_не_падает(self):
        кисть.отпустить_замок(self.замок)


class ЖурналЧемРисовали(unittest.TestCase):
    def setUp(self):
        self._д = tempfile.TemporaryDirectory()
        self.addCleanup(self._д.cleanup)
        self.журнал = Path(self._д.name) / "браузер" / "чем-рисовали.txt"

    def test_строка_в_московском_времени(self):
        когда = datetime(2026, 9, 13, 23, 30, tzinfo=timezone(timedelta(hours=0)))
        строка = кисть.строка_журнала({"режим ответа": "Instant"}, когда)
        self.assertIn("2026-09-14 02:30 МСК", строка)   # 23:30 UTC = 02:30 следующего дня в Москве
        self.assertIn("режим ответа: Instant", строка)

    def test_пишем_наблюдаемое_а_не_имя_модели(self):
        строка = кисть.строка_журнала({"режим ответа": "Instant",
                                       "режим картинки": "включён",
                                       "кадр": "1586×992 (1.599)",
                                       "просили": "16:10"})
        self.assertIn("режим картинки: включён", строка)
        self.assertIn("1586×992", строка)
        self.assertNotIn("не удалось прочитать", строка)

    def test_пустые_поля_не_печатаются(self):
        строка = кисть.строка_журнала({"режим ответа": "Instant", "просили": None, "кадр": ""})
        self.assertNotIn("просили", строка)
        self.assertNotIn("кадр", строка)

    def test_дописывается_а_не_затирается(self):
        кисть.записать_журнал({"режим ответа": "Instant"}, self.журнал)
        кисть.записать_журнал({"режим ответа": "Thinking"}, self.журнал)
        строки = self.журнал.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(строки), 2)
        self.assertIn("Thinking", строки[1])


class РежимКартинки(unittest.TestCase):
    """⭐ Без явного «Создать изображение» рисует старая модель и отдаёт 3:2 — решение
    владелицы 13.09.2026 отменило перенесённое «модель не прибиваем гвоздями»."""

    def test_метка_в_композере_значит_включено(self):
        self.assertTrue(кисть.режим_картинки_включён("Создать изображение\n \n\nInstant"))

    def test_английская_метка_тоже_считается(self):
        self.assertTrue(кисть.режим_картинки_включён("Create image\n\nInstant"))

    def test_без_метки_выключено(self):
        self.assertFalse(кисть.режим_картинки_включён("Instant"))
        self.assertFalse(кисть.режим_картинки_включён(""))
        self.assertFalse(кисть.режим_картинки_включён(None))


class Пропорция(unittest.TestCase):
    def test_разбор_записей(self):
        self.assertAlmostEqual(кисть.разобрать_пропорцию("16:10"), 1.6)
        self.assertAlmostEqual(кисть.разобрать_пропорцию("4:5"), 0.8)
        self.assertAlmostEqual(кисть.разобрать_пропорцию("1:1"), 1.0)
        self.assertAlmostEqual(кисть.разобрать_пропорцию("1920x1080"), 16 / 9)
        self.assertAlmostEqual(кисть.разобрать_пропорцию("1,6"), 1.6)

    def test_непонятное_не_угадываем(self):
        for мусор in (None, "", "как получится", "16:0", "-2"):
            self.assertIsNone(кисть.разобрать_пропорцию(мусор), мусор)

    def test_живой_замер_шестнадцать_на_десять_проходит(self):
        # 1586×992 — настоящий кадр от свежей модели, замер 13.09.2026: расхождение 0,06 %.
        self.assertTrue(кисть.пропорция_совпала(1586 / 992, 1.6))

    def test_откат_на_старую_модель_ловится(self):
        # 3:2 вместо 16:10 — расхождение 6,7 %, это и есть признак старой модели.
        self.assertFalse(кисть.пропорция_совпала(1.5, 1.6))
        # 2:3 вместо 4:5 — расхождение 20 %.
        self.assertFalse(кисть.пропорция_совпала(2 / 3, 0.8))

    def test_допуск_два_процента(self):
        self.assertEqual(кисть.ДОПУСК_ПРОПОРЦИИ, 0.02)
        self.assertTrue(кисть.пропорция_совпала(1.6 * 1.019, 1.6))
        self.assertFalse(кисть.пропорция_совпала(1.6 * 1.021, 1.6))

    def test_не_просили_формат_нечему_не_совпасть(self):
        self.assertTrue(кисть.пропорция_совпала(1.5, None))

    def test_пропорция_уходит_в_промт(self):
        промт = кисть.промт_с_пропорцией("кабинет врача", "16:10")
        self.assertIn("16:10", промт)
        self.assertTrue(промт.startswith("кабинет врача"))

    def test_второй_раз_не_дописываем(self):
        промт = кисть.промт_с_пропорцией("кадр 16:10, светлый", "16:10")
        self.assertEqual(промт.count("16:10"), 1)

    def test_без_пропорции_промт_не_трогаем(self):
        self.assertEqual(кисть.промт_с_пропорцией("кабинет", None), "кабинет")


class ЗамерИПодрезка(unittest.TestCase):
    def setUp(self):
        self._д = tempfile.TemporaryDirectory()
        self.addCleanup(self._д.cleanup)
        self.д = Path(self._д.name)

    def кадр(self, ширина, высота, имя="k.png"):
        from PIL import Image
        путь = self.д / имя
        Image.new("RGB", (ширина, высота), (120, 140, 160)).save(путь)
        return путь

    def test_замер(self):
        ш, в, п = кисть.замерить_кадр(self.кадр(1586, 992))
        self.assertEqual((ш, в), (1586, 992))
        self.assertAlmostEqual(п, 1586 / 992)

    def test_подрезка_широкого_до_четыре_на_пять(self):
        путь = self.кадр(1500, 1000)
        кисть.подрезать_кадр(путь, 0.8)
        ш, в, п = кисть.замерить_кадр(путь)
        self.assertAlmostEqual(п, 0.8, places=2)
        self.assertEqual(в, 1000)          # режем по ширине, высоту не трогаем

    def test_подрезка_узкого_до_шестнадцать_на_десять(self):
        путь = self.кадр(1000, 1500)
        кисть.подрезать_кадр(путь, 1.6)
        ш, в, п = кисть.замерить_кадр(путь)
        self.assertAlmostEqual(п, 1.6, places=2)
        self.assertEqual(ш, 1000)


class ГотовностьБраузера(unittest.TestCase):
    """Порт ответил — ещё не значит, что браузер готов: на первом запуске подключение падает
    «Browser context management is not supported» (13.09.2026, Chrome 152, Playwright 1.62).

    ⚠️ Проверяем ПОВЕДЕНИЕ, а не текст исходника. Прежние тесты искали в коде строку
    `ждать_вкладку(порт)` — и были бы зелены для `def ждать_вкладку(...): return False`, то есть
    проверяли сами себя, а не работу. Живой Chrome здесь по-прежнему не поднимается: подъём,
    ответ порта и вкладка подставляются параметрами.
    """

    def setUp(self):
        self._д = tempfile.TemporaryDirectory()
        self.addCleanup(self._д.cleanup)
        self.д = Path(self._д.name)
        self.запуски = []

    def поднять(self, **свои):
        доводы = {"профиль": self.д / "профиль", "путь_chrome": "/bin/echo", "ждать_с": 3,
                  "запустить": lambda флаги, отдельно: self.запуски.append(флаги),
                  "живой": lambda порт: True, "вкладка": lambda порт: True,
                  "файл_порта": self.д / "порт.txt", "пауза": lambda с: None}
        доводы.update(свои)
        return кисть.поднять_chrome(9500, **доводы)

    def test_вкладка_дождалась_порт_записан(self):
        self.assertEqual(self.поднять(), 9500)
        self.assertEqual((self.д / "порт.txt").read_text(encoding="utf-8"), "9500")
        self.assertEqual(len(self.запуски), 1)

    def test_вкладки_нет_порт_не_записан_и_беда_своими_словами(self):
        # Ровно та гонка, ради которой написана `ждать_вкладку`: раньше её ответ выбрасывался,
        # и подъём рапортовал успех даже без вкладки — только на двадцать секунд позже.
        with self.assertRaises(кисть.ОкноНеПоднялось) as беда:
            self.поднять(вкладка=lambda порт: False)
        self.assertIn("вкладка", str(беда.exception))
        self.assertFalse((self.д / "порт.txt").exists())

    def test_порт_так_и_не_ответил(self):
        with self.assertRaises(кисть.ОкноНеПоднялось):
            self.поднять(живой=lambda порт: False)
        self.assertFalse((self.д / "порт.txt").exists())

    def test_беда_подъёма_это_не_сеть(self):
        # `ОкноНеПоднялось` наследует `НеГотово` (наверху это по-прежнему беда канала, которую
        # повторяют), но слова у неё свои: «повторите позже» рядом с «закройте окно системы»
        # читались как два противоречащих совета в одном абзаце.
        self.assertTrue(issubclass(кисть.ОкноНеПоднялось, кисть.НеГотово))
        свои = "\n".join(кисть.слова_канала(кисть.НЕ_ПОДНЯЛСЯ))
        self.assertNotEqual(свои, "\n".join(кисть.слова_канала(кисть.СЕТЬ)))
        self.assertNotIn("проверка на роботов", свои)

    def _ответ(self, цели):
        import io as _io
        import json as _json
        ответ = _io.BytesIO(_json.dumps(цели).encode("utf-8"))
        ответ.__enter__ = lambda сам=ответ: сам
        ответ.__exit__ = lambda *а: False
        return ответ

    def test_вкладка_есть_ждём_недолго(self):
        # Готовность меряем по существу: не «порт ответил», а «в браузере есть вкладка».
        спросили = []

        def открыть(адрес, timeout=None):
            спросили.append(адрес)
            return self._ответ([{"type": "page", "url": "about:blank"}])
        with patch.object(кисть.urllib.request, "urlopen", открыть):
            self.assertTrue(кисть.ждать_вкладку(9500, ждать_с=3))
        self.assertEqual(len(спросили), 1)
        self.assertIn("json/list", спросили[0])

    def test_только_служебные_цели_это_ещё_не_вкладка(self):
        # Ровно щель гонки первого запуска: порт отвечает, а страницы в браузере ещё нет.
        цели = [{"type": "browser"}, {"type": "service_worker"}]
        with patch.object(кисть.urllib.request, "urlopen",
                          lambda адрес, timeout=None: self._ответ(цели)), \
             patch.object(кисть.time, "sleep", lambda с: None):
            self.assertFalse(кисть.ждать_вкладку(9500, ждать_с=2))

    def test_порт_молчит_вкладки_нет(self):
        def падает(адрес, timeout=None):
            raise OSError("connection refused")
        with patch.object(кисть.urllib.request, "urlopen", падает), \
             patch.object(кисть.time, "sleep", lambda с: None):
            self.assertFalse(кисть.ждать_вкладку(9500, ждать_с=2))

    def test_подключение_повторяет_заход(self):
        текст = _исходник("подключение")
        self.assertIn("попыток", текст)
        self.assertIn("ждать_вкладку(порт)", текст)


class ЧужойБраузерНеТрогаем(unittest.TestCase):
    """⛔ `--порт` сам по себе пропуском не служит: порт считается нашим, только если процесс на
    нём запущен с нашей папкой профиля. Иначе система однажды напечатает промт в чужую беседу."""

    def порт(self, порт=None, *, свой=None, живые=(), поднялся=9500):
        подняли = []

        def поднять(п):
            подняли.append(п)
            return поднялся
        итог = кисть.порт_браузера(порт, наш=lambda запомненный=None: свой,
                                   живой=lambda п: п in живые, поднять=поднять,
                                   запомнено=lambda: None)
        return итог, подняли

    def test_чужой_живой_порт_это_отказ_а_не_подключение(self):
        with self.assertRaises(кисть.БедаКисти) as беда:
            self.порт(9222, свой=None, живые=(9222,))
        сказано = str(беда.exception)
        self.assertIn("чужой Chrome", сказано)
        self.assertIn("не подключаемся", сказано)

    def test_чужой_живой_порт_не_обходится_даже_когда_своё_окно_есть(self):
        with self.assertRaises(кисть.БедаКисти):
            self.порт(9222, свой=9501, живые=(9222, 9501))

    def test_свой_порт_названный_руками_принимается(self):
        итог, подняли = self.порт(9500, свой=9500, живые=(9500,))
        self.assertEqual(итог, 9500)
        self.assertEqual(подняли, [])

    def test_своё_окно_находится_и_без_порта(self):
        итог, подняли = self.порт(None, свой=9501, живые=(9501,))
        self.assertEqual(итог, 9501)
        self.assertEqual(подняли, [])

    def test_ничей_порт_поднимаем_своим_окном(self):
        итог, подняли = self.порт(9503, свой=None, живые=(), поднялся=9503)
        self.assertEqual(итог, 9503)
        self.assertEqual(подняли, [9503])


class ЖивостьПроцессаНеУбивает(unittest.TestCase):
    """⛔ `os.kill(номер, 0)` безобиден только на POSIX: на Windows CPython зовёт там
    `TerminateProcess()` и ЗАВЕРШАЕТ процесс с этим номером. Номера на Windows переиспользуются,
    и брошенный замок рано или поздно указывает на чужую живую программу."""

    def test_на_windows_os_kill_не_зовётся_вовсе(self):
        было = os.kill
        звали = []
        os.kill = lambda *а, **к: звали.append(а)          # сработает — тест это увидит
        try:
            self.assertTrue(кисть._процесс_жив(4242, платформа="win32", спросить=lambda н: True))
            self.assertFalse(кисть._процесс_жив(4242, платформа="win32", спросить=lambda н: False))
        finally:
            os.kill = было
        self.assertEqual(звали, [], "на Windows os.kill не должен звучать ни разу")

    def test_на_windows_беда_спрашивалки_не_запирает_систему(self):
        def сломалась(номер):
            raise OSError("ctypes не завёлся")
        self.assertFalse(кисть._процесс_жив(4242, платформа="win32", спросить=сломалась))

    def test_на_posix_спрашиваем_сигналом_ноль(self):
        self.assertTrue(кисть._процесс_жив(os.getpid(), платформа="darwin"))
        self.assertFalse(кисть._процесс_жив(999999, платформа="darwin"))

    def test_нулевой_номер_не_живой_ни_на_чём(self):
        for платформа in ("win32", "darwin", "linux"):
            self.assertFalse(кисть._процесс_жив(0, платформа=платформа), платформа)


class ВоротаВвода(unittest.TestCase):
    """Беда ввода не должна стоить человеку ни поднятого браузера, ни генерации по подписке:
    всё это проверяется до замка и до окна."""

    def test_пустой_промт_это_беда_ввода_а_не_поломка_страницы(self):
        for пусто in ("", "   ", "\n"):
            with self.assertRaises(кисть.БедаКисти) as беда:
                кисть.проверить_промт(пусто)
            self.assertIn("промт пустой", str(беда.exception))

    def test_короткий_промт_законен(self):
        self.assertEqual(кисть.проверить_промт("рыжий кот"), "рыжий кот")

    def test_имя_только_латиницей_цифрами_и_дефисом(self):
        for годное in ("kadr", "kadr-1", "master2"):
            self.assertEqual(кисть.проверить_имя(годное), годное)
        for негодное in ("", "кадр", "../../профили/_активный", "kadr.png", "Kadr", "a b"):
            with self.assertRaises(кисть.БедаКисти, msg=негодное):
                кисть.проверить_имя(негодное)

    def test_в_img_кисть_не_рисует_ни_одним_написанием(self):
        for путь in ("сайты/x/img", "сайты/x/img/кадры", "сайты/x/IMG",
                     "сайты/x/img/кадры/ещё-глубже"):
            with self.assertRaises(кисть.БедаКисти, msg=путь) as беда:
                кисть.проверить_куда(путь)
            self.assertIn("кисть не рисует", str(беда.exception))
            self.assertIn("кадр-ждёт", str(беда.exception))

    def test_папка_ожидания_законна(self):
        self.assertTrue(кисть.проверить_куда("сайты/x/витрина/кадр-ждёт"))

    def test_нарисовать_отказывает_до_замка(self):
        # Ни браузера, ни замка: беду ввода видно сразу, а не после поднятого окна.
        д = tempfile.TemporaryDirectory()
        self.addCleanup(д.cleanup)
        for довод in ({"промт": ""}, {"имя": "../чужое"}, {"куда": "сайты/x/img"}):
            доводы = {"промт": "кабинет", "куда": д.name, "имя": "kadr"}
            доводы.update(довод)
            with self.assertRaises(кисть.БедаКисти, msg=str(довод)):
                кисть.нарисовать(доводы["промт"], Path(доводы["куда"]), имя=доводы["имя"])
            self.assertFalse(кисть.ЗАМОК.exists())


class ПечатьПромтаСверяетсяСЗаказанным(unittest.TestCase):
    """⚠️ Порог «12 символов» мерил длину ПРОМТА, а не факт печати: `--нарисуй "рыжий кот"`
    печатался целиком и объявлялся поломкой страницы ChatGPT с уходом в «повторите позже»."""

    def test_короткий_промт_считается_напечатанным(self):
        self.assertTrue(кисть.напечаталось("рыжий кот", "рыжий кот"))
        self.assertTrue(кисть.напечаталось("кот", "кот"))

    def test_пустое_поле_это_не_напечаталось(self):
        self.assertFalse(кисть.напечаталось("", "рыжий кот"))
        self.assertFalse(кисть.напечаталось(None, "рыжий кот"))

    def test_чужой_текст_в_поле_не_считается_нашим(self):
        self.assertFalse(кисть.напечаталось("предыдущий разговор про сайт", "кабинет мастера"))

    def test_переносы_и_двойные_пробелы_не_мешают(self):
        self.assertTrue(кисть.напечаталось("кабинет  мастера,\nсветлый", "кабинет мастера, светлый"))

    def test_длинный_промт_узнаётся_по_началу(self):
        промт = "Фотография: мастер за верстаком. " + "Фон спокойный. " * 40
        self.assertTrue(кисть.напечаталось(промт, промт))


class ПрочаяБедаВыходитСловами(unittest.TestCase):
    """⛔ Раньше всё, кроме трёх своих классов, выходило трассировкой и кодом 1 — тем самым,
    который шапка модуля отдала под «сессия умерла, нужны руки»."""

    def test_закрытое_окно_это_повторите_а_не_нужны_руки(self):
        беда = type("TargetClosedError", (Exception,), {})("окно закрыто")
        строки, код = кисть.слова_прочей_беды(беда)
        self.assertEqual(код, 2)
        self.assertIn("окно", "\n".join(строки).lower())
        self.assertNotIn("Traceback", "\n".join(строки))

    def test_битая_картинка_это_повторите(self):
        беда = type("UnidentifiedImageError", (OSError,), {})("не картинка")
        _, код = кисть.слова_прочей_беды(беда)
        self.assertEqual(код, 2)

    def test_куда_указывает_на_файл_это_беда_ввода(self):
        строки, код = кисть.слова_прочей_беды(FileExistsError(17, "File exists", "/tmp/kadr.png"))
        self.assertEqual(код, 3)
        self.assertIn("--имя", "\n".join(строки))

    def test_незнакомая_беда_не_занимает_код_нужны_руки(self):
        строки, код = кисть.слова_прочей_беды(ValueError("что-то своё"))
        self.assertEqual(код, 3)
        self.assertNotEqual(код, 1)
        self.assertTrue("\n".join(строки).strip())


def _исходник(имя: str) -> str:
    import inspect
    цель = getattr(кисть, имя)
    цель = getattr(цель, "__wrapped__", цель)
    return inspect.getsource(цель)


class ИмяФайла(unittest.TestCase):
    def test_по_типу_ответа(self):
        self.assertEqual(кисть.расширение_картинки("image/webp"), ".webp")
        self.assertEqual(кисть.расширение_картинки("image/png; charset=binary"), ".png")
        self.assertEqual(кисть.расширение_картинки("image/jpeg"), ".jpg")

    def test_не_подписан_считаем_png(self):
        self.assertEqual(кисть.расширение_картинки(None), ".png")
        self.assertEqual(кисть.расширение_картинки("application/octet-stream"), ".png")


class БезРефаНеРисуем(unittest.TestCase):
    def test_нет_файла_образца_говорим_сразу(self):
        # До браузера дело не доходит: замок не берём, окно не поднимаем.
        with self.assertRaises(кисть.БедаКисти) as беда:
            кисть.нарисовать("промт", Path("/tmp"), рефы=["/нет/такого/файла.png"])
        self.assertIn("нет файла-образца", str(беда.exception))
        self.assertFalse(кисть.ЗАМОК.exists())


class ПутиЧерезApiНет(unittest.TestCase):
    """⛔ Запрет владелицы: никакого API OpenAI — ни основным путём, ни запасным.

    Правило проверяется тестом, а не только словом в шапке: запасной путь заводят «на всякий
    случай» именно тогда, когда живой канал сбоит, а потом он тихо включается сам.
    """

    def test_в_модуле_нет_ключей_и_запросов_к_api(self):
        текст = (СКРИПТЫ / "кисть.py").read_text(encoding="utf-8").lower()
        for запрет in ("api.openai.com", "openai_api_key", "sk-", "import openai",
                       "/v1/images", "dall-e"):
            self.assertNotIn(запрет, текст, f"в кисти завёлся путь через API: {запрет}")

    def test_адрес_только_живой_chatgpt(self):
        self.assertEqual(кисть.АДРЕС, "https://chatgpt.com/")


class ПравилоСвежейМодели(unittest.TestCase):
    """Правило «модель не прибиваем гвоздями» отменено 13.09.2026 — в коде это должно быть
    сказано вслух, иначе следующий разработчик вернёт его как «перенесённое из цеха»."""

    def test_в_шапке_сказано_что_правило_поменялось(self):
        шапка = (кисть.__doc__ or "")
        self.assertIn("отменено", шапка.lower())
        self.assertIn("Imagen", шапка)

    def test_оба_написания_пункта_меню(self):
        self.assertIn("Создать изображение", кисть.ПУНКТЫ_РЕЖИМА_КАРТИНКИ)
        self.assertIn("Create image", кисть.ПУНКТЫ_РЕЖИМА_КАРТИНКИ)


class ЧетыреСостоянияКанала(unittest.TestCase):
    """Канала нет · не входили ни разу · вход умер · занято — и пятое, отдельное: сеть.

    Ложный вызов к экрану стоит доверия ко всем следующим, поэтому состояния обязаны
    различаться не только внутри кода, но и словами, которые видит человек.
    """

    def setUp(self):
        self.д = Path(tempfile.mkdtemp())
        self.профиль = self.д / "профиль-chatgpt"
        self.журнал = self.д / "чем-рисовали.txt"
        self.замок = self.д / ".замок"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.д, ignore_errors=True)

    def состояние(self, найти=lambda: "/путь/к/chrome"):
        return кисть.состояние_канала(найти=найти, профиль=self.профиль,
                                      журнал=self.журнал, замок=self.замок)

    def нет_chrome(self):
        raise кисть.БедаКисти("Не нашёл Google Chrome на этом компьютере.")

    def test_канала_нет_когда_chrome_не_найден(self):
        self.assertEqual(self.состояние(найти=self.нет_chrome), кисть.НЕТ_БРАУЗЕРА)

    def test_опечатка_в_переменной_это_своё_состояние_а_не_общее_канала_нет(self):
        def мимо():
            raise кисть.ПутьМимоБраузера("/нет/такого")
        self.assertEqual(self.состояние(найти=мимо), кисть.ПУТЬ_МИМО)

    def test_не_входили_ни_разу_когда_профиль_пуст(self):
        self.assertEqual(self.состояние(), кисть.НЕ_ВХОДИЛИ)

    def test_вход_был_виден_по_журналу(self):
        self.журнал.write_text("2026-09-13 19:07 МСК — вход: выполнен руками\n", encoding="utf-8")
        self.assertEqual(self.состояние(), кисть.ГОТОВ)

    def test_вход_был_виден_по_базе_кук(self):
        куки = self.профиль / "Default" / "Cookies"
        куки.parent.mkdir(parents=True)
        куки.write_bytes(b"x" * (кисть.ПУСТАЯ_БАЗА_КУК + 1))
        self.assertEqual(self.состояние(), кисть.ГОТОВ)

    def test_окно_открывали_но_не_вошли_это_не_умерший_вход(self):
        # Пустая база кук заводится и без входа: сказать такому человеку «вход умер» —
        # соврать ему про его же первый запуск.
        куки = self.профиль / "Default" / "Cookies"
        куки.parent.mkdir(parents=True)
        куки.write_bytes(b"x" * 4096)
        self.assertEqual(self.состояние(), кисть.НЕ_ВХОДИЛИ)

    def test_занято_когда_замок_держит_живой_прогон(self):
        self.замок.write_text(str(os.getpid()), encoding="utf-8")
        self.assertEqual(self.состояние(), кисть.ЗАНЯТО)

    def test_брошенный_замок_занятостью_не_считается(self):
        self.журнал.write_text("вход: выполнен руками\n", encoding="utf-8")
        self.замок.write_text("999999", encoding="utf-8")   # такого процесса нет
        self.assertEqual(self.состояние(), кисть.ГОТОВ)

    def test_нет_браузера_старше_всего_остального(self):
        self.замок.write_text(str(os.getpid()), encoding="utf-8")
        self.assertEqual(self.состояние(найти=self.нет_chrome), кисть.НЕТ_БРАУЗЕРА)


class СловаЧетырёхСостояний(unittest.TestCase):
    ВСЕ = (кисть.НЕТ_БРАУЗЕРА, кисть.ПУТЬ_МИМО, кисть.НЕ_ВХОДИЛИ, кисть.ВХОД_УМЕР,
           кисть.ЗАНЯТО, кисть.СЕТЬ, кисть.НЕ_ПОДНЯЛСЯ, кисть.ГОТОВ)

    def test_у_каждого_состояния_свои_слова(self):
        сказанное = {с: "\n".join(кисть.слова_канала(с)) for с in self.ВСЕ}
        self.assertEqual(len(set(сказанное.values())), len(self.ВСЕ),
                         "два состояния говорят одно и то же — человек их не различит")
        for состояние, текст in сказанное.items():
            self.assertTrue(текст.strip(), состояние)

    def test_канала_нет_говорит_что_поставить_и_что_сайт_всё_равно_соберётся(self):
        текст = "\n".join(кисть.слова_канала(кисть.НЕТ_БРАУЗЕРА))
        self.assertIn("google.com/chrome", текст)
        self.assertIn("CHROME_BIN", текст)
        self.assertIn("сайт", текст.lower())

    def test_не_входили_зовёт_к_окну_и_обещает_не_видеть_пароля(self):
        текст = "\n".join(кисть.слова_канала(кисть.НЕ_ВХОДИЛИ))
        self.assertIn("--вход", текст)
        self.assertIn("пароль", текст.lower())

    def test_вход_умер_говорит_что_это_не_поломка(self):
        текст = "\n".join(кисть.слова_канала(кисть.ВХОД_УМЕР))
        self.assertIn("--вход", текст)
        self.assertIn("не поломка", текст.lower())

    def test_занято_запрещает_трогать_чужие_окна(self):
        текст = "\n".join(кисть.слова_канала(кисть.ЗАНЯТО))
        self.assertIn(кисть.ИМЯ_ПРОФИЛЯ, текст)
        self.assertIn("не закрывайте", текст.lower())

    def test_занято_не_советует_закрыть_окно(self):
        # ⚠️ «Занято» — это ЗАМОК, а не окно: закрытое окно замка не снимает (процесс-владелец
        # жив), зато обрывает картинку тому прогону, который её сейчас рисует. Совет не лечил
        # то, ради чего дан, и ломал то, что было цело.
        текст = "\n".join(кисть.слова_канала(кисть.ЗАНЯТО)).lower()
        self.assertNotIn("закройте это окно", текст)
        self.assertIn("дождитесь конца прогона", текст)
        self.assertIn("снимется сам", текст)

    def test_окно_не_поднялось_не_говорит_про_сеть_и_не_зовёт_входить(self):
        текст = "\n".join(кисть.слова_канала(кисть.НЕ_ПОДНЯЛСЯ)).lower()
        self.assertNotIn("--вход", текст)
        self.assertNotIn("проверка на роботов", текст)
        self.assertIn("повторите команду", текст)

    def test_сеть_тормозит_не_превращается_в_идите_входите(self):
        # Пятое состояние: человека не будим вовсе.
        текст = "\n".join(кисть.слова_канала(кисть.СЕТЬ)).lower()
        for звонок in ("--вход", "войдите"):
            self.assertNotIn(звонок, текст, "сеть зовёт к экрану, а не должна")
        self.assertIn("не надо", текст)
        self.assertIn("позже", текст)

    def test_путь_мимо_называет_путь_и_не_велит_ставить_chrome(self):
        # Chrome у человека есть; «поставьте Chrome» здесь — совет чинить то, что не сломано.
        текст = "\n".join(кисть.слова_канала(кисть.ПУТЬ_МИМО, путь="/нет/такого/chrome"))
        self.assertIn("/нет/такого/chrome", текст)
        self.assertIn("CHROME_BIN", текст)
        self.assertNotIn("google.com/chrome", текст)
        self.assertIn("опечатка", текст)

    def test_путь_берётся_из_окружения_когда_его_не_передали(self):
        было = os.environ.get("CHROME_BIN")
        os.environ["CHROME_BIN"] = "/из/окружения/chrome"
        try:
            текст = "\n".join(кисть.слова_канала(кисть.ПУТЬ_МИМО))
        finally:
            os.environ.pop("CHROME_BIN") if было is None else os.environ.update(CHROME_BIN=было)
        self.assertIn("/из/окружения/chrome", текст)

    def test_незнакомое_состояние_не_роняет_печать(self):
        self.assertTrue(кисть.слова_канала("что-то новое"))


class ОтчётОКанале(unittest.TestCase):
    """`--канал` — отчёт, а не ворота: на нём стоит установка, и падать ей нельзя."""

    def прогон(self, состояние):
        было = кисть.состояние_канала
        кисть.состояние_канала = lambda *а, **к: состояние
        поток = io.StringIO()
        try:
            with contextlib.redirect_stdout(поток):
                код = кисть.команда_канал()
        finally:
            кисть.состояние_канала = было
        return код, поток.getvalue()

    def test_любое_состояние_даёт_ноль(self):
        for состояние in СловаЧетырёхСостояний.ВСЕ:
            код, вывод = self.прогон(состояние)
            self.assertEqual(код, 0, состояние)
            self.assertTrue(вывод.strip(), состояние)

    def test_канала_нет_печатается_словами_а_не_молчанием(self):
        _, вывод = self.прогон(кисть.НЕТ_БРАУЗЕРА)
        self.assertIn("google.com/chrome", вывод)


if __name__ == "__main__":
    unittest.main()
