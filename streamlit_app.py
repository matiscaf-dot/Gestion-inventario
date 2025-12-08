# app.py
import streamlit as st
import pandas as pd
from datetime import datetime
import os
import json
from io import BytesIO
from PIL import Image

# ==============================
# CONFIGURACIÓN GENERAL
# ==============================
st.set_page_config(page_title="Inventario FullTime", layout="wide")
DATA_FILE = "inventario.xlsx"
USUARIOS_FILE = "usuarios.json"
HISTORIAL_FILE = "historial.csv"
FACTURAS_DIR = "facturas"
BOLETAS_DIR = "boletas"
BACKUPS_DIR = "backups"
CAPTURAS_DIR = "capturas"

# Asegurar carpetas
os.makedirs(FACTURAS_DIR, exist_ok=True)
os.makedirs(BOLETAS_DIR, exist_ok=True)
os.makedirs(BACKUPS_DIR, exist_ok=True)
os.makedirs(CAPTURAS_DIR, exist_ok=True)

# ==============================
# Intento de import para lector de códigos de barras (pyzbar)
# ==============================
_HAS_PYZBAR = False
try:
    from pyzbar.pyzbar import decode as zbar_decode
    _HAS_PYZBAR = True
except Exception:
    _HAS_PYZBAR = False

# ==============================
# FUNCIONES AUXILIARES
# ==============================
# ... (todo tu bloque de funciones auxiliares se mantiene igual)

# ==============================
# LOGIN
# ==============================
# ... (se mantiene igual)

# ==============================
# MENÚ PRINCIPAL
# ==============================
# ... (se mantiene igual)

# ==============================
# DASHBOARD
# ==============================
# ... (se mantiene igual)

# ==============================
# PRODUCTOS
# ==============================
# ... (se mantiene igual)

