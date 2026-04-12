import json
import re
from typing import Any

from openai import OpenAI

from app.config import get_settings
from app.schemas import PitchDeck, SLIDE_STRUCTURE, Slide

UNSUPPORTED_SPECIFIC_PHRASES = [
    "whatsapp",
    "telegram",
    "email",
    "sms",
    "linkedin",
    "crm integrator",
    "crm integrators",
    "founders' network",
    "founder's network",
    "local crm",
    "load balancing",
    "pilot",
    "pilots",
    "case study",
    "case studies",
    "webinar",
    "webinars",
    "пилот",
    "пилоты",
    "вебинар",
    "вебинары",
]

MAX_GENERATION_ATTEMPTS = 2
MAX_GUARDRAIL_REWRITES = 2


def get_client() -> OpenAI:
    settings = get_settings()
    return OpenAI(
        base_url=settings.groq_base_url,
        api_key=settings.groq_api_key,
    )


def build_prompt(user_text: str) -> str:
    slide_list = "\n".join(f"{index + 1}. {name}" for index, name in enumerate(SLIDE_STRUCTURE))
    return f"""
Ты опытный стратег по стартап-нарративу, редактор инвестиционных презентаций и советник ранних стадий.

Твоя задача — превратить свободный текст основателя в четкую, правдоподобную и качественную презентацию ранней стадии.

Исходный текст пользователя:
{user_text}

Обязательные правила вывода:
- Верни только валидный JSON.
- Не используй markdown.
- Не оборачивай JSON в кодовые блоки.
- Не добавляй пояснения до или после JSON.
- Используй только указанную ниже схему.
- Все текстовые значения в JSON должны быть на русском языке.
- Названия слайдов должны быть ровно такими, как указано в структуре.

Правила мышления и достоверности:
- Опирайся в первую очередь на текст пользователя.
- Можно улучшать ясность, структуру, позиционирование и формулировки.
- Можно делать только легкие выводы, если они явно следуют из исходного текста.
- Не выдумывай выручку, traction, клиентов, партнерства, инвестиции, регуляторные разрешения и точные метрики.
- Не выдумывай TAM, SAM, SOM, количество клиник, цены, проценты, сроки и численные оценки, если пользователь их не дал.
- Не добавляй страны, регионы и географические рынки, если пользователь их прямо не указал.
- Если число или цена неизвестны, используй качественное описание без чисел.
- Если информации не хватает, сохрани правдоподобность и укажи пробелы в поле "info_gaps".

Требования к качеству текста:
- Пиши как сильный основатель, обращающийся к прагматичным инвесторам.
- Избегай пустых buzzword-формулировок, шаблонного хайпа и общих фраз.
- Избегай bullet-поинтов, которые являются только ярлыками или обрывками мысли.
- Каждый bullet должен выражать одну содержательную мысль.
- Каждый bullet должен читаться самостоятельно.
- Избегай однотипных начал и повторяющихся формулировок.
- Презентация должна логично идти от проблемы к решению, продукту, рынку и стратегии выхода.

Требования к deck:
- Ровно 8 слайдов в таком порядке:
{slide_list}
- В каждом слайде ровно 3 bullet-поинта.
- Каждый bullet: от 8 до 16 слов.
- Каждый bullet: цельная, полированная и презентационная формулировка.
- Без дубликатов и повторов.

Требования к полям:
- "startup_name": короткое и правдоподобное название.
- "one_liner": одно предложение с сутью продукта и ценности.
- "audience": для кого сделана презентация.
- "tone": короткая характеристика тона, например "прагматичный" или "инвесторский".
- "info_gaps": массив коротких заметок о том, чего не хватает, может быть пустым.

Подсказки по слайдам:
- Титул:
  Название компании, позиционирование и ключевая ценность.
- Проблема:
  Какая боль есть у пользователя, кто ее чувствует и почему это важно.
- Решение:
  Что делает продукт, что меняется для клиента и почему это лучше.
- Продукт:
  Как выглядит workflow, что автоматизируется и какой результат получает пользователь.
- Рынок:
  Кто покупатель, в каком контексте он принимает решение и почему спрос реален.
- Бизнес-модель:
  Кто платит, как выглядит логика монетизации и как масштабируется выручка без цифр.
- Выход на рынок:
  С чего начать, как привлекать первых клиентов и почему это реалистично.
- Видение:
  Куда может вырасти компания и в чем долгосрочное преимущество.

Планка качества:
- Презентация должна звучать так, будто ее можно реально показать инвестору.
- Сохраняй реализм ранней стадии: амбициозно, но без лишних обещаний.
- Если исходный текст слабый, улучшай framing, но не выдумывай факты.
- Предпочитай конкретный бизнес-язык абстрактным формулировкам.

JSON schema:
{{
  "startup_name": "строка",
  "one_liner": "строка",
  "audience": "строка",
  "tone": "строка",
  "info_gaps": ["строка"],
  "slides": [
    {{
      "title": "Титул",
      "bullets": ["пункт 1", "пункт 2", "пункт 3"]
    }}
  ]
}}
""".strip()


