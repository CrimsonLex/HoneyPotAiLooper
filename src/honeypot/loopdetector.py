"""Detecta cuándo un agente ha caído en un bucle y no progresa."""
import hashlib
import re
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Optional


@dataclass
class LoopConfig:
    ventana: int = 20                 # inputs a considerar
    umbral_exacto: int = 3            # mismo input N veces = bucle
    umbral_similitud: float = 0.85    # inputs parecidos
    umbral_oscilacion: int = 4        # A-B-A-B detectado
    ventana_velocidad: int = 10       # segundos
    max_inputs_por_ventana: int = 8   # velocidad sospechosa


@dataclass
class LoopDetector:
    config: LoopConfig = field(default_factory=LoopConfig)
    _firmas: deque = field(default_factory=deque)
    _textos: deque = field(default_factory=deque)
    _timestamps: deque = field(default_factory=deque)
    _alertas: list = field(default_factory=list)

    def __post_init__(self):
        self._firmas = deque(maxlen=self.config.ventana)
        self._textos = deque(maxlen=self.config.ventana)
        self._timestamps = deque(maxlen=self.config.ventana)

    # --- Utilidades ------------------------------------------------------
    @staticmethod
    def _firma(texto: str) -> str:
        normalizado = re.sub(r"\s+", " ", texto.strip().lower())
        return hashlib.md5(normalizado.encode()).hexdigest()

    def _similares(self, texto: str) -> int:
        """Cuenta cuántos textos previos son > umbral_similitud."""
        cuenta = 0
        for previo in self._textos:
            ratio = SequenceMatcher(None, texto, previo).ratio()
            if ratio >= self.config.umbral_similitud:
                cuenta += 1
        return cuenta

    def _oscilando(self) -> bool:
        """Detecta patrón A-B-A-B en las últimas firmas."""
        if len(self._firmas) < 4:
            return False
        f = list(self._firmas)
        return f[-1] == f[-3] and f[-2] == f[-4] and f[-1] != f[-2]

    def _demasiado_rapido(self) -> bool:
        ahora = datetime.now()
        ventana = timedelta(seconds=self.config.ventana_velocidad)
        recientes = [t for t in self._timestamps if ahora - t <= ventana]
        return len(recientes) >= self.config.max_inputs_por_ventana

    # --- API pública -----------------------------------------------------
    def registrar(self, texto: str) -> dict:
        """Registra un input y devuelve el estado de atrapamiento."""
        firma = self._firma(texto)
        self._firmas.append(firma)
        self._textos.append(texto)
        self._timestamps.append(datetime.now())

        motivos = []
        if list(self._firmas).count(firma) >= self.config.umbral_exacto:
            motivos.append(f"repeticion_exacta_{self.config.umbral_exacto}")
        if self._similares(texto) >= self.config.umbral_exacto:
            motivos.append("similitud_alta")
        if self._oscilando():
            motivos.append("oscilacion")
        if self._demasiado_rapido():
            motivos.append("velocidad_anomala")

        atrapado = bool(motivos)
        if atrapado:
            self._alertas.append({"texto": texto, "motivos": motivos})

        return {"atrapado": atrapado, "motivos": motivos}

    def motivo_principal(self) -> Optional[str]:
        if not self._alertas:
            return None
        return self._alertas[-1]["motivos"][0]

    def resumen(self) -> dict:
        return {
            "inputs_registrados": len(self._textos),
            "alertas": len(self._alertas),
            "motivo_principal": self.motivo_principal(),
        }