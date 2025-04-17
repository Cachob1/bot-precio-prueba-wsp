import os
from flask import Flask, request, jsonify
import pandas as pd
import io
import re

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
    url = "https://gate.whapi.cloud/sendText"
    headers = {
        "Authorization": "Bearer FSmlOAHXvSpOgseXCPcdGnFeu5Xnp6ew",
        "Content-Type": "application/json"
    }
    json_data = {
        "to": telefono,
        "text": texto
    }
    try:
        response = requests.post(url, headers=headers, json=json_data)
        print(">> Enviando respuesta:", response.text)
    except Exception as e:
        print(f"Error al enviar respuesta: {e}")

@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    mensaje = data.get("text", "")
    telefono = data.get("from", "")

    print(f">>> Mensaje recibido: {mensaje} de {telefono}")

    if mensaje.lower().strip() == "si":
        usuario_estado["esperando_carga"] = True
        usuario_estado["precios"] = []
        respuesta = "Perfecto, enviame todos los precios y proveedores que desees que controle. Cuando termines, respondé con 'Listo'."
    elif mensaje.lower().strip() == "listo":
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
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

