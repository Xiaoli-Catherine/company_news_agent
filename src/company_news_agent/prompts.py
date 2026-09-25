from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from string import Template


PROMPTS_DIR = Path(__file__).with_name("prompts")


def render_prompt(name: str, **values: object) -> str:
    template = Template(_load_prompt(name))
    return template.substitute({key: str(value) for key, value in values.items()})


@lru_cache(maxsize=None)
def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    return path.read_text(encoding="utf-8").strip()
