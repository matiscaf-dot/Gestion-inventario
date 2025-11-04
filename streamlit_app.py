import streamlit as st
import pandas as pd
from datetime import datetime
import os

# ==============================
# CONFIGURACIÓN GENERAL
# ==============================
st.set_page_config(page_title="Inventario FullTime", layout="wide")
DATA_FILE = "inventario.xlsx"

# ==============================
# FUNCIONES AUXILIARES
# ==============================
def cargar_datos():
    if os.path.exists(DATA_FILE):
        return pd.read_excel(DATA_FILE)
    else:
        df = pd.DataFrame(columns=["codigo", "nombre", "categoria", "cantidad", "fecha ingreso"])
        df.to_xlsx(DATA_FILE, index=False)
        return df

def guardar_datos(df):
    df.to_xlsx(DATA_FILE, index=False)

def registrar_movimiento(tipo, codigo, nombre, cantidad):
    df = cargar_datos()
    if tipo == "entrada":
        if codigo in df["codigo"].values:
            df.loc[df["codigo"] == codigo, "cantidad"] += cantidad
        else:
            nueva_fila = pd.DataFrame({
                "codigo": [codigo],
                "nombre": [nombre],
                "Categoría": ["General"],
                "cantidad": [cantidad],
                "Fecha_ingreso": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
            })
            df = pd.concat([df, nueva_fila], ignore_index=True)
    elif tipo == "salida":
        if codigo in df["Código"].values:
            df.loc[df["Código"] == codigo, "cantidad"] -= cantidad
            if df.loc[df["Código"] == codigo, "cantidad"].iloc[0] <= 0:
                df = df[df["Código"] != codigo]
        else:
            st.error("❌ El producto no existe en inventario.")
            return
    guardar_datos(df)

# ==============================
# LOGIN SIMPLE
# ==============================
usuarios = {"admin": "1234", "hector": "fulltime"}

if "logueado" not in st.session_state:
    st.session_state["logueado"] = False

if "pagina" not in st.session_state:
    st.session_state["pagina"] = "inicio"

if not st.session_state["logueado"]:
    st.title("🔐 Sistema de Inventario FullTime")
    usuario = st.text_input("Usuario")
    clave = st.text_input("Contraseña", type="password")

    if st.button("Iniciar sesión"):
        if usuario in usuarios and usuarios[usuario] == clave:
            st.session_state["logueado"] = True
            st.session_state["pagina"] = "menu"
            st.success("✅ Inicio de sesión correcto")
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")
    st.stop()

# ==============================
# MENÚ PRINCIPAL VISUAL
# ==============================
if st.session_state["pagina"] == "menu":
    st.title("📦 Bienvenido a Inventario FullTime")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📊 Dashboard", use_container_width=True):
            st.session_state["pagina"] = "dashboard"
            st.rerun()
    with col2:
        if st.button("🗂️ Productos", use_container_width=True):
            st.session_state["pagina"] = "productos"
            st.rerun()
    with col3:
        if st.button("➕ Entradas", use_container_width=True):
            st.session_state["pagina"] = "entradas"
            st.rerun()

    col4, col5, col6 = st.columns(3)
    with col4:
        if st.button("➖ Salidas", use_container_width=True):
            st.session_state["pagina"] = "salidas"
            st.rerun()
    with col5:
        if st.button("⚙️ Configuración", use_container_width=True):
            st.session_state["pagina"] = "configuracion"
            st.rerun()
    with col6:
        if st.button("🚪 Cerrar sesión", use_container_width=True):
            st.session_state["logueado"] = False
            st.session_state["pagina"] = "inicio"
            st.success("Sesión cerrada correctamente 👋")
            st.rerun()

# ==============================
# DASHBOARD
# ==============================
if st.session_state["pagina"] == "dashboard":
    st.title("📊 Panel de Control")
    df = cargar_datos()

    #col1, col2 = st.columns()
#    col1.metric("Total de Productos", len(df))
 #   col2.metric("Stock Total", int(df["cantidad"].sum()))
    

    st.dataframe(df, use_container_width=True)

    if st.button("⬅️ Volver al menú principal"):
        st.session_state["pagina"] = "menu"
        st.rerun()

