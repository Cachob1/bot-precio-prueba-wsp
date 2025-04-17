import os
from flask import Flask, request, jsonify
import pandas as pd
import io
import re
import requests

# Configuración Whapi
WHAPI_API_URL = "https://gate.whapi.cloud"
WHAPI_TOKEN = "FSmlOAHXvSpOgseXCPcdGnFeu5Xnp6ew"

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

# Función para generar resumen tipo PDF en texto
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

# Función para enviar mensaje por Whapi
def enviar_respuesta(telefono, texto):
    try:
        response = requests.post(f"{WHAPI_API_URL}/sendText", headers={
            "Authorization": f"Bearer {WHAPI_TOKEN}",
            "Content-Type": "application/json"
        }, json={
            "to": telefono,
            "text": texto
        })
        if response.status_code != 200:
            print(f"❌ Error al enviar respuesta: {response.text}")
        else:
            print(f"✅ Respuesta enviada a {telefono}: {texto}")
    except Exception as e:
        print(f"❌ Error en enviar_respuesta: {e}")

# Ruta principal que escucha Webhooks
@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()
    print("📩 Mensaje recibido:", data)

    mensaje = data.get("text", "").strip()
    telefono = data.get("from", "").strip()

    if not mensaje or not telefono:
        return jsonify({"status": "ignored"}), 200

    mensaje_lower = mensaje.lower()

    if mensaje_lower == "si":
        usuario_estado["esperando_carga"] = True
        usuario_estado["precios"] = []
        respuesta = "Perfecto, enviame todos los precios y proveedores que desees que controle. Cuando termines, respondé con 'Listo'."
    elif mensaje_lower == "listo":
        buffer = generar_pdf_comparativo(usuario_estado["precios"])
        usuario_estado["esperando_carga"] = False
        usuario_estado["precios"] = []
        respuesta = "Análisis finalizado. Aquí tenés el resumen de precios:\n\n" + buffer.getvalue()
    else:
        productos = extraer_productos(mensaje)
        if productos:
            usuario_estado["precios"].extend(productos)
            respuesta = f"Productos cargados: {len(productos)}"
        else:
            respuesta = "Formato no reconocido. Por favor enviá: Producto - Presentación - $Precio"

    enviar_respuesta(telefono, respuesta)
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


