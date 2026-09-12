"""обложки.py: подбор картинок под тип, все схемы набора на текстах, палитре и картинке; каталог без копий медиа."""
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "ядро" / "скрипты"))
import витрина  # noqa: E402
import глаза  # noqa: E402
import находки  # noqa: E402
import обложки  # noqa: E402

ФИКСТУРЫ = ROOT / "ядро" / "скрипты" / "tests" / "фикстуры"
# Задача 6: «разворот-слева» — не рецепт, а карточка каталога поверх «разворот» с forced стороной
# (обложки.py, схемы_набора) — вставлена в список сразу за «разворот».
ВИЗИТКА = ("разворот", "разворот-слева", "орбита", "сцена", "живая-сцена", "товар-крупно", "бенто", "центр", "живой-портрет")


def _скопировать_образец(д: Path) -> Path:
    shutil.copytree(ФИКСТУРЫ / "работа-образец", д / "работа")
    shutil.copytree(ФИКСТУРЫ / "профиль-образец", д / "профиль-образец")
    return д / "работа"


def _материалы(работа: Path) -> None:
    """Файлы по контракту З: фото 3:4, вырез, кадр 16:9, экран, товар 9:16, голос, живая, портрет-вырез, три ролика."""
    img, video = работа / "img", работа / "video"
    for имя in ("portret-3x4.webp", "stsena-16x9.webp", "ekran.webp", "tovar-9x16.webp"):
        Image.new("RGB", (40, 30), (9, 9, 9)).save(img / имя)
    вырез = Image.new("RGBA", (40, 60), (0, 0, 0, 0))
    вырез.paste((1, 2, 3, 255), (10, 6, 30, 56))
    вырез.save(img / "portret-vyrez.png")
    for имя in ("golos.mp4", "golos-poster.jpg", "zhivaya.mp4", "zhivaya.webm", "zhivaya-telefon.mp4", "zhivaya-poster.jpg",
                "zhivaya-telefon-poster.jpg", "portret-vyrez.webm", "portret-vyrez-poster.png",
                "rolik-1.mp4", "rolik-1-poster.jpg", "rolik-2.mp4", "rolik-2-poster.jpg", "rolik-3.mp4"):
        (video / имя).write_bytes(b"")


