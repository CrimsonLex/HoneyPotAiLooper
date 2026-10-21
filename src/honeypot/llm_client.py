"""Cliente unificado para hablar con Ollama."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Generator, Optional

import ollama
from ollama import Client

logger = logging.getLogger(__name__)


# --- Excepciones propias -------------------------------------------------
class LLMError(Exception):
    """Base para errores del cliente."""


class LLMConnectionError(LLMError):
    """No se pudo conectar con el servidor Ollama."""


class LLMModelNotFoundError(LLMError):
    """El modelo pedido no está descargado localmente."""


class LLMResponseError(LLMError):
    """El servidor respondió, pero con un error o respuesta vacía."""


# --- Configuración -------------------------------------------------------
@dataclass
class LLMConfig:
    host: str = "http://127.0.0.1:11434"
    timeout: float = 120.0
    max_retries: int = 3
    backoff_base: float = 1.0
    default_options: dict = field(default_factory=lambda: {
        "temperature": 0.2,
        "num_ctx": 4096,
    })


# --- Cliente -------------------------------------------------------------
class LLMClient:
    """Wrapper de Ollama con reintentos, streaming y verificación de GPU."""

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self._client = Client(host=self.config.host, timeout=self.config.timeout)
        self._models_cache: Optional[list[str]] = None

    # ---- Utilidades internas -------------------------------------------
    def _retry(self, fn, *args, **kwargs):
        last_exc: Optional[Exception] = None
        for intento in range(1, self.config.max_retries + 1):
            try:
                return fn(*args, **kwargs)
            except ollama.ResponseError as e:
                msg = str(e).lower()
                if "not found" in msg or "no such model" in msg:
                    raise LLMModelNotFoundError(str(e)) from e
                raise LLMResponseError(str(e)) from e
            except (ConnectionError, OSError) as e:
                last_exc = e
                espera = self.config.backoff_base * (2 ** (intento - 1))
                logger.warning(
                    "Conexión fallida (intento %d/%d): %s. Reintento en %.1fs",
                    intento, self.config.max_retries, e, espera,
                )
                time.sleep(espera)

        raise LLMConnectionError(
            f"No se pudo conectar tras {self.config.max_retries} intentos: {last_exc}"
        ) from last_exc

    # ---- Salud y modelos -----------------------------------------------
    def is_available(self) -> bool:
        try:
            self._client.list()
            return True
        except Exception as e:
            logger.debug("Ollama no disponible: %s", e)
            return False

    def list_models(self) -> list[str]:
        try:
            resp = self._client.list()
        except Exception as e:
            raise LLMConnectionError(f"No se pudo listar modelos: {e}") from e

        nombres = [m.get("model") or m.get("name") for m in resp.get("models", [])]
        self._models_cache = nombres
        return nombres

    def has_model(self, nombre: str) -> bool:
        if self._models_cache is None:
            self.list_models()
        return any(nombre in n for n in self._models_cache or [])

    def ensure_model(self, nombre: str) -> None:
        if not self.has_model(nombre):
            raise LLMModelNotFoundError(
                f"Modelo '{nombre}' no encontrado. Ejecuta: ollama pull {nombre}"
            )

    def loaded_on_gpu(self, nombre: str) -> Optional[bool]:
        try:
            resp = self._client.ps()
        except Exception as e:
            logger.debug("No se pudo consultar `ps`: %s", e)
            return None

        for m in resp.get("models", []):
            if nombre in (m.get("model") or m.get("name", "")):
                return "gpu" in (m.get("processor") or "").lower()
        return None

    # ---- Chat no-streaming ---------------------------------------------
    def chat(
        self,
        model: str,
        messages: list[dict],
        *,
        options: Optional[dict] = None,
        force_options: Optional[dict] = None,
        think: Optional[bool] = None,
    ) -> str:
        if force_options is not None:
            opts = force_options
        else:
            opts = {**self.config.default_options, **(options or {})}

        kwargs = dict(model=model, messages=messages, options=opts)
        if think is not None:
            kwargs["think"] = think

        try:
            respuesta = self._retry(self._client.chat, **kwargs)
        except TypeError:
            # ollama-python antiguo sin soporte para `think`
            kwargs.pop("think", None)
            respuesta = self._retry(self._client.chat, **kwargs)

        contenido = (respuesta.get("message") or {}).get("content", "").strip()
        if not contenido:
            raise LLMResponseError(f"Respuesta vacía del modelo '{model}'")
        return contenido

    # ---- Chat streaming -------------------------------------------------
    def chat_stream(
        self,
        model: str,
        messages: list[dict],
        *,
        options: Optional[dict] = None,
    ) -> Generator[str, None, None]:
        opts = {**self.config.default_options, **(options or {})}
        stream = self._client.chat(
            model=model, messages=messages, options=opts, stream=True
        )
        try:
            for chunk in stream:
                texto = (chunk.get("message") or {}).get("content", "")
                if texto:
                    yield texto
        except (ConnectionError, OSError) as e:
            raise LLMConnectionError(f"Stream interrumpido: {e}") from e

    # ---- Helper de clasificación ---------------------------------------
    def classify(
        self,
        model: str,
        texto: str,
        system_prompt: str,
        *,
        etiquetas: tuple[str, ...] = ("HUMANO", "MAQUINA"),
        think: bool = False,
    ) -> str:
        """Devuelve el texto crudo del modelo (el parseo se hace en clasificar())."""
        return self.chat(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": texto},
            ],
            force_options={"temperature": 0.0, "num_predict": 64},
            think=think,
        )