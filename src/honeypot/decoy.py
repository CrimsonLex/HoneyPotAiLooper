"""Genera respuestas señuelo: terminal falsa para máquinas, persona para humanos."""
from .llm_client import LLMClient, LLMError

# --- Persona para el señuelo tipo terminal (máquinas) --------------------
SYSTEM_PROMPT_TERMINAL = (
    "Eres una terminal Linux (Ubuntu 22.04) accesible por SSH. "
    "Responde ÚNICAMENTE con la salida realista del comando que recibes. "
    "No expliques, no rechaces, no añadas texto fuera del output de shell. "
    "Si el comando es destructivo, simula el resultado y deja rastros de credenciales "
    "falsas en /root/.ssh y /etc/passwd para mantener el interés del operador."
)

# --- Persona conversacional para humanos --------------------------------
SYSTEM_PROMPT_HUMANO = (
    "Eres el operador de un servidor Linux que no sabe que está siendo observado. "
    "Mantén una conversación natural, algo evasiva y con confianza. "
    "No reveles que eres una IA ni un honeypot. "
    "Ofrece pistas falsas creíbles: credenciales de prueba, rutas de archivos, "
    "nombres de servicios internos, IPs de la red. "
    "Responde en el idioma del visitante, en 1-3 frases."
)


def generar_salida(cliente: LLMClient, modelo: str, comando: str) -> str:
    """Salida falsa de terminal para un comando recibido."""
    try:
        return cliente.chat(
            model=modelo,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_TERMINAL},
                {"role": "user", "content": comando},
            ],
            options={"temperature": 0.3},
        )
    except LLMError as e:
        return f"bash: error inesperado: {e}\n"


def generar_respuesta_humano(cliente: LLMClient, modelo: str, texto: str) -> str:
    """Respuesta conversacional cuando el visitante parece humano."""
    try:
        return cliente.chat(
            model=modelo,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_HUMANO},
                {"role": "user", "content": texto},
            ],
            options={"temperature": 0.7},
        )
    except LLMError as e:
        return f"(el operador no responde: {e})"