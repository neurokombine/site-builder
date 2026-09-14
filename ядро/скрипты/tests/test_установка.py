"""Установка и самопроверка про канал до генератора картинок.

Живой Chrome здесь не поднимается. Проверяем ровно две обещанные вещи: установка называет цену
входа канала заранее и переживает его отсутствие, а шаг самопроверки говорит словами и не роняет
самопроверку — картинки возможность, а не шаг маршрута.
"""
import contextlib
import io
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

СКРИПТЫ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(СКРИПТЫ))
import кисть  # noqa: E402
import selftest  # noqa: E402

УСТАНОВКА = СКРИПТЫ / "setup.sh"


def тело_функции(текст: str, имя: str) -> str:
    """Вырезать из скрипта установки одну функцию — чтобы проверять её настоящий код,
    а не свой пересказ. Кончается функция строкой из одной закрывающей скобки."""
    строки = текст.splitlines()
    начало = next(н for н, с in enumerate(строки) if с.startswith(f"{имя}()"))
    конец = next(н for н in range(начало + 1, len(строки)) if строки[н] == "}")
    return "\n".join(строки[начало:конец + 1])


class ЦенаВходаКанала(unittest.TestCase):
    """Цена названа вслух и ЗАРАНЕЕ — до первого мегабайта, а не посреди установки."""

    def setUp(self):
        self.текст = УСТАНОВКА.read_text(encoding="utf-8")

    def test_цена_канала_названа_в_первом_блоке(self):
        первый_блок = self.текст.split("# 1.")[0]
        for слово in ("Chrome", "вход руками", "подписке"):
            self.assertIn(слово, первый_блок, "цена канала должна звучать первым делом")

    def test_сказано_что_chrome_не_качаем_и_денег_он_не_стоит(self):
        self.assertIn("не качаем", self.текст)
        self.assertIn("не стоит", self.текст)

    def test_сказано_что_окно_с_входом_наружу_не_уезжает(self):
        self.assertIn("наружу", self.текст)
        self.assertIn("браузер/", self.текст)


class УстановкаПереживаетОтсутствиеКанала(unittest.TestCase):
    """Канал необязателен ровно как rembg: не нашёлся — говорим словами и идём дальше.

    Проверяем не чтением, а запуском: берём настоящую функцию из setup.sh, подсовываем ей
    заведомо падающий питон и смотрим, что установка на этом не кончается.
    """

    def прогнать(self, vpy: str) -> subprocess.CompletedProcess:
        функция = тело_функции(УСТАНОВКА.read_text(encoding="utf-8"), "channel_report")
        сценарий = ("set -euo pipefail\n" + f"VPY={shlex.quote(vpy)}\n" + функция
                    + "\nchannel_report || true\necho ХВОСТ\n")
        with tempfile.TemporaryDirectory() as папка:
            файл = Path(папка) / "проба.sh"
            файл.write_text(сценарий, encoding="utf-8")
            return subprocess.run(["bash", str(файл)], capture_output=True, text=True,
                                  cwd=СКРИПТЫ.parent.parent)

    def test_питон_упал_установка_идёт_дальше(self):
        готово = self.прогнать("false")
        self.assertEqual(готово.returncode, 0, готово.stderr)
        self.assertIn("ХВОСТ", готово.stdout, "установка оборвалась на необязательном шаге")
        self.assertIn("не ломает", готово.stdout)

    def test_рабочий_питон_печатает_слова_состояния(self):
        готово = self.прогнать(sys.executable)
        self.assertEqual(готово.returncode, 0, готово.stderr)
        self.assertIn("[setup]", готово.stdout)
        self.assertIn("канал", готово.stdout.lower())
        self.assertIn("ХВОСТ", готово.stdout)

    def test_установка_зовёт_отчёт_о_канале_а_не_живую_проверку(self):
        # `--проверь` поднимает окно и ждёт человека; в установке ему делать нечего.
        функция = тело_функции(УСТАНОВКА.read_text(encoding="utf-8"), "channel_report")
        self.assertIn("--канал", функция)
        self.assertNotIn("--проверь", функция)
        self.assertNotIn("--вход", функция)


class ШагСамопроверки(unittest.TestCase):
    """Шаг «канал до генератора» говорит словами и не роняет самопроверку ни при каком ответе."""

    def прогон(self, найти):
        было = кисть.найти_chrome
        кисть.найти_chrome = найти
        поток = io.StringIO()
        try:
            with contextlib.redirect_stdout(поток):
                selftest.проверить_канал()
        finally:
            кисть.найти_chrome = было
        return поток.getvalue()

    def test_канала_нет_шаг_не_роняет_самопроверку(self):
        def нет_chrome():
            raise кисть.БедаКисти("Не нашёл Google Chrome на этом компьютере.")
        вывод = self.прогон(нет_chrome)          # sys.exit(1) здесь был бы провалом теста
        self.assertIn("google.com/chrome", вывод)
        self.assertIn("сайт", вывод.lower())

    def test_шаг_не_открывает_окна_даже_когда_chrome_есть(self):
        # Единственный признак, что окна не поднимали: шаг отработал мгновенно и сказал,
        # что живой вход покажет отдельная команда.
        вывод = self.прогон(lambda: "/путь/к/chrome")
        self.assertIn("окно не открываю", вывод)

    def test_беда_внутри_шага_не_роняет_самопроверку(self):
        def взорвётся():
            raise RuntimeError("что-то совсем неожиданное")
        вывод = self.прогон(взорвётся)
        self.assertIn("не поломка", вывод)


if __name__ == "__main__":
    unittest.main()
