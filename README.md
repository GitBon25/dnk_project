# Pitch Deck MVP

Backend-only MVP that converts free-form user text into a structured startup deck and exports it to PowerPoint.

## What it does

- accepts raw user text about a startup idea
- converts that text into a validated 8-slide deck JSON
- exports the result to `.pptx`
- exposes both CLI and API flows

## Project flow

1. user sends free-form text
2. LLM converts it into structured deck JSON
3. backend validates the deck contract
4. exporter creates a PowerPoint file

## Setup

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
```

Then put your Groq API key into `.env`.

## CLI usage

```powershell
python main.py "We build AI software for freight brokers that automates quoting, follow-up, and exception handling."
```

Optional:

```powershell
python main.py "AI workflow assistant for dental clinics" --output dental_deck.pptx --save-json dental_deck.json
```

## API usage

Start the server:

```powershell
uvicorn app.api:app --reload
```

Generate JSON:

```powershell
curl -X POST "http://127.0.0.1:8000/generate/json" ^
  -H "Content-Type: application/json" ^
  -d "{\"idea_text\":\"We build AI software for freight brokers that automates quoting, follow-up, and exception handling.\"}"
```

Generate PPT:

```powershell
curl -X POST "http://127.0.0.1:8000/generate/ppt" ^
  -H "Content-Type: application/json" ^
  -d "{\"idea_text\":\"We build AI software for freight brokers that automates quoting, follow-up, and exception handling.\"}" ^
  --output generated_deck.pptx
```

## Current architecture

- [main.py](/d:/VSCode/dnk_project/main.py): CLI entrypoint
- [app/config.py](/d:/VSCode/dnk_project/app/config.py): environment loading and settings
- [app/generator.py](/d:/VSCode/dnk_project/app/generator.py): prompt, LLM call, parsing, validation
- [app/exporter.py](/d:/VSCode/dnk_project/app/exporter.py): PowerPoint export
- [app/api.py](/d:/VSCode/dnk_project/app/api.py): FastAPI endpoints

## Next good improvements

- add retry and JSON repair flow when the model breaks schema
- support deck modes like `investor`, `sales`, and `product-demo`
- add stronger slide styling and templates
- add tests for parser and validator behavior
