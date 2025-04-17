import os
import time
import requests
import pandas as pd
import io
import re
from flask import Flask

# Configuración Whapi
WHAPI_API_URL = "https://gate.whapi.cloud"
WHAPI_TOKEN = "FSmlOAHXvSpOgseXCPcdGnFeu5Xnp6ew"

# Inicializa Flask
app = Flask(__name__)

# Estado global
usuario_estado = {
    "esperando_carga": False,
    "precios": []
}

# Función para extraer productos desde texto
def extraer_productos(mensaje):
    productos = []
    lineas = mensaje.strip().split("\n")
    for linea in lineas:
        match = re.match(r"(.*?)-(.*?)-\$(\d+)", linea.strip())
        if match:
            producto, presentacion, precio = match.groups()
            productos.append({
                "Producto": producto.strip(),
                "Presentación": presentacion.strip(),
                "Precio": float(precio.strip())
            })
    return productos

# Genera resumen en texto (tipo PDF simulado)
def generar_pdf_comparativo(lista_precios):
    buffer = io.StringIO()
    df = pd.DataFrame(lista_precios)
    if df.empty:
        buffer.write("No se encontraron productos.")
    else:
        resumen = df.groupby("Producto").agg({"Precio": ["min", "max", "mean"]})
        buffer.write(resumen.to_string())
    buffer.seek(0)
    return buffer

# Función para obtener mensajes nuevos desde Whapi
def obtener_mensajes():
    try:
        response = requests.get(f"{WHAPI_API_URL}/messages", headers={
            "Authorization": f"Bearer {WHAPI_TOKEN}"
        })
        if response.status_code == 200:
            return response.json().get("messages", [])
        else:
            print(f"Error al obtener mensajes: {response.text}")
            return []
    except Exception as e:
        print(f"Error en obtener_mensajes: {e}")
        return []

# Función para enviar respuesta por Whapi
def enviar_respuesta(telefono, texto):
    try:
        r = requests.post(f"{WHAPI_API_URL}/sendText", headers={
            "Authorization": f"Bearer {WHAPI_TOKEN}",
            "Content-Type": "application/json"
        }, json={
            "to": telefono,
            "text": texto
        })
        print(f">>> Respuesta del POST: {r.status_code} {r.text}")
    except Exception as e:
        print(f"Error al enviar respuesta: {e}")

# Lógica de procesamiento
def procesar_mensaje(mensaje, telefono):
    texto = mensaje.lower().strip()
    if texto == "si":
        usuario_estado["esperando_carga"] = True
        usuario_estado["precios"] = []
        return "Perfecto, enviame todos los precios y proveedores que desees que controle. Cuando termines, respondé con 'Listo'."
    elif texto == "listo":
        buffer = generar_pdf_comparativo(usuario_estado["precios"])
        usuario_estado["esperando_carga"] = False
        usuario_estado["precios"] = []
        return "Análisis finalizado. Aquí tenés el resumen de precios:\n\n" + buffer.getvalue()
    else:
        productos = extraer_productos(texto)
        if productos:
            usuario_estado["precios"].extend(productos)
            return f"Productos cargados: {len(productos)}"
        else:
            return "Formato no reconocido. Por favor enviá: Producto - Presentación - $Precio"

# Endpoint para ver si el bot está vivo
@app.route("/")
def start_polling():
    return "Bot activo y funcionando con Whapi."

# Bucle que escucha y responde
def loop():
    print(">>> Iniciando bucle de escucha...")
    mensajes_procesados = set()
    while True:
        mensajes = obtener_mensajes()
        for mensaje in mensajes:
            id_msg = mensaje.get("id")
            if id_msg in mensajes_procesados:
                continue  # Ya procesado

            texto = mensaje.get("text", "")
            telefono = mensaje.get("from", "")
            print(f">>> Mensaje recibido: {texto} de {telefono}")

            respuesta = procesar_mensaje(texto, telefono)
            enviar_respuesta(telefono, respuesta)

            mensajes_procesados.add(id_msg)
        time.sleep(10)

# Inicia servidor y bucle
if __name__ == "__main__":
    from threading import Thread
    thread = Thread(target=loop)
    thread.daemon = True
    thread.start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

