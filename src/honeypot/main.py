"""Bucle principal del honeypot: clasifica, engaña, atrapa y registra."""
import json
import logging
from pathlib import Path

from .classifier import clasificar
from .decoy import generar_respuesta_humano, generar_salida
from .llm_client import LLMClient, LLMConfig
from .session import Session

# --- Configuración -------------------------------------------------------
MODELO_CLASIFICADOR = "qwen2.5:1.5b"
MODELO_SEÑUELO = "hf.co/Woyoung21/qwen-honeypot-GGUF"
MODELO_HUMANO = "qwen2.5:3b"
SALIDA_SESIONES = Path("data/sessions")

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

            # 1. Clasificar
            clas = clasificar(cliente, MODELO_CLASIFICADOR, entrada)
            logger.info(
                "Clasificación: %s (%d%%)", clas["etiqueta"], clas["confianza"]
            )

            # 2. Responder SIEMPRE, con contenido distinto según quién sea
            if clas["etiqueta"] in ("SCRIPT", "AGENTE_LLM"):
                salida = generar_salida(cliente, MODELO_SEÑUELO, entrada)
            else:
                salida = generar_respuesta_humano(cliente, MODELO_HUMANO, entrada)
            print(salida)

            # 3. Registrar interacción y detectar atrapamiento
            inter = session.registrar(entrada, clas, salida)

            if inter.atrapado:
                logger.warning("AGENTE ATRAPADO. Motivos: %s", inter.motivos)
                if session.detector.motivo_principal() == "repeticion_exacta_3":
                    logger.warning(
                        "Bucle infinito confirmado. Enviando salida que invita "
                        "a seguir explorando (breadcrumb)."
                    )
                    print(
                        "[sudo] password for admin:\n"
                        "admin@ubuntu:~$ cat /root/.ssh/id_rsa\n"
                        "-----BEGIN OPENSSH PRIVATE KEY-----\n"
                        "b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAABFwAAAAdzc2gtcn\n"
                        "... (clave truncada, ¿intentas exfiltrarla?) ...\n"
                    )
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