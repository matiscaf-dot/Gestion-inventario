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
# FUNCIONES AUXILIARES
# ==============================
def asegurar_usuarios_iniciales():
    if not os.path.exists(USUARIOS_FILE):
        usuarios_default = {
            "admin": {"clave": "1234", "rol": "admin"},
            "jefe": {"clave": "jefe123", "rol": "admin"},
            "hector": {"clave": "fulltime", "rol": "bodeguero"},
            "vendedor1": {"clave": "1234", "rol": "vendedor"},
            "vendedor2": {"clave": "abc123", "rol": "vendedor"}
        }
        with open(USUARIOS_FILE, "w", encoding="utf-8") as f:
            json.dump(usuarios_default, f, indent=4)

def cargar_usuarios():
    asegurar_usuarios_iniciales()
    with open(USUARIOS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def guardar_usuarios(data):
    with open(USUARIOS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def cargar_datos():
    if os.path.exists(DATA_FILE):
        try:
            df = pd.read_excel(DATA_FILE, sheet_name="productos")
        except Exception:
            try:
                df = pd.read_excel(DATA_FILE, sheet_name=0)
            except Exception:
                df = pd.DataFrame()
    else:
        df = pd.DataFrame()
    if df is None or df.empty:
        df = pd.DataFrame(columns=[
            "codigo", "nombre", "descripcion", "categoria",
            "cantidad", "precio_costo", "precio_venta", "fecha_ingreso", "proveedor"
        ])
    df.columns = df.columns.str.lower().str.replace(" ", "_")
    expected_cols = ["codigo", "nombre", "descripcion", "categoria",
                     "cantidad", "precio_costo", "precio_venta", "fecha_ingreso", "proveedor"]
    for col in expected_cols:
        if col not in df.columns:
            if col in ["cantidad"]:
                df[col] = 0
            elif col in ["precio_costo", "precio_venta"]:
                df[col] = 0.0
            else:
                df[col] = ""
    try:
        df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(0).astype(int)
    except Exception:
        df["cantidad"] = df["cantidad"].apply(lambda x: int(x) if pd.notna(x) and str(x).isdigit() else 0)
    for pcol in ["precio_costo", "precio_venta"]:
        try:
            df[pcol] = pd.to_numeric(df[pcol], errors="coerce").fillna(0.0).astype(float)
        except Exception:
            df[pcol] = df[pcol].apply(lambda x: float(x) if pd.notna(x) and is_number(str(x)) else 0.0)
    df["codigo"] = df["codigo"].astype(str)
    return df

def cargar_proveedores():
    if os.path.exists(DATA_FILE):
        try:
            prov = pd.read_excel(DATA_FILE, sheet_name="proveedores")
            prov.columns = prov.columns.str.lower().str.replace(" ", "_")
        except Exception:
            prov = pd.DataFrame()
    else:
        prov = pd.DataFrame()
    if prov is None or prov.empty:
        prov = pd.DataFrame(columns=["id", "nombre", "contacto", "email", "telefono", "direccion", "notas"])
    return prov

def guardar_all(product_df, prov_df):
    try:
        with pd.ExcelWriter(DATA_FILE, engine="openpyxl") as writer:
            product_df.to_excel(writer, sheet_name="productos", index=False)
            prov_df.to_excel(writer, sheet_name="proveedores", index=False)
    except Exception:
        product_df.to_excel(DATA_FILE, index=False)

def guardar_datos(df):
    prov = cargar_proveedores()
    guardar_all(df, prov)

def guardar_proveedores(df_prov):
    prod = cargar_datos()
    guardar_all(prod, df_prov)

def is_number(s):
    try:
        float(s)
        return True
    except:
        return False

def registrar_historial(usuario, tipo, codigo, nombre, cantidad, proveedor="", nota=""):
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entrada = pd.DataFrame([{
        "fecha": fecha,
        "usuario": usuario,
        "tipo": tipo,
        "codigo": codigo,
        "nombre": nombre,
        "cantidad": cantidad,
        "proveedor": proveedor,
        "nota": nota
    }])
    if os.path.exists(HISTORIAL_FILE):
        historial = pd.read_csv(HISTORIAL_FILE)
        historial = pd.concat([historial, entrada], ignore_index=True)
    else:
        historial = entrada
    historial.to_csv(HISTORIAL_FILE, index=False)

def registrar_movimiento(tipo, codigo, nombre, cantidad, usuario_actual=None,
                         precio_costo=None, precio_venta=None, descripcion=None, categoria=None, proveedor=""):
    df = cargar_datos()
    df["codigo"] = df["codigo"].astype(str)
    codigo = str(codigo).strip()
    usuario_actual = usuario_actual or "desconocido"

    if tipo == "entrada":
        if codigo in df["codigo"].values:
            df.loc[df["codigo"] == codigo, "cantidad"] = df.loc[df["codigo"] == codigo, "cantidad"].astype(int) + int(cantidad)
            if precio_costo is not None:
                df.loc[df["codigo"] == codigo, "precio_costo"] = float(precio_costo)
            if precio_venta is not None:
                df.loc[df["codigo"] == codigo, "precio_venta"] = float(precio_venta)
            if descripcion is not None:
                df.loc[df["codigo"] == codigo, "descripcion"] = descripcion
            if categoria is not None:
                df.loc[df["codigo"] == codigo, "categoria"] = categoria
            if proveedor:
                df.loc[df["codigo"] == codigo, "proveedor"] = proveedor
            guardar_datos(df)
            registrar_historial(usuario_actual, "entrada", codigo, nombre, int(cantidad), proveedor=proveedor, nota="")
        else:
            nueva_fila = pd.DataFrame({
                "codigo": [codigo],
                "nombre": [nombre if nombre else "Sin nombre"],
                "descripcion": [descripcion if descripcion else ""],
                "categoria": [categoria if categoria else "general"],
                "cantidad": [int(cantidad)],
                "precio_costo": [float(precio_costo) if precio_costo is not None else 0.0],
                "precio_venta": [float(precio_venta) if precio_venta is not None else 0.0],
                "fecha_ingreso": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
                "proveedor": [proveedor if proveedor else ""]
            })
            df = pd.concat([df, nueva_fila], ignore_index=True)
            guardar_datos(df)
            registrar_historial(usuario_actual, "nuevo", codigo, nombre, int(cantidad), proveedor=proveedor, nota="Producto agregado como nuevo en inventario")
    elif tipo == "salida":
        if codigo in df["codigo"].values:
            idx = df.index[df["codigo"] == codigo]
            df.loc[idx, "cantidad"] = df.loc[idx, "cantidad"].astype(int) - int(cantidad)
            if df.loc[idx, "cantidad"].iloc[0] <= 0:
                df = df[df["codigo"] != codigo]
            guardar_datos(df)
            registrar_historial(usuario_actual, "salida", codigo, nombre, int(cantidad), proveedor=proveedor, nota="")
        else:
            st.error("❌ El producto no existe en inventario.")
            return
        elif tipo == "nuevo":
        # fuerza creación manual desde página Productos
        df = cargar_datos()
        nueva_fila = pd.DataFrame({
            "codigo": [codigo],
            "nombre": [nombre if nombre else "Sin nombre"],
            "descripcion": [descripcion if descripcion else ""],
            "categoria": [categoria if categoria else "general"],
            "cantidad": [int(cantidad)],
            "precio_costo": [float(precio_costo) if precio_costo is not None else 0.0],
            "precio_venta": [float(precio_venta) if precio_venta is not None else 0.0],
            "fecha_ingreso": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            "proveedor": [proveedor if proveedor else ""]
        })
        df = pd.concat([df, nueva_fila], ignore_index=True)
        guardar_datos(df)
        registrar_historial(usuario_actual, "nuevo", codigo, nombre, int(cantidad),
                            proveedor=proveedor, nota="Producto creado manualmente")

# ==============================
# Helpers para navegación
# ==============================
def go_to(page):
    st.session_state["pagina"] = page
    st.rerun()

# ==============================
# INICIALIZACIÓN DE SESSION_STATE
# ==============================
if "logueado" not in st.session_state:
    st.session_state["logueado"] = False
if "pagina" not in st.session_state:
    st.session_state["pagina"] = "inicio"
if "rol" not in st.session_state:
    st.session_state["rol"] = None
if "usuario" not in st.session_state:
    st.session_state["usuario"] = None

# ==============================
# LOGIN
# ==============================
usuarios = cargar_usuarios()
if not st.session_state["logueado"]:
    st.title("🔐 Sistema de Inventario FullTime")
    usuario_input = st.text_input("Usuario")
    clave_input = st.text_input("Contraseña", type="password")
    if st.button("Iniciar sesión"):
        if usuario_input in usuarios and usuarios[usuario_input]["clave"] == clave_input:
            st.session_state["logueado"] = True
            st.session_state["usuario"] = usuario_input
            st.session_state["rol"] = usuarios[usuario_input]["rol"]
            st.session_state["pagina"] = "menu"
            st.success("✅ Inicio de sesión correcto")
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")
    st.stop()

# ==============================
# MENÚ PRINCIPAL
# ==============================
if st.session_state["pagina"] == "menu":
    st.title("📦 Bienvenido a Inventario FullTime")
    st.markdown(f"**Usuario:** {st.session_state.get('usuario')} — **Rol:** {st.session_state.get('rol')}")
    rol = st.session_state.get("rol")
    col1, col2 = st.columns(2)
    with col1:
        if rol in ["admin", "vendedor"]:
            st.button("📦 Tabla Inventario", use_container_width=True, on_click=go_to, args=("dashboard",))
            st.button("➖ Registrar Salida", use_container_width=True, on_click=go_to, args=("salidas",))
    with col2:
        if rol in ["admin", "bodeguero"]:
            st.button("🗂️ Productos", use_container_width=True, on_click=go_to, args=("productos",))
            st.button("➕ Registrar Entrada", use_container_width=True, on_click=go_to, args=("entradas",))
    st.markdown("---")
    col3, col4, col5 = st.columns(3)
    with col3:
        st.button("📝 Historial de movimientos", use_container_width=True, on_click=go_to, args=("historial",))
    with col5:
        if rol == "admin":
            st.button("⚙️ Configuración", use_container_width=True, on_click=go_to, args=("configuracion",))
            st.button("📇 Proveedores", use_container_width=True, on_click=go_to, args=("proveedores",))
            st.button("📄 Subir Factura", use_container_width=True, on_click=go_to, args=("subir_facturas",))
            st.button("✅ Autorizar Facturas", use_container_width=True, on_click=go_to, args=("autorizar_facturas",))
    st.markdown("---")
    if st.button("🚪 Cerrar sesión", use_container_width=True):
        st.session_state["logueado"] = False
        st.session_state["pagina"] = "inicio"
        st.session_state["rol"] = None
        st.session_state["usuario"] = None
        st.success("Sesión cerrada correctamente 👋")
        st.rerun()

# ==============================
# DASHBOARD
# ==============================
if st.session_state["pagina"] == "dashboard":
    st.title("📦 Tabla Inventario")
    df = cargar_datos()
    st.metric("Total de Productos", int(len(df)))
    st.metric("Stock Total", int(df["cantidad"].sum()))
    st.dataframe(df, use_container_width=True)
    if st.button("⬅️ Volver al menú principal"):
        go_to("menu")

# ==============================
# PRODUCTOS (solo manual)
# ==============================
if st.session_state["pagina"] == "productos":
    if st.session_state["rol"] not in ["admin", "bodeguero"]:
        st.error("No tienes permiso para acceder a esta sección.")
        st.stop()
    st.title("🗂️ Gestión de Productos")
    df = cargar_datos()
    prov_df = cargar_proveedores()
    st.subheader("Listado actual")
    st.dataframe(df, use_container_width=True)
    st.divider()
    st.subheader("Agregar o editar producto")
    codigo = st.text_input("Código del producto")
    nombre = st.text_input("Nombre del producto")
    descripcion = st.text_area("Descripción (opcional)")
    categoria = st.text_input("Categoría", value="General")
    cantidad = st.number_input("Cantidad inicial", min_value=0, step=1, value=0)
    precio_costo = st.number_input("Precio costo", min_value=0.0, step=0.1, format="%.2f", value=0.0)
    precio_venta = st.number_input("Precio venta", min_value=0.0, step=0.1, format="%.2f", value=0.0)
    prov_options = [""] + prov_df["nombre"].astype(str).tolist()
    proveedor_sel = st.selectbox("Proveedor (opcional)", prov_options)
    nuevo_proveedor_txt = st.text_input("O crea un nuevo proveedor (nombre) - opcional")
    if st.button("💾 Guardar producto"):
        # ... misma lógica de guardar que antes
        pass
    if st.button("⬅️ Volver al menú principal"):
        go_to("menu")

# ==============================
# ENTRADAS (manual + PDF)
# ==============================
if st.session_state["pagina"] == "entradas":
    if st.session_state["rol"] not in ["admin", "bodeguero"]:
        st.error("No tienes permiso para acceder a esta sección.")
        st.stop()
    st.title("📦 Registrar Entrada de Inventario")
    prov_df = cargar_proveedores()
    codigo = st.text_input("Código del producto")
    nombre = st.text_input("Nombre del producto (opcional)")
    cantidad = st.number_input("Cantidad a ingresar", min_value=1, step=1, value=1)
    precio_costo = st.number_input("Precio costo (opcional)", min_value=0.0, step=0.1, format="%.2f", value=0.0)
    precio_venta = st.number_input("Precio venta (opcional)", min_value=0.0, step=0.1, format="%.2f", value=0.0)
    prov_options = [""] + prov_df["nombre"].astype(str).tolist()
    proveedor_sel = st.selectbox("Proveedor asociado (opcional)", prov_options)
    nuevo_proveedor_txt = st.text_input("O crea nuevo proveedor (nombre) - opcional")
    factura_file = st.file_uploader("Subir factura en PDF", type=["pdf"])
    if factura_file is not None and st.button("Procesar Factura PDF"):
        # ... lógica de pdfplumber/OCR
        pass
    if st.button("✅ Registrar entrada"):
        # ... lógica de registrar_movimiento
        pass
    if st.button("⬅️ Volver al menú principal"):
        go_to("menu")

# ==============================
# SALIDAS (manual + boleta)
# ==============================
if st.session_state["pagina"] == "salidas":
    if st.session_state["rol"] not in ["admin", "vendedor"]:
        st.error("No tienes permiso para acceder a esta sección.")
        st.stop()
    st.title("📤 Registrar Salida de Inventario")
    codigo = st.text_input("Código del producto")
    cantidad = st.number_input("Cantidad a descontar", min_value=1, step=1, value=1)
    boleta_file = st.file_uploader("Subir boleta (opcional)", type=["pdf", "png", "jpg", "jpeg"])
    if st.button("✅ Registrar salida"):
