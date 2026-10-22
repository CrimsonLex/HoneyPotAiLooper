"""Estado de una sesión de honeypot (un atacante = una sesión)."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from .loopdetector import LoopDetector


@dataclass
class Interaccion:
    timestamp: datetime
    input: str
    clasificacion: str
    confianza: int
    salida: str = ""
    atrapado: bool = False
    motivos: list = field(default_factory=list)
    origen: str = "visitante"


@dataclass
class Session:
    id: str = field(default_factory=lambda: str(uuid4()))
    inicio: datetime = field(default_factory=datetime.now)
    interacciones: list = field(default_factory=list)
    detector: LoopDetector = field(default_factory=LoopDetector)
    agente_confirmado: bool = False

    def registrar(
        self,
        input_texto: str,
        clasificacion: dict,
        salida: str = "",
        origen: str = "visitante",
    ) -> Interaccion:
        estado = self.detector.registrar(input_texto)
        inter = Interaccion(
            timestamp=datetime.now(),
            input=input_texto,
            clasificacion=clasificacion["etiqueta"],
            confianza=clasificacion["confianza"],
            salida=salida,
            atrapado=estado["atrapado"],
            motivos=estado["motivos"],
            origen=origen,
        )
        self.interacciones.append(inter)

        # Confirmamos agente si el clasificador lo dice O si cae en bucle
        if clasificacion["etiqueta"] == "AGENTE_LLM" or estado["atrapado"]:
            self.agente_confirmado = True
        return inter

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "inicio": self.inicio.isoformat(),
            "agente_confirmado": self.agente_confirmado,
            "detector": self.detector.resumen(),
            "interacciones": [
                {
                    "timestamp": i.timestamp.isoformat(),
                    "input": i.input,
                    "origen": i.origen,
                    "clasificacion": i.clasificacion,
                    "confianza": i.confianza,
                    "salida": i.salida[:500],  # truncado para el JSON
                    "atrapado": i.atrapado,
                    "motivos": i.motivos,
                }
                for i in self.interacciones
            ],
        }