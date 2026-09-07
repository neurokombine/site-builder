"""Тесты служебных скриптов: что_уедет, sync_agents, глаза.

Запуск из корня репозитория:
    .venv/bin/python -m unittest discover -s ядро/скрипты/tests -t .
"""
import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

СКРИПТЫ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(СКРИПТЫ))

import глаза  # noqa: E402
import sync_agents  # noqa: E402
import что_уедет  # noqa: E402


def _git(*аргументы, cwd):
    subprocess.run(["git", *аргументы], cwd=cwd, capture_output=True, text=True, check=True)


class ЧемОпасенТесты(unittest.TestCase):
    def setUp(self):
        self._временная = tempfile.TemporaryDirectory()
        self.корень = Path(self._временная.name)
        self.addCleanup(self._временная.cleanup)

    def test_ловит_env(self):
        файл = self.корень / ".env"
        файл.write_text("SECRET=1\n", encoding="utf-8")
        причины = что_уедет.чем_опасен(файл, self.корень)
        self.assertTrue(причины, "файл .env должен считаться опасным")

    def test_ловит_профили(self):
        папка = self.корень / "профили" / "клиент-1"
        папка.mkdir(parents=True)
        файл = папка / "profile.json"
        файл.write_text("{}", encoding="utf-8")
        причины = что_уедет.чем_опасен(файл, self.корень)
        self.assertTrue(причины, "профиль с данными клиента должен считаться опасным")

    def test_пропускает_шаблон(self):
        папка = self.корень / "профили" / "_шаблон"
        папка.mkdir(parents=True)
        файл = папка / "profile.json"
        файл.write_text("{}", encoding="utf-8")
        причины = что_уедет.чем_опасен(файл, self.корень)
        self.assertEqual(причины, [], "учебный шаблон уезжает вместе с системой")

    def test_пропускает_readme_и_gitkeep_служебных_папок(self):
        # Ложное срабатывание из ревью: README.md и .gitkeep — служебные файлы
        # самой системы, а не чьи-то данные, даже когда лежат в «опасных» на вид
        # папках (профили/, сайты/).
        readme = self.корень / "профили" / "README.md"
        readme.parent.mkdir(parents=True)
        readme.write_text("Как устроены профили.\n", encoding="utf-8")
        self.assertEqual(что_уедет.чем_опасен(readme, self.корень), [])

        gitkeep = self.корень / "сайты" / ".gitkeep"
        gitkeep.parent.mkdir(parents=True)
        gitkeep.write_text("", encoding="utf-8")
        self.assertEqual(что_уедет.чем_опасен(gitkeep, self.корень), [])

        # а настоящий профиль с данными клиента по-прежнему ловится
        профиль = self.корень / "профили" / "клиент-1" / "profile.json"
        профиль.parent.mkdir(parents=True)
        профиль.write_text("{}", encoding="utf-8")
        self.assertTrue(что_уедет.чем_опасен(профиль, self.корень))

    def test_пропускает_файлы_самой_системы(self):
        # Ложное срабатывание: `ядро/скрипты/профиль.py` — скрипт системы, а не чей-то профиль.
        скрипт = self.корень / "ядро" / "скрипты" / "профиль.py"
        скрипт.parent.mkdir(parents=True)
        скрипт.write_text("# управляет профилями\n", encoding="utf-8")
        self.assertEqual(что_уедет.чем_опасен(скрипт, self.корень), [])

        # а профиль человека по-прежнему ловится
        профиль = self.корень / "профили" / "клиент-1" / "profile.json"
        профиль.parent.mkdir(parents=True)
        профиль.write_text("{}", encoding="utf-8")
        self.assertTrue(что_уедет.чем_опасен(профиль, self.корень))

        # ключ, по ошибке вписанный в файл системы, ловится и там.
        # Складываем его из кусков, иначе сам файл теста выглядит как файл с ключом.
        с_ключом = self.корень / "ядро" / "скрипты" / "настройки.py"
        с_ключом.write_text("api" + "_key" + ' = "' + "z" * 20 + '"\n', encoding="utf-8")
        self.assertTrue(что_уедет.чем_опасен(с_ключом, self.корень))

    def test_похожая_по_имени_папка_не_считается_системной(self):
        # Пропуск имённой эвристики держится на косой черте: «ядро/» — папка самой
        # системы, а «ядро-старое/» человек завёл сам, отложив прежнюю версию в сторону.
        # Профиль в ней должен пугать ровно так же, как в любой другой своей папке.
        отложенное = self.корень / "ядро-старое" / "profile.json"
        отложенное.parent.mkdir(parents=True)
        отложенное.write_text("{}", encoding="utf-8")
        self.assertTrue(что_уедет.чем_опасен(отложенное, self.корень))

        # и наоборот: тот же файл внутри самой системы — её собственный, не чей-то
        свой = self.корень / "ядро" / "скрипты" / "profile.json"
        свой.parent.mkdir(parents=True)
        свой.write_text("{}", encoding="utf-8")
        self.assertEqual(что_уедет.чем_опасен(свой, self.корень), [])


