"""Свежесть экрана: замечает ли система, что копия в работе отстала от рецепта ядра, и что она
предлагает вместо того, чтобы переписать её молча (фикс-раунд З, дело 2)."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

СКРИПТЫ = Path(__file__).resolve().parent.parent
ФИКСТУРЫ = Path(__file__).resolve().parent / "фикстуры"
sys.path.insert(0, str(СКРИПТЫ))
import находки  # noqa: E402
import свежесть  # noqa: E402
import собрать  # noqa: E402


def _образец(д: Path) -> Path:
    shutil.copytree(ФИКСТУРЫ / "работа-образец", д / "работа")
    shutil.copytree(ФИКСТУРЫ / "профиль-образец", д / "профиль-образец")
    return д / "работа"


class ЧистыеТесты(unittest.TestCase):
    def test_признаки_это_имена_классов_без_полей_дизайна(self):
        html = '<section class="блок тёмный фон--пятна"><p class="кикер">а</p></section>'
        self.assertEqual(свежесть.признаки(html), {"блок", "кикер"})

    def test_отстал_называет_то_чего_нет_в_экране(self):
        экран = '<section class="блок"><h1>Имя</h1></section>'
        свежий = '<section class="блок"><header class="шапка"></header><h1>Имя <span class="хвост">и</span></h1></section>'
        self.assertEqual(свежесть.отстал(экран, свежий), ["хвост", "шапка"])
        self.assertEqual(свежесть.отстал(свежий, экран), [])

    def test_хвост_имени_снимает_номер_экрана(self):
        self.assertEqual(свежесть.хвост_имени(Path("03-программа.html")), "программа")
        self.assertEqual(свежесть.хвост_имени(Path("01-первый-экран.html")), "первый-экран")

    def test_перенести_кадр_берёт_картинку_из_старого_экрана(self):
        старый = ('<figure class="первый-экран__картинка"><picture>'
                  '<source media="(max-width: 899px)" srcset="img/моё-telefon.webp">'
                  '<img src="img/моё.webp" alt="моя подпись" data-лицо="54,27"></picture></figure>')
        свежий = ('<figure class="картинка картинка--сцена первый-экран__картинка"><picture>'
                  '<source media="(max-width: 899px)" srcset="img/чужое-telefon.webp">'
                  '<img src="img/чужое.webp" alt="чужая" data-лицо="50,22" fetchpriority="high">'
                  "</picture></figure>")
        итог = свежесть.перенести_кадр(свежий, старый)
        for кусок in ('src="img/моё.webp"', 'srcset="img/моё-telefon.webp"',
                      'alt="моя подпись"', 'data-лицо="54,27"'):
            self.assertIn(кусок, итог, кусок)
        self.assertIn("картинка--сцена", итог)      # классы рецепта остаются рецептовы
        self.assertIn('fetchpriority="high"', итог)
        self.assertNotIn("чужое", итог)


class СверкаСРаботой(unittest.TestCase):
    def test_первый_экран_образца_не_отстал_от_рецептов(self):
        """Тот же сторож, что у фикстуры `экраны-все`: первый экран образцовой работы обязан
        совпадать с нынешним рецептом. Разошёлся — пересобрать:
        `.venv/bin/python ядро/скрипты/обновить_экран.py ядро/скрипты/tests/фикстуры/работа-образец --перезаложим`."""
        with tempfile.TemporaryDirectory() as д:
            работа = _образец(Path(д))
            жёлтые = [н["что"] for н in свежесть.сверить(работа) if н["уровень"] == находки.ПОПРАВИТЬ]
            self.assertEqual(жёлтые, [])

    def test_экраны_ниже_обложки_не_сверяются(self):
        """Гибрид: рецепт остался только у обложки. Всё ниже неё нейросеть верстает свободно —
        сверять такой экран не с чем, и «расхождение с рецептом» там означало бы, что система
        зовёт свободную вёрстку ошибкой."""
        self.assertIn("ниже обложки", свежесть.НИЖЕ_ОБЛОЖКИ)
        self.assertEqual(свежесть.почему_не_сверяется(Path("02-о-себе.html")), свежесть.НИЖЕ_ОБЛОЖКИ)
        self.assertEqual(свежесть.почему_не_сверяется(Path("09-финал.html")), свежесть.НИЖЕ_ОБЛОЖКИ)
        self.assertIsNone(свежесть.почему_не_сверяется(Path("01-первый-экран.html")))
        self.assertIsNone(свежесть.рецепт_для(Path("03-программа.html"), "лендинг"))
        with tempfile.TemporaryDirectory() as д:
            работа = _образец(Path(д))
            прочие = [н["что"] for н in свежесть.сверить(работа) if "ниже первого" in н["что"]]
            self.assertEqual(прочие, [], "сверка всё ещё судит экраны ниже обложки по рецепту")

    def test_состаренный_первый_экран_ловится_жёлтой(self):
        with tempfile.TemporaryDirectory() as д:
            работа = _образец(Path(д))
            файл = работа / "экраны" / "01-первый-экран.html"
            # состариваем копию: убираем верхнюю строку целиком, как её не было до переделки дизайна
            текст = файл.read_text(encoding="utf-8")
            начало, конец = текст.index("<header"), текст.index("</header>") + len("</header>")
            файл.write_text(текст[:начало] + текст[конец:], encoding="utf-8")
            найденное = свежесть.сверить(работа)
            жёлтые = [н for н in найденное if н["уровень"] == находки.ПОПРАВИТЬ]
            self.assertEqual(len(жёлтые), 1, найденное)
            self.assertEqual(жёлтые[0]["что"], "Первый экран отстал от рецепта ядра")
            self.assertIn("шапка", жёлтые[0]["строки"][0])
            self.assertIn("обновить_экран.py", жёлтые[0]["чем_грозит"])

    def test_сборка_показывает_находку_свежести(self):
        with tempfile.TemporaryDirectory() as д:
            работа = _образец(Path(д))
            файл = работа / "экраны" / "01-первый-экран.html"
            текст = файл.read_text(encoding="utf-8")
            начало, конец = текст.index("<header"), текст.index("</header>") + len("</header>")
            файл.write_text(текст[:начало] + текст[конец:], encoding="utf-8")
            _, найденное = собрать.собрать(работа)
            self.assertIn("Первый экран отстал от рецепта ядра", [н["что"] for н in найденное])

    def test_перезаложить_возвращает_шапку_и_бережёт_комментарий(self):
        with tempfile.TemporaryDirectory() as д:
            работа = _образец(Path(д))
            файл = работа / "экраны" / "01-первый-экран.html"
            текст = файл.read_text(encoding="utf-8")
            начало, конец = текст.index("<header"), текст.index("</header>") + len("</header>")
            метка = "<!-- почему этот экран такой: моя запись -->"
            открывающий = текст.index(">") + 1
            файл.write_text(текст[:открывающий] + "\n  " + метка + текст[открывающий:начало] + текст[конец:],
                            encoding="utf-8")
            _, новый, пропало = свежесть.перезаложить(работа)
            self.assertIn("шапка", пропало)
            self.assertIn('<header class="шапка">', новый)
            self.assertIn(метка, новый)


class КомандаОбновитьЭкран(unittest.TestCase):
    def _запустить(self, работа: Path, *флаги):
        return subprocess.run([sys.executable, str(СКРИПТЫ / "обновить_экран.py"), str(работа), *флаги],
                              capture_output=True, text=True, encoding="utf-8")

    def test_сухой_прогон_файла_не_трогает(self):
        with tempfile.TemporaryDirectory() as д:
            работа = _образец(Path(д))
            файл = работа / "экраны" / "01-первый-экран.html"
            текст = файл.read_text(encoding="utf-8")
            начало, конец = текст.index("<header"), текст.index("</header>") + len("</header>")
            состаренный = текст[:начало] + текст[конец:]
            файл.write_text(состаренный, encoding="utf-8")
            итог = self._запустить(работа)
            self.assertEqual(итог.returncode, 0, итог.stderr)
            self.assertIn("шапка", итог.stdout)
            self.assertIn("Сухой прогон", итог.stdout)
            self.assertEqual(файл.read_text(encoding="utf-8"), состаренный)

    def test_с_флагом_перезакладывает(self):
        with tempfile.TemporaryDirectory() as д:
            работа = _образец(Path(д))
            файл = работа / "экраны" / "01-первый-экран.html"
            текст = файл.read_text(encoding="utf-8")
            начало, конец = текст.index("<header"), текст.index("</header>") + len("</header>")
            файл.write_text(текст[:начало] + текст[конец:], encoding="utf-8")
            итог = self._запустить(работа, "--перезаложим")
            self.assertEqual(итог.returncode, 0, итог.stderr)
            текст_после = файл.read_text(encoding="utf-8")
            self.assertIn('<header class="шапка">', текст_после)
            # слот связи остаётся слотом: адрес ставит собрать.py из профиля той работы, которую собирают
            self.assertIn("{{СВЯЗЬ:Написать про занятия}}", текст_после)
            self.assertEqual([н for н in свежесть.сверить(работа) if н["уровень"] == находки.ПОПРАВИТЬ], [])

    def test_команда_говорит_про_экраны_ниже_обложки(self):
        """Команда перекладывает только обложку — и говорит об этом сама, а не молчит: человек,
        позвавший её ради восьмого экрана, иначе решит, что она его молча переписала."""
        with tempfile.TemporaryDirectory() as д:
            работа = _образец(Path(д))
            итог = self._запустить(работа)
            self.assertEqual(итог.returncode, 0, итог.stderr)
            self.assertIn("ниже обложки", итог.stdout)

    def test_чужая_папка_говорит_словами(self):
        итог = self._запустить(Path("сайты/такого-нет"))
        self.assertEqual(итог.returncode, 2)
        self.assertIn("Не нашёл папку работы", итог.stdout)


if __name__ == "__main__":
    unittest.main()
