# Pitch Deck MVP

Небольшой Python-сервис, который превращает свободное описание стартапа в структурированную презентацию на русском языке и экспортирует результат в PowerPoint (`.pptx`).

Проект поддерживает три сценария использования:
- CLI через `main.py`
- HTTP API на FastAPI
- простую веб-страницу по адресу `/`

## Что умеет

- принимает произвольное текстовое описание идеи
- генерирует JSON-структуру презентации из 8 слайдов
- проверяет схему и базовую достоверность результата
- экспортирует готовую презентацию в `.pptx`

## Как работает

1. Пользователь передает текст с описанием стартапа.
2. LLM преобразует этот текст в структурированный deck JSON.
3. Бэкенд валидирует структуру и отбрасывает неподтвержденные детали.
4. Экспортер собирает `.pptx`-файл.

## Установка

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
```

После этого укажите ключ API Groq в файле `.env`.

Пример `.env`:

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_BASE_URL=https://api.groq.com/openai/v1
PITCH_MODEL=openai/gpt-oss-120b
OUTPUT_DIR=generated
```

## Использование через CLI

Базовый запуск:

```powershell
python main.py "Мы делаем AI-сервис для логистических брокеров, который автоматизирует расчёт ставок, follow-up и обработку исключений."
```

С сохранением презентации и JSON:

```powershell
python main.py "AI-помощник для стоматологических клиник" --output dental_deck.pptx --save-json dental_deck.json
```

Поддерживаемые аргументы:
- `idea_text` — свободное описание идеи
- `--model` — переопределение модели из `.env`
- `--output` — путь к итоговому `.pptx`
- `--save-json` — путь для сохранения итогового JSON

## Использование через API

Запуск сервера:

```powershell
uvicorn app.api:app --reload
```

После запуска будут доступны:
- `GET /` — простая веб-страница для генерации deck
- `GET /health` — проверка состояния сервиса
- `POST /generate/json` — генерация JSON
- `POST /generate/ppt` — генерация и скачивание PowerPoint

Пример запроса на генерацию JSON:

```powershell
curl -X POST "http://127.0.0.1:8000/generate/json" ^
  -H "Content-Type: application/json" ^
  -d "{\"idea_text\":\"Мы создаем AI-сервис для небольших стоматологических клиник, который автоматизирует напоминания, переносы записей и ответы на типовые вопросы пациентов.\"}"
```

Пример запроса на генерацию PPT:

```powershell
curl -X POST "http://127.0.0.1:8000/generate/ppt" ^
  -H "Content-Type: application/json" ^
  -d "{\"idea_text\":\"Мы создаем AI-сервис для небольших стоматологических клиник, который автоматизирует напоминания, переносы записей и ответы на типовые вопросы пациентов.\"}" ^
  --output generated_deck.pptx
```

## Структура проекта

- [main.py](/d:/VSCode/dnk_project/main.py) — CLI-входная точка
- [app/config.py](/d:/VSCode/dnk_project/app/config.py) — загрузка окружения и настройки
- [app/generator.py](/d:/VSCode/dnk_project/app/generator.py) — промптинг, вызов модели, парсинг и валидация
- [app/exporter.py](/d:/VSCode/dnk_project/app/exporter.py) — экспорт в PowerPoint
- [app/api.py](/d:/VSCode/dnk_project/app/api.py) — FastAPI API и встроенная веб-страница
- [app/schemas.py](/d:/VSCode/dnk_project/app/schemas.py) — схема deck и структура слайдов

## Ограничения

- проект зависит от внешнего LLM API и не работает без `GROQ_API_KEY`
- качество презентации зависит от полноты исходного описания
- сервис старается не выдумывать факты, но всё равно требует ручной проверки перед реальным использованием