# ==============================
# ENTRADAS (con cámara + proveedor + factura PDF mejorado)
# ==============================
if st.session_state["pagina"] == "entradas":
    if st.session_state["rol"] not in ["admin", "bodeguero"]:
        st.error("No tienes permiso para acceder a esta sección.")
        st.stop()

    st.title("📦 Registrar Entrada de Inventario")
    prov_df = cargar_proveedores()

    # Captura por cámara (opcional) para obtener código de barras
    st.subheader("Capturar imagen con la cámara (opcional) para leer código de barras")
    camera_image = st.camera_input("Toma una foto del producto o código")

    pre_codigo = ""
    if camera_image:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        camera_path = os.path.join(CAPTURAS_DIR, f"entrada_{timestamp}.jpg")
        with open(camera_path, "wb") as f:
            f.write(camera_image.getbuffer())
        st.success("Imagen guardada.")
        try:
            pil_img = Image.open(camera_path).convert("RGB")
            detected = decode_barcode_from_pil(pil_img)
            if detected:
                st.info(f"Código detectado: {detected}")
                pre_codigo = detected
            else:
                if not _HAS_PYZBAR:
                    st.warning("pyzbar no está instalado: no se pudo decodificar automáticamente.")
                else:
                    st.info("No se detectó código en la imagen.")
        except Exception as e:
            st.error(f"No se pudo procesar la imagen: {e}")

    st.markdown("---")
    codigo = st.text_input("Código del producto", value=pre_codigo)
    nombre = st.text_input("Nombre del producto (opcional)")
    cantidad = st.number_input("Cantidad a ingresar", min_value=1, step=1, value=1)
    precio_costo = st.number_input("Precio costo (opcional)", min_value=0.0, step=0.1, format="%.2f", value=0.0)
    precio_venta = st.number_input("Precio venta (opcional)", min_value=0.0, step=0.1, format="%.2f", value=0.0)

    # Proveedor en entrada
    prov_options = [""] + prov_df["nombre"].astype(str).tolist()
    proveedor_sel = st.selectbox("Proveedor asociado (opcional)", prov_options)
    nuevo_proveedor_txt = st.text_input("O crea nuevo proveedor (nombre) - opcional")

    # --- Subida de factura PDF ---
    st.subheader("Subir factura en PDF")
    factura_file = st.file_uploader("Selecciona factura en PDF", type=["pdf"])

    if factura_file is not None and st.button("Procesar Factura PDF"):
        try:
            import re, uuid, pdfplumber, io
            from PIL import Image
            import pytesseract

            safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', factura_file.name)
            unique_filename = f"{uuid.uuid4()}_{safe_filename}"
            factura_path = os.path.join(FACTURAS_DIR, unique_filename)
            with open(factura_path, "wb") as f:
                f.write(factura_file.getbuffer())

            productos = []

            # 1. Intentar con pdfplumber
            with pdfplumber.open(io.BytesIO(factura_file.getvalue())) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    tables = page.extract_tables()
                    st.write(f"Página {page_num} → Tablas detectadas: {len(tables)}")
                    for table in tables:
                        for row in table:
                            st.write("Fila:", row)
                            if row and len(row) >= 4:
                                codigo = str(row[0]).strip()
                                descripcion = str(row[1]).strip()
                                try:
                                    cantidad = int(str(row[2]).replace(".", "").replace(",", ""))
                                    precio_costo = float(str(row[3]).replace(".", "").replace(",", "."))
                                except Exception as e:
                                    st.write("Error parseando fila:", e)
                                    continue
                                productos.append({
                                    "codigo": codigo,
                                    "nombre": descripcion,
                                    "cantidad": cantidad,
                                    "precio_costo": precio_costo
                                })

            # 2. Fallback OCR si productos está vacío
            if not productos:
                st.warning("⚠️ No se detectaron productos con pdfplumber. Intentando con OCR...")
                img = Image.open(io.BytesIO(factura_file.getvalue()))
                texto = pytesseract.image_to_string(img, lang="spa")
                for line in texto.split("\n"):
                    parts = line.split()
                    if len(parts) >= 4 and parts[2].isdigit():
                        codigo = parts[0]
                        nombre = parts[1]
                        cantidad = int(parts[2])
                        try:
                            precio_costo = float(parts[3].replace(",", "."))
                        except:
                            precio_costo = 0.0
                        productos.append({
                            "codigo": codigo,
                            "nombre": nombre,
                            "cantidad": cantidad,
                            "precio_costo": precio_costo
                        })

            if productos:
                st.success(f"✅ Productos detectados: {len(productos)}")
                st.dataframe(productos)
                for p in productos:
                    registrar_movimiento("entrada", p["codigo"], p["nombre"], p["cantidad"],
                                         usuario_actual=st.session_state.get("usuario"),
                                         precio_costo=p["precio_costo"], proveedor=proveedor_sel)
                st.success("✅ Productos ingresados desde factura PDF")
            else:
                st.error("❌ No se detectaron productos válidos en la factura.")

        except Exception as e:
            st.error(f"❌ Error al procesar factura PDF: {e}")

    # --- Captura de factura con cámara ---
    st.subheader("Capturar factura con cámara")
    foto = st.camera_input("📸 Toma una foto de la factura")

    if foto is not None and st.button("Procesar Factura Foto"):
        try:
            import re, uuid
            from PIL import Image
            import pytesseract

            safe_filename = f"{uuid.uuid4()}_captura.jpg"
            factura_path = os.path.join(FACTURAS_DIR, safe_filename)
            with open(factura_path, "wb") as f:
                f.write(foto.getbuffer())

            img = Image.open(foto)
            texto = pytesseract.image_to_string(img, lang="spa")

            productos = []
            for line in texto.split("\n"):
                parts = line.split()
                if len(parts) >= 4 and parts[2].isdigit():
                    codigo = parts[0]
                    nombre = parts[1]
                    cantidad = int(parts[2])
                    try:
                        precio_costo = float(parts[3].replace(",", "."))
                    except:
                        precio_costo = 0.0
                    productos.append({
                        "codigo": codigo,
                        "nombre": nombre,
                        "cantidad": cantidad,
                        "precio_costo": precio_costo
                    })

                        if productos:
                st.success(f"✅ Productos detectados: {len(productos)}")
                st.dataframe(productos)
                for p in productos:
                    registrar_movimiento(
                        "entrada",
                        p["codigo"],
                        p["nombre"],
                        p["cantidad"],
                        usuario_actual=st.session_state.get("usuario"),
                        precio_costo=p["precio_costo"],
                        proveedor=proveedor_sel
                    )
                st.success("✅ Productos ingresados desde factura Foto")
            else:
                st.error("❌ No se detectaron productos válidos en la foto.")

        except Exception as e:
            st.error(f"❌ Error al procesar factura Foto: {e}")

    # Botón volver
    if st.button("⬅️ Volver al menú principal"):
        go_to("menu")

