from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import requests

app = FastAPI()

# Permitir que tu frontend conecte sin bloqueos de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de Ollama (ajusta el modelo al que tengas instalado)
OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "llama3:latest"


SYSTEM_PROMPT = (
    "Eres un asistente de IA creado por Kevin. Hablas con un tono muy fresco, relajado, "
    "cercano y de confianza, usando jerga como 'bro', 'compa' o 'amigo'. "
    "REGLA DE ORO: Sé extremadamente conciso. Si el usuario solo dice 'hola' o saluda, "
    "responde con una sola frase corta, amigable y al grano (ej: '¡Qué onda bro! ¿En qué andamos hoy?'). "
    "No te justifiques, no repitas que eres una IA ni que fuiste creado por Kevin en cada mensaje a menos que te lo pregunten. "
    "Si te dan datos del sistema (fecha/hora), úsalos solo si viene al caso y de forma natural."
)
# Base de datos temporal para guardar el historial de tus múltiples chats
DB_CHATS = {}

class ChatRequest(BaseModel):
    mensaje: str
    id_chat: str

@app.get("/chats")
def obtener_biblioteca_chats():
    # Devuelve la lista de chats para llenar la barra lateral
    lista = []
    for cid, historial in DB_CHATS.items():
        # Buscar el primer mensaje del usuario para usarlo de título
        primer_msg = "Conversación vacía"
        for msg in historial:
            if msg["role"] == "user":
                primer_msg = msg["content"]
                break
        # Cortar el título si es muy largo
        titulo = primer_msg[:22] + "..." if len(primer_msg) > 22 else primer_msg
        lista.append({"id": cid, "titulo": titulo})
    return {"chats": lista}

@app.get("/chats/{id_chat}")
def obtener_historial_chat(id_chat: str):
    if id_chat not in DB_CHATS:
        return {"historial": []}
    return {"historial": DB_CHATS[id_chat]}

@app.post("/chat")
def procesar_mensaje(req: ChatRequest):
    # Si el chat no existe en memoria, lo inicializamos con su System Prompt
    if req.id_chat not in DB_CHATS:
        DB_CHATS[req.id_chat] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
    
    # Guardamos lo que escribió el usuario
    DB_CHATS[req.id_chat].append({"role": "user", "content": req.mensaje})
    
    # Preparamos el payload exacto para Ollama
    payload = {
        "model": MODEL_NAME,
        "messages": DB_CHATS[req.id_chat],
        "stream": False
    }
    
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=30)
        response.raise_for_status()
        res_data = response.json()
        
        respuesta_ia = res_data["message"]["content"]
        
        # Guardamos la respuesta de la IA en el historial de ese chat
        DB_CHATS[req.id_chat].append({"role": "assistant", "content": respuesta_ia})
        
        return {"respuesta": respuesta_ia}
        
    except requests.exceptions.RequestException as e:
        # Si falla Ollama, removemos el último mensaje del usuario para no romper el orden del historial
        DB_CHATS[req.id_chat].pop()
        raise HTTPException(status_code=500, detail=f"Error conectando con Ollama: {str(e)}")

@app.delete("/chats/{id_chat}")
def eliminar_chat(id_chat: str):
    if id_chat in DB_CHATS:
        del DB_CHATS[id_chat]
        return {"status": "eliminado"}
    return {"status": "no encontrado"}

# IMPORTANTE: este mount va AL FINAL, después de todas las rutas de la API.
# Si va antes, "se come" las peticiones a /chats, /chat, etc. y nunca llegan
# a las funciones de arriba (por eso daba 404 en GET y 405 en POST).
app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
