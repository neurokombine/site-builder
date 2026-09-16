"""Три направления: один прототип, три разные вёрстки одних и тех же экранов — выбор глазами.

Браузер поднимаем так же, как в `test_витрина.py`: страницу открываем файлом, снимаем оба
размера. Фикстура — работа-образец плюс папка `направления/1..3` из `фикстуры/направления/`.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

СКРИПТЫ = Path(__file__).resolve().parent.parent
ФИКСТУРЫ = Path(__file__).resolve().parent / "фикстуры"
sys.path.insert(0, str(СКРИПТЫ))

import направления  # noqa: E402
import находки  # noqa: E402
import профиль  # noqa: E402
import собрать  # noqa: E402


def _работа(д: Path) -> Path:
    """Работа-образец, рядом профиль-образец, внутри — три направления."""
    работа = д / "работа"
    shutil.copytree(ФИКСТУРЫ / "работа-образец", работа)
    shutil.copytree(ФИКСТУРЫ / "профиль-образец", д / "профиль-образец")
    shutil.copytree(ФИКСТУРЫ / "направления", работа / "направления")
    return работа


class ЧтениеТесты(unittest.TestCase):
    def test_поля_направления(self):
        имя = направления.прочитать_направление(ФИКСТУРЫ / "направления" / "1" / "направление.md")
        self.assertEqual(имя["имя"], "Спокойные карточки")
        self.assertIn("слева направо", имя["идея"])
        self.assertIn("галерея", имя["откуда"])
        self.assertIn("секция__шапка", имя["детали"])

    def test_без_имени_говорим_словами(self):
        with tempfile.TemporaryDirectory() as д:
            файл = Path(д) / "направление.md"
            файл.write_text("- Идея: что-то\n", encoding="utf-8")
            self.assertEqual(направления.прочитать_направление(файл)["имя"], "")

    def test_номера_экранов_из_строки(self):
        self.assertEqual(направления.номера_экранов("02,04"), ["02", "04"])
        self.assertEqual(направления.номера_экранов(" 2 , 4 "), ["02", "04"])
        self.assertEqual(направления.номера_экранов(None), [])


class СтраницаПоказаТесты(unittest.TestCase):
    def test_три_колонки_и_шесть_снимков(self):
        собранные = [{"номер": n, "имя": f"Имя {n}", "идея": "идея", "откуда": "галерея",
                      "детали": "сетка"} for n in ("1", "2", "3")]
        html = направления._страница_направлений("проба", собранные)
        self.assertEqual(html.count('<section class="направление">'), 3)
        self.assertEqual(len(re.findall(r'<img src="направления/\d/(?:компьютер|телефон)\.png"', html)), 6)
        self.assertIn("Имя 2", html)
        self.assertIn("Выбирает человек", html)


class ВзятьТесты(unittest.TestCase):
    def test_экраны_переезжают_а_решение_ложится_в_дизайн(self):
        with tempfile.TemporaryDirectory() as д:
            работа = _работа(Path(д))
            было = работа / "экраны" / "02-услуги-и-цены.html"
            self.assertTrue(было.is_file())
            взятые, предупреждения = направления.взять(работа, "2")
            self.assertEqual(sorted(п.name for п in взятые), ["02-боль.html", "03-решение.html"])
            self.assertFalse(было.exists(), "экран с тем же номером обязан уступить место")
            self.assertTrue(any("02-услуги-и-цены.html" in п for п in предупреждения), предупреждения)
            дизайн = (работа / "дизайн.md").read_text(encoding="utf-8")
            строка = re.search(r"- Направление: 2 — Крупное слева \((\d\d\.\d\d\.\d{4} \d\d:\d\d) МСК\)",
                               дизайн)
            self.assertTrue(строка, дизайн[дизайн.index("## Решения"):][:400])
            # решение встало ВНУТРЬ раздела «Решения», до палитры
            хвост = дизайн[дизайн.index("## Решения"):]
            self.assertLess(хвост.index("- Направление:"), хвост.index("```css"))
            # дизайн.md остался читаемым для сборки
            прочитанный = собрать.прочитать_дизайн(работа / "дизайн.md")
            self.assertEqual(прочитанный["решения_поля"]["схема"], "разворот")

    def test_одноимённый_экран_перезаписан_но_со_словом(self):
        """Самый частый случай: `02-боль.html` есть и в работе, и в направлении. Раньше он
        переписывался молча — человек узнавал об этом, когда искал свою вёрстку."""
        with tempfile.TemporaryDirectory() as д:
            работа = _работа(Path(д))
            свой = работа / "экраны" / "02-боль.html"
            свой.write_text("<section>моя прежняя вёрстка</section>\n", encoding="utf-8")
            взятые, предупреждения = направления.взять(работа, "1")
            self.assertTrue(any("02-боль.html" in п and "перезаписан" in п for п in предупреждения),
                            предупреждения)
            self.assertNotIn("моя прежняя вёрстка", свой.read_text(encoding="utf-8"))
            self.assertIn(свой, взятые)

    def test_нет_такого_направления(self):
        with tempfile.TemporaryDirectory() as д:
            работа = _работа(Path(д))
            with self.assertRaises(направления.НетНаправления):
                направления.взять(работа, "7")


class СборкаТесты(unittest.TestCase):
    """Самый долгий тест: три направления собираются настоящей сборкой и снимаются браузером."""

    def test_показ_собран_и_снимки_на_месте(self):
        with tempfile.TemporaryDirectory() as д:
            работа = _работа(Path(д))
            путь, найденное = направления.направления(работа)
            self.assertEqual([н["что"] for н in найденное if н["уровень"] == находки.ЧИНИТЬ], [])
            self.assertTrue(путь.is_file(), путь)
            html = путь.read_text(encoding="utf-8")
            self.assertEqual(html.count('<section class="направление">'), 3)
            for n in ("1", "2", "3"):
                папка = работа / "показ" / "направления" / n
                self.assertTrue((папка / "сайт" / "index.html").is_file(), папка)
                for размер in ("компьютер", "телефон"):
                    self.assertTrue((папка / f"{размер}.png").is_file(), f"{n}/{размер}.png")
                собрано = (папка / "сайт" / "index.html").read_text(encoding="utf-8")
                self.assertIn('data-тип="первый-экран"', собрано)
                self.assertIn('data-тип="решение"', собрано)
                # стиль направления уехал в style.css, а не остался в разметке
                self.assertNotIn("#экран-03", собрано)
                self.assertIn("/* экран 03 */",
                              (папка / "сайт" / "style.css").read_text(encoding="utf-8"))


class КомандаТесты(unittest.TestCase):
    def test_без_папки_направлений_говорим_что_делать(self):
        with tempfile.TemporaryDirectory() as д:
            работа = Path(д) / "работа"
            shutil.copytree(ФИКСТУРЫ / "работа-образец", работа)
            р = subprocess.run([sys.executable, str(СКРИПТЫ / "направления.py"), "--работа", str(работа)],
                               capture_output=True, text=True, timeout=180)
            self.assertEqual(р.returncode, 1, р.stdout)
            self.assertIn("направления", р.stdout.lower())

    def test_бедный_профиль_не_прячет_собранный_показ(self):
        """Неукомплектованная палитра профиля — красное про другое: пробы собрались, тёмные тона
        взяты из «Решений» работы, и снимки показывают ровно то, что увидит человек. `направления()`
        этот вердикт уже пропускает мимо своего гейта и снимает пробы; команда же спрашивала
        нефильтрованное «есть_красное» — и прятала готовый файл, не открывала его и выходила кодом 1
        ровно в том случае, ради которого бедный профиль и заводят.

        Заодно сторожит A-M4: профиль у трёх направлений ОДИН, и вердикт о нём один — сборка зовётся
        трижды и каждый раз возвращает его заново, а три одинаковые строки читаются как три беды."""
        with tempfile.TemporaryDirectory() as д:
            работа = _работа(Path(д))
            файл = Path(д) / "профиль-образец" / "profile.json"
            данные = json.loads(файл.read_text(encoding="utf-8"))
            # Та же бедная палитра, что у тестового профиля «электрик»: тёмного фона нет и вывести
            # его не из чего (копия `test_профиль.БедныйПрофиль.БЕДНАЯ`).
            данные["палитра"] = {"акцент": "#2C7A5B", "текст": "#20241F", "светлый_фон_1": "#FAF7F2"}
            файл.write_text(json.dumps(данные, ensure_ascii=False), encoding="utf-8")
            р = subprocess.run([sys.executable, str(СКРИПТЫ / "направления.py"),
                                "--работа", str(работа), "--без-показа"],
                               capture_output=True, text=True, timeout=600)
            self.assertEqual(р.returncode, 0, р.stdout + р.stderr)
            итог = работа / "показ" / "направления.html"
            self.assertTrue(итог.is_file(), р.stdout)
            self.assertIn(str(итог), р.stdout)
            self.assertEqual(р.stdout.count(профиль.СЛОВА_НЕУКОМПЛЕКТОВАН), 1,
                             "вердикт о профиле обязан быть напечатан ровно один раз:\n" + р.stdout)


if __name__ == "__main__":
    unittest.main()
