"""Публикация: репозиторий сайта, что поедет, закрыть/открыть поиску, отправка, Pages через подменённый gh, откат."""
import contextlib, io, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
СКРИПТЫ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(СКРИПТЫ))
import опубликовать  # noqa: E402

СТРАНИЦА = ('<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"><title>Проба</title>'
            '<meta name="robots" content="noindex, nofollow"></head><body><h1>Проба</h1></body></html>')


def _git(*а, cwd):
    return subprocess.run(["git", *а], cwd=cwd, capture_output=True, text=True, check=True).stdout


class ПубликацияТесты(unittest.TestCase):
    def setUp(self):
        self._д = tempfile.TemporaryDirectory(); д = Path(self._д.name); self.addCleanup(self._д.cleanup)
        self.работа = д / "моё-дело"; self.сайт = self.работа / "сайт"; self.сайт.mkdir(parents=True)
        (self.сайт / "index.html").write_text(СТРАНИЦА, encoding="utf-8")
        (self.сайт / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
        (self.работа / "поиск.md").write_text("# Как нас находят\n\n- Заголовок вкладки: Проба\n- Статус: закрыт\n", encoding="utf-8")
        self.полка = д / "полка.git"; self.полка.mkdir()
        _git("init", "--bare", "-b", "main", cwd=self.полка)

    def test_репозиторий_и_отправка_без_gh(self):
        опубликовать.завести_репозиторий(self.сайт)
        _git("remote", "add", "origin", str(self.полка), cwd=self.сайт)
        код, _ = опубликовать.отправить(self.сайт, "Первый экран")
        self.assertEqual(код, 0)
        self.assertIn("Первый экран", _git("log", "--oneline", cwd=self.полка))

    def test_что_поедет_помечает_личное(self):
        опубликовать.завести_репозиторий(self.сайт)
        (self.сайт / ".env").write_text("KEY=1", encoding="utf-8")
        файлы = dict((п.name, причины) for п, причины in опубликовать.что_поедет(self.сайт))
        self.assertIn("index.html", файлы); self.assertEqual(файлы["index.html"], [])
        self.assertTrue(файлы[".env"])

    def test_закрыть_открыть(self):
        self.assertTrue(опубликовать.закрыт_ли(self.сайт))
        опубликовать.открыть_поиску(self.сайт)
        self.assertFalse(опубликовать.закрыт_ли(self.сайт))
        self.assertIn("Allow: /", (self.сайт / "robots.txt").read_text(encoding="utf-8"))
        self.assertIn("Статус: открыт", (self.работа / "поиск.md").read_text(encoding="utf-8"))
        опубликовать.закрыть_от_поиска(self.сайт)
        self.assertTrue(опубликовать.закрыт_ли(self.сайт))
        self.assertIn("Статус: закрыт", (self.работа / "поиск.md").read_text(encoding="utf-8"))

    def test_сухой_прогон_не_отправляет(self):
        опубликовать.завести_репозиторий(self.сайт)
        _git("remote", "add", "origin", str(self.полка), cwd=self.сайт)
        код = опубликовать.main_с_аргументами([str(self.сайт)])
        self.assertEqual(код, 0)
        self.assertNotIn("Первый экран", subprocess.run(["git", "log", "--oneline"], cwd=self.полка, capture_output=True, text=True).stdout)

    def test_pages_через_подменённый_gh(self):
        вызовы = []
        def подмена(команда, cwd=None):
            вызовы.append(команда)
            if команда[:2] == ["gh", "api"] and "-X" in команда:
                return 0, json.dumps({"html_url": "https://кто-то.github.io/moyo-delo/"})
            if команда[:2] == ["gh", "api"]:
                return 0, json.dumps({"status": "built"})
            return 0, ""
        with patch.object(опубликовать, "запустить", подмена):
            адрес = опубликовать.включить_pages("кто-то", "moyo-delo")
            self.assertEqual(адрес, "https://кто-то.github.io/moyo-delo/")
            self.assertEqual(опубликовать.состояние_pages("кто-то", "moyo-delo"), "built")
        self.assertTrue(any("repos/кто-то/moyo-delo/pages" in " ".join(в) for в in вызовы))

    def test_имя_полки_латиницей(self):
        вывод = io.StringIO()
        with contextlib.redirect_stdout(вывод):
            код = опубликовать.main_с_аргументами([str(self.сайт), "--завести", "моё-дело", "--выкладываем"])
        self.assertEqual(код, 2)
        self.assertIn("строчн", вывод.getvalue())
        # п. 5: заглавные — не отказ, имя приводится к строчным и дальше идёт оно
        вывод = io.StringIO()
        with patch.object(опубликовать, "gh_есть", lambda: False), contextlib.redirect_stdout(вывод):
            код = опубликовать.main_с_аргументами([str(self.сайт), "--завести", "Moyo-Delo", "--выкладываем"])
        self.assertEqual(код, 3)
        self.assertIn("github.io/moyo-delo/", вывод.getvalue())
        self.assertNotIn("Moyo-Delo", вывод.getvalue())

    def test_без_gh_ручной_путь(self):
        with patch.object(опубликовать, "gh_есть", lambda: False):
            код = опубликовать.main_с_аргументами([str(self.сайт), "--завести", "moyo-delo", "--выкладываем"])
        self.assertEqual(код, 3)
        self.assertIn("Settings", опубликовать.ручной_путь("moyo-delo"))
        self.assertIn("github.io/moyo-delo", опубликовать.ручной_путь("moyo-delo"))
        # п. 6: без своего .git «git remote add origin» ушёл бы в репозиторий системы
        self.assertIn(".git", опубликовать.ручной_путь("moyo-delo"))
        self.assertTrue(опубликовать.репозиторий_есть(self.сайт))   # к моменту печати он уже есть

    def test_откат(self):
        опубликовать.завести_репозиторий(self.сайт)
        _git("remote", "add", "origin", str(self.полка), cwd=self.сайт)
        опубликовать.отправить(self.сайт, "Первый экран")
        (self.сайт / "index.html").write_text(СТРАНИЦА.replace("Проба", "Сломал"), encoding="utf-8")
        опубликовать.отправить(self.сайт, "Второй экран")
        код, _ = опубликовать.откатить(self.сайт)
        self.assertEqual(код, 0)
        self.assertIn("<h1>Проба</h1>", (self.сайт / "index.html").read_text(encoding="utf-8"))
        self.assertIn("Revert", _git("log", "--oneline", cwd=self.полка))


class ПравкиРевьюТесты(unittest.TestCase):
    """Правки ревью: гейт до первого коммита, отказ отката без риска задеть чужой репозиторий
    (единственный коммит, папка без своего .git), владелец_и_имя не путает родительский
    репозиторий, включить_pages/завести_полку не маскируют провал gh под успех,
    --выкладываем без --завести и без origin не пытается push."""

    def setUp(self):
        self._д = tempfile.TemporaryDirectory(); д = Path(self._д.name); self.addCleanup(self._д.cleanup)
        self.работа = д / "моё-дело"; self.сайт = self.работа / "сайт"; self.сайт.mkdir(parents=True)
        (self.сайт / "index.html").write_text(СТРАНИЦА, encoding="utf-8")
        (self.сайт / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
        self.полка = д / "полка.git"; self.полка.mkdir()
        _git("init", "--bare", "-b", "main", cwd=self.полка)

    def test_гейт_до_первого_коммита(self):
        # находка 1: .env не должен ни разу попасть в историю — гейт обязан остановить
        # публикацию раньше, чем что-либо закоммичено.
        (self.сайт / ".env").write_text("KEY=1", encoding="utf-8")
        код = опубликовать.main_с_аргументами([str(self.сайт), "--выкладываем"])
        self.assertEqual(код, 1)
        лог = subprocess.run(["git", "log", "--oneline"], cwd=self.сайт, capture_output=True, text=True)
        self.assertNotEqual(лог.returncode, 0)   # коммитов ещё нет вовсе

    def test_откат_единственного_коммита_отказ(self):
        опубликовать.завести_репозиторий(self.сайт)
        _git("remote", "add", "origin", str(self.полка), cwd=self.сайт)
        опубликовать.отправить(self.сайт, "Первый экран")
        код, сообщение = опубликовать.откатить(self.сайт)
        self.assertNotEqual(код, 0)
        self.assertIn("нечего", сообщение)
        self.assertNotIn("Revert", _git("log", "--oneline", cwd=self.полка))

    def test_владелец_без_своего_репозитория_не_путает_родителя(self):
        # self.работа — родитель self.сайт — становится репозиторием с настоящим origin;
        # у self.сайт своего .git нет. Без защиты владелец_и_имя поднялась бы к родителю.
        _git("init", "-b", "main", cwd=self.работа)
        _git("remote", "add", "origin", "https://github.com/чужой/чужая-полка.git", cwd=self.работа)
        self.assertEqual(опубликовать.владелец_и_имя(self.сайт), ("", ""))

    def test_pages_422_не_маскируется_под_успех(self):
        подмена = lambda команда, cwd=None: (1, "HTTP 422: Validation Failed")
        with patch.object(опубликовать, "запустить", подмена):
            self.assertEqual(опубликовать.включить_pages("кто-то", "moyo-delo"), "")

    def test_откат_без_своего_репозитория_не_трогает_родителя(self):
        # находка 1 раунда 2: у self.сайт своего .git нет, а у self.работа — есть, с двумя
        # коммитами и настоящим origin. Без защиты откатить откатил бы и запушил бы HEAD
        # РОДИТЕЛЯ (в продакшне — саму систему), а не сайт.
        _git("init", "-b", "main", cwd=self.работа)
        (self.работа / "README.md").write_text("версия 1\n", encoding="utf-8")
        _git("add", "-A", cwd=self.работа)
        _git("commit", "-m", "родительский коммит 1", cwd=self.работа)
        (self.работа / "README.md").write_text("версия 2\n", encoding="utf-8")
        _git("add", "-A", cwd=self.работа)
        _git("commit", "-m", "родительский коммит 2", cwd=self.работа)
        _git("remote", "add", "origin", str(self.полка), cwd=self.работа)
        _git("push", "-u", "origin", "main", cwd=self.работа)
        код, сообщение = опубликовать.откатить(self.сайт)
        self.assertEqual(код, 1)
        self.assertIn("своего репозитория", сообщение)
        self.assertNotIn("Revert", _git("log", "--oneline", cwd=self.полка))

    def test_завести_повторно_не_путает_старую_полку_с_успехом(self):
        # находка 2 раунда 2: у сайта уже есть GitHub-origin (со старой публикации).
        # Повторный gh repo create падает («Name already exists») — этого не должно
        # хватить, чтобы main принял старую полку за новую и записал «опубликовано».
        опубликовать.завести_репозиторий(self.сайт)
        _git("commit", "--allow-empty", "-m", "уже было опубликовано", cwd=self.сайт)
        _git("remote", "add", "origin", "https://github.com/старый/старая-полка.git", cwd=self.сайт)

        реальный = subprocess.run

        def подмена(команда, cwd=None):
            if команда[:3] == ["gh", "repo", "create"]:
                return 1, "Name already exists on this account (createRepository)"
            if команда[:2] == ["gh", "api"] and "-X" in команда:
                return 0, json.dumps({"html_url": "https://старый.github.io/старая-полка/"})
            if команда[:2] == ["gh", "api"]:
                return 0, json.dumps({"status": "built"})
            if команда[0] == "gh":
                return 1, "не должно вызываться в этом тесте"
            готово = реальный(команда, cwd=cwd, capture_output=True, text=True)
            return готово.returncode, готово.stdout + готово.stderr

        with patch.object(опубликовать, "gh_есть", lambda: True), \
             patch.object(опубликовать, "gh_вошёл", lambda: True), \
             patch.object(опубликовать, "запустить", подмена):
            код = опубликовать.main_с_аргументами(
                [str(self.сайт), "--завести", "moyo-delo", "--выкладываем"])
        self.assertEqual(код, 1)
        self.assertFalse((self.работа / "журнал.md").exists())

    def test_без_origin_и_без_завести_отказ_без_коммита(self):
        # находка 1 раунда 3: --выкладываем без --завести на свежей папке (свой .git уже
        # есть — например, после раунда с .env — но origin ещё не добавлен) не должен
        # пытаться push: голый push до первого коммита/без полки падал бы сырой git-руганью.
        with patch.object(опубликовать, "gh_есть", lambda: True), \
             patch.object(опубликовать, "gh_вошёл", lambda: True):
            код = опубликовать.main_с_аргументами([str(self.сайт), "--выкладываем"])
        self.assertEqual(код, 2)
        лог = subprocess.run(["git", "log", "--oneline"], cwd=self.сайт, capture_output=True, text=True)
        self.assertNotEqual(лог.returncode, 0)   # коммитов ещё нет вовсе


class ФиксВолнаТесты(unittest.TestCase):
    """Фикс-волна: нейтральная подпись поверх глобальной, origin не на GitHub, --открыть-поиску
    с отправкой, журнал без изменений."""

    def setUp(self):
        self._д = tempfile.TemporaryDirectory(); д = Path(self._д.name); self.addCleanup(self._д.cleanup)
        self.работа = д / "моё-дело"; self.сайт = self.работа / "сайт"; self.сайт.mkdir(parents=True)
        (self.сайт / "index.html").write_text(СТРАНИЦА, encoding="utf-8")
        (self.сайт / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
        (self.работа / "поиск.md").write_text("# Как нас находят\n\n- Заголовок вкладки: Проба\n- Статус: закрыт\n", encoding="utf-8")
        self.полка = д / "полка.git"; self.полка.mkdir()
        _git("init", "--bare", "-b", "main", cwd=self.полка)

    def _своя_полка(self):
        опубликовать.завести_репозиторий(self.сайт)
        _git("remote", "add", "origin", str(self.полка), cwd=self.сайт)

    def test_личная_почта_из_глобального_git_не_уезжает_в_историю(self):
        # п. 7: у человека после М2 глобальные user.name/user.email есть — раньше они и уезжали
        # в каждый коммит публичной полки. Глобальный конфиг подменяем файлом через GIT_CONFIG_GLOBAL.
        глобальный = Path(self._д.name) / "gitconfig"
        глобальный.write_text("[user]\n\tname = Личное Имя\n\temail = личная@почта-образец.рф\n", encoding="utf-8")
        with patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": str(глобальный)}):
            self._своя_полка()
            self.assertEqual(_git("config", "user.email", cwd=self.сайт).strip(), "личная@почта-образец.рф")
            код, _ = опубликовать.отправить(self.сайт, "Первый экран")
        self.assertEqual(код, 0)
        self.assertEqual(_git("log", "-1", "--format=%ae", cwd=self.полка).strip(), "system@local")
        self.assertEqual(_git("log", "-1", "--format=%an", cwd=self.полка).strip(), "Хозяин системы")

    def test_origin_не_на_github_называется_адресом_а_не_отсутствием_полки(self):
        # п. 10: после удачного push на не-GitHub origin печаталось «полки на GitHub нет».
        self._своя_полка()
        вывод = io.StringIO()
        with contextlib.redirect_stdout(вывод):
            код = опубликовать.main_с_аргументами([str(self.сайт), "--выкладываем"])
        self.assertEqual(код, 0, вывод.getvalue())
        self.assertIn(str(self.полка), вывод.getvalue())
        self.assertIn("не на GitHub", вывод.getvalue())
        self.assertNotIn("полки на GitHub нет", вывод.getvalue())
        self.assertNotIn("полки на GitHub ещё нет", вывод.getvalue())
        вывод = io.StringIO()
        with contextlib.redirect_stdout(вывод):
            self.assertEqual(опубликовать.main_с_аргументами([str(self.сайт), "--статус"]), 0)
        self.assertIn("не на GitHub", вывод.getvalue())

    def test_открыть_поиску_с_отправкой_попадает_в_коммит(self):
        # п. 11: флаг обязан быть закоммичен до push — HEAD полки несёт index, follow.
        self._своя_полка()
        with contextlib.redirect_stdout(io.StringIO()):
            код = опубликовать.main_с_аргументами([str(self.сайт), "--открыть-поиску", "--выкладываем"])
        self.assertEqual(код, 0)
        self.assertIn("index, follow", _git("show", "HEAD:index.html", cwd=self.полка))
        self.assertIn("Allow: /", _git("show", "HEAD:robots.txt", cwd=self.полка))
        журнал = (self.работа / "журнал.md").read_text(encoding="utf-8")
        self.assertIn("открыт поиску", журнал)
        self.assertIn("обновление отправлено на полку", журнал)

    def test_без_изменений_журнал_не_врёт_про_отправку(self):
        # п. 16: без изменений коммита нет — журнал говорит об этом, а не «отправлено».
        self._своя_полка()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(опубликовать.main_с_аргументами([str(self.сайт), "--выкладываем"]), 0)
            self.assertEqual(опубликовать.main_с_аргументами([str(self.сайт), "--выкладываем"]), 0)
        журнал = (self.работа / "журнал.md").read_text(encoding="utf-8")
        self.assertEqual(журнал.count("обновление отправлено на полку"), 1)
        self.assertIn("изменений не было", журнал)
        self.assertEqual(_git("rev-list", "--count", "HEAD", cwd=self.полка).strip(), "1")