class Правила(unittest.TestCase):
    def test_рекомендации(self):
        т = {"фото": "a.jpg", "видео": "", "цифры": [1, 2, 3]}
        self.assertEqual(list(обложки.рекомендации(т, "визитка")), ["разворот"])
        self.assertEqual(list(обложки.рекомендации(т, "лендинг")), ["разворот", "орбита"])
        self.assertEqual(list(обложки.рекомендации({**т, "видео": "v"}, "лендинг")), ["живая-обложка", "разворот"])
        self.assertEqual(list(обложки.рекомендации({**т, "видео": "v", "голос": "g"}, "визитка")), ["живая-сцена", "разворот"])
        self.assertEqual(list(обложки.рекомендации({"фото": "", "видео": "", "цифры": []}, "визитка")), ["сцена"])
        for почему in обложки.рекомендации(т, "лендинг").values():
            self.assertGreater(len(почему), 30)

    def test_схемы_набора(self):
        self.assertEqual(tuple(обложки.схемы_набора("визитка")), ВИЗИТКА)
        self.assertEqual(len(обложки.схемы_набора("лендинг")), 12)   # одиннадцать рецептов + карточка «разворот-слева»
        self.assertEqual(tuple(обложки.схемы_набора("нет-такого")), ВИЗИТКА)

    def test_подбор_картинок_под_тип(self):
        with tempfile.TemporaryDirectory() as д:
            работа = _скопировать_образец(Path(д))
            _материалы(работа)
            к = обложки.картинки_для_схем(работа, "лендинг", {"фото": "пример.svg", "видео": "", "постер": ""})
            self.assertEqual(к["разворот"]["фото"], "portret-3x4.webp")
            self.assertEqual(к["сцена"]["фото"], "stsena-16x9.webp")
            self.assertEqual(к["бенто"]["фото"], "stsena-16x9.webp")
            self.assertEqual((к["орбита"]["фото"], к["центр"]["лицо"]), ("portret-vyrez.png", "50,25"))
            self.assertEqual(к["афиша-с-экраном"]["фото"], "ekran.webp")
            self.assertEqual(к["товар-крупно"]["фото"], "tovar-9x16.webp")
            self.assertEqual((к["живая-сцена"]["видео"], к["живая-сцена"]["постер"]), ("golos", "golos-poster.jpg"))
            self.assertEqual((к["живая-обложка"]["видео"], к["живая-обложка"]["видео_телефон"], к["живая-обложка"]["постер_телефон"]),
                             ("zhivaya", "zhivaya-telefon", "zhivaya-telefon-poster.jpg"))
            self.assertEqual((к["живой-портрет"]["видео"], к["живой-портрет"]["постер"]), ("portret-vyrez", "portret-vyrez-poster.png"))
            self.assertEqual(к["мозаика-роликов"]["ролики"], [("rolik-1", "rolik-1-poster.jpg"), ("rolik-2", "rolik-2-poster.jpg"), ("rolik-3", "кадр.svg")])
            пусто = обложки.картинки_для_схем(работа / "нет", "визитка", {"фото": "", "видео": "", "постер": ""})
            self.assertEqual((пусто["разворот"]["фото"], пусто["живой-портрет"]["видео"], пусто["орбита"]["лицо"]), ("", "", "50,22"))
            self.assertEqual(tuple(обложки.картинки_для_схем(работа, "нет-такого", {"фото": "", "видео": "", "постер": ""})), ВИЗИТКА)   # чужой пресет → визитка, не FileNotFoundError

    def test_каталог_заглушки_ведут_в_ядро(self):
        """В каталоге медиа — по ссылке в папку работы, а силуэт и кадр — в ядро/блоки/заглушки: в папке примера их нет."""
        with tempfile.TemporaryDirectory() as д:
            работа = _скопировать_образец(Path(д))
            своя = Path(д) / "каталог" / "обложка-разворот"
            своя.mkdir(parents=True)
            html = обложки._в_каталог('<img src="img/пример.svg"><img src="img/силуэт.svg"><video poster="video/кадр.svg">'
                                      '<source src="video/пример.mp4"><img src="video/кадр.svg">', работа, своя)
            self.assertIn('src="../../работа/img/пример.svg"', html)
            self.assertIn('src="../../работа/video/пример.mp4"', html)
            self.assertNotIn("работа/img/силуэт.svg", html)
            self.assertNotIn("работа/video/кадр.svg", html)
            ссылки = re.findall(r'"([^"]*(?:силуэт|кадр)\.svg)"', html)
            self.assertEqual(len(ссылки), 3)
            for ссылка in ссылки:
                self.assertTrue((своя / ссылка).resolve().is_file(), ссылка)
                self.assertEqual((своя / ссылка).resolve().parent, витрина.ЗАГЛУШКИ.resolve())

    def test_каталог_не_ломает_тип_видео(self):
        """Задача 4: замена путей '"video/' → к_работе не должна трогать type="video/mp4" — иначе браузер не узнаёт
        MIME-тип источника и пропускает его (живая сцена показывает только постер). src/poster переписываются как раньше."""
        with tempfile.TemporaryDirectory() as д:
            работа = _скопировать_образец(Path(д))
            своя = Path(д) / "каталог" / "обложка-живая-сцена"
            своя.mkdir(parents=True)
            html = обложки._в_каталог(
                '<video poster="video/golos-poster.jpg" data-телефон="video/zhivaya-telefon.mp4" '
                'data-телефон-постер="video/zhivaya-telefon-poster.jpg">'
                '<source src="video/golos.mp4" type="video/mp4"><source src="video/zhivaya.webm" type="video/webm">'
                '</video>', работа, своя)
            self.assertIn('type="video/mp4"', html)
            self.assertIn('type="video/webm"', html)
            self.assertIn('src="../../работа/video/golos.mp4"', html)
            self.assertIn('poster="../../работа/video/golos-poster.jpg"', html)
            self.assertIn('data-телефон="../../работа/video/zhivaya-telefon.mp4"', html)
            self.assertIn('data-телефон-постер="../../работа/video/zhivaya-telefon-poster.jpg"', html)

    def test_картинка_под_схему_разбирается_словами(self):
        """Фикс-раунд Ж, дела 2 и 3: до сборки сайта система говорит, что не так с картинкой под схему —
        вырез не человека у схем с вырезом и слишком близкий кадр у схем с плашкой «имя · опора».
        Раньше оба случая проходили молча, и человек узнавал о них по готовому сайту."""
        with tempfile.TemporaryDirectory() as д:
            работа = _скопировать_образец(Path(д))
            _материалы(работа)   # portret-vyrez.png — прямоугольник: вырез, но не человек
            по_схемам = обложки.картинки_для_схем(работа, "визитка", {"фото": "", "видео": "", "постер": ""})
            что = [н["что"] for н in обложки.находки_картинок(работа, "визитка", по_схемам)]
            self.assertIn("Схеме «орбита» нужен вырез человека", что)
            self.assertIn("Схеме «центр» нужен вырез человека", что)
            [н] = [н for н in обложки.находки_картинок(работа, "визитка", по_схемам) if н["что"].startswith("Схеме «орбита»")]
            self.assertIn("вырез без человека", н["строки"][0])
            self.assertIn("выберите схему без выреза", н["чем_грозит"])
            # у разворота фотография-заглушка: голову на ней не видно — просим проверить кадр самому,
            # но только в примерке: каталог — пример, а не чья-то работа
            просьба = [н for н in что if н.startswith("Кадр для схемы")]
            self.assertEqual(просьба, ["Кадр для схемы «разворот» может быть слишком близким",
                                       "Кадр для схемы «разворот-слева» может быть слишком близким"], что)
            в_каталоге = [н["что"] for н in обложки.находки_картинок(работа, "визитка", по_схемам, каталог=True)]
            self.assertEqual([н for н in в_каталоге if н.startswith("Кадр для схемы")], [])
            # а измеримо близкий кадр называется замером и в каталоге тоже
            фигура = Image.new("RGBA", (400, 600), (0, 0, 0, 0))
            from PIL import ImageDraw
            р = ImageDraw.Draw(фигура)
            р.ellipse((120, 30, 280, 330), fill=(120, 90, 60, 255))          # голова во весь кадр
            р.rectangle((170, 300, 230, 360), fill=(120, 90, 60, 255))
            р.rectangle((60, 355, 340, 600), fill=(120, 90, 60, 255))
            фигура.save(работа / "img" / "portret-3x4.webp")
            по_схемам = обложки.картинки_для_схем(работа, "визитка", {"фото": "", "видео": "", "постер": ""})
            близко = [н for н in обложки.находки_картинок(работа, "визитка", по_схемам, каталог=True)
                      if н["что"].startswith("Кадр для схемы")]
            self.assertEqual(len(близко), 2, близко)
            self.assertIn("кадр слишком близкий", близко[0]["строки"][0])
            self.assertEqual(близко[0]["уровень"], находки.ПОПРАВИТЬ)

    def test_без_палитры_красное(self):
        with tempfile.TemporaryDirectory() as д:
            работа = _скопировать_образец(Path(д))
            дизайн = работа / "дизайн.md"
            дизайн.write_text(дизайн.read_text(encoding="utf-8").split("## Решения")[0], encoding="utf-8")
            путь, н = обложки.обложки(работа, куда=Path(д) / "витрина")
            self.assertEqual([x["что"] for x in н if x["уровень"] == находки.ЧИНИТЬ], ["Палитра ещё не выбрана"])
            self.assertFalse(путь.exists())


