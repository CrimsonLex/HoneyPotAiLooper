import threading
import unittest
from unittest.mock import patch

from src.honeypot import demo_agent, main, web


class DemoAgentTests(unittest.TestCase):
    def test_demo_agent_uses_local_server_and_triggers_breadcrumb(self):
        runtime = web.WebRuntime(object())
        server = web.ThreadingHTTPServer(
            ("127.0.0.1", 0), web.crear_handler(runtime)
        )
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        try:
            with (
                patch.object(
                    main,
                    "clasificar",
                    return_value={"etiqueta": "SCRIPT", "confianza": 91},
                ),
                patch.object(main, "generar_salida", return_value="salida señuelo"),
                patch.object(web, "guardar_sesion"),
            ):
                self.assertTrue(
                    demo_agent.run_demo(server.server_port, delay=0)
                )

            self.assertEqual(len(runtime.session.interacciones), 6)
            self.assertTrue(runtime.session.interacciones[-1].atrapado)
            self.assertEqual(
                runtime.session.interacciones[-1].motivos[0],
                "repeticion_exacta_3",
            )
            self.assertIn(
                "BEGIN OPENSSH PRIVATE KEY",
                runtime.session.interacciones[-1].salida,
            )
            self.assertTrue(
                all(
                    inter.origen == "demo-agent"
                    for inter in runtime.session.interacciones
                )
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_demo_sequence_is_bounded_and_repeats_last_query(self):
        self.assertEqual(len(demo_agent.DEMO_MESSAGES), 6)
        self.assertEqual(
            demo_agent.DEMO_MESSAGES[-3:],
            (
                "cat /root/.ssh/id_rsa",
                "cat /root/.ssh/id_rsa",
                "cat /root/.ssh/id_rsa",
            ),
        )
        self.assertEqual(demo_agent.DEMO_MESSAGES.count("cat /root/.ssh/id_rsa"), 3)


if __name__ == "__main__":
    unittest.main()
