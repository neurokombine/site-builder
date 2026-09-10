"""Картинка первого экрана под схему: точка лица, кроп 9:16 под телефон, проверка выреза для схемы «центр»,
вырез фона (rembg — если стоит), петля 8 секунд и WebM с прозрачностью (ffmpeg — если стоит).
Импортирует только картинка и находки — никогда проверить, собрать, витрина (GC 17).

Запуск:
  .venv/bin/python ядро/скрипты/обложка.py <фото> --куда сайты/<имя>/img [--фокус 50,22] [--вырез] [--проверить-вырез]
  .venv/bin/python ядро/скрипты/обложка.py <ролик> --куда сайты/<имя>/video --петля [--вертикально] [--секунд 8]
  .venv/bin/python ядро/скрипты/обложка.py <ролик> --куда сайты/<имя>/video --альфа [--хромакей 00FF00] [--секунд 8]"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from картинка import КАЧЕСТВО, _открыть, имя_латиницей  # noqa: E402
from находки import вывод_в_utf8  # noqa: E402

ФОКУС_ФОТО = (50, 22)        # обычное фото: лицо по центру, в верхней трети — так снимают портрет по грудь
ДОЛЯ_ГОЛОВЫ = .18            # у выреза лицо — на 18 % высоты фигуры от макушки
ЛИЦО_В_ОКНЕ = (50, 28)       # куда кроп ставит лицо на телефоне: по центру, на 28 % высоты окна
ШИРИНА_ТЕЛЕФОНА = 900
ПРОПОРЦИЯ_ТЕЛЕФОНА = (9, 16)
ПОРОГ_АЛЬФЫ = 32
СЕКУНД = 8
ПРЕДЕЛ_ВИДЕО_МБ = 5
НЕТ_REMBG = ("Вырез сделать нечем: rembg не установлен. Или `.venv/bin/pip install rembg` (тянет модель ~170 МБ), "
             "или вырежьте фон сами — remove.bg, Canva, «Скопировать объект» на iPhone — и положите PNG с прозрачностью в img/.")
НЕТ_FFMPEG = ("Ролик собрать нечем: ffmpeg не найден. Поставить: `brew install ffmpeg` (Mac) или `winget install ffmpeg` (Windows). "
              "Или вручную: CapCut или iMovie, 6–10 секунд, без звука, mp4 не тяжелее 5 МБ, плюс кадр-постер jpg — всё в video/.")


def _альфа(картинка: Image.Image):
    """Маска непрозрачного (альфа выше порога); у картинки без альфы — None, полностью непрозрачная RGBA — тоже фото."""
    if картинка.mode != "RGBA":
        return None
    альфа = картинка.getchannel("A")
    if альфа.getextrema()[0] > ПОРОГ_АЛЬФЫ:   # ни одного прозрачного пикселя: PNG из Preview, Figma, скриншот
        return None
    return альфа.point(lambda а: 255 if а > ПОРОГ_АЛЬФЫ else 0)


def _рамка(файл: Path) -> tuple[Image.Image, tuple | None]:
    картинка = _открыть(Path(файл))
    маска = _альфа(картинка)
    return картинка, (маска.getbbox() if маска is not None else None)


def фокус(файл: Path) -> tuple[int, int]:
    """Точка лица в процентах от картинки: у выреза — середина фигуры по ширине и 18 % её высоты от
    макушки; у фото без прозрачности — ФОКУС_ФОТО. Значение идёт в data-лицо (слот {{ЛИЦО}})."""
    картинка, рамка = _рамка(файл)
    if not рамка:
        return ФОКУС_ФОТО
    л, в, п, н = рамка
    return (round((л + п) / 2 / картинка.width * 100), round((в + (н - в) * ДОЛЯ_ГОЛОВЫ) / картинка.height * 100))


def кроп_телефон(файл: Path, куда: Path, точка: tuple[int, int] | None = None) -> Path:
    """Кроп 9:16 под телефон: лицо на 28 % высоты окна, ширина ≤ 900 → <имя>-telefon.webp (слот {{ФОТО_ТЕЛЕФОН}})."""
    файл, куда = Path(файл), Path(куда)
    картинка = _открыть(файл)
    x, y = точка or фокус(файл)
    ш, в = картинка.size
    пш, пв = ПРОПОРЦИЯ_ТЕЛЕФОНА
    окно_ш, окно_в = (ш, ш * пв / пш) if ш / в < пш / пв else (в * пш / пв, в)
    лево = min(max(x / 100 * ш - ЛИЦО_В_ОКНЕ[0] / 100 * окно_ш, 0), ш - окно_ш)
    верх = min(max(y / 100 * в - ЛИЦО_В_ОКНЕ[1] / 100 * окно_в, 0), в - окно_в)
    центр = (лево / (ш - окно_ш) if ш > окно_ш else .5, верх / (в - окно_в) if в > окно_в else .5)
    итог_ш = min(ШИРИНА_ТЕЛЕФОНА, int(окно_ш))
    итог = ImageOps.fit(картинка, (итог_ш, int(итог_ш * пв / пш)), centering=центр, method=Image.Resampling.LANCZOS)
    куда.mkdir(parents=True, exist_ok=True)
    путь = куда / f"{имя_латиницей(файл.stem)}-telefon.webp"
    итог.save(путь, "WEBP", quality=КАЧЕСТВО, method=6)
    return путь


def касается_краёв(файл: Path, порог: int = 8) -> list[str]:
    """Схема «центр»: фигура не должна упираться в левый, верхний и правый края (низ — можно и нужно).
    Картинка без прозрачности — ["не вырез"]."""
    картинка, рамка = _рамка(файл)
    if not рамка:
        return ["не вырез"]
    л, в, п, _ = рамка
    return [имя for имя, беда in (("слева", л < порог), ("сверху", в < порог), ("справа", п > картинка.width - порог)) if беда]


def вырез(файл: Path, куда: Path) -> Path | None:
    """Фон долой через rembg (необязательная зависимость) → <имя>-vyrez.png; без rembg — None."""
    try:
        from rembg import remove
    except ImportError:
        return None
    файл, куда = Path(файл), Path(куда)
    куда.mkdir(parents=True, exist_ok=True)
    путь = куда / f"{имя_латиницей(файл.stem)}-vyrez.png"
    remove(_открыть(файл).convert("RGBA")).save(путь, "PNG")
    return путь


def ffmpeg_есть() -> str | None:
    return shutil.which("ffmpeg")


def _ffmpeg(*аргументы: str) -> None:
    subprocess.run([ffmpeg_есть(), "-hide_banner", "-nostdin", "-loglevel", "error", "-y", *аргументы], check=True)


def _мб(*файлы: Path) -> float:
    return round(sum(ф.stat().st_size for ф in файлы) / 1_048_576, 2)


def петля(видео: Path, куда: Path, секунд: int = СЕКУНД, вертикально: bool = False) -> dict | None:
    """Живая обложка: первые N секунд без звука, 720 по короткой стороне → webm (VP9) + mp4 (H.264) + постер jpg.
    Вертикальный вариант для телефона — суффикс -telefon. Без ffmpeg — None (CLI печатает НЕТ_FFMPEG)."""
    if not ffmpeg_есть():
        return None
    видео, куда = Path(видео), Path(куда)
    куда.mkdir(parents=True, exist_ok=True)
    основа = куда / (имя_латиницей(видео.stem) + ("-telefon" if вертикально else ""))
    масштаб = "scale=720:-2" if вертикально else "scale=-2:720"
    общие = ("-i", str(видео), "-an", "-t", str(секунд), "-vf", масштаб)
    webm, mp4, постер = основа.with_suffix(".webm"), основа.with_suffix(".mp4"), куда / (основа.name + "-poster.jpg")
    _ffmpeg(*общие, "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "34", "-row-mt", "1", str(webm))
    _ffmpeg(*общие, "-c:v", "libx264", "-crf", "28", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(mp4))
    _ffmpeg("-i", str(видео), "-vf", масштаб, "-frames:v", "1", "-q:v", "3", str(постер))
    return {"webm": webm, "mp4": mp4, "постер": постер, "мб": _мб(webm, mp4)}


def альфа_вебм(видео: Path, куда: Path, хромакей: str | None = None, секунд: int = СЕКУНД) -> dict | None:
    """Живой портрет: ролик с прозрачным фоном (как отдаёт HeyGen) или на зелёном (--хромакей 00FF00) →
    WebM VP9 с альфой <имя>-vyrez.webm и постер PNG с прозрачностью. Без ffmpeg — None."""
    if not ffmpeg_есть():
        return None
    видео, куда = Path(видео), Path(куда)
    куда.mkdir(parents=True, exist_ok=True)
    основа = куда / (имя_латиницей(видео.stem) + "-vyrez")
    фильтр = (f"chromakey=0x{хромакей}:0.12:0.1,despill=type=green," if хромакей else "") + "scale=-2:960,format=yuva420p"
    webm, постер = основа.with_suffix(".webm"), куда / (основа.name + "-poster.png")
    _ffmpeg("-i", str(видео), "-an", "-t", str(секунд), "-vf", фильтр, "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p",
            "-auto-alt-ref", "0", "-b:v", "0", "-crf", "32", str(webm))
    _ffmpeg("-c:v", "libvpx-vp9", "-i", str(webm), "-frames:v", "1", "-pix_fmt", "rgba", str(постер))
    return {"webm": webm, "постер": постер, "мб": _мб(webm)}


def построить_парсер() -> argparse.ArgumentParser:
    п = argparse.ArgumentParser(description="Картинка или ролик первого экрана под схему")
    п.add_argument("файл", type=Path)
    п.add_argument("--куда", type=Path, required=True, help="img/ или video/ работы")
    п.add_argument("--фокус", default="", help="точка лица X,Y в процентах; пусто — найти самой")
    п.add_argument("--вырез", action="store_true", help="убрать фон (rembg)")
    п.add_argument("--проверить-вырез", action="store_true", dest="проверить_вырез", help="касается ли фигура краёв (схема центр)")
    п.add_argument("--петля", action="store_true", help="ролик → webm + mp4 + постер на N секунд")
    п.add_argument("--вертикально", action="store_true", help="петля 9:16 для телефона (-telefon)")
    п.add_argument("--альфа", action="store_true", help="ролик → WebM с прозрачностью (-vyrez)")
    п.add_argument("--хромакей", default=None, help="цвет фона hex без #, например 00FF00")
    п.add_argument("--секунд", type=int, default=СЕКУНД)
    return п


def main_с_аргументами(argv) -> int:
    а = построить_парсер().parse_args(argv)
    if not а.файл.is_file():
        print(f"Нет файла: {а.файл}")
        return 1
    if а.петля or а.альфа:
        итог = альфа_вебм(а.файл, а.куда, а.хромакей, а.секунд) if а.альфа else петля(а.файл, а.куда, а.секунд, а.вертикально)
        if итог is None:
            print(НЕТ_FFMPEG)
            return 1
        тяжело = f" — тяжелее {ПРЕДЕЛ_ВИДЕО_МБ} МБ: укороти --секунд или подрежь исходник" if итог["мб"] > ПРЕДЕЛ_ВИДЕО_МБ else ""
        print("Готово: " + ", ".join(итог[к].name for к in итог if к != "мб") + f" · {итог['мб']} МБ" + тяжело)
        return 0
    источник = а.файл
    if а.вырез:
        источник = вырез(а.файл, а.куда)
        if источник is None:
            print(НЕТ_REMBG)
            return 1
        print(f"Вырез: {источник}")
    точка = tuple(int(ч) for ч in а.фокус.split(",")) if а.фокус else фокус(источник)
    print(f"Лицо: {точка[0]},{точка[1]} — это значение для data-лицо (слот {{{{ЛИЦО}}}}) и поле «Лицо смотрит» человек называет сам")
    if а.проверить_вырез:
        края = касается_краёв(источник)
        print("Края: " + (", ".join(края) if края else "не касается — годится для схемы «центр»"))
    print(f"Телефон: {кроп_телефон(источник, а.куда, точка)}")
    return 0


def main() -> int:
    вывод_в_utf8()
    return main_с_аргументами(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
