import json
import re
from typing import Any

from openai import OpenAI

from app.config import get_settings
from app.schemas import PitchDeck, SLIDE_STRUCTURE, Slide
from app.presentation_templates import PresentationTemplate, get_presentation_template

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

UNSUPPORTED_ABSENCE_PHRASES = [
    "не указано",
    "неизвестно",
    "не хватает данных",
    "недостаточно данных",
    "не хватает информации",
    "нет данных",
    "не определено",
    "не раскрыто",
    "не уточнено",
    "неясно",
    "without data",
    "no data",
    "unknown",
]

MAX_GENERATION_ATTEMPTS = 2
MAX_GUARDRAIL_REWRITES = 2
MAX_ABSENCE_REWRITES = 2

TEMPLATE_BRAND_ALIASES = {
    "tbank": {"tbank", "t-bank", "тбанк", "т-банк", "т банк", "тинькофф", "tinkoff"},
    "sber": {"sber", "сбер", "сбербанк"},
    "alpha": {"alpha", "альфа", "альфа-банк", "alfa", "alfabank"},
}


def _fallback_slide_bullets(title: str, template: PresentationTemplate) -> list[str]:
    style_prefix = {
        "tbank": "Делаем ставку на скорость, ясность и операционную эффективность.",
        "sber": "Держим фокус на надежности, системности и долгом горизонте роста.",
        "alpha": "Подчеркиваем энергию, заметный эффект и современную подачу.",
    }.get(
        template.key,
        "Держим фокус на ясной ценности, реалистичности и сильной подаче.",
    )

    fallback_map = {
        "Титул": [
            "Позиционируем продукт через понятную ценность и сильный первый экран.",
            style_prefix,
            "Сразу задаем уверенный контекст для дальнейшего рассказа.",
        ],
        "Проблема": [
            "Проблема описана через повторяющуюся операционную боль клиента.",
            "Команда теряет время на ручные действия и координацию.",
            "Боль напрямую влияет на качество сервиса и скорость работы.",
        ],
        "Решение": [
            "Продукт снимает рутину и делает процесс более предсказуемым.",
            "Клиент получает более быстрый и прозрачный рабочий контур.",
            "Решение можно внедрять без сложной перестройки процессов.",
        ],
        "Продукт": [
            "Сценарий использования остается простым и понятным для команды.",
            "Автоматизация забирает на себя повторяющиеся действия.",
            "Первые эффекты видны уже на базовом рабочем потоке.",
        ],
        "Рынок": [
            "Спрос возникает там, где есть частые и дорогие повторения.",
            "Покупатель выбирает решение через операционную пользу, а не обещания.",
            "Рынок поддерживается цифровизацией и ростом ожиданий к скорости.",
        ],
        "Бизнес-модель": [
            "Монетизация строится на понятной и повторяемой подписке.",
            "Дополнительная ценность раскрывается через расширенные функции и сценарии.",
            "Выручка масштабируется по мере углубления использования продукта.",
        ],
        "Выход на рынок": [
            "Стартуем с узкого сценария, где ценность видна быстрее всего.",
            "Первые клиенты приходят через прямую работу и рекомендации.",
            "Дальше расширяемся в соседние процессы и команды.",
        ],
        "Видение": [
            "Платформа может стать системным слоем операционной работы.",
            "Долгосрочное преимущество строится на данных и повторяемом workflow.",
            "Продукт получает потенциал к расширению в широкую экосистему.",
        ],
    }

    return fallback_map.get(
        title,
        [
            "Формулировка остается ясной, прагматичной и инвесторски читаемой.",
            "Делаем акцент на ценности для клиента и логике продукта.",
            "Сохраняем сильный тон без лишней конкретики и обещаний.",
        ],
    )


def _normalize_name_token(value: str) -> str:
    return re.sub(r"[^a-zа-я0-9]+", "", _normalize_text(value))


def _is_brand_template_name(name: str, template: PresentationTemplate) -> bool:
    normalized = _normalize_name_token(name)
    aliases = {_normalize_name_token(template.label), _normalize_name_token(template.key)}
    aliases.update(_normalize_name_token(alias) for alias in TEMPLATE_BRAND_ALIASES.get(template.key, set()))
    return bool(normalized) and normalized in aliases