def build_repair_prompt(user_text: str, issues: str) -> str:
    return f"""
Предыдущая версия deck содержала неподтвержденные детали.

Исходный текст пользователя:
{user_text}

Проблемы, которые нужно исправить:
{issues}

Инструкции по исправлению:
- Полностью перегенерируй deck заново.
- Удали или перепиши все неподтвержденные детали.
- Не добавляй каналы, партнеров, цены, размеры рынка, числа, сроки и тактики, если их нет в тексте пользователя.
- Сохрани качество и читабельность для инвестора.
- Верни только валидный JSON по той же схеме.
- Все значения должны быть на русском языке.
""".strip()


def build_json_fix_prompt(raw_response: str) -> str:
    return f"""
Исправь поврежденный JSON ниже.

Правила:
- Верни только валидный JSON.
- Максимально сохрани исходный смысл и поля.
- Не добавляй пояснения.
- Не используй markdown.
- Сохрани ту же схему.
- Все текстовые значения должны остаться на русском языке, если они уже были на русском.

Поврежденный JSON:
{raw_response}
""".strip()


def build_grounding_rewrite_prompt(user_text: str, deck_payload: dict[str, Any], issues: str) -> str:
    payload_json = json.dumps(deck_payload, ensure_ascii=False, indent=2)
    return f"""
Перепиши deck ниже так, чтобы он оставался строго привязан к исходному тексту пользователя.

Исходный текст пользователя:
{user_text}

Текущий deck JSON:
{payload_json}

Проблемы с достоверностью:
{issues}

Правила переписывания:
- Сохрани ту же JSON-схему и тот же порядок слайдов.
- Переписывай только то, что нужно для удаления неподтвержденных деталей.
- Заменяй выдуманную конкретику на более общие, но правдоподобные формулировки.
- Не добавляй новые каналы, партнеров, числа, географию, пилоты, кейсы или цены, если их нет в исходном тексте.
- Сохрани качество текста и читаемость для инвестора.
- Верни только валидный JSON.
- Все текстовые значения должны быть на русском языке.
""".strip()


def _extract_json_candidate(data: str) -> str:
    text = data.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and start < end:
        return text[start : end + 1]
    return text


def parse_json_response(data: str) -> dict[str, Any]:
    if not data or not data.strip():
        raise ValueError("Модель вернула пустой ответ вместо JSON.")

    text = _extract_json_candidate(data)

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        preview = text[:300].replace("\n", "\\n")
        raise ValueError(
            f"Не удалось распарсить JSON из ответа модели: {preview}. Ошибка парсера: {exc}"
        ) from exc


def validate_pitch_deck(payload: dict[str, Any]) -> PitchDeck:
    startup_name = payload.get("startup_name")
    one_liner = payload.get("one_liner")
    audience = payload.get("audience")
    tone = payload.get("tone")
    info_gaps = payload.get("info_gaps")
    slides = payload.get("slides")

    if not isinstance(startup_name, str) or not startup_name.strip():
        raise ValueError("JSON должен содержать непустое поле 'startup_name'.")
    if not isinstance(one_liner, str) or not one_liner.strip():
        raise ValueError("JSON должен содержать непустое поле 'one_liner'.")
    if not isinstance(audience, str) or not audience.strip():
        raise ValueError("JSON должен содержать непустое поле 'audience'.")
    if not isinstance(tone, str) or not tone.strip():
        raise ValueError("JSON должен содержать непустое поле 'tone'.")
    if not isinstance(info_gaps, list):
        raise ValueError("JSON должен содержать поле 'info_gaps' как массив.")
    if not isinstance(slides, list) or len(slides) != len(SLIDE_STRUCTURE):
        raise ValueError(f"JSON должен содержать ровно {len(SLIDE_STRUCTURE)} слайдов.")

    clean_gaps = []
    for gap in info_gaps:
        if isinstance(gap, str) and gap.strip():
            clean_gaps.append(gap.strip())

    validated_slides: list[Slide] = []
    for index, expected_title in enumerate(SLIDE_STRUCTURE):
        slide = slides[index]
        if not isinstance(slide, dict):
            raise ValueError(f"Слайд {index + 1} должен быть объектом.")

        title = slide.get("title")
        bullets = slide.get("bullets")

        if title != expected_title:
            raise ValueError(
                f"Название слайда {index + 1} должно быть '{expected_title}', получено '{title}'."
            )
        if not isinstance(bullets, list) or len(bullets) != 3:
            raise ValueError(f"Слайд '{title}' должен содержать ровно 3 bullet-поинта.")

        clean_bullets: list[str] = []
        for bullet in bullets:
            if not isinstance(bullet, str) or not bullet.strip():
                raise ValueError(f"Слайд '{title}' содержит пустой bullet-поинт.")
            clean_bullets.append(bullet.strip())

        validated_slides.append(Slide(title=title, bullets=clean_bullets))

    return PitchDeck(
        startup_name=startup_name.strip(),
        one_liner=one_liner.strip(),
        audience=audience.strip(),
        tone=tone.strip(),
        info_gaps=clean_gaps,
        slides=validated_slides,
    )


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _collect_deck_text(deck: PitchDeck) -> str:
    parts = [deck.startup_name, deck.one_liner, deck.audience, deck.tone, *deck.info_gaps]
    for slide in deck.slides:
        parts.append(slide.title)
        parts.extend(slide.bullets)
    return _normalize_text(" ".join(parts))


