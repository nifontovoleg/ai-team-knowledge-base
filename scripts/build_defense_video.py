"""Build 5–7 min defense video: slides + Edge TTS (ru-RU-DmitryNeural)."""

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

# ~6 minutes of speech when paced calmly
SECTIONS: list[dict[str, str]] = [
    {
        "title": "Защита проекта",
        "subtitle": "Система знаний команды",
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
        "subtitle": "Что сознательно не делали",
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
        "subtitle": "Панель → API → БД → поиск → LLM → quality → audit",
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
        "subtitle": "Минимум пять контролей",
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
        "subtitle": "Практический план",
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
        "subtitle": "Что дальше",
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
        "subtitle": "Ценность и результат",
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


def font(size: int) -> ImageFont.FreeTypeFont:
    path = Path(r"C:\Windows\Fonts\segoeui.ttf")
    bold = Path(r"C:\Windows\Fonts\segoeuib.ttf")
    try:
        return ImageFont.truetype(str(bold if size >= 40 else path), size)
    except OSError:
        return ImageFont.load_default()


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=fnt) <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def make_slide(idx: int, title: str, subtitle: str, out_path: Path) -> None:
    w, h = 1920, 1080
    img = Image.new("RGB", (w, h), "#0f2740")
    draw = ImageDraw.Draw(img)
    # accent bar
    draw.rectangle((0, 0, 18, h), fill="#2f6fed")
    draw.rectangle((0, h - 18, w, h), fill="#1b3a57")

    title_font = font(64)
    sub_font = font(36)
    meta_font = font(28)

    draw.text((80, 120), f"{idx + 1} / {len(SECTIONS)}", fill="#8fb3d9", font=meta_font)
    draw.text((80, 200), title, fill="#ffffff", font=title_font)

    y = 320
    for line in wrap(draw, subtitle, sub_font, w - 160):
        draw.text((80, y), line, fill="#cfe0f5", font=sub_font)
        y += 52

    footer = "Система знаний команды · защита проекта"
    draw.text((80, h - 90), footer, fill="#7f9bb8", font=meta_font)
    img.save(out_path, "PNG")


def wav_duration(path: Path) -> float:
    # edge-tts writes mp3; use ffprobe
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


async def synth_section(text: str, mp3_path: Path) -> None:
    communicate = edge_tts.Communicate(text, VOICE, rate=RATE)
    await communicate.save(str(mp3_path))


def write_script_md() -> None:
    lines = ["# Текст защиты (голос: Dmitry / ru-RU-DmitryNeural)", ""]
    for i, sec in enumerate(SECTIONS, start=1):
        lines.append(f"## {i}. {sec['title']}")
        lines.append("")
        lines.append(sec["text"])
        lines.append("")
    SCRIPT_MD.write_text("\n".join(lines), encoding="utf-8")


async def build() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True, exist_ok=True)
    write_script_md()

    concat_lines: list[str] = []
    total = 0.0
    parts: list[Path] = []

    for i, sec in enumerate(SECTIONS):
        slide = WORK / f"slide_{i:02d}.png"
        audio = WORK / f"audio_{i:02d}.mp3"
        make_slide(i, sec["title"], sec["subtitle"], slide)
        print(f"TTS {i + 1}/{len(SECTIONS)}: {sec['title']}", flush=True)
        await synth_section(sec["text"], audio)
        dur = wav_duration(audio)
        total += dur
        part = WORK / f"part_{i:02d}.mp4"
        cmd = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(slide),
            "-i",
            str(audio),
            "-c:v",
            "libx264",
            "-tune",
            "stillimage",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-pix_fmt",
            "yuv420p",
            "-shortest",
            "-t",
            f"{dur:.3f}",
            str(part),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr[-2000:] if proc.stderr else "ffmpeg part failed")
        parts.append(part)
        concat_lines.append(f"file '{part.as_posix()}'")

    list_file = WORK / "concat.txt"
    list_file.write_text("\n".join(concat_lines), encoding="utf-8")

    tmp_out = WORK / "defense.mp4"
    proc = subprocess.run(
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
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-2000:] if proc.stderr else "ffmpeg concat failed")

    shutil.copy2(tmp_out, FINAL_MP4)
    meta = {"voice": VOICE, "rate": RATE, "sections": len(SECTIONS), "duration_sec": round(total, 2)}
    (OUT / "defense_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False), flush=True)
    print(f"saved {FINAL_MP4}", flush=True)


if __name__ == "__main__":
    asyncio.run(build())
