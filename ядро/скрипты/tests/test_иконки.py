"""60 иконок ядра: имена, форма файла, инлайнер."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "ядро" / "скрипты"))
import собрать  # noqa: E402

ИМЕНА = ("галочка звезда телефон телеграм ватсап почта часы календарь стрелка щит документ деньги рубль "
         "график лампочка чат камера видео микрофон картинка кисть код сердце замок карта-точка пользователь "
         "группа книга награда молния глаз скрепка дом корзина лупа плюс "
         "карандаш ножницы палитра ролик-плёнки "
         "воспроизведение пауза загрузка ссылка "
         "бирка доставка гарантия "
         "диплом ступени галочка-в-круге "
         "наушники настройки флаг папка закладка "
         "молоток гаечный-ключ розетка дверь диван").split()
ШАПКА = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
         'stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round">')


class Иконки(unittest.TestCase):
    def test_ровно_60_и_каждая_по_форме(self):
        self.assertEqual(sorted(ф.name for ф in собрать.ИКОНКИ.glob("*.svg")), sorted(f"{и}.svg" for и in ИМЕНА))
        for имя in ИМЕНА:
            текст = (собрать.ИКОНКИ / f"{имя}.svg").read_text(encoding="utf-8")
            with self.subTest(иконка=имя):
                self.assertTrue(текст.startswith(ШАПКА), "шапка не по контракту В")
                self.assertLessEqual(len(текст.strip().splitlines()), 12)
                self.assertNotRegex(текст, r'fill="(?!none)|#[0-9a-fA-F]{3,8}\b')
                self.assertRegex(текст, r"<(path|circle|rect|line|polyline)\b")

    def test_подставить_иконки(self):
        html, нет = собрать.подставить_иконки('<li>{{ИКОНКА:галочка}}<span>Да</span> {{ИКОНКА:галочка}}</li>')
        self.assertEqual((нет, html.count('<svg class="иконка" aria-hidden="true"'), "{{" in html), ([], 2, False))
        self.assertIn('stroke-width="2"', собрать.подставить_иконки("{{ИКОНКА:щит}}", толщина="2")[0])
        html, нет = собрать.подставить_иконки("<p>{{ИКОНКА:единорог}} текст {{ЗАГОЛОВОК}}</p>")
        self.assertEqual((html, нет), ("<p> текст {{ЗАГОЛОВОК}}</p>", ["единорог"]))   # чужой слот — как был
        self.assertEqual(собрать.подставить_иконки("{{ИКОНКА:../иконки/щит}} {{ИКОНКА:..\\щит}} {{ИКОНКА:a/щит}}"), ("  ", ["../иконки/щит", "..\\щит", "a/щит"]))   # путь — не имя, файл вне папки не читаем


if __name__ == "__main__":
    unittest.main()