class ВБраузере(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls._playwright = sync_playwright().start()
        cls.браузер = глаза.запустить_браузер(cls._playwright)

    @classmethod
    def tearDownClass(cls):
        cls.браузер.close()
        cls._playwright.stop()

    def test_девять_обложек_образца(self):
        with tempfile.TemporaryDirectory() as д:
            работа = _скопировать_образец(Path(д))
            путь, н = обложки.обложки(работа, куда=Path(д) / "витрина", браузер=self.браузер, сторона="слева")
            self.assertFalse(находки.есть_красное(н), н)
            self.assertNotIn("Картинки первого экрана ещё нет", [x["что"] for x in н])
            текст = путь.read_text(encoding="utf-8")
            for номер, схема in enumerate(ВИЗИТКА, 1):
                папка = Path(д) / "витрина" / f"обложка-{схема}"
                страница = (папка / "index.html").read_text(encoding="utf-8")
                # «разворот-слева» рендерится рецептом «разворот» (задача 6) — data-схема в разметке своя.
                self.assertIn(f'data-схема="{"разворот" if схема == "разворот-слева" else схема}"', страница)
                self.assertIn("сторона--слева", страница.split("</section>")[0])
                self.assertIn('data-лицо="50,22"', страница)
                self.assertNotIn("{{", страница)
                self.assertIn("--цвет-акцент", страница)                       # палитра из Решений
                for файл in ("компьютер.jpg", "телефон.jpg", "style.css", "img/пример.svg", "video/пример.webm", "img/силуэт.svg"):
                    self.assertTrue((папка / файл).is_file(), файл)
                self.assertIn(f"{номер} · {схема}", текст)
                self.assertIn(f"обложка-{схема}/index.html", текст)
            живая = (Path(д) / "витрина" / "обложка-живая-сцена" / "index.html").read_text(encoding="utf-8")
            self.assertEqual(живая.count("<script>"), 2)                       # обложка.js + звук.js
            self.assertIn("рекомендую", текст)
            self.assertIn("номер · сторона", текст)
            self.assertIn("слева", текст.split("Что ответить")[1])

    def test_ничего_не_уезжает_под_липкую_кнопку(self):
        """Приёмка фикса И: липкая панель прибита к низу ОКНА и закрывает нижние ~80 px на любой
        прокрутке, а первый экран у восьми схем выше окна телефона. Резерв под панель держит вся
        семья первого экрана, а не три схемы с текстом у нижней кромки: у разворота под панель
        уезжали «Ближайший старт» и строка лицензии, у мозаики и афиши — бегущая строка."""
        СЧИТАЕМ = """() => {
            const s = document.querySelector('section.блок--первый-экран');
            const кн = document.querySelector('.липкая-кнопка');
            if (!кн) return ['липкой кнопки нет'];
            window.scrollTo(0, Math.max(0, s.getBoundingClientRect().height - window.innerHeight));
            const кромка = кн.getBoundingClientRect().top, под = [];
            s.querySelectorAll('*').forEach(e => {
                if (e.children.length) return;
                const b = e.getBoundingClientRect(), т = (e.textContent || '').trim();
                if (!т || !b.height) return;
                if (b.bottom > кромка + 1) под.push(т.slice(0, 30));
            });
            return под; }"""
        with tempfile.TemporaryDirectory() as д:
            работа = _скопировать_образец(Path(д))
            обложки.обложки(работа, куда=Path(д) / "каталог", браузер=self.браузер, каталог=True)
            контекст = self.браузер.new_context(**глаза.РАЗМЕРЫ["телефон"])
            try:
                for папка in sorted((Path(д) / "каталог").glob("обложка-*")):
                    страница = контекст.new_page()
                    страница.goto((папка / "index.html").as_uri())
                    страница.wait_for_timeout(150)
                    self.assertEqual(страница.evaluate(СЧИТАЕМ), [], f"{папка.name}: уехало под липкую кнопку")
                    страница.close()
            finally:
                контекст.close()

    def test_каталог_без_копий_медиа(self):
        with tempfile.TemporaryDirectory() as д:
            работа = _скопировать_образец(Path(д))
            путь, н = обложки.обложки(работа, куда=Path(д) / "каталог", браузер=self.браузер, каталог=True)
            self.assertFalse(находки.есть_красное(н), н)
            папка = Path(д) / "каталог" / "обложка-разворот"
            страница = (папка / "index.html").read_text(encoding="utf-8")
            self.assertIn('src="../../работа/img/пример.svg"', страница)
            self.assertFalse((папка / "img").exists())
            self.assertIn('poster="../../работа/video/', (Path(д) / "каталог" / "обложка-живая-сцена" / "index.html").read_text(encoding="utf-8"))
            self.assertTrue((папка / "компьютер.jpg").is_file())
            for схема in ВИЗИТКА:   # заглушки никогда не ведут в папку работы; если есть — файл существует
                своя = Path(д) / "каталог" / f"обложка-{схема}"
                html = (своя / "index.html").read_text(encoding="utf-8")
                self.assertNotIn("работа/img/силуэт.svg", html)
                self.assertNotIn("работа/video/кадр.svg", html)
                for ссылка in re.findall(r'"([^"]*(?:силуэт|кадр)\.svg)"', html):
                    self.assertTrue((своя / ссылка).resolve().is_file(), ссылка)
            текст = путь.read_text(encoding="utf-8")
            self.assertIn("Каталог схем первого экрана", текст)
            self.assertIn("обложки.py сайты/", текст)

    def test_без_картинки_силуэт_и_жёлтое(self):
        with tempfile.TemporaryDirectory() as д:
            работа = _скопировать_образец(Path(д))
            shutil.rmtree(работа / "img")
            путь, н = обложки.обложки(работа, куда=Path(д) / "витрина", браузер=self.браузер)
            self.assertIn("Картинки первого экрана ещё нет", [x["что"] for x in н])
            self.assertFalse(находки.есть_красное(н), н)
            self.assertIn('src="img/силуэт.svg"', (Path(д) / "витрина" / "обложка-разворот" / "index.html").read_text(encoding="utf-8"))
            self.assertIn("силуэт", путь.read_text(encoding="utf-8"))

    def test_карточка_мессенджера_напоминает_пересобрать(self):
        """Задача 10, п. 6: og:image не пересобирается сам (для этого нужен человек и картинка.py),
        но система честно напоминает, что старая карточка могла остаться от прошлой схемы."""
        with tempfile.TemporaryDirectory() as д:
            работа = _скопировать_образец(Path(д))
            поиск = работа / "поиск.md"
            поиск.write_text(поиск.read_text(encoding="utf-8").replace("Картинка карточки: нет", "Картинка карточки: img/card.jpg"),
                              encoding="utf-8")
            путь, н = обложки.обложки(работа, куда=Path(д) / "витрина", браузер=self.браузер)
            self.assertFalse(находки.есть_красное(н), н)
            self.assertIn("Картинка карточки в мессенджере может остаться от прошлой схемы", [x["что"] for x in н])
            # каталог — не «моё дело», напоминание про пересборку там неуместно
            _, н2 = обложки.обложки(обложки.ПРИМЕР, куда=Path(д) / "каталог", браузер=self.браузер, каталог=True)
            self.assertNotIn("Картинка карточки в мессенджере может остаться от прошлой схемы", [x["что"] for x in н2])

    def test_визитке_с_альфа_роликом_рекомендуют_живой_портрет(self):
        """Сквозное ревью 3 (дыра T4): у визитки в video/ только portret-vyrez.webm — mp4 нет, но живой портрет рекомендуется через обложки()."""
        with tempfile.TemporaryDirectory() as д:
            работа = _скопировать_образец(Path(д))
            shutil.rmtree(работа / "video")
            (работа / "video").mkdir()
            for имя in ("portret-vyrez.webm", "portret-vyrez-poster.png"):
                (работа / "video" / имя).write_bytes(b"")
            путь, н = обложки.обложки(работа, куда=Path(д) / "витрина", браузер=self.браузер)
            self.assertFalse(находки.есть_красное(н), н)
            текст = путь.read_text(encoding="utf-8")
            портрет = текст.split("· живой-портрет</h2>")[1].split("</section>")[0]
            self.assertIn("рекомендую — вырез с движением уже есть", портрет)
            self.assertNotIn("рекомендую", текст.split("· живая-сцена</h2>")[1].split("</section>")[0])   # речи нет — живая сцена не рекомендуется
            self.assertIn('<source src="video/portret-vyrez.webm"', (Path(д) / "витрина" / "обложка-живой-портрет" / "index.html").read_text(encoding="utf-8"))

    def test_cli_без_показа(self):
        with tempfile.TemporaryDirectory() as д:
            работа = _скопировать_образец(Path(д))
            р = subprocess.run([sys.executable, str(ROOT / "ядро/скрипты/обложки.py"), str(работа), "--сторона", "справа", "--без-показа"],
                               capture_output=True, text=True, timeout=300)
            self.assertEqual(р.returncode, 0, р.stdout[-2000:] + р.stderr[-2000:])
            self.assertIn("# Обложки:", р.stdout)
            self.assertTrue((работа / "витрина" / "обложки.html").is_file())


if __name__ == "__main__":
    unittest.main()
