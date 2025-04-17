import os
from flask import Flask, request, jsonify
import pandas as pd
import io
import re
from difflib import get_close_matches
import requests

app = Flask(__name__)

WHAPI_TOKEN = os.getenv("WHAPI_TOKEN")
WHAPI_URL = "https://gate.whapi.cloud/messages/text"

usuario_estado = {
    "esperando_carga": False,
    "precios": []
}

def extraer_productos(texto):
    productos = []
    lineas = texto.split("\n")
    for linea in lineas:
        partes = re.split(r"\s*-\s*", linea)
        if len(partes) == 3:
            producto, presentacion, precio = partes
            precio = re.sub(r"[^\d.,]", "", precio).replace(",", ".")
            try:
                precio_float = float(precio)
                productos.append({
                    "Producto": producto.strip(),
                    "Presentación": presentacion.strip(),
                    "Precio": precio_float
                })
            except:
                continue
    return productos

def generar_pdf_comparativo(productos):
    df = pd.DataFrame(productos)
    buffer = io.BytesIO()
    df.to_string(buf := io.StringIO(), index=False)
    buffer.write(buf.getvalue().encode("utf-8"))
    buffer.seek(0)
    return buffer

def enviar_mensaje(numero, texto):
    headers = {
        "Authorization": f"Bearer {WHAPI_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "to": numero,
        "text": texto
    }
    response = requests.post(WHAPI_URL, headers=headers, json=payload)
    return response.status_code

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    numero = data.get("phone")
    mensaje = data.get("message", "").strip().lower()

    if not numero or not mensaje:
        return jsonify({"error": "Falta número o mensaje"}), 400

    if mensaje == "si":
        usuario_estado["esperando_carga"] = True
        usuario_estado["precios"] = []
        enviar_mensaje(numero, "Perfecto, enviame todos los precios y proveedores que desees que controle. Cuando termines, respondé con 'Listo'.")
    elif mensaje == "listo":
        buffer = generar_pdf_comparativo(usuario_estado["precios"])
        usuario_estado["esperando_carga"] = False
        usuario_estado["precios"] = []
        resumen = buffer.getvalue().decode("utf-8")
        enviar_mensaje(numero, "Análisis finalizado. Aquí tenés el resumen de precios:\n\n" + resumen)
    else:
        productos = extraer_productos(mensaje)
        if productos:
            usuario_estado["precios"].extend(productos)
            enviar_mensaje(numero, f"Productos cargados: {len(productos)}")
        else:
            enviar_mensaje(numero, "Estoy aquí para ayudarte. Si ya tenés todos los precios respondé: 'Si'. O bien, mandá productos con el formato: Producto - Presentación - $Precio")

    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

