from pathlib import Path


def load_prompt(name: str, **kwargs) -> str:
    """Load prompts/{name}.txt and fill {placeholder} values."""
    path = Path(__file__).parent / "prompts" / f"{name}.txt"
    template = path.read_text(encoding="utf-8")
    return template.format_map(kwargs)
