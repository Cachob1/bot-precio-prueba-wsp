
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import pandas as pd
import io
import re
from difflib import get_close_matches

app = Flask(__name__)

usuario_estado = {
    "esperando_carga": False,
    "precios": []
}

nombres_referencia = ["Coca Cola 1.5L", "Quilmes 1L", "Sprite 1.5L"]

def normalizar_producto(nombre):
    coincidencias = get_close_matches(nombre, nombres_referencia, n=1, cutoff=0.6)
    return coincidencias[0] if coincidencias else nombre

def calcular_precio_unitario(precio_total, descripcion):
    match = re.search(r"x(\d+)", descripcion.lower())
    if match:
        cantidad = int(match.group(1))
        return round(precio_total / cantidad, 2)
    return precio_total

def extraer_productos(texto):
    lineas = texto.split('\n')
    resultados = []
    for linea in lineas:
        match = re.match(r"(.*?)-(.*?)-\$?(\d+[.,]?\d*)", linea)
        if match:
            producto_raw = match.group(1).strip()
            unidad = match.group(2).strip()
            precio = float(match.group(3).replace(",", "."))
            producto = normalizar_producto(producto_raw)
            precio_unitario = calcular_precio_unitario(precio, unidad)
            resultados.append({
                "Producto": producto,
                "Unidad": "1 ud",
                "Precio": precio_unitario,
                "Descripcion": unidad
            })
    return resultados

def generar_pdf_comparativo(productos):
    df = pd.DataFrame(productos)
    resumen = df.groupby("Producto").agg({"Precio": ["min", "mean"]})
    resumen.columns = ["Precio más bajo", "Promedio"]
    resumen = resumen.reset_index()
    resumen["Ahorro vs promedio"] = resumen["Promedio"] - resumen["Precio más bajo"]
    resumen["% más barato"] = 100 * (1 - resumen["Precio más bajo"] / resumen["Promedio"])
    resumen["Unidad"] = "1 ud"
    resultado = resumen[["Producto", "Unidad", "Precio más bajo", "Ahorro vs promedio", "% más barato"]]
    buffer = io.StringIO()
    resultado.to_string(buf=buffer, index=False)
    buffer.seek(0)
    return buffer

@app.route("/wsp", methods=["POST"])
def whatsapp_bot():
    mensaje = request.form.get("Body")
    resp = MessagingResponse()

    if not usuario_estado["esperando_carga"]:
        if mensaje.lower().strip() == "si":
            usuario_estado["esperando_carga"] = True
            usuario_estado["precios"] = []
            resp.message("Perfecto, enviame todos los precios y proveedores que desees que controle. Cuando termines, respondé con 'Listo'.")
        else:
            resp.message("Estoy aquí para ayudarte. Si ya tenés todos los precios de tus proveedores respondé: 'Si'")
    elif mensaje.lower().strip() == "listo":
        buffer = generar_pdf_comparativo(usuario_estado["precios"])
        usuario_estado["esperando_carga"] = False
        usuario_estado["precios"] = []
        mensaje_final = resp.message("Análisis finalizado. Aquí tenés el resumen de precios:\n\n" + buffer.getvalue())

" + buffer.getvalue())
    else:
        productos = extraer_productos(mensaje)
        if productos:
            usuario_estado["precios"].extend(productos)
            resp.message(f"Productos cargados: {len(productos)}")
        else:
            resp.message("Formato no reconocido. Por favor enviá: Producto - Presentación - $Precio")

    return str(resp)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # Render define PORT automáticamente
    app.run(host="0.0.0.0", port=port)
