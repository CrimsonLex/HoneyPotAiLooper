"""Interfaz web local para mostrar el honeypot en una demo."""
import argparse
import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.parse import urlsplit

from .main import (
    MODELO_CLASIFICADOR,
    MODELO_HUMANO,
    MODELO_SEÑUELO,
    guardar_sesion,
    procesar_interaccion,
)
from .llm_client import LLMClient, LLMConfig
from .session import Session

logger = logging.getLogger("honeypot.web")
MAX_REQUEST_BYTES = 16_384
INDEX_PATH = Path(__file__).with_name("web") / "index.html"


class WebRuntime:
    def __init__(self, cliente: LLMClient):
        self.cliente = cliente
        self.session = Session()
        self.lock = Lock()


def crear_handler(runtime: WebRuntime):
    class HoneypotHandler(BaseHTTPRequestHandler):
        def _send(self, status: int, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                "script-src 'self' 'unsafe-inline'; connect-src 'self'; "
                "img-src 'self' data:",
            )
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, status: int, data: dict) -> None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self._send(status, "application/json; charset=utf-8", body)

        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            if path == "/":
                try:
                    body = INDEX_PATH.read_bytes()
                except OSError:
                    logger.exception("No se pudo cargar la interfaz web")
                    self._send_json(500, {"error": "No se pudo cargar la interfaz."})
                    return
                self._send(200, "text/html; charset=utf-8", body)
                return

            if path == "/api/state":
                with runtime.lock:
                    state = runtime.session.to_dict()
                    state["status"] = "online"
                self._send_json(200, state)
                return

            self._send_json(404, {"error": "Ruta no encontrada."})

        def do_POST(self) -> None:
            path = urlsplit(self.path).path
            if path == "/api/reset":
                with runtime.lock:
                    runtime.session = Session()
                    state = runtime.session.to_dict()
                    state["status"] = "online"
                self._send_json(200, state)
                return
            if path != "/api/message":
                self._send_json(404, {"error": "Ruta no encontrada."})
                return

            try:
                content_length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._send_json(400, {"error": "Longitud de solicitud inválida."})
                return
            if content_length < 1:
                self._send_json(400, {"error": "La solicitud no contiene un mensaje."})
                return
            if content_length > MAX_REQUEST_BYTES:
                self._send_json(413, {"error": "El mensaje supera el límite permitido."})
                return

            try:
                data = json.loads(self.rfile.read(content_length))
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._send_json(400, {"error": "El cuerpo debe ser JSON válido."})
                return
            if not isinstance(data, dict) or not isinstance(data.get("text"), str):
                self._send_json(400, {"error": "Se requiere un campo de texto."})
                return
            origen = data.get("source", "visitante")
            if origen not in ("visitante", "demo-agent"):
                self._send_json(400, {"error": "Origen de mensaje no válido."})
                return
            entrada = data["text"].strip()
            if not entrada:
                self._send_json(400, {"error": "Escribe un mensaje antes de enviarlo."})
                return

            try:
                with runtime.lock:
                    clas, _, inter, _ = procesar_interaccion(
                        runtime.cliente, runtime.session, entrada, origen
                    )
                    guardar_sesion(runtime.session)
                    state = runtime.session.to_dict()
                self._send_json(
                    200,
                    {
                        "clasificacion": clas["etiqueta"],
                        "confianza": clas["confianza"],
                        "atrapado": inter.atrapado,
                        "motivos": inter.motivos,
                        "salida": inter.salida,
                        "state": state,
                    },
                )
            except Exception:
                logger.exception("No se pudo procesar un mensaje web")
                self._send_json(
                    500,
                    {"error": "No se pudo procesar el mensaje. Revisa Ollama y los registros."},
                )

    return HoneypotHandler


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inicia el dashboard web local del honeypot."
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Puerto local (por defecto: 8000)"
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port debe estar entre 1 y 65535")

    cliente = LLMClient(LLMConfig(timeout=180, max_retries=3))
    if not cliente.is_available():
        logger.error("Ollama no responde. Ejecuta: ollama serve")
        return
    for modelo in (MODELO_CLASIFICADOR, MODELO_SEÑUELO, MODELO_HUMANO):
        try:
            cliente.ensure_model(modelo)
        except Exception as error:
            logger.error("%s", error)
            return

    runtime = WebRuntime(cliente)
    server = ThreadingHTTPServer(
        ("127.0.0.1", args.port), crear_handler(runtime)
    )
    logger.info("Demo web lista en http://127.0.0.1:%d", args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Cerrando servidor web.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