class ФайлыПодГитТесты(unittest.TestCase):
    """Находки ревью round 1: кириллические имена и папка, закрытая родительским .gitignore."""

    def setUp(self):
        self._временная = tempfile.TemporaryDirectory()
        self.корень = Path(self._временная.name)
        self.addCleanup(self._временная.cleanup)

    def test_кириллические_имена_не_экранируются(self):
        # git по умолчанию отдаёт не-ASCII имена в кавычках-октетах вида
        # "\320\277...". Без -c core.quotepath=false это сломало бы весь список:
        # система целиком на кириллических именах.
        _git("init", "-q", cwd=self.корень)
        файл = self.корень / "сайты" / "моё-дело.txt"
        файл.parent.mkdir(parents=True)
        файл.write_text("тест", encoding="utf-8")
        _git("add", "-A", cwd=self.корень)

        файлы, под_git = что_уедет.файлы_под_git(self.корень)

        self.assertTrue(под_git)
        self.assertIn(файл, файлы, "кириллическое имя должно вернуться как есть, не octal-строкой")

    def test_папка_закрытая_родительским_gitignore_считается_сама(self):
        # Сценарий шага 7: у сайта своей истории нет, а родительский репозиторий
        # системы закрывает «сайты/*» целиком — git ls-files тут отработает без
        # ошибки и вернёт пустой список, будто в папке ничего нет.
        _git("init", "-q", cwd=self.корень)
        (self.корень / ".gitignore").write_text("сайты/*\n", encoding="utf-8")
        _git("add", "-A", cwd=self.корень)

        сайт = self.корень / "сайты" / "тест-сайт"
        сайт.mkdir(parents=True)
        (сайт / "index.html").write_text("<html></html>", encoding="utf-8")
        (сайт / ".env").write_text("SECRET=1\n", encoding="utf-8")

        файлы, под_git = что_уедет.файлы_под_git(сайт)

        self.assertFalse(под_git, "у папки сайта нет своей истории — считаем сами")
        имена = {ф.name for ф in файлы}
        self.assertEqual(имена, {"index.html", ".env"}, ".env не должен потеряться молча")

    def _репозиторий_с_исключениями(self):
        """Временный репозиторий, в котором сайты/ и профили/ уже закрыты."""
        _git("init", "-q", cwd=self.корень)
        (self.корень / ".gitignore").write_text("сайты/*\nпрофили/*\n", encoding="utf-8")
        _git("add", "-A", cwd=self.корень)

    def test_новый_несохранённый_файл_попадает_в_список(self):
        # Critical финального ревью: голый `git ls-files` показывает только то, что уже
        # в истории. Файл, положенный час назад и ни разу не сохранённый, в неё не попал —
        # и скрипт молчал, хотя `версия.py сохрани` делает `git add -A` и забирает его.
        self._репозиторий_с_исключениями()
        env = self.корень / ".env"
        env.write_text("КЛЮЧ=1\n", encoding="utf-8")
        чужой_профиль = self.корень / "клиент" / "profile.json"
        чужой_профиль.parent.mkdir(parents=True)
        чужой_профиль.write_text("{}", encoding="utf-8")

        файлы, под_git = что_уедет.файлы_под_git(self.корень)

        self.assertTrue(под_git)
        self.assertIn(env, файлы, "новый .env ещё не в истории — но сохранение его заберёт")
        self.assertIn(чужой_профиль, файлы,
                      "профиль мимо папки профили/ ничем не закрыт — он уедет")
        self.assertTrue(что_уедет.чем_опасен(env, self.корень))
        self.assertTrue(что_уедет.чем_опасен(чужой_профиль, self.корень))

    def test_закрытое_в_исключениях_в_список_не_идёт(self):
        # Обратная половина: то, что человек уже закрыл, никуда не уедет — и пугать им
        # не надо, иначе список превращается в шум и его перестают читать.
        self._репозиторий_с_исключениями()
        личное = self.корень / "сайты" / "личное" / "выписка.pdf"
        личное.parent.mkdir(parents=True)
        личное.write_text("суммы", encoding="utf-8")
        свой_профиль = self.корень / "профили" / "имя" / "profile.json"
        свой_профиль.parent.mkdir(parents=True)
        свой_профиль.write_text("{}", encoding="utf-8")

        файлы, _ = что_уедет.файлы_под_git(self.корень)

        self.assertNotIn(личное, файлы)
        self.assertNotIn(свой_профиль, файлы)


