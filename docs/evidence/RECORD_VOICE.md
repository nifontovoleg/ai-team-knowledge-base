# Запись своего голоса для защиты

## 1. Откройте телесуфлёр

Дважды кликните файл (или перетащите в браузер):

`docs/evidence/teleprompter.html`

## 2. Референс-аудио (как эталон темпа)

`docs/evidence/defense_reference_dmitry.mp3` — озвучка Dmitry (~6:40).

В телесуфлёре: нажмите **«Синхр. с аудио»** → **«Старт прокрутки»** — текст будет идти в такт записи. Читайте **своим** голосом в микрофон.

## 3. Запись

- **Win+G** → «Запись» → включите микрофон (можно без экрана, только звук).
- Или **Audacity** → запись → Export MP3.

Сохраните как: `docs/evidence/defense_my_voice.mp3`

## 4. Подставить ваш голос в видео

```powershell
python -m scripts.replace_defense_audio docs/evidence/defense_my_voice.mp3
```

Старый ролик сохранится в `defense_dmitry_backup.mp4`.

## 5. Загрузить на Google Диск

Обновите ссылку в `docs/REPORT.md` или пришлите ссылку для вставки.