def _infer_startup_name_from_text(user_text: str, one_liner: str | None = None) -> str:
    quoted_patterns = [
        r"«([^»]{2,40})»",
        r'"([^"]{2,40})"',
    ]
    for pattern in quoted_patterns:
        match = re.search(pattern, user_text)
        if match:
            candidate = match.group(1).strip(" .,:;!?\n\t")
            if len(candidate) >= 2:
                return candidate

    phrase_patterns = [
        r"(?:продукт|сервис|платформа|решение|стартап|проект|система|ассистент|помощник)\s+(?:под названием\s+)?([A-ZА-Я][A-Za-zА-Яа-я0-9\-]{1,40}(?:\s+[A-ZА-Я][A-Za-zА-Яа-я0-9\-]{1,30}){0,2})",
        r"([A-ZА-Я][A-Za-zА-Яа-я0-9\-]{2,30}(?:\s+[A-ZА-Я][A-Za-zА-Яа-я0-9\-]{2,30}){0,2})\s+(?:для|помогает|автоматизирует|сервис|платформа)",
    ]
    for pattern in phrase_patterns:
        match = re.search(pattern, user_text)
        if match:
            candidate = match.group(1).strip(" .,:;!?\n\t")
            if len(candidate) >= 2:
                return candidate

    if one_liner:
        stopwords = {
            "для",
            "и",
            "или",
            "как",
            "что",
            "это",
            "на",
            "по",
            "из",
            "за",
            "в",
            "во",
            "с",
            "со",
            "of",
            "to",
            "for",
            "and",
            "with",
            "from",
            "that",
            "this",
            "into",
            "the",
            "a",
            "an",
            "on",
            "at",
            "by",
            "or",
        }
        cleaned_words = [
            word.strip(" .,:;!?\n\t")
            for word in re.split(r"\s+", one_liner)
            if word.strip(" .,:;!?\n\t")
        ]
        useful_words = [
            word
            for word in cleaned_words
            if len(word) > 2 and word.lower().strip("-") not in stopwords
        ]
        if useful_words:
            candidate = " ".join(useful_words[:2]).strip()
            return candidate[:1].upper() + candidate[1:] if candidate else "Новый продукт"

    return "Новый продукт"


def build_startup_name_fix_prompt(
    user_text: str,
    one_liner: str,
    current_name: str,
    template: PresentationTemplate,
) -> str:
    return f"""
Исправь только название продукта.

Требования:
- Название должно быть названием самого продукта или компании, а не названием шаблона.
- Не используй: {template.label}
- Название должно звучать как реальное имя продукта из исходного контекста.
- Если в тексте нет явного имени, придумай короткое, уместное и нейтральное название по смыслу продукта.
- Верни только JSON вида {{"startup_name":"..."}}.

Исходный текст пользователя:
{user_text}

One-liner:
{one_liner}

Текущее название:
{current_name}
""".strip()


def _rewrite_startup_name(
    client: OpenAI,
    selected_model: str,
    user_text: str,
    one_liner: str,
    current_name: str,
    template: PresentationTemplate,
) -> str:
    prompt = build_startup_name_fix_prompt(user_text, one_liner, current_name, template)
    response = client.chat.completions.create(
        model=selected_model,
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты исправляешь только название продукта в JSON. "
                    "Верни только валидный JSON с одним полем startup_name."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )
    raw_response = response.choices[0].message.content or ""
    payload = parse_json_response(raw_response)
    candidate = payload.get("startup_name")
    if isinstance(candidate, str) and candidate.strip() and not _is_brand_template_name(candidate, template):
        return candidate.strip()
    return _infer_startup_name_from_text(user_text, one_liner)


def get_client() -> OpenAI:
    settings = get_settings()
    return OpenAI(
        base_url=settings.groq_base_url,
        api_key=settings.groq_api_key,
    )


def build_prompt(user_text: str, template: PresentationTemplate) -> str:
    slide_list = "\n".join(f"{index + 1}. {name}" for index, name in enumerate(SLIDE_STRUCTURE))
    return f"""
Ты опытный стратег по стартап-нарративу, редактор инвестиционных презентаций и советник ранних стадий.

Твоя задача — превратить свободный текст основателя в четкую, правдоподобную и качественную презентацию ранней стадии.

Выбранный визуально-редакционный шаблон:
- Название: {template.label}
- Характер: {template.description}
- Стиль: {template.prompt_guidance}
- Шаблон влияет только на визуальный и редакционный стиль, но не на название продукта.

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
- Если информации не хватает, не проговаривай это прямо в слайдах.
- Замещай отсутствие конкретики более общими, но сильными формулировками.
- Поле "info_gaps" используй только для действительно критичных пробелов, и по возможности оставляй его пустым.

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
- "startup_name" должно быть названием самого продукта или компании из исходного контекста, а не названием шаблона.
- Если явного имени нет, придумай короткое название по смыслу продукта, но не используй название шаблона.
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


def build_repair_prompt(user_text: str, issues: str, template: PresentationTemplate) -> str:
    return f"""
