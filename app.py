import os
import requests
import pandas as pd
import io
import re
from flask import Flask, request, jsonify

app = Flask(__name__)

usuario_estado = {
    "esperando_carga": False,
    "precios": []
}

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

def enviar_respuesta(telefono, texto):
    url = "https://gate.whapi.cloud/messages/text"
    headers = {
        "Authorization": "Bearer FSmlOAHXvSpOgseXCPcdGnFeu5Xnp6ew",
        "Content-Type": "application/json"
    }
    payload = {
        "to": telefono,
        "body": texto
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f">>> Respuesta enviada: {response.text}")
    except Exception as e:
        print(f"Error al enviar respuesta: {e}")

@app.route("/", methods=["POST"])
def webhook():
    print(">>> 📥 POST recibido desde Whapi")
    data = request.json
    print(data)

    mensajes = data.get("messages", [])
    if not mensajes:
        print(">>> ❌ No hay mensajes nuevos.")
        return jsonify({"status": "ok"})

    for mensaje in mensajes:
        texto = mensaje.get("text", {}).get("body", "").strip()
        telefono = mensaje.get("from", "").strip()

        print(f">>> Mensaje recibido: {texto}")
        print(f">>> Enviado por: {telefono}")

        if not texto or not telefono:
            continue

        if texto.lower() == "si":
            usuario_estado["esperando_carga"] = True
            usuario_estado["precios"] = []
            respuesta = "Perfecto, enviame todos los precios y proveedores que desees que controle. Cuando termines, respondé con 'Listo'."
        elif texto.lower() == "listo":
            buffer = generar_pdf_comparativo(usuario_estado["precios"])
            usuario_estado["esperando_carga"] = False
            usuario_estado["precios"] = []
            respuesta = "Análisis finalizado. Aquí tenés el resumen de precios:\n\n" + buffer.getvalue()
        else:
            productos = extraer_productos(texto)
            if productos:
                usuario_estado["precios"].extend(productos)
                respuesta = f"Productos cargados: {len(productos)}"
            else:
                respuesta = "Formato no reconocido. Por favor enviá: Producto - Presentación - $Precio"

        enviar_respuesta(telefono, respuesta)

    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

