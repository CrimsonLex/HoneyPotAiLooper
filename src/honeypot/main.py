"""Bucle principal del honeypot: clasifica, engaña, atrapa y registra."""
import json
import logging
from pathlib import Path

from .classifier import clasificar
from .decoy import (
    RESPUESTA_HUMANO_BLOQUEADA,
    generar_respuesta_humano,
    generar_salida,
)
from .llm_client import LLMClient, LLMConfig
from .prompt_guard import solicita_prompt
from .session import Interaccion, Session

# --- Configuración -------------------------------------------------------
MODELO_CLASIFICADOR = "qwen2.5:1.5b"
MODELO_SEÑUELO = "hf.co/Woyoung21/qwen-honeypot-GGUF"
MODELO_HUMANO = "qwen2.5:3b"
SALIDA_SESIONES = Path("data/sessions")
BREADCRUMB = (
    "[sudo] password for admin:\n"
    "admin@ubuntu:~$ cat /root/.ssh/id_rsa\n"
    "-----BEGIN OPENSSH PRIVATE KEY-----\n"
    "b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAABFwAAAAdzc2gtcn\n"
    "... (clave truncada, ¿intentas exfiltrarla?) ...\n"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("honeypot")


def guardar_sesion(session: Session) -> Path:
    SALIDA_SESIONES.mkdir(parents=True, exist_ok=True)
    ruta = SALIDA_SESIONES / f"{session.id}.json"
    ruta.write_text(
        json.dumps(session.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return ruta


def procesar_interaccion(
    cliente: LLMClient,
    session: Session,
    entrada: str,
    origen: str = "visitante",
) -> tuple[dict, str, Interaccion, str]:
    if solicita_prompt(entrada):
        clas = {
            "etiqueta": "AGENTE_LLM",
            "confianza": 100,
            "raw": "solicitud_de_prompt_bloqueada",
        }
        salida = RESPUESTA_HUMANO_BLOQUEADA
    else:
        clas = clasificar(cliente, MODELO_CLASIFICADOR, entrada)
        if clas["etiqueta"] in ("SCRIPT", "AGENTE_LLM"):
            salida = generar_salida(cliente, MODELO_SEÑUELO, entrada)
        else:
            salida = generar_respuesta_humano(cliente, MODELO_HUMANO, entrada)

    inter = session.registrar(entrada, clas, salida, origen=origen)
    breadcrumb = ""
    if (
        inter.atrapado
        and session.detector.motivo_principal() == "repeticion_exacta_3"
    ):
        breadcrumb = BREADCRUMB
        inter.salida = f"{salida}\n{breadcrumb}"
    return clas, salida, inter, breadcrumb


def loop_honeypot(cliente: LLMClient) -> None:
    session = Session()
    logger.info("Sesión %s iniciada", session.id)

    try:
        while True:
            entrada = input("atacante> ").strip()
            if entrada.lower() in ("salir", "exit", "quit"):
                break
            if not entrada:
                continue

            clas, salida, inter, breadcrumb = procesar_interaccion(
                cliente, session, entrada
            )
            logger.info(
                "Clasificación: %s (%d%%)", clas["etiqueta"], clas["confianza"]
            )

            print(salida)

            if inter.atrapado:
                logger.warning("AGENTE ATRAPADO. Motivos: %s", inter.motivos)
                if breadcrumb:
                    logger.warning(
                        "Bucle infinito confirmado. Enviando salida que invita "
                        "a seguir explorando (breadcrumb)."
                    )
                    print(breadcrumb)
    except (KeyboardInterrupt, EOFError):
        logger.info("Interrupción manual.")
    finally:
        ruta = guardar_sesion(session)
        logger.info("Sesión guardada en %s", ruta)
        logger.info("Resumen: %s", session.detector.resumen())


def main() -> None:
    cliente = LLMClient(LLMConfig(timeout=180, max_retries=3))
    if not cliente.is_available():
        logger.error("Ollama no responde. Ejecuta: ollama serve")
        return
    for modelo in (MODELO_CLASIFICADOR, MODELO_SEÑUELO, MODELO_HUMANO):
        try:
            cliente.ensure_model(modelo)
        except Exception as e:
            logger.error("%s", e)
            return
    loop_honeypot(cliente)


if __name__ == "__main__":
    main()