def find_invented_specifics(deck: PitchDeck, user_text: str) -> list[str]:
    source_text = _normalize_text(user_text)
    deck_text = _collect_deck_text(deck)
    findings: list[str] = []

    for phrase in UNSUPPORTED_SPECIFIC_PHRASES:
        if phrase in deck_text and phrase not in source_text:
            findings.append(f"неподтвержденная деталь: '{phrase}'")

    deck_numbers = set(re.findall(r"\b\d+(?:[.,]\d+)?\b", deck_text))
    source_numbers = set(re.findall(r"\b\d+(?:[.,]\d+)?\b", source_text))
    invented_numbers = sorted(deck_numbers - source_numbers)
    if invented_numbers:
        findings.append(
            "неподтвержденные числовые детали: " + ", ".join(invented_numbers[:5])
        )

    return findings


def validate_invented_specifics(deck: PitchDeck, user_text: str) -> None:
    findings = find_invented_specifics(deck, user_text)
    if findings:
        raise ValueError(
            "Deck содержит детали, которых не было в исходном тексте: " + "; ".join(findings)
        )


def _repair_json_response(client: OpenAI, selected_model: str, raw_response: str) -> dict[str, Any]:
    repair_prompt = build_json_fix_prompt(_extract_json_candidate(raw_response))
    response = client.chat.completions.create(
        model=selected_model,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты исправляешь поврежденный JSON. "
                    "Верни только валидный JSON по той же схеме и без комментариев."
                ),
            },
            {"role": "user", "content": repair_prompt},
        ],
    )
    return parse_json_response(response.choices[0].message.content or "")


def _rewrite_grounded_payload(
    client: OpenAI,
    selected_model: str,
    user_text: str,
    deck_payload: dict[str, Any],
    issues: list[str],
) -> dict[str, Any]:
    rewrite_prompt = build_grounding_rewrite_prompt(user_text, deck_payload, "; ".join(issues))
    response = client.chat.completions.create(
        model=selected_model,
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты переписываешь JSON-презентацию стартапа, чтобы убрать неподтвержденные детали. "
                    "Верни только валидный JSON по той же схеме и на русском языке."
                ),
            },
            {"role": "user", "content": rewrite_prompt},
        ],
    )
    raw_response = response.choices[0].message.content or ""
    try:
        return parse_json_response(raw_response)
    except ValueError:
        return _repair_json_response(client, selected_model, raw_response)


def _generate_payload(
    client: OpenAI,
    selected_model: str,
    user_text: str,
    repair_issues: str | None = None,
) -> dict[str, Any]:
    base_prompt = build_prompt(user_text)
    if repair_issues:
        user_prompt = base_prompt + "\n\n" + build_repair_prompt(user_text, repair_issues)
    else:
        user_prompt = base_prompt

    response = client.chat.completions.create(
        model=selected_model,
        temperature=0.4,
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты строгий генератор JSON-презентаций для стартапов. "
                    "Ты возвращаешь только валидный JSON по заданной схеме. "
                    "Ты пишешь все значения на русском языке. "
                    "Ты не выдумываешь числа, цены, размеры рынка, географию и неподтвержденные детали."
                ),
            },
            {"role": "user", "content": user_prompt},
        ],
    )

    raw_response = response.choices[0].message.content or ""
    try:
        return parse_json_response(raw_response)
    except ValueError:
        return _repair_json_response(client, selected_model, raw_response)


def _soften_grounding_issues(
    client: OpenAI,
    selected_model: str,
    user_text: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    current_payload = payload
    for _ in range(MAX_GUARDRAIL_REWRITES):
        deck = validate_pitch_deck(current_payload)
        findings = find_invented_specifics(deck, user_text)
        if not findings:
            return current_payload
        current_payload = _rewrite_grounded_payload(
            client, selected_model, user_text, current_payload, findings
        )
    return current_payload


def generate_deck_from_text(user_text: str, model: str | None = None) -> PitchDeck:
    settings = get_settings()
    client = get_client()
    selected_model = model or settings.model
    last_error: Exception | None = None
    repair_issues: str | None = None

    for _ in range(MAX_GENERATION_ATTEMPTS):
        try:
            payload = _generate_payload(client, selected_model, user_text, repair_issues)
            payload = _soften_grounding_issues(client, selected_model, user_text, payload)
            deck = validate_pitch_deck(payload)
            validate_invented_specifics(deck, user_text)
            return deck
        except ValueError as exc:
            last_error = exc
            repair_issues = str(exc)

    raise ValueError(f"Не удалось сгенерировать deck после повторных попыток: {last_error}")