class РазобратьТесты(unittest.TestCase):
    def test_парсит_шапку_и_тело(self):
        with tempfile.TemporaryDirectory() as папка:
            файл = Path(папка) / "site-checker.md"
            файл.write_text(
                "---\n"
                "name: site-checker\n"
                "description: проверяющий собранный сайт свежим взглядом\n"
                "tools: Read, Bash\n"
                "---\n"
                "Текст роли для нейросети.\n",
                encoding="utf-8",
            )
            разобранное = sync_agents.разобрать(файл)
            self.assertIsNotNone(разобранное)
            шапка, тело = разобранное
            self.assertEqual(шапка["name"], "site-checker")
            self.assertEqual(шапка["description"], "проверяющий собранный сайт свежим взглядом")
            self.assertEqual(шапка["tools"], "Read, Bash")
            self.assertEqual(тело, "Текст роли для нейросети.")

    def test_без_шапки_возвращает_none(self):
        with tempfile.TemporaryDirectory() as папка:
            файл = Path(папка) / "без-шапки.md"
            файл.write_text("Просто текст, без шапки.\n", encoding="utf-8")
            # разобрать() честно предупреждает в stdout — здесь это ожидаемо, не даём
            # этому шуму попасть в чистый вывод тестов.
            with contextlib.redirect_stdout(io.StringIO()):
                результат = sync_agents.разобрать(файл)
            self.assertIsNone(результат)


class РазмерыТесты(unittest.TestCase):
    def test_оба_размера_на_месте(self):
        self.assertIn("компьютер", глаза.РАЗМЕРЫ)
        self.assertIn("телефон", глаза.РАЗМЕРЫ)

    def test_ширины_экранов(self):
        self.assertEqual(глаза.РАЗМЕРЫ["компьютер"]["viewport"]["width"], 1440)
        self.assertEqual(глаза.РАЗМЕРЫ["компьютер"]["viewport"]["height"], 900)
        self.assertEqual(глаза.РАЗМЕРЫ["телефон"]["viewport"]["width"], 390)
        self.assertEqual(глаза.РАЗМЕРЫ["телефон"]["viewport"]["height"], 844)

    def test_телефон_мобильный_и_с_касанием(self):
        self.assertTrue(глаза.РАЗМЕРЫ["телефон"]["is_mobile"])
        self.assertTrue(глаза.РАЗМЕРЫ["телефон"]["has_touch"])


if __name__ == "__main__":
    unittest.main()
