import streamlit as st
import pandas as pd
from datetime import datetime
import os
from pyzbar.pyzbar import decode
from PIL import Image

# --------------------------------------------------------
# CONFIGURACIÓN INICIAL
# --------------------------------------------------------
st.set_page_config(page_title="Inventario Fulltime", page_icon="📦", layout="wide")
DATA_PATH = "inventario.csv"

# --------------------------------------------------------
# FUNCIONES DE BASE DE DATOS
# --------------------------------------------------------
def init_db():
    if not os.path.exists(DATA_PATH):
        df = pd.DataFrame(columns=["codigo", "nombre", "cantidad", "fecha", "tipo_movimiento"])
        df.to_csv(DATA_PATH, index=False)

def leer_datos():
    if os.path.exists(DATA_PATH):
        return pd.read_csv(DATA_PATH)
    else:
        return pd.DataFrame(columns=["codigo", "nombre", "cantidad", "fecha", "tipo_movimiento"])

def guardar_datos(df):
    df.to_csv(DATA_PATH, index=False)

def registrar_movimiento(codigo, nombre, cantidad, tipo):
    df = leer_datos()
    nuevo = pd.DataFrame([{
        "codigo": codigo,
        "nombre": nombre,
        "cantidad": cantidad,
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "tipo_movimiento": tipo
    }])
    df = pd.concat([df, nuevo], ignore_index=True)
    guardar_datos(df)

# --------------------------------------------------------
# FUNCIÓN PARA LEER CÓDIGO QR O DE BARRAS
# --------------------------------------------------------
def leer_codigo_por_camara():
    st.info("Activa la cámara y apunta al código QR o de barras")
    img_file = st.camera_input("📸 Capturar código")
    if img_file is not None:
        img = Image.open(img_file)
        result = decode(img)
        if result:
            return result[0].data.decode('utf-8')
        else:
            st.warning("No se detectó ningún código. Intenta nuevamente.")
    return None

# --------------------------------------------------------
# INTERFAZ PRINCIPAL
# --------------------------------------------------------
init_db()

st.title("📦 Inventario Fulltime")

menu = st.sidebar.radio("Menú", ["🏠 Inicio", "📥 Ingreso de Inventario", "📤 Salida de Inventario", "📊 Panel de Control"])

# --------------------------------------------------------
# INICIO
# --------------------------------------------------------
if menu == "🏠 Inicio":
    st.markdown("""
    ### Bienvenido al Sistema de Inventario Fulltime
    Usa el menú lateral para **ingresar o retirar productos**,  
    o para ver el **panel de control con el stock actual**.
    """)

# --------------------------------------------------------
# INGRESO DE INVENTARIO
# --------------------------------------------------------
elif menu == "📥 Ingreso de Inventario":
    st.subheader("📥 Ingreso de Inventario")

    codigo = st.text_input("Código del producto:")
    if st.button("Usar cámara"):
        result = leer_codigo_por_camara()
        if result:
            codigo = result
            st.success(f"Código detectado: {codigo}")

    nombre = st.text_input("Nombre del producto:")
    cantidad = st.number_input("Cantidad ingresada:", min_value=1, step=1)

    if st.button("Registrar ingreso"):
        if codigo and nombre and cantidad:
            registrar_movimiento(codigo, nombre, cantidad, "Ingreso")
            st.success("✅ Ingreso registrado con éxito")
        else:
            st.error("Por favor completa todos los campos.")

# --------------------------------------------------------
# SALIDA DE INVENTARIO
# --------------------------------------------------------
elif menu == "📤 Salida de Inventario":
    st.subheader("📤 Salida de Inventario")

    codigo = st.text_input("Código del producto:")
    if st.button("Usar cámara"):
        result = leer_codigo_por_camara()
        if result:
            codigo = result
            st.success(f"Código detectado: {codigo}")

    nombre = st.text_input("Nombre del producto:")
    cantidad = st.number_input("Cantidad retirada:", min_value=1, step=1)

    if st.button("Registrar salida"):
        if codigo and nombre and cantidad:
            registrar_movimiento(codigo, nombre, cantidad, "Salida")
            st.success("✅ Salida registrada con éxito")
        else:
            st.error("Por favor completa todos los campos.")

# --------------------------------------------------------
# PANEL DE CONTROL
# --------------------------------------------------------
elif menu == "📊 Panel de Control":
    st.subheader("📊 Panel de Control")

    df = leer_datos()
    if df.empty:
        st.info("No hay registros aún.")
    else:
        st.dataframe(df)

        st.subheader("📈 Resumen por producto")
        resumen = df.groupby(["codigo", "nombre", "tipo_movimiento"])["cantidad"].sum().unstack(fill_value=0)
        resumen["Stock actual"] = resumen.get("Ingreso", 0) - resumen.get("Salida", 0)
        st.dataframe(resumen)
