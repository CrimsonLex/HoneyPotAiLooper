"""Clasifica cada input como HUMANO, SCRIPT o AGENTE_LLM."""
import logging
from pathlib import Path

from .llm_client import LLMClient, LLMError

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "classifier_system.txt"


def cargar_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8").strip()


def clasificar(cliente: LLMClient, modelo: str, texto: str) -> dict:
    """Devuelve {'etiqueta': 'AGENTE_LLM', 'confianza': 87, 'raw': '...'}."""
    prompt = cargar_prompt()
    try:
        raw = cliente.classify(
            model=modelo,
            texto=texto,
            system_prompt=prompt,
            etiquetas=("AGENTE_LLM", "SCRIPT", "HUMANO"),
        )
    except LLMError as e:
        logger.warning("Clasificador falló: %s", e)
        return {"etiqueta": "HUMANO", "confianza": 0, "raw": f"ERROR: {e}"}

    upper = raw.upper()
    etiqueta = "HUMANO"
    for cand in ("AGENTE_LLM", "SCRIPT", "HUMANO"):
        if cand in upper:
            etiqueta = cand
            break

    confianza = 0
    for parte in raw.replace("%", " ").replace(":", " ").split():
        if parte.isdigit():
            confianza = int(parte)
            break

    return {"etiqueta": etiqueta, "confianza": confianza, "raw": raw}