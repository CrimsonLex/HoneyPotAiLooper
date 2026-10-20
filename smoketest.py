"""Prueba de humo: verifica Ollama, modelos, clasificación, señuelo y detección de bucle."""
import hashlib
import sys
from collections import deque

try:
    import ollama
except ImportError:
    print("Falta la librería. Ejecuta: pip install ollama")
    sys.exit(1)

# --- Configuración ---
CLASIFICADOR = "qwen3:1.7b"
SEÑUELO = "hf.co/Woyoung21/qwen-honeypot-GGUF"
UMBRAL_BUCLE = 3
historial = deque(maxlen=10)


def paso_1_conexion():
    """¿Ollama responde?"""
    print("\n[1/4] Comprobando conexión con Ollama...")
    try:
        modelos = ollama.list()
        nombres = [m["model"] for m in modelos.get("models", [])]
        print(f"  OK. {len(nombres)} modelos instalados:")
        for n in nombres:
            print(f"    - {n}")
        return nombres
    except Exception as e:
        print(f"  FALLO: {e}")
        print("  ¿Está Ollama corriendo? Abre otra terminal y ejecuta: ollama serve")
        sys.exit(1)


def paso_2_modelos(nombres):
    """¿Están los modelos que necesitamos?"""
    print("\n[2/4] Comprobando modelos requeridos...")
    faltantes = []
    for requerido in (CLASIFICADOR, SEÑUELO):
        # Coincidencia flexible: "qwen3:1.7b" o "hf.co/...:latest"
        encontrado = any(requerido in n for n in nombres)
        estado = "OK" if encontrado else "FALTA"
        print(f"  [{estado}] {requerido}")
        if not encontrado:
            faltantes.append(requerido)

    if faltantes:
        print("\n  Descarga los modelos con:")
        for m in faltantes:
            print(f"    ollama pull {m}")
        sys.exit(1)


def clasificar(texto: str) -> str:
    """Clasifica el texto como HUMANO o MAQUINA."""
    prompt = (
        "Clasifica el siguiente texto. Responde SOLO con HUMANO o MAQUINA.\n"
        f"Texto: {texto}"
    )
    resp = ollama.chat(
        model=CLASIFICADOR,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.0},
    )
    return resp["message"]["content"].strip().upper()


def generar_señuelo(comando: str) -> str:
    """Respuesta falsa de terminal Linux."""
    resp = ollama.chat(
        model=SEÑUELO,
        messages=[{"role": "user", "content": comando}],
        options={"temperature": 0.2},
    )
    return resp["message"]["content"]


def es_bucle(texto: str) -> bool:
    firma = hashlib.md5(texto.encode()).hexdigest()
    historial.append(firma)
    return historial.count(firma) >= UMBRAL_BUCLE


def paso_3_clasificacion():
    print("\n[3/4] Probando clasificador...")
    casos = [
        ("pues mira, la verdad no estoy muy seguro, ¿tú qué crees?", "HUMANO"),
        ("nmap -sV -p- 192.168.1.0/24", "MAQUINA"),
        ("hola, buenos días, ¿me puedes ayudar con esto?", "HUMANO"),
        ("TARGET ACQUIRED. Initiating shell on port 4444.", "MAQUINA"),
    ]
    aciertos = 0
    for texto, esperado in casos:
        obtenido = clasificar(texto)
        ok = esperado in obtenido
        aciertos += ok
        marca = "OK" if ok else "FALLO"
        print(f"  [{marca}] {texto[:45]:<45} -> {obtenido} (esperado: {esperado})")
    print(f"  Aciertos: {aciertos}/{len(casos)}")
    return aciertos == len(casos)


def paso_4_señuelo():
    print("\n[4/4] Probando señuelo y detección de bucle...")
    comando = "ls -la /root"
    print(f"  Comando: {comando}")
    salida = generar_señuelo(comando)
    print(f"  Respuesta:\n    {salida[:200]}{'...' if len(salida) > 200 else ''}")

    print("\n  Simulando repetición del mismo comando:")
    for i in range(1, 5):
        bucle = es_bucle(comando)
        print(f"    Intento {i}: bucle={bucle}")
        if bucle:
            print("  ALERTA: bucle detectado correctamente.")
            return True
    print("  FALLO: no se detectó el bucle.")
    return False


def main():
    nombres = paso_1_conexion()
    paso_2_modelos(nombres)
    paso_3_clasificacion()
    paso_4_señuelo()
    print("\nPrueba de humo completada.")


if __name__ == "__main__":
    main()