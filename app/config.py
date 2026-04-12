import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    groq_api_key: str
    groq_base_url: str
    model: str
    output_dir: str


def load_dotenv(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_settings() -> Settings:
    load_dotenv()

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Missing GROQ_API_KEY. Create a .env file or export GROQ_API_KEY before running."
        )

    return Settings(
        groq_api_key=api_key,
        groq_base_url=os.getenv(
            "GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
        model=os.getenv("PITCH_MODEL", "openai/gpt-oss-120b"),
        output_dir=os.getenv("OUTPUT_DIR", "generated"),
    )