# ==============================
# PRODUCTOS
# ==============================
if st.session_state["pagina"] == "productos":
    st.title("🗂️ Gestión de Productos")
    df = cargar_datos()

    st.subheader("Listado actual")
    st.dataframe(df, use_container_width=True)

    st.divider()
    st.subheader("Agregar o editar producto")

    codigo = st.text_input("Código del producto")
    nombre = st.text_input("Nombre del producto")
    categoria = st.text_input("Categoría", "General")
    cantidad = st.number_input("Cantidad inicial", min_value=0, step=1)

    if st.button("💾 Guardar producto"):
        if codigo and nombre:
            nueva_fila = pd.DataFrame({
                "Código": [codigo],
                "Nombre": [nombre],
                "Categoría": [categoria],
                "Cantidad": [cantidad],
                "Fecha_ingreso": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
            })
            df = pd.concat([df, nueva_fila], ignore_index=True)
            guardar_datos(df)
            st.success("✅ Producto guardado correctamente.")
            st.rerun()
        else:
            st.warning("Completa todos los campos antes de guardar.")

    if st.button("⬅️ Volver al menú principal"):
        st.session_state["pagina"] = "menu"
        st.rerun()

# ==============================
# ENTRADAS
# ==============================
if st.session_state["pagina"] == "entradas":
    st.title("📦 Registrar Entrada de Inventario")

    # --- Sección: Código de barras o manual ---
    st.subheader("Código de producto")
    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("📷 Código de barra"):
            st.info("Lectura de código de barras/QR pendiente de implementación.")
    with col2:
        codigo = st.text_input("O ingrese el código manualmente (nuevo o existente):")

    # --- Sección: Subir factura ---
    st.subheader("📄 Subir factura (PDF o imagen)")
    factura_file = st.file_uploader("Selecciona la factura relacionada", type=["pdf", "png", "jpg", "jpeg"])

    factura_path = None
    if factura_file:
        import os
        FACTURA_DIR = "facturas"
        os.makedirs(FACTURA_DIR, exist_ok=True)

        factura_path = os.path.join(FACTURA_DIR, factura_file.name)
        with open(factura_path, "wb") as f:
            f.write(factura_file.getbuffer())

        st.success(f"Factura guardada correctamente: {factura_file.name}")
        st.info("Procesamiento automático de factura aún no implementado.")

    st.markdown("---")

    # --- Sección: Datos del producto ---
    nombre = st.text_input("Nombre del producto")
    cantidad = st.number_input("Cantidad a ingresar", min_value=1, step=1)

    # --- Botón de registro ---
    if st.button("✅ Registrar entrada"):
        registrar_movimiento("entrada", codigo, nombre, cantidad)

        # Guardar referencia a la factura si se subió una
        if factura_path:
            st.session_state["factura_subida"] = factura_path

        st.success(f"Entrada registrada correctamente. Producto: {nombre} (+{cantidad})")
        st.rerun()

    # --- Botón volver ---
    if st.button("⬅️ Volver al menú principal"):
        st.session_state["pagina"] = "menu"
        st.rerun()


# ==============================
# SALIDAS
# ==============================
if st.session_state["pagina"] == "salidas":
    st.title("📤 Registrar Salida de Inventario")

    # --- Sección: Subir boleta ---
    st.subheader("📄 Subir boleta (PDF o imagen)")
    boleta_file = st.file_uploader("Selecciona la boleta asociada", type=["pdf", "png", "jpg", "jpeg"])

    boleta_path = None
    if boleta_file:
        import os
        BOLETA_DIR = "boletas"
        os.makedirs(BOLETA_DIR, exist_ok=True)

        boleta_path = os.path.join(BOLETA_DIR, boleta_file.name)
        with open(boleta_path, "wb") as f:
            f.write(boleta_file.getbuffer())

        st.success(f"Boleta guardada correctamente: {boleta_file.name}")
        st.info("Procesamiento automático de boleta aún no implementado.")

    st.markdown("---")

    # --- Sección: Datos del producto ---
    codigo = st.text_input("Código del producto")
    cantidad = st.number_input("Cantidad a descontar", min_value=1, step=1)

    # --- Botón de registro ---
    if st.button("✅ Registrar salida"):
        registrar_movimiento("salida", codigo, "", -cantidad)

        # Guardar referencia de la boleta si se subió una
        if boleta_path:
            st.session_state["boleta_subida"] = boleta_path

        st.success(f"Salida registrada correctamente. Producto: {codigo} (-{cantidad})")
        st.rerun()

    # --- Botón volver ---
    if st.button("⬅️ Volver al menú principal"):
        st.session_state["pagina"] = "menu"
        st.rerun()


# ==============================
# CONFIGURACIÓN
# ==============================
if st.session_state["pagina"] == "configuracion":
    st.title("⚙️ Configuración del Sistema")
    st.write("Desde aquí puedes descargar el inventario completo o reiniciar los datos (opcional).")

    df = cargar_datos()
    xlsx = df.to_xlsx(index=False).encode('utf-8')
    st.download_button("📥 Descargar Inventario (xlsx)", xlsx, "inventario.xlsx", "text/xlsx")

    if st.button("⬅️ Volver al menú principal"):
        st.session_state["pagina"] = "menu"
        st.rerun()
