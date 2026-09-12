"""Блоки-рецепты: контракт секции, слоты только из блоки.md, нет hex, лимиты, картинки в обёртках."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "ядро" / "скрипты"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import собрать  # noqa: E402

БЛОКИ = ROOT / "ядро" / "блоки"
СЕКЦИЯ = re.compile(r'^<section class="блок блок--([а-яё-]+)((?: [а-яё-]+--[а-яё-]+)*) '
                    r'(светлый(?: второй)?|тёмный)( фон--(?:пятна|сетка|зерно))?" '
                    r'id="экран-\{\{НОМЕР\}\}" data-тип="\1"')
ОЖИДАЕМ = {"визитка": 15, "лендинг": 23}
СХЕМЫ_НАБОРА = {"визитка": ("разворот", "орбита", "сцена", "живая-сцена", "товар-крупно", "бенто", "центр", "живой-портрет"),
                "лендинг": собрать.СХЕМЫ}
# После class у обёртки может стоять `style="--…"` — объявление своей переменной (фикс-раунд Е, ниже).
ОБЁРТКА = re.compile(r'<figure class="(?:фото|мокап|картинка)[^"]*"[^>]*>.*?</figure>', re.S)
ФАЙЛЫ = [ф for набор in ОЖИДАЕМ for ф in sorted((БЛОКИ / набор).glob("*.html"))]


class Блоки(unittest.TestCase):
    карта = (ROOT / "ядро" / "блоки.md").read_text(encoding="utf-8")

    def test_в_комментариях_нет_слотов(self):
        for ф in ФАЙЛЫ:   # сборщик подставляет и в инструкцию: слот в комментарии = 🔴 у человека, стёршего абзац
            for к in re.findall(r"<!--.*?-->", ф.read_text(encoding="utf-8"), re.S):
                self.assertNotIn("{{", к, ф.name)

    def test_состав_наборов(self):
        for набор, сколько in ОЖИДАЕМ.items():
            имена = sorted(ф.name for ф in (БЛОКИ / набор).glob("*.html"))
            self.assertEqual(len(имена), сколько, имена)
            self.assertEqual(sorted(ф.stem.split("01-первый-экран-", 1)[1] for ф in (БЛОКИ / набор).glob("01-*.html")), sorted(СХЕМЫ_НАБОРА[набор]))
        self.assertLessEqual(len((БЛОКИ / "таймер.js").read_text(encoding="utf-8").splitlines()), 25)

    def test_каждый_блок_по_контракту(self):
        for ф in ФАЙЛЫ:
            текст = ф.read_text(encoding="utf-8")
            with self.subTest(файл=ф.name):
                self.assertRegex(текст.splitlines()[0], СЕКЦИЯ)
                self.assertEqual(текст.count("<section"), 1)
                self.assertIn('<div class="блок__внутри">', текст)
                if ф.name.startswith("01-"):
                    схема = ф.stem.split("01-первый-экран-", 1)[1]
                    self.assertIn(схема, СХЕМЫ_НАБОРА[ф.parent.name])
                    self.assertIn(f'data-схема="{схема}"', текст)
                    # Фикс-раунд Л, замечание 1: рецепт несёт ключ СВОЕГО макета, чтобы стили
                    # знали, где светлый ключ — родной (разворот, товар крупно, бенто: макет плоский
                    # и таким задуман), а где он перекрашен из тёмного и обязан взять ту же глубину.
                    ключ = собрать.РОДНОЙ_КЛЮЧ[схема]
                    self.assertIn(f'data-ключ-макета="{ключ}"', текст,
                                  f"{ф.name}: ключ макета разошёлся с собрать.РОДНОЙ_КЛЮЧ")
                    self.assertRegex(текст, r'data-картинка="(?:фото|вырез|видео|видео-с-голосом|живой-портрет|мозаика|мокап|товар)"')
                    if 'data-картинка="видео-с-голосом"' in текст:
                        for кусок in ('<button class="звук"', 'class="звук__почему', 'preload="auto"'):
                            self.assertIn(кусок, текст)
                    self.assertNotIn("<track", текст)
                    self.assertIn(f"первый-экран--{схема}", текст)
                    self.assertIn('первый-экран__картинка"', текст)            # GC 21: картинка обязательна
                    self.assertRegex(текст, r'<(?:img|video) [^>]*data-лицо="\{\{ЛИЦО\}\}"')
                    self.assertNotIn("data-концепция", текст)
                self.assertNotRegex(текст, r"#[0-9a-fA-F]{3,8}\b")
                # Инлайн-стиль в блоке по-прежнему запрещён — с одной узкой оговоркой (фикс-раунд Е):
                # ОБЪЯВЛЕНИЕ СОБСТВЕННОЙ ПЕРЕМЕННОЙ разметкой. Это не оформление, а замер, которого
                # стиль сам сделать не может: `--лицо-в-кадре` — доля высоты картинки, на которой стоит
                # лицо ИМЕННО ЭТОГО человека. Оформление остаётся в css-файле, здесь только число.
                for м in re.finditer(r'style="([^"]*)"', текст):
                    self.assertRegex(м.group(1).strip(), r"^(?:--[\w-]+:[^;]+;?\s*)+$",
                                     "инлайн-стиль в блоке — только объявление своей переменной")
                self.assertNotIn("object-fit", текст)
                self.assertLessEqual(len(текст.splitlines()), 140 if ф.name.startswith("01-") else 110)
                self.assertLessEqual(текст.count("{{СВЯЗЬ:"), 1)
                self.assertNotIn("кнопка--главная", текст)   # главную ставит только начинка_связи
                обёртки = [м.span() for м in ОБЁРТКА.finditer(текст)]
                for м in re.finditer(r"<img [^>]*>", текст):
                    if 'class="аватар"' not in м.group(0):
                        self.assertTrue(any(а <= м.start() < б for а, б in обёртки), "img вне .фото/.мокап/.картинка/.аватар")
                for м in re.finditer(r"<video [^>]*>", текст):
                    self.assertTrue(all(с in м.group(0) for с in ("muted", "playsinline", "poster=")), м.group(0))
                for с in собрать.ПЛЕЙСХОЛДЕР.finditer(текст):
                    if с.group(1) not in ("СВЯЗЬ", "ИКОНКА", "НОМЕР"):
                        self.assertIn(f"`{{{{{с.group(1)}}}}}`", self.карта, f"слота {с.group(1)} нет в блоки.md § 3")

    def test_фикстура_экраны_все_из_всех_рецептов(self):
        фикстура = sorted((ROOT / "ядро/скрипты/tests/фикстуры/экраны-все").glob("*.html"))
        self.assertEqual(len(фикстура), 38)
        for ф in фикстура:
            текст = ф.read_text(encoding="utf-8")
            # Решение контроллёра 3: {{СВЯЗЬ:…}} и {{ИКОНКА:…}} в фикстуре остаются — их подставляет собрать.py
            лишние = [с.group(1) for с in собрать.ПЛЕЙСХОЛДЕР.finditer(текст) if с.group(1) not in ("ИКОНКА", "СВЯЗЬ")]
            self.assertEqual(лишние, [], ф.name)
            self.assertRegex(текст, r'id="экран-\d+"')
        self.assertEqual(sorted(ф.stem for ф in фикстура if ф.name.startswith("01-")),
                         sorted(f"01-первый-экран-{с}-{н}" for н, сс in СХЕМЫ_НАБОРА.items() for с in сс))

    def test_фикстура_первых_экранов_не_отстала_от_рецептов(self):
        """Фикс-раунд Г, долг трёх раундов: фикстуру `экраны-все` правили рецепты, а её саму — нет,
        и браузерный гейт `test_флаги_дизайна` мерил вчерашние экраны, оставаясь зелёным. Теперь
        первые экраны фикстуры собираются тем же кодом, что и настоящий сайт, и этот тест каждый
        раз пересобирает их в памяти: разошлись — падаем и называем команду, а не молчим."""
        import пересобрать_фикстуру
        self.assertEqual(пересобрать_фикстуру.разошлись(), [],
                         "фикстура отстала от рецептов — пересобери: "
                         ".venv/bin/python ядро/скрипты/tests/пересобрать_фикстуру.py")


if __name__ == "__main__":
    unittest.main()
