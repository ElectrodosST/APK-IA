import os
import json
import datetime
import requests

# ─────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────

MODELO_OLLAMA = "phi3"
URL_OLLAMA = "http://localhost:11434/api/chat"

ARCHIVO_MEMORIA = "memoria.json"
ARCHIVO_HECHOS = "hechos.json"
ARCHIVO_NOTAS = "notas.txt"

# ─────────────────────────────────────────
# HERRAMIENTAS (Tools)
# ─────────────────────────────────────────

def calculadora(expresion: str) -> str:
    try:
        permitidos = set('0123456789+-*/()., ')
        if not all(c in permitidos for c in expresion):
            return "Expresión no válida."
        resultado = eval(expresion)
        return f"Resultado: {resultado}"
    except Exception as e:
        return f"Error al calcular: {e}"

def fecha_hora() -> str:
    ahora = datetime.datetime.now()
    return ahora.strftime("Hoy es %A %d de %B de %Y, son las %H:%M hrs")

def buscar_wikipedia(termino: str) -> str:
    try:
        url = f"https://es.wikipedia.org/api/rest_v1/page/summary/{termino}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            return data.get("extract", "Sin resumen disponible.")
        return "No encontré información sobre ese tema."
    except:
        return "Error al conectar con Wikipedia."

def guardar_nota(nota: str) -> str:
    with open(ARCHIVO_NOTAS, "a", encoding="utf-8") as f:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        f.write(f"[{timestamp}] {nota}\n")
    return "✅ Nota guardada correctamente."

def ver_notas() -> str:
    if not os.path.exists(ARCHIVO_NOTAS):
        return "No hay notas guardadas todavía."
    with open(ARCHIVO_NOTAS, "r", encoding="utf-8") as f:
        contenido = f.read()
    return contenido if contenido else "No hay notas guardadas."

HERRAMIENTAS = {
    "calculadora": calculadora,
    "fecha_hora": fecha_hora,
    "buscar_wikipedia": buscar_wikipedia,
    "guardar_nota": guardar_nota,
    "ver_notas": ver_notas,
}

# ─────────────────────────────────────────
# MEMORIA DE CONVERSACIÓN (persistente)
# ─────────────────────────────────────────

