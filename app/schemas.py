from dataclasses import asdict, dataclass


SLIDE_STRUCTURE = [
    "Титул",
    "Проблема",
    "Решение",
    "Продукт",
    "Рынок",
    "Бизнес-модель",
    "Выход на рынок",
    "Видение",
]


@dataclass
class Slide:
    title: str
    bullets: list[str]


@dataclass
class PitchDeck:
    startup_name: str
    one_liner: str
    audience: str
    tone: str
    info_gaps: list[str]
    slides: list[Slide]

    def to_dict(self) -> dict:
        return asdict(self)
