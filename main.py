import argparse
import json
from pathlib import Path

from app.config import load_dotenv
from app.exporter import create_ppt
from app.generator import generate_deck_from_text
from app.presentation_templates import list_presentation_templates


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Сгенерировать презентацию стартапа из свободного текста."
    )
    parser.add_argument(
        "idea_text",
        nargs="?",
        help="Свободное описание идеи, рынка и бизнеса.",
    )
    parser.add_argument(
        "--model",
        help="Необязательное переопределение модели из настроек окружения.",
    )
    parser.add_argument(
        "--template",
        choices=[template.key for template in list_presentation_templates()],
        default="neutral",
        help="Шаблон оформления презентации.",
    )
    parser.add_argument(
        "--output",
        default="output.pptx",
        help="Путь для сохранения презентации PowerPoint.",
    )
    parser.add_argument(
        "--save-json",
        help="Необязательный путь для сохранения итогового deck JSON.",
    )
    return parser


def main() -> None:
    load_dotenv()
    parser = build_arg_parser()
    args = parser.parse_args()

    idea_text = args.idea_text or input("Опишите идею стартапа: ").strip()
    if not idea_text:
        raise RuntimeError("Описание идеи обязательно.")

    print("Генерирую структуру презентации...")
    deck = generate_deck_from_text(idea_text, model=args.model, template=args.template)

    if args.save_json:
        Path(args.save_json).write_text(
            json.dumps(deck.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print("Создаю PPT...")
    create_ppt(deck, args.output, template=args.template)
    print(f"Готово! Файл сохранен в {args.output}")


if __name__ == "__main__":
    main()
