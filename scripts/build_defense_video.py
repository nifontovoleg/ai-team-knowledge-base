"""Build defense video: real product screenshots + Edge TTS (Dmitry)."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import edge_tts

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "evidence"
WORK = Path(os.environ.get("TEMP", "/tmp")) / "kb_defense_build"
VOICE = "ru-RU-DmitryNeural"
RATE = "-15%"
FINAL_MP4 = OUT / "defense.mp4"
SCRIPT_MD = OUT / "defense_script.md"
W, H = 1920, 1080

SECTIONS: list[dict] = [
    {
        "title": "Проблема и ценность",
        "caption": "Витрина документов и ответы только по своим данным",
        "images": [
            "01-documents-showcase.png",
            "02-ask-success.png",
            "02b-ask-success-with-source-doc.png",
        ],
        "text": (
            "Здравствуйте. Представляю проект «Система знаний команды» — поиск по своим данным плюс память. "
            "Проблема простая: знания команды разбросаны по файлам и чатам, одни и те же вопросы повторяются, "
            "а ответы часто додумываются. Это опасно для онбординга и поддержки клиентов. "
            "Решение — веб-панель, где ответы строятся только по найденным фрагментам документов с цитатами. "
            "Если опоры в базе нет — система честно ставит метку ручной проверки needs review "
            "и говорит, что данных недостаточно, а не выдумывает факты. "
            "Кому полезно: новичкам в команде, менеджерам и тимлидам, которым нужна единая точка правды "
            "по внутренним правилам, шаблонам ответов и процессам."
        ),
    },
    {
        "title": "Контекст и ограничения",
        "caption": "Веб-панель, SQLite, keyword-поиск, Docker и offline-режим",
        "images": [
            "01-documents-showcase.png",
            "02-ask-success.png",
            "architecture.png",
        ],
        "text": (
            "Проект сделан как воспроизводимая учебная и рабочая витрина. "
            "Интерфейс — только веб-панель с тремя вкладками: документы, вопросы и история. "
            "База данных — SQLite. Поиск — keyword по фрагментам, без тяжёлых embeddings. "
            "Есть режим с LLM через Proxy API и offline extractive-режим без ключа. "
            "Нет ролей и разграничения доступа, нет загрузки PDF — документы подаются как текст. "
            "Эти ограничения осознанные: быстрее запуск, проще аудит и защита, "
            "проще повторить результат по README и Docker за десять минут."
        ),
    },
    {
        "title": "Архитектура",
        "caption": "Панель → FastAPI → SQLite → поиск → LLM JSON → quality → audit",
        "images": [
            "architecture.png",
            "00-architecture-drawio.png",
            "02-ask-success.png",
        ],
        "text": (
            "Архитектура линейная и прозрачная. Пользователь работает в веб-панели. "
            "Запросы принимает FastAPI. Документы и абзацы-фрагменты snippets хранятся в SQLite. "
            "По вопросу система ищет top K подходящих фрагментов. "
            "Если фрагменты найдены — они идут в LLM как context. Модель возвращает строгий JSON: "
            "answer, sources, confidence и needs review. Температура низкая — ноль целых одна десятая. "
            "Дальше контроль качества: пустые источники или низкая уверенность ведут к ручной проверке. "
            "Каждое ключевое действие пишется в таблицу audit runs: вход, выход, статус, ошибка и время. "
            "Если подходящих фрагментов нет — LLM не вызывается. "
            "Сразу безопасный ответ «данных недостаточно» и needs review равно true."
        ),
    },
    {
        "title": "Риски и меры",
        "caption": "needs_review, пустые источники, причина no_matching_snippets",
        "images": [
            "03-ask-needs-review-input.png",
            "03b-history-needs-review-card.png",
            "02-ask-success.png",
        ],
        "text": (
            "Риск первый — галлюцинации модели. Мера: ответ только по context, строгий JSON и needs review. "
            "Риск второй — утечка секретов. Мера: ключи только в env, gitignore, запрет секретов в документах. "
            "Риск третий — пустая база знаний. Мера: честный отказ без вызова модели. "
            "Риск четвёртый — нестабильный формат ответа LLM. Мера: валидация Pydantic и fallback в review. "
            "Риск пятый — потеря воспроизводимости. Мера: Docker, seed-скрипт, tests data и короткая инструкция. "
            "Дополнительно: offline-режим явно помечен в ответе, цитаты-источники обязательны."
        ),
    },
    {
        "title": "Внедрение за 1 день",
        "caption": "Документы → контрольные вопросы → история и аудит",
        "images": [
            "01-documents-showcase.png",
            "02-ask-success.png",
            "03b-history-needs-review-card.png",
        ],
        "text": (
            "План внедрения на один рабочий день. "
            "Утро: поднять сервис по README или Docker Compose, скопировать env example в env. "
            "Днём: загрузить от пяти до двадцати актуальных внутренних документов "
            "и прогнать десять контрольных вопросов из tests data. "
            "Вечером: показать операторам вкладку «требует проверки», настроить ключ LLM "
            "и проверить три curl-запроса из README. "
            "После этого команда уже может пользоваться панелью как единой точкой ответов с аудитом."
        ),
    },
    {
        "title": "План развития",
        "caption": "Экспорт, история QA и путь к гибридному поиску",
        "images": [
            "04-export-json.png",
            "05-export-csv.png",
            "architecture.png",
        ],
        "text": (
            "План развития из четырёх шагов. "
            "Первое — гибридный поиск: keyword плюс embeddings для более точного нахождения фрагментов. "
            "Второе — роли и доступ к документам, чтобы разные команды видели разные материалы. "
            "Третье — загрузка файлов PDF и Markdown без ручного копирования текста. "
            "Четвёртое — кнопка «подтвердить или исправить» для needs review "
            "с обратной записью правильного ответа в базу знаний. "
            "Так система из витрины ответов вырастет в полноценный контур управления знаниями команды."
        ),
    },
    {
        "title": "Мини-экономика и итог",
        "caption": "Ответы с источниками, review и экспорт результатов",
        "images": [
            "02-ask-success.png",
            "05-export-csv.png",
            "03b-history-needs-review-card.png",
            "01-documents-showcase.png",
        ],
        "text": (
            "Мини-экономика из отчёта. "
            "До внедрения типовой вопрос занимает около пятнадцати минут поиска по файлам и людям. "
            "После — примерно одна-две минуты: открыть панель и проверить цитаты. "
            "На ста операциях это порядка двадцати пяти часов против примерно трёх часов. "
            "Оценка на салфетке — экономия более двадцати часов на сотне однотипных вопросов "
            "онбординга или поддержки. "
            "Итог в трёх строках для портфолио. "
            "Проблема: знания разбросаны и ответы додумываются. "
            "Решение: поиск по своим документам, строгий JSON и ручная проверка. "
            "Результат: ответы с источниками, история QA, аудит и запуск по README и Docker. "
            "Спасибо за внимание. Готов ответить на вопросы."
        ),
    },
]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    regular = Path(r"C:\Windows\Fonts\segoeui.ttf")
    bold_path = Path(r"C:\Windows\Fonts\segoeuib.ttf")
    path = bold_path if bold and bold_path.exists() else regular
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.load_default()


def cover_fit(src: Image.Image, tw: int, th: int) -> Image.Image:
    """Scale image to cover target box, center-crop."""
    sw, sh = src.size
    scale = max(tw / sw, th / sh)
    nw, nh = int(sw * scale), int(sh * scale)
    resized = src.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - tw) // 2
    top = (nh - th) // 2
    return resized.crop((left, top, left + tw, top + th))


def make_frame(image_name: str, title: str, caption: str, out_path: Path) -> None:
    src_path = OUT / image_name
    if not src_path.exists():
        raise FileNotFoundError(src_path)

    base = Image.new("RGB", (W, H), "#0b1c2e")
    shot = Image.open(src_path).convert("RGB")
    # Keep a band for caption; fit screenshot into upper area
    content_h = H - 170
    fitted = cover_fit(shot, W - 80, content_h - 40)
    base.paste(fitted, (40, 30))

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((0, H - 170, W, H), fill=(8, 22, 38, 230))
    draw.rectangle((0, 0, 14, H), fill=(47, 111, 237, 255))
    base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(base)
    draw.text((40, H - 145), title, fill="#ffffff", font=font(42, bold=True))
    draw.text((40, H - 85), caption, fill="#c5d7eb", font=font(28))
    base.save(out_path, "PNG")


def probe_duration(path: Path) -> float:
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        text=True,
    ).strip()
    return float(out)


async def synth(text: str, mp3_path: Path) -> None:
    await edge_tts.Communicate(text, VOICE, rate=RATE).save(str(mp3_path))


def write_script_md() -> None:
    lines = ["# Текст защиты (голос: Dmitry / ru-RU-DmitryNeural)", ""]
    for i, sec in enumerate(SECTIONS, start=1):
        lines.append(f"## {i}. {sec['title']}")
        lines.append("")
        lines.append(f"Кадры: {', '.join(sec['images'])}")
        lines.append("")
        lines.append(sec["text"])
        lines.append("")
    SCRIPT_MD.write_text("\n".join(lines), encoding="utf-8")


def ffmpeg_ok(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-2500:] if proc.stderr else "ffmpeg failed")


async def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True, exist_ok=True)
    write_script_md()

    concat_lines: list[str] = []
    total = 0.0
    frame_i = 0

    for si, sec in enumerate(SECTIONS):
        audio = WORK / f"audio_{si:02d}.mp3"
        print(f"TTS {si + 1}/{len(SECTIONS)}: {sec['title']}", flush=True)
        await synth(sec["text"], audio)
        dur = probe_duration(audio)
        total += dur

        images = sec["images"]
        slice_dur = dur / len(images)
        part_list: list[str] = []

        for ii, image_name in enumerate(images):
            frame = WORK / f"frame_{frame_i:03d}.png"
            frame_i += 1
            make_frame(image_name, sec["title"], sec["caption"], frame)

            # Last slice absorbs rounding remainder
            this_dur = slice_dur if ii < len(images) - 1 else (dur - slice_dur * (len(images) - 1))
            this_dur = max(this_dur, 0.8)

            # Silent video for this still
            still = WORK / f"still_{si:02d}_{ii:02d}.mp4"
            ffmpeg_ok(
                [
                    "ffmpeg",
                    "-y",
                    "-loop",
                    "1",
                    "-i",
                    str(frame),
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=channel_layout=mono:sample_rate=24000",
                    "-c:v",
                    "libx264",
                    "-tune",
                    "stillimage",
                    "-c:a",
                    "aac",
                    "-pix_fmt",
                    "yuv420p",
                    "-t",
                    f"{this_dur:.3f}",
                    str(still),
                ]
            )
            part_list.append(f"file '{still.as_posix()}'")

        visuals_concat = WORK / f"visuals_{si:02d}.txt"
        visuals_concat.write_text("\n".join(part_list), encoding="utf-8")
        visuals_mp4 = WORK / f"visuals_{si:02d}.mp4"
        ffmpeg_ok(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(visuals_concat),
                "-c",
                "copy",
                str(visuals_mp4),
            ]
        )

        section_mp4 = WORK / f"section_{si:02d}.mp4"
        ffmpeg_ok(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(visuals_mp4),
                "-i",
                str(audio),
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
                str(section_mp4),
            ]
        )
        concat_lines.append(f"file '{section_mp4.as_posix()}'")

    list_file = WORK / "concat.txt"
    list_file.write_text("\n".join(concat_lines), encoding="utf-8")
    tmp_out = WORK / "defense.mp4"
    ffmpeg_ok(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c",
            "copy",
            str(tmp_out),
        ]
    )
    shutil.copy2(tmp_out, FINAL_MP4)
    meta = {
        "voice": VOICE,
        "rate": RATE,
        "sections": len(SECTIONS),
        "duration_sec": round(total, 2),
        "style": "product_screenshots",
    }
    (OUT / "defense_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False), flush=True)
    print(f"saved {FINAL_MP4}", flush=True)


if __name__ == "__main__":
    asyncio.run(build())