Предыдущая версия deck содержала неподтвержденные детали.

Соблюдай стиль шаблона:
- Название: {template.label}
- Характер: {template.description}
- Шаблон не должен попадать в название продукта.

Исходный текст пользователя:
{user_text}

Проблемы, которые нужно исправить:
{issues}

Инструкции по исправлению:
- Полностью перегенерируй deck заново.
- Название продукта должно быть отдельным, не брендом шаблона.
- Удали или перепиши все неподтвержденные детали.
- Не проговаривай отсутствие данных, нехватку информации или неизвестные значения.
- Если конкретика отсутствует, сформулируй мысль более широко и уверенно.
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
- Если в тексте есть прямые упоминания о нехватке данных, замени их на более нейтральную формулировку или убери.
- Все текстовые значения должны остаться на русском языке, если они уже были на русском.

Поврежденный JSON:
{raw_response}
""".strip()


def build_grounding_rewrite_prompt(
    user_text: str,
    deck_payload: dict[str, Any],
    issues: str,
    template: PresentationTemplate,
) -> str:
    payload_json = json.dumps(deck_payload, ensure_ascii=False, indent=2)
    return f"""
Перепиши deck ниже так, чтобы он оставался строго привязан к исходному тексту пользователя.

Сохраняй стиль шаблона:
- Название: {template.label}
- Характер: {template.description}
- Шаблон влияет на стиль, но не на имя продукта.

Исходный текст пользователя:
{user_text}

Текущий deck JSON:
{payload_json}

Проблемы с достоверностью:
{issues}

Правила переписывания:
- Сохрани ту же JSON-схему и тот же порядок слайдов.
- Не используй название шаблона в startup_name.
- Переписывай только то, что нужно для удаления неподтвержденных деталей.
- Заменяй выдуманную конкретику на более общие, но правдоподобные формулировки.
- Не добавляй новые каналы, партнеров, числа, географию, пилоты, кейсы или цены, если их нет в исходном тексте.
- Убирай прямые фразы про нехватку данных, неизвестность или отсутствие информации.
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


def find_absence_mentions(deck: PitchDeck) -> list[str]:
    deck_text = _collect_deck_text(deck)
    findings: list[str] = []

    for phrase in UNSUPPORTED_ABSENCE_PHRASES:
        if phrase in deck_text:
            findings.append(f"прямое упоминание нехватки данных: '{phrase}'")

    return findings


def normalize_pitch_deck_payload(payload: dict[str, Any], template: PresentationTemplate) -> dict[str, Any]:
    normalized = dict(payload) if isinstance(payload, dict) else {}

    slides_raw = normalized.get("slides")
    if not isinstance(slides_raw, list):
        slides_raw = []

    normalized_slides: list[dict[str, Any]] = []
    for index, expected_title in enumerate(SLIDE_STRUCTURE):
        slide = slides_raw[index] if index < len(slides_raw) and isinstance(slides_raw[index], dict) else {}
        bullets_raw = slide.get("bullets") if isinstance(slide, dict) else []
        if not isinstance(bullets_raw, list):
            bullets_raw = []

        clean_bullets = [bullet.strip() for bullet in bullets_raw if isinstance(bullet, str) and bullet.strip()]
        fallback_bullets = _fallback_slide_bullets(expected_title, template)

        if len(clean_bullets) < 3:
            for fallback_bullet in fallback_bullets:
                if len(clean_bullets) >= 3:
                    break
                if fallback_bullet not in clean_bullets:
                    clean_bullets.append(fallback_bullet)

        if len(clean_bullets) > 3:
            clean_bullets = clean_bullets[:3]

        if len(clean_bullets) < 3:
            clean_bullets.extend(fallback_bullets[len(clean_bullets) : 3])

        normalized_slides.append({"title": expected_title, "bullets": clean_bullets})

    normalized["slides"] = normalized_slides
    return normalized


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
    template: PresentationTemplate,
) -> dict[str, Any]:
    rewrite_prompt = build_grounding_rewrite_prompt(
        user_text, deck_payload, "; ".join(issues), template
    )
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


