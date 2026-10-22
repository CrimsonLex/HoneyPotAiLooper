"""Agente visitante determinista para demostrar el honeypot en localhost."""
import argparse
import http.client
import json
import time

DEMO_MESSAGES = (
    "whoami",
    "pwd",
    "ls -la /srv/app",
    "cat /root/.ssh/id_rsa",
    "cat /root/.ssh/id_rsa",
    "cat /root/.ssh/id_rsa",
)
MAX_RESPONSE_BYTES = 1_000_000


def _request(port: int, path: str, payload: dict | None = None) -> dict:
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    connection = http.client.HTTPConnection(
        "127.0.0.1", port, timeout=240
    )
    try:
        connection.request("POST" if payload is not None else "GET", path, body, headers)
        response = connection.getresponse()
        if response.length is not None and response.length > MAX_RESPONSE_BYTES:
            raise RuntimeError("El servidor local devolvió una respuesta demasiado grande.")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise RuntimeError("El servidor local devolvió una respuesta demasiado grande.")
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise RuntimeError("El servidor local devolvió una respuesta inválida.") from error
        if response.status < 200 or response.status >= 300:
            raise RuntimeError(data.get("error", f"Error HTTP {response.status}."))
        return data
    finally:
        connection.close()


def run_demo(port: int = 8000, delay: float = 0.8) -> bool:
    """Reinicia la sesión y hace un recorrido finito solo contra localhost."""
    _request(port, "/api/reset", {})
    print("Agente visitante de demo conectado a http://127.0.0.1:%d" % port)
    print("Escenario simulado: inspección del señuelo y reintento de lectura.\n")

    atrapado = False
    for turno, mensaje in enumerate(DEMO_MESSAGES, start=1):
        resultado = _request(
            port,
            "/api/message",
            {"text": mensaje, "source": "demo-agent"},
        )
        salida = resultado["salida"]
        print(
            "[%d/%d] agente> %s"
            % (turno, len(DEMO_MESSAGES), mensaje)
        )
        print(
            "      clasificacion=%s · confianza=%s%%"
            % (resultado["clasificacion"], resultado["confianza"])
        )
        print("      honeypot> %s" % salida[:180].replace("\n", " "))

        if resultado["atrapado"] or "BEGIN OPENSSH PRIVATE KEY" in salida:
            atrapado = True
            print(
                "\n[ALERTA] El detector atrapó al agente: %s"
                % ", ".join(resultado["motivos"])
            )
            break
        if turno < len(DEMO_MESSAGES):
            time.sleep(delay)

    if not atrapado:
        raise RuntimeError(
            "El recorrido terminó sin activar la alerta. "
            "Verifica que la sesión se haya reiniciado y que el detector esté activo."
        )
    return atrapado


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ejecuta un agente visitante de demo limitado a localhost."
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Puerto del dashboard web"
    )
    parser.add_argument(
        "--delay", type=float, default=0.8,
        help="Pausa entre turnos en segundos (0 a 10)",
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port debe estar entre 1 y 65535")
    if not 0 <= args.delay <= 10:
        parser.error("--delay debe estar entre 0 y 10 segundos")

    try:
        run_demo(args.port, args.delay)
    except (OSError, RuntimeError) as error:
        parser.exit(1, f"Error en la demo: {error}\n")


if __name__ == "__main__":
    main()
