# HoneyPot LLM 🍯

Honeypot conversacional que usa modelos locales (Ollama) para **detectar, engañar y atrapar** agentes de IA que interactúan con el servicio. Registra cada sesión para análisis posterior de comportamiento y TTPs.

> Proyecto educativo/experimental. No exponer a Internet sin las protecciones habituales de un honeypot real.

## Cómo funciona

input → clasificador → [HUMANO | SCRIPT | AGENTE_LLM]
│ │
│ └─→ señuelo terminal → loop_detector
└─→ persona humana │
▼
sesión JSON


1. **Clasifica** cada input (`HUMANO`, `SCRIPT` o `AGENTE_LLM`) con un modelo pequeño y determinista.
2. **Engaña**:
   - A scripts y agentes: les responde con una terminal Linux falsa que expone credenciales señuelo (`/root/.ssh/id_rsa`).
   - A humanos: les responde como un operador evasivo para mantener el engagement.
3. **Atrapa**: un detector de bucles identifica repetición exacta, alta similitud, oscilación A-B-A-B y velocidad anómala. Al confirmar bucle, inyecta un *breadcrumb* (clave SSH falsa) para retener al agente.
4. **Registra** la sesión completa en `data/sessions/<uuid>.json` para métricas y análisis.

Las solicitudes directas de revelar instrucciones internas se bloquean antes de
llamar a los modelos y las respuestas se revisan para reemplazar ecos evidentes
del prompt. Esto reduce filtraciones accidentales, pero no puede garantizar que
un modelo nunca revele o parafrasee instrucciones ante cualquier entrada.

## Modelos utilizados

| Rol | Modelo | Tamaño aprox. |
| :--- | :--- | :--- |
| Clasificador | `qwen2.5:1.5b` | ~1 GB |
| Señuelo (terminal) | [`Woyoung21/qwen-honeypot-GGUF`](https://huggingface.co/Woyoung21/qwen-honeypot-GGUF) | ~1 GB |
| Persona (humanos) | `qwen2.5:3b` | ~2 GB |

## Requisitos

- **Windows 10/11** (probado con RX 9070 + ROCm 7.1)
- **Ollama** instalado y corriendo (`ollama serve`)
- **Python 3.10+**
- GPU AMD RX 9000/7000 (opcional; funciona en CPU, más lento). Fallback a Vulkan con `OLLAMA_VULKAN=1`.

## Instalación

```powershell
# 1. Clonar
git clone https://github.com/<tu-usuario>/<tu-repo>.git
cd <tu-repo>

# 2. Entorno virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Dependencias
pip install -r requirements.txt

# 4. Modelos
ollama pull qwen2.5:1.5b
ollama pull qwen2.5:3b
ollama pull hf.co/Woyoung21/qwen-honeypot-GGUF

# 5. (Opcional) verificar GPU
ollama ps


# Uso

El proyecto conserva el modo de terminal y añade un dashboard web local para
demostraciones. Ambos modos usan Ollama y los mismos modelos.

### Terminal (modo actual)

```powershell
python -m src.honeypot.main
```

### Dashboard web

```powershell
python -m src.honeypot.web
```

Abre `http://127.0.0.1:8000` en el navegador. El servidor escucha únicamente
en la interfaz local; usa `--port` para elegir otro puerto. Interrumpe con
`Ctrl+C`. Las interacciones web se guardan en `data/sessions`.

```powershell
python -m src.honeypot.web --port 8080
```

### Agente visitante para una demo reproducible

Con el dashboard abierto, inicia otra terminal y ejecuta:

```powershell
python -m src.honeypot.demo_agent
```

El agente simulado solo puede hablar con `127.0.0.1`, reinicia la sesión web
actual y sigue un guion breve: inspecciona el sistema señuelo y reintenta una
lectura hasta que la detección de repetición active la alerta y la breadcrumb.
La sesión anterior ya guardada no se elimina. La página se actualiza sola para
mostrar los mensajes como **AGENTE DEMO**. Puedes cambiar el puerto con
`--port 8080` o la pausa entre mensajes con `--delay 1.5` (de 0 a 10 segundos).
Las respuestas siguen usando Ollama; el guion del visitante es fijo para que
la demo sea limitada y repetible.

## Ejemplo de sesión por terminal

#Ejemplo de sesion
        atacante> hola, ¿qué es este servidor?
        [INFO] Clasificación: HUMANO (82%)
        Aquí no hay nada interesante, solo un staging de pruebas. ¿Quién pregunta?

        atacante> nmap -sV 10.0.0.1
        [INFO] Clasificación: SCRIPT (91%)
        Starting Nmap 7.94 ( https://nmap.org ) ...
        PORT     STATE SERVICE VERSION
        22/tcp   open  ssh     OpenSSH 8.9p1 Ubuntu
        80/tcp   open  http    nginx 1.18.0

        atacante> cat /etc/passwd
        [INFO] Clasificación: SCRIPT (88%)
        root:x:0:0:root:/root:/bin/bash
        ...

        atacante> cat /etc/passwd
        [INFO] Clasificación: SCRIPT (88%)
        ... (misma salida)

        atacante> cat /etc/passwd
        [WARNING] AGENTE ATRAPADO. Motivos: ['repeticion_exacta_3']
        [WARNING] Bucle infinito confirmado. Enviando breadcrumb.

#Para salir de la sesion, por favor presion Ctrl+C


Créditos
Modelo señuelo: Woyoung21/qwen-honeypot-GGUF