def _rewrite_absence_mentions(
    client: OpenAI,
    selected_model: str,
    user_text: str,
    deck_payload: dict[str, Any],
    issues: list[str],
    template: PresentationTemplate,
) -> dict[str, Any]:
    rewrite_prompt = build_grounding_rewrite_prompt(
        user_text, deck_payload, "; ".join(issues), template
    )
    response = client.chat.completions.create(
        model=selected_model,
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты переписываешь JSON-презентацию стартапа, чтобы убрать прямые упоминания о нехватке данных. "
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
    template: PresentationTemplate,
    repair_issues: str | None = None,
) -> dict[str, Any]:
    base_prompt = build_prompt(user_text, template)
    if repair_issues:
        user_prompt = base_prompt + "\n\n" + build_repair_prompt(user_text, repair_issues, template)
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
                    "Название продукта в startup_name должно быть названием самого продукта или компании, а не названием шаблона. "
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
    template: PresentationTemplate,
) -> dict[str, Any]:
    current_payload = payload
    for _ in range(MAX_GUARDRAIL_REWRITES):
        current_payload = normalize_pitch_deck_payload(current_payload, template)
        deck = validate_pitch_deck(current_payload)
        findings = find_invented_specifics(deck, user_text)
        if not findings:
            return current_payload
        current_payload = _rewrite_grounded_payload(
            client, selected_model, user_text, current_payload, findings, template
        )
    return current_payload


def _soften_absence_mentions(
    client: OpenAI,
    selected_model: str,
    user_text: str,
    payload: dict[str, Any],
    template: PresentationTemplate,
) -> dict[str, Any]:
    current_payload = payload
    for _ in range(MAX_ABSENCE_REWRITES):
        current_payload = normalize_pitch_deck_payload(current_payload, template)
        deck = validate_pitch_deck(current_payload)
        findings = find_absence_mentions(deck)
        if not findings:
            return current_payload
        current_payload = _rewrite_absence_mentions(
            client, selected_model, user_text, current_payload, findings, template
        )
    return current_payload


def _ensure_product_name(
    client: OpenAI,
    selected_model: str,
    user_text: str,
    payload: dict[str, Any],
    template: PresentationTemplate,
) -> dict[str, Any]:
    current_payload = dict(payload)
    current_name = current_payload.get("startup_name")
    one_liner = current_payload.get("one_liner")

    if not isinstance(current_name, str) or not current_name.strip():
        current_payload["startup_name"] = _infer_startup_name_from_text(
            user_text, one_liner if isinstance(one_liner, str) else None
        )
        return current_payload

    if _is_brand_template_name(current_name, template):
        fixed_name = _rewrite_startup_name(
            client,
            selected_model,
            user_text,
            one_liner if isinstance(one_liner, str) else "",
            current_name,
            template,
        )
        current_payload["startup_name"] = fixed_name

    return current_payload


def generate_deck_from_text(
    user_text: str,
    model: str | None = None,
    template: str | None = None,
) -> PitchDeck:
    settings = get_settings()
    client = get_client()
    selected_model = model or settings.model
    selected_template = get_presentation_template(template)
    last_error: Exception | None = None
    repair_issues: str | None = None

    for _ in range(MAX_GENERATION_ATTEMPTS):
        try:
            payload = _generate_payload(
                client,
                selected_model,
                user_text,
                selected_template,
                repair_issues,
            )
            payload = normalize_pitch_deck_payload(payload, selected_template)
            payload = _ensure_product_name(
                client, selected_model, user_text, payload, selected_template
            )
            payload = _soften_grounding_issues(
                client, selected_model, user_text, payload, selected_template
            )
            payload = _soften_absence_mentions(
                client, selected_model, user_text, payload, selected_template
            )
            payload = normalize_pitch_deck_payload(payload, selected_template)
            payload = _ensure_product_name(
                client, selected_model, user_text, payload, selected_template
            )
            deck = validate_pitch_deck(payload)
            validate_invented_specifics(deck, user_text)
            absence_mentions = find_absence_mentions(deck)
            if absence_mentions:
                raise ValueError(
                    "Deck содержит прямые упоминания о нехватке данных: "
                    + "; ".join(absence_mentions)
                )
            return deck
        except ValueError as exc:
            last_error = exc
            repair_issues = str(exc)

    raise ValueError(f"Не удалось сгенерировать deck после повторных попыток: {last_error}")