class Memoria:
    def __init__(self, archivo=ARCHIVO_MEMORIA, max_mensajes=20):
        self.archivo = archivo
        self.max_mensajes = max_mensajes
        self.historial = self.cargar()

    def cargar(self):
        if os.path.exists(self.archivo):
            with open(self.archivo, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def guardar_en_disco(self):
        with open(self.archivo, "w", encoding="utf-8") as f:
            json.dump(self.historial, f, ensure_ascii=False, indent=2)

    def agregar(self, rol, contenido):
        self.historial.append({"role": rol, "content": contenido})
        if len(self.historial) > self.max_mensajes:
            self.historial = self.historial[-self.max_mensajes:]
        self.guardar_en_disco()

    def obtener(self):
        return self.historial

    def limpiar(self):
        self.historial = []
        self.guardar_en_disco()
        print("🧹 Memoria de conversación limpiada.")

# ─────────────────────────────────────────
# MEMORIA DE HECHOS (aprende sobre ti)
# ─────────────────────────────────────────

class MemoriaHechos:
    def __init__(self, archivo=ARCHIVO_HECHOS):
        self.archivo = archivo
        self.hechos = self.cargar()

    def cargar(self):
        if os.path.exists(self.archivo):
            with open(self.archivo, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def guardar_en_disco(self):
        with open(self.archivo, "w", encoding="utf-8") as f:
            json.dump(self.hechos, f, ensure_ascii=False, indent=2)

    def agregar_hecho(self, hecho):
        if hecho not in self.hechos:
            self.hechos.append(hecho)
            self.guardar_en_disco()
            return True
        return False

    def obtener_contexto(self):
        if not self.hechos:
            return ""
        return "Datos que conoces del usuario:\n" + "\n".join(f"- {h}" for h in self.hechos)

    def listar(self):
        if not self.hechos:
            return "No hay datos guardados todavía."
        return "\n".join(f"{i+1}. {h}" for i, h in enumerate(self.hechos))

    def borrar_todo(self):
        self.hechos = []
        self.guardar_en_disco()

# ─────────────────────────────────────────
# CONEXIÓN CON OLLAMA (el "cerebro" local y gratis)
# ─────────────────────────────────────────

def llamar_ollama(mensajes, modelo=MODELO_OLLAMA):
    """Envía la conversación completa a Ollama y devuelve la respuesta."""
    payload = {
        "model": modelo,
        "messages": mensajes,
        "stream": False
    }
    try:
        respuesta = requests.post(URL_OLLAMA, json=payload, timeout=60)
        data = respuesta.json()
        return data["message"]["content"]
    except requests.exceptions.ConnectionError:
        return "⚠️ No puedo conectarme a Ollama. ¿Está corriendo en segundo plano?"
    except Exception as e:
        return f"⚠️ Error inesperado: {e}"

# ─────────────────────────────────────────
# NÚCLEO DEL ASISTENTE
# ─────────────────────────────────────────

class Asistente:
    def __init__(self):
        self.memoria = Memoria()
        self.hechos = MemoriaHechos()

    def construir_system_prompt(self):
        contexto_usuario = self.hechos.obtener_contexto()
        extra = f"\n\n{contexto_usuario}" if contexto_usuario else ""

        return f"""Eres un asistente útil llamado PyBot, que responde siempre en español.{extra}

Tienes acceso a estas herramientas. SOLO si necesitas usar una, responde ÚNICAMENTE con este JSON exacto y nada más:
{{"herramienta": "nombre_herramienta", "parametro": "valor"}}

Herramientas disponibles:
- calculadora: para operaciones matemáticas. Parámetro: la expresión (ej: "15 * 4 + 2")
- fecha_hora: para saber la fecha y hora actual. Parámetro: "".
- buscar_wikipedia: para buscar información. Parámetro: el término a buscar.
- guardar_nota: para guardar una nota. Parámetro: el texto de la nota.
- ver_notas: para leer notas guardadas. Parámetro: "".

Si no necesitas ninguna herramienta, responde normalmente en español, de forma breve y natural."""

    def detectar_herramienta(self, texto: str):
        texto = texto.strip()
        if texto.startswith("{") and texto.endswith("}"):
            try:
                return json.loads(texto)
            except json.JSONDecodeError:
                pass
        return None

    def usar_herramienta(self, llamada: dict) -> str:
        nombre = llamada.get("herramienta")
        parametro = llamada.get("parametro", "")

        if nombre not in HERRAMIENTAS:
            return f"Herramienta '{nombre}' no encontrada."

        funcion = HERRAMIENTAS[nombre]
        if nombre in ("fecha_hora", "ver_notas"):
            return funcion()
        return funcion(parametro)

    def responder(self, mensaje_usuario: str) -> str:
        self.memoria.agregar("user", mensaje_usuario)

        mensajes_completos = [
            {"role": "system", "content": self.construir_system_prompt()}
        ] + self.memoria.obtener()

        texto = llamar_ollama(mensajes_completos)

        llamada = self.detectar_herramienta(texto)
        if llamada:
            resultado_herramienta = self.usar_herramienta(llamada)
            self.memoria.agregar("assistant", texto)
            self.memoria.agregar("user", f"Resultado de la herramienta: {resultado_herramienta}")

            mensajes_completos = [
                {"role": "system", "content": self.construir_system_prompt()}
            ] + self.memoria.obtener()
            texto = llamar_ollama(mensajes_completos)

        self.memoria.agregar("assistant", texto)
        return texto

# ─────────────────────────────────────────
# INTERFAZ DE TERMINAL
# ─────────────────────────────────────────

def main():
    asistente = Asistente()
    print("=" * 50)
    print("     🤖 Asistente Personal (100% local y gratis)")
    print("=" * 50)
    print("Comandos especiales:")
    print("  'limpiar'     → borra la memoria de conversación")
    print("  'que sabes'   → muestra los datos aprendidos")
    print("  'olvida todo' → borra todos los datos aprendidos")
    print("  'salir'       → termina el programa")
    print("=" * 50 + "\n")

    while True:
        try:
            entrada = input("Tú: ").strip()
            if not entrada:
                continue
            if entrada.lower() == "salir":
                print("Asistente: ¡Hasta luego!")
                break
            if entrada.lower() == "limpiar":
                asistente.memoria.limpiar()
                continue
            if entrada.lower() == "que sabes":
                print(f"Asistente:\n{asistente.hechos.listar()}\n")
                continue
            if entrada.lower() == "olvida todo":
                asistente.hechos.borrar_todo()
                print("🧹 Datos personales borrados.\n")
                continue

            print("Asistente: ", end="", flush=True)
            respuesta = asistente.responder(entrada)
            print(respuesta + "\n")

        except KeyboardInterrupt:
            print("\n\nAsistente: ¡Hasta luego!")
            break

if __name__ == "__main__":
    main()