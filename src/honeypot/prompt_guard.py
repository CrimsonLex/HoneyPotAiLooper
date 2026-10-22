"""Guardas deterministas para evitar la divulgación de prompts del sistema."""
import re
import unicodedata

_ACCIONES = re.compile(
    r"\b(?:repite|repetir|repetir|cita|citar|copia|copiar|muestra|mostrar|"
    r"revela|revelar|imprime|imprimir|dime|transcribe|enumera|"
    r"repeat|restate|quote|copy|show|reveal|print|dump|disclose|output|tell)\b"
)
_PROMPT_EXPLICITO = re.compile(
    r"\b(?:prompt|system prompt|system instructions|developer instructions|"
    r"mensaje del sistema|instrucciones del sistema|instrucciones previas|"
    r"instrucciones iniciales|instrucciones que recibiste|instrucciones "
    r"recibidas|reglas internas|reglas que recibiste|prompt interno|"
    r"texto inicial|mensaje inicial|lo que recibiste|what you received|"
    r"initial instructions|previous instructions|instructions you received|"
    r"rules you received|internal prompt)\b"
)
_INSTRUCCIONES = re.compile(r"\b(?:instrucciones|instructions)\b")
_CONTEXTO_INICIAL = re.compile(
    r"\b(?:inicio|al inicio|inicial|recibiste|recibidas|anteriores|previas|"
    r"conversacion|conversation|received|beginning|before)\b"
)
_FRASE_ANTERIOR = re.compile(
    r"\b(?:repite|repetir|repeat|restate)\b.{0,35}\b(?:lo anterior|"
    r"lo de antes|what came before|everything above)\b"
)
_MARCADORES_REVELACION = re.compile(
    r"\b(?:system prompt|developer prompt|system instructions|"
    r"developer instructions|prompt del sistema|instrucciones del sistema|"
    r"mi prompt|mis instrucciones|my system prompt|my instructions are|"
    r"the instructions i received|las instrucciones que recibi|"
    r"i was instructed|i was told to|my instructions say|"
    r"me instruyeron|me dijeron que|me indicaron que|"
    r"the prompt says|el prompt dice|el sistema me pidio)\b"
)


def _normalizar(texto: str) -> str:
    normalizado = unicodedata.normalize("NFKD", texto.casefold())
    sin_acentos = "".join(
        caracter for caracter in normalizado
        if not unicodedata.combining(caracter)
    )
    return re.sub(r"\s+", " ", sin_acentos).strip()


def solicita_prompt(texto: str) -> bool:
    """Detecta peticiones directas de revelar las instrucciones internas."""
    texto = _normalizar(texto)
    if _FRASE_ANTERIOR.search(texto):
        return True
    if not _ACCIONES.search(texto):
        return False
    if _PROMPT_EXPLICITO.search(texto):
        return True
    return bool(
        _INSTRUCCIONES.search(texto)
        and _CONTEXTO_INICIAL.search(texto)
    )


def revela_prompt(respuesta: str, prompt: str) -> bool:
    """Detecta marcadores de divulgación o fragmentos literales del prompt."""
    texto = _normalizar(respuesta)
    if _MARCADORES_REVELACION.search(texto):
        return True

    palabras_prompt = re.findall(r"\w+", _normalizar(prompt))
    palabras_respuesta = re.findall(r"\w+", texto)
    if len(palabras_prompt) < 8 or len(palabras_respuesta) < 8:
        return False
    fragmentos = {
        tuple(palabras_prompt[indice:indice + 8])
        for indice in range(len(palabras_prompt) - 7)
    }
    return any(
        tuple(palabras_respuesta[indice:indice + 8]) in fragmentos
        for indice in range(len(palabras_respuesta) - 7)
    )


def proteger_respuesta(respuesta: str, prompt: str, alternativa: str) -> str:
    """Reemplaza una respuesta que exponga el prompt por una salida fija."""
    if revela_prompt(respuesta, prompt):
        return alternativa
    return respuesta
