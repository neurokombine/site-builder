"""Проверка прототипа: форма, пресет, гейт, кнопки, цифры, стоп-слова и запреты из профиля."""
import subprocess, sys, unittest
from pathlib import Path

СКРИПТЫ = Path(__file__).resolve().parent.parent
ФИКСТУРЫ = Path(__file__).resolve().parent / "фикстуры"
ЯДРО = СКРИПТЫ.parent
sys.path.insert(0, str(СКРИПТЫ))
import проверить_прототип as пп  # noqa: E402


def уровни(находки):
    return [н["уровень"] for н in находки]


def тексты(находки):
    return " | ".join(н["что"] for н in находки)


class РазборТесты(unittest.TestCase):
    def test_чистый_разбирается_целиком(self):
        [п] = пп.разобрать((ФИКСТУРЫ / "прототип-чистый.md").read_text(encoding="utf-8"))
        self.assertEqual(п["шапка"]["Пресет"], "визитка")
        self.assertEqual(len(п["экраны"]), 5)
        self.assertEqual(п["экраны"][0]["название"], "Первый экран")
        self.assertEqual(п["экраны"][0]["статус"], "принят")
        self.assertIn("Заголовок", п["экраны"][0]["слоты"])
        self.assertEqual(len(п["экраны"][0]["слоты"]["Заголовок"]), 3)   # текст + две «или»

    def test_эталон_содержит_два_прототипа(self):
        прототипы = пп.разобрать((ЯДРО / "эталон-прототипа.md").read_text(encoding="utf-8"))
        self.assertEqual([п["шапка"]["Пресет"] for п in прототипы], ["визитка", "лендинг"])


class НаходкиТесты(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        [cls.чистый] = пп.разобрать((ФИКСТУРЫ / "прототип-чистый.md").read_text(encoding="utf-8"))
        [cls.грязный] = пп.разобрать((ФИКСТУРЫ / "прототип-грязный.md").read_text(encoding="utf-8"))

    def test_чистый_без_красного(self):
        н = пп.проверить_прототип(self.чистый, нельзя_говорить=[], тип_из_профиля="визитка")
        self.assertNotIn(пп.ЧИНИТЬ, уровни(н), тексты(н))

    def test_эталон_без_красного(self):
        for п in пп.разобрать((ЯДРО / "эталон-прототипа.md").read_text(encoding="utf-8")):
            н = пп.проверить_прототип(п, нельзя_говорить=[], тип_из_профиля=None)
            self.assertNotIn(пп.ЧИНИТЬ, уровни(н), f"{п['имя']}: {тексты(н)}")

    def test_грязный_ловит_всё(self):
        н = пп.проверить_прототип(self.грязный, нельзя_говорить=["гарантия результата"], тип_из_профиля="лендинг")
        т = тексты(н)
        for ожидаем in ("мало экранов", "точка в конце заголовка", "стоп-слово", "одна «или»",
                        "ведут в разные места", "не принят, а экран", "цифра без источника",
                        "нельзя говорить", "пунктов в списке", "капс", "принят целиком",
                        "тип из профиля"):
            with self.subTest(ожидаем=ожидаем):
                self.assertIn(ожидаем, т)
        self.assertIn(пп.ЧИНИТЬ, уровни(н))

    def test_кнопка_нет_допустима_в_середине(self):
        текст = (ФИКСТУРЫ / "прототип-чистый.md").read_text(encoding="utf-8")
        текст = текст.replace("- Кнопка: Написать в Телеграм → написать в Телеграм", "- Кнопка: нет", 1)
        # первая замена попадает на экран 1 — там кнопка обязательна
        [п] = пп.разобрать(текст)
        н = пп.проверить_прототип(п, нельзя_говорить=[], тип_из_профиля=None)
        self.assertIn("на первом экране нет кнопки", тексты(н))


class CLIТесты(unittest.TestCase):
    def test_коды_выхода(self):
        чистый = subprocess.run([sys.executable, str(СКРИПТЫ / "проверить_прототип.py"),
                                 str(ФИКСТУРЫ / "прототип-чистый.md"), "--без-профиля"],
                                capture_output=True, text=True)
        self.assertEqual(чистый.returncode, 0, чистый.stdout)
        грязный = subprocess.run([sys.executable, str(СКРИПТЫ / "проверить_прототип.py"),
                                  str(ФИКСТУРЫ / "прототип-грязный.md"), "--без-профиля"],
                                 capture_output=True, text=True)
        self.assertEqual(грязный.returncode, 1, грязный.stdout)
        self.assertIn("🔴", грязный.stdout)

    def test_не_прототип(self):
        р = subprocess.run([sys.executable, str(СКРИПТЫ / "проверить_прототип.py"),
                            str(ФИКСТУРЫ / "лендинг.html"), "--без-профиля"], capture_output=True, text=True)
        self.assertEqual(р.returncode, 2)
