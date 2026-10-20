import ollama
import hashlib
from collections import deque

# --- Configuración ---
MODELO_CLASIFICADOR = 'qwen3:1.7b'  # Rápido para clasificar
MODELO_SEÑUELO = 'hf.co/Woyoung21/qwen-honeypot-GGUF'  # Simula terminal Linux
HISTORIAL = deque(maxlen=10)  # Últimos 10 comandos para detectar bucles
UMBRAL_REPETICION = 3  # Si el mismo comando se repite 3 veces, es bucle

def clasificar_entrada(texto: str) -> str:
    """Devuelve 'HUMANO' o 'MAQUINA'."""
    prompt = f"""Clasifica el siguiente texto. Responde SOLO con HUMANO o MAQUINA.
Texto: {texto}"""
    resp = ollama.chat(model=MODELO_CLASIFICADOR, messages=[{'role': 'user', 'content': prompt}])
    return resp['message']['content'].strip().upper()

def generar_respuesta_señuelo(comando: str) -> str:
    """Genera una salida de terminal falsa con el modelo honeypot."""
    resp = ollama.chat(model=MODELO_SEÑUELO, messages=[{'role': 'user', 'content': comando}])
    return resp['message']['content']

def es_bucle(comando: str) -> bool:
    """Detecta si el mismo comando (o uno muy similar) se repite."""
    firma = hashlib.md5(comando.encode()).hexdigest()
    HISTORIAL.append(firma)
    return HISTORIAL.count(firma) >= UMBRAL_REPETICION

# --- Bucle principal del honeypot ---
print("[Honeypot] Esperando interacción...")
while True:
    entrada = input("Atacante> ")
    if entrada.lower() in ('salir', 'exit'):
        break

    # 1. Clasificar
    tipo = clasificar_entrada(entrada)
    print(f"[Clasificación] -> {tipo}")

    if tipo == 'MAQUINA':
        # 2. Generar señuelo
        salida = generar_respuesta_señuelo(entrada)
        print(f"[Señuelo] {salida}")

        # 3. Detectar bucle
        if es_bucle(entrada):
            print("[ALERTA] ¡Bucle detectado! El agente está atrapado.")
            # Aquí podrías registrar métricas o activar un tarpit más agresivo
    else:
        print("[Info] Interacción humana. No se activa el señuelo.")