from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from app.config import get_settings, load_dotenv
from app.exporter import create_ppt
from app.generator import generate_deck_from_text


load_dotenv()
app = FastAPI(title="Pitch Deck MVP API", version="0.1.0")

INDEX_HTML = """
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pitch Deck MVP</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f3ec;
      --surface: #fffdf8;
      --border: #d9d2c5;
      --text: #1b1f26;
      --muted: #69707d;
      --accent: #c95c37;
      --accent-dark: #8d3a1d;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Aptos, Segoe UI, sans-serif;
      background: var(--bg);
      color: var(--text);
    }
    .wrap {
      max-width: 980px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }
    h1 {
      margin: 0 0 8px;
      font-size: 32px;
    }
    p {
      margin: 0;
      color: var(--muted);
      line-height: 1.5;
    }
    .card {
      margin-top: 24px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 18px;
    }
    label {
      display: block;
      margin-bottom: 8px;
      font-size: 14px;
      font-weight: 600;
    }
    textarea, input, select {
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px 14px;
      font: inherit;
      color: var(--text);
      background: #fff;
    }
    textarea {
      min-height: 220px;
      resize: vertical;
      line-height: 1.45;
    }
    .grid {
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 16px;
      margin-top: 16px;
    }
    .actions {
      display: flex;
      gap: 12px;
      margin-top: 18px;
      flex-wrap: wrap;
    }
    button {
      border: 0;
      border-radius: 10px;
      padding: 12px 16px;
      font: inherit;
      font-weight: 600;
      cursor: pointer;
    }
    .primary {
      background: var(--accent);
      color: white;
    }
    .secondary {
      background: #efe7da;
      color: var(--accent-dark);
    }
    .status {
      margin-top: 14px;
      min-height: 22px;
      color: var(--muted);
      font-size: 14px;
    }
    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: Consolas, monospace;
      font-size: 13px;
      line-height: 1.5;
    }
    @media (max-width: 720px) {
      .grid { grid-template-columns: 1fr; }
      .wrap { padding: 20px 14px 36px; }
    }
  </style>
</head>
<body>
  <main class="wrap">
    <h1>Pitch Deck MVP</h1>
    <p>Вставьте описание идеи, сгенерируйте структуру презентации или скачайте PowerPoint.</p>

    <section class="card">
      <label for="ideaText">Описание стартапа</label>
      <textarea id="ideaText" placeholder="Опишите продукт, аудиторию, проблему, ценность, монетизацию и стратегию выхода на рынок."></textarea>

      <div class="grid">
        <div>
          <label for="model">Модель</label>
          <input id="model" placeholder="Необязательно, можно оставить пустым">
        </div>
        <div>
          <label for="mode">Действие</label>
          <select id="mode">
            <option value="json">Сгенерировать JSON</option>
            <option value="ppt">Скачать PPT</option>
          </select>
        </div>
      </div>

      <div class="actions">
        <button class="primary" id="runButton">Сгенерировать</button>
        <button class="secondary" id="sampleButton" type="button">Вставить пример</button>
      </div>

      <div class="status" id="status"></div>
    </section>

    <section class="card">
      <label>Ответ</label>
      <pre id="output">Пока ничего не сгенерировано.</pre>
    </section>
  </main>

  <script>
    const ideaText = document.getElementById("ideaText");
    const model = document.getElementById("model");
    const mode = document.getElementById("mode");
    const status = document.getElementById("status");
    const output = document.getElementById("output");
    const runButton = document.getElementById("runButton");
    const sampleButton = document.getElementById("sampleButton");

    const sampleText = "Мы создаем AI-сервис для небольших стоматологических клиник. Сегодня администраторы тратят много времени на подтверждение записей, переносы визитов и ответы на типовые вопросы пациентов. Из-за этого клиники теряют время сотрудников, получают пропущенные приемы и недозагружают расписание врачей. Наш продукт автоматизирует напоминания, помогает пациентам быстро перенести запись и собирает всю коммуникацию в одном рабочем окне. Основные клиенты — частные стоматологии с небольшой командой и слабой автоматизацией процессов. Мы хотим продавать продукт по подписке для клиники, а позже добавить расширенную аналитику и инструменты для управления загрузкой врачей. На старте планируем искать первых клиентов через прямые продажи, рекомендации и общение с владельцами клиник. В будущем хотим стать операционной AI-платформой для малого медицинского бизнеса.";

    sampleButton.addEventListener("click", () => {
      ideaText.value = sampleText;
    });

    runButton.addEventListener("click", async () => {
      const text = ideaText.value.trim();
      if (!text) {
        status.textContent = "Сначала добавьте описание стартапа.";
        return;
      }

      const payload = { idea_text: text, model: model.value.trim() || null };
      const target = mode.value === "ppt" ? "/generate/ppt" : "/generate/json";
      status.textContent = "Идет генерация...";
      output.textContent = "Ожидание ответа...";
      runButton.disabled = true;

      try {
        const response = await fetch(target, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });

        if (!response.ok) {
          const error = await response.json().catch(() => ({ detail: "Запрос завершился ошибкой." }));
          throw new Error(error.detail || "Запрос завершился ошибкой.");
        }

        if (mode.value === "ppt") {
          const blob = await response.blob();
          const url = URL.createObjectURL(blob);
          const anchor = document.createElement("a");
          anchor.href = url;
          anchor.download = "pitch_deck.pptx";
          anchor.click();
          URL.revokeObjectURL(url);
          status.textContent = "Презентация готова, скачивание началось.";
          output.textContent = "PPT-файл успешно создан и скачан.";
        } else {
          const data = await response.json();
          output.textContent = JSON.stringify(data, null, 2);
          status.textContent = "JSON deck успешно сгенерирован.";
        }
      } catch (error) {
        status.textContent = "Во время генерации произошла ошибка.";
        output.textContent = error.message;
      } finally {
        runButton.disabled = false;
      }
    });
  </script>
</body>
</html>
"""


class GenerateRequest(BaseModel):
    idea_text: str = Field(..., min_length=20, description="Свободное описание стартапа.")
    model: str | None = Field(default=None, description="Необязательное переопределение модели.")


class DeckResponse(BaseModel):
    startup_name: str
    one_liner: str
    audience: str
    tone: str
    info_gaps: list[str]
    slides: list[dict[str, list[str] | str]]


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return INDEX_HTML


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/generate/json", response_model=DeckResponse)
def generate_json(request: GenerateRequest) -> dict:
    try:
        deck = generate_deck_from_text(request.idea_text, model=request.model)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return deck.to_dict()


@app.post("/generate/ppt")
def generate_ppt(request: GenerateRequest) -> FileResponse:
    try:
        deck = generate_deck_from_text(request.idea_text, model=request.model)
        settings = get_settings()
        output_dir = Path(settings.output_dir)
        output_path = output_dir / f"{uuid4().hex}.pptx"
        create_ppt(deck, str(output_path))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return FileResponse(
        path=output_path,
        media_type=(
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        ),
        filename=f"{deck.startup_name.replace(' ', '_').lower()}_deck.pptx",
    )
