from dataclasses import dataclass


@dataclass(frozen=True)
class PresentationTemplate:
    key: str
    label: str
    description: str
    prompt_guidance: str
    background: tuple[int, int, int]
    surface: tuple[int, int, int]
    ink: tuple[int, int, int]
    muted: tuple[int, int, int]
    accent: tuple[int, int, int]
    accent_dark: tuple[int, int, int]
    line: tuple[int, int, int]
    title_font: str = "Aptos Display"
    body_font: str = "Aptos"


PRESENTATION_TEMPLATES: dict[str, PresentationTemplate] = {
    "neutral": PresentationTemplate(
        key="neutral",
        label="Нейтральный",
        description="Спокойный универсальный инвесторский стиль без ярко выраженного брендинга.",
        prompt_guidance=(
            "Пиши нейтрально, ясно и убедительно. "
            "Сохраняй баланс между амбициозностью и реализмом."
        ),
        background=(246, 243, 236),
        surface=(255, 252, 245),
        ink=(27, 31, 38),
        muted=(98, 105, 117),
        accent=(201, 92, 55),
        accent_dark=(125, 51, 28),
        line=(224, 214, 196),
    ),
    "tbank": PresentationTemplate(
        key="tbank",
        label="Т-Банк",
        description="Контрастный продуктовый стиль: смелый, быстрый, очень прямой.",
        prompt_guidance=(
            "Пиши коротко, точно и энергично. "
            "Делай акцент на скорости, цифровом продукте, контроле и операционной эффективности. "
            "Избегай канцелярита и лишней мягкости."
        ),
        background=(16, 16, 18),
        surface=(30, 30, 34),
        ink=(248, 248, 241),
        muted=(183, 183, 183),
        accent=(255, 213, 0),
        accent_dark=(194, 158, 0),
        line=(67, 67, 74),
    ),
    "sber": PresentationTemplate(
        key="sber",
        label="Сбер",
        description="Спокойный, надежный и системный стиль с акцентом на масштаб и доверие.",
        prompt_guidance=(
            "Пиши собранно, уверенно и без резких лозунгов. "
            "Подчеркивай надежность, долгий горизонт, экосистемный подход и устойчивый рост."
        ),
        background=(241, 247, 241),
        surface=(255, 255, 255),
        ink=(21, 34, 27),
        muted=(88, 100, 92),
        accent=(0, 158, 96),
        accent_dark=(0, 122, 74),
        line=(206, 223, 210),
    ),
    "alpha": PresentationTemplate(
        key="alpha",
        label="Альфа",
        description="Энергичный, дерзкий и современный стиль с ясным акцентом на клиентскую ценность.",
        prompt_guidance=(
            "Пиши энергично, современно и по делу. "
            "Делай акцент на скорости решения, заметном эффекте для клиента и сильной подаче. "
            "Избегай тяжеловесности."
        ),
        background=(255, 248, 247),
        surface=(255, 255, 255),
        ink=(28, 22, 22),
        muted=(112, 98, 98),
        accent=(229, 0, 37),
        accent_dark=(178, 0, 31),
        line=(239, 209, 213),
    ),
}


def get_presentation_template(template_key: str | None) -> PresentationTemplate:
    key = (template_key or "neutral").strip().lower()
    if key not in PRESENTATION_TEMPLATES:
        available = ", ".join(sorted(PRESENTATION_TEMPLATES))
        raise ValueError(f"Unknown presentation template '{template_key}'. Available: {available}.")
    return PRESENTATION_TEMPLATES[key]


def list_presentation_templates() -> list[PresentationTemplate]:
    return list(PRESENTATION_TEMPLATES.values())
