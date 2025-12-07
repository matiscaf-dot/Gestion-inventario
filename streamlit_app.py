# app.py
import streamlit as st
import pandas as pd
from datetime import datetime
import os
import json
from io import BytesIO
from PIL import Image
from pyzbar.pyzbar import decode
from github import Github

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

os.makedirs(FACTURAS_DIR, exist_ok=True)
os.makedirs(BOLETAS_DIR, exist_ok=True)
os.makedirs(BACKUPS_DIR, exist_ok=True)
os.makedirs(CAPTURAS_DIR, exist_ok=True)

# ==============================
# Lector de códigos de barras
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
def is_number(s):
    try:
        float(s)
        return True
    except:
        return False

def cargar_usuarios():
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
    with open(USUARIOS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def guardar_usuarios(data):
    with open(USUARIOS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def cargar_datos():
    if os.path.exists(DATA_FILE):
        df = pd.read_excel(DATA_FILE)
        df.columns = df.columns.str.lower().str.replace(" ", "_")
    else:
        df = pd.DataFrame(columns=[
            "codigo", "nombre", "descripcion", "categoria",
            "cantidad", "precio_costo", "precio_venta", "fecha_ingreso"
        ])
        df.to_excel(DATA_FILE, index=False)
    expected_cols = ["codigo", "nombre", "descripcion", "categoria", "cantidad", "precio_costo", "precio_venta", "fecha_ingreso"]
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
    except:
        df["cantidad"] = df["cantidad"].apply(lambda x: int(x) if pd.notna(x) and str(x).isdigit() else 0)
    for pcol in ["precio_costo", "precio_venta"]:
        try:
            df[pcol] = pd.to_numeric(df[pcol], errors="coerce").fillna(0.0).astype(float)
        except:
            df[pcol] = df[pcol].apply(lambda x: float(x) if pd.notna(x) and is_number(str(x)) else 0.0)
    return df

def guardar_datos(df):
    df_to_save = df.copy()
    df_to_save.columns = df_to_save.columns.str.lower().str.replace(" ", "_")
    df_to_save.to_excel(DATA_FILE, index=False)

def registrar_historial(usuario, tipo, codigo, nombre, cantidad):
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entrada = pd.DataFrame([{
        "fecha": fecha,
        "usuario": usuario,
        "tipo": tipo,
        "codigo": codigo,
        "nombre": nombre,
        "cantidad": cantidad
    }])
    if os.path.exists(HISTORIAL_FILE):
        historial = pd.read_csv(HISTORIAL_FILE)
        historial = pd.concat([historial, entrada], ignore_index=True)
    else:
        historial = entrada
    historial.to_csv(HISTORIAL_FILE, index=False)

def decode_barcode_from_pil(pil_img):
    if not _HAS_PYZBAR:
        return ""
    try:
        decoded = zbar_decode(pil_img)
        if not decoded:
            return ""
        return decoded[0].data.decode("utf-8")
    except:
        return ""

def go_to(page):
    st.session_state["pagina"] = page
    st.rerun()

# ==============================
# GITHUB - Subir Excel automáticamente
# ==============================
def subir_excel_a_github(file_path, commit_message="Actualización inventario"):
    try:
        token = st.secrets["GITHUB_TOKEN"]
        user = st.secrets["GITHUB_USER"]
        repo_name = st.secrets["GITHUB_REPO"]
        branch = st.secrets.get("GITHUB_BRANCH", "main")

        g = Github(token)
        repo = g.get_user(user).get_repo(repo_name)

        with open(file_path, "rb") as f:
            content = f.read()

        try:
            gh_file = repo.get_contents(file_path, ref=branch)
            repo.update_file(
                path=file_path,
                message=commit_message,
                content=content,
                sha=gh_file.sha,
                branch=branch
            )
        except:
            repo.create_file(
                path=file_path,
                message=commit_message,
                content=content,
                branch=branch
            )
        st.info("✅ Inventario actualizado en GitHub correctamente.")
    except Exception as e:
        st.error(f"❌ Error al subir a GitHub: {e}")

# ==============================
# Registrar movimientos (entrada/salida)
# ==============================
def registrar_movimiento(tipo, codigo, nombre, cantidad, usuario_actual=None, precio_costo=None, precio_venta=None, descripcion=None, categoria=None):
    df = cargar_datos()
    df["codigo"] = df["codigo"].astype(str)
    codigo = str(codigo).strip()

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
        else:
            nueva_fila = pd.DataFrame({
                "codigo": [codigo],
                "nombre": [nombre if nombre else "Sin nombre"],
                "descripcion": [descripcion if descripcion else ""],
                "categoria": [categoria if categoria else "general"],
                "cantidad": [int(cantidad)],
                "precio_costo": [float(precio_costo) if precio_costo is not None else 0.0],
                "precio_venta": [float(precio_venta) if precio_venta is not None else 0.0],
                "fecha_ingreso": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
            })
            df = pd.concat([df, nueva_fila], ignore_index=True)

        guardar_datos(df)
        subir_excel_a_github(DATA_FILE, commit_message=f"{tipo.capitalize()} de {codigo} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        registrar_historial(usuario_actual or "desconocido", "entrada", codigo, nombre, int(cantidad))

    elif tipo == "salida":
        if codigo in df["codigo"].values:
            idx = df.index[df["codigo"] == codigo]
            df.loc[idx, "cantidad"] = df.loc[idx, "cantidad"].astype(int) - int(cantidad)
            if df.loc[idx, "cantidad"].iloc[0] <= 0:
                df = df[df["codigo"] != codigo]
            guardar_datos(df)
            subir_excel_a_github(DATA_FILE, commit_message=f"{tipo.capitalize()} de {codigo} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            registrar_historial(usuario_actual or "desconocido", "salida", codigo, nombre, int(cantidad))
        else:
            st.error("❌ El producto no existe en inventario.")
            return

# ==============================
# LOGIN Y NAVEGACIÓN
# ==============================
if "logueado" not in st.session_state:
    st.session_state["logueado"] = False
if "pagina" not in st.session_state:
    st.session_state["pagina"] = "inicio"
if "rol" not in st.session_state:
    st.session_state["rol"] = None
if "usuario" not in st.session_state:
    st.session_state["usuario"] = None

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
menu = ["Productos", "Entradas", "Salidas", "Historial", "Configuración"]
st.sidebar.title(f"Usuario: {st.session_state['usuario']}")
opcion = st.sidebar.radio("Menú", menu)

df_inventario = cargar_datos()

# ==============================
# SECCIÓN PRODUCTOS
# ==============================
if opcion == "Productos":
    st.title("📦 Inventario de Productos")
    st.dataframe(df_inventario)

# ==============================
# SECCIÓN ENTRADAS
# ==============================
elif opcion == "Entradas":
    st.title("➕ Registrar Entrada de Inventario")
    with st.form("form_entrada"):
        codigo = st.text_input("Código del producto")
        nombre = st.text_input("Nombre")
        descripcion = st.text_input("Descripción")
        categoria = st.text_input("Categoría")
        cantidad = st.number_input("Cantidad", min_value=1, step=1)
        precio_costo = st.number_input("Precio de costo", min_value=0.0, step=0.01)
        precio_venta = st.number_input("Precio de venta", min_value=0.0, step=0.01)
        enviar = st.form_submit_button("Registrar Entrada")
        if enviar:
            registrar_movimiento("entrada", codigo, nombre, cantidad, st.session_state["usuario"], precio_costo, precio_venta, descripcion, categoria)
            st.success("✅ Entrada registrada")

# ==============================
# SECCIÓN SALIDAS
# ==============================
elif opcion == "Salidas":
    st.title("➖ Registrar Salida de Inventario")
    with st.form("form_salida"):
        codigo = st.text_input("Código del producto")
        nombre = st.text_input("Nombre")
        cantidad = st.number_input("Cantidad", min_value=1, step=1)
        enviar = st.form_submit_button("Registrar Salida")
        if enviar:
            registrar_movimiento("salida", codigo, nombre, cantidad, st.session_state["usuario"])
            st.success("✅ Salida registrada")

# ==============================
# SECCIÓN HISTORIAL
# ==============================
elif opcion == "Historial":
    st.title("📜 Historial de Movimientos")
    if os.path.exists(HISTORIAL_FILE):
        df_hist = pd.read_csv(HISTORIAL_FILE)
        st.dataframe(df_hist)
    else:
        st.info("No hay historial registrado.")

# ==============================
# SECCIÓN CONFIGURACIÓN
# ==============================
elif opcion == "Configuración":
    st.title("⚙️ Configuración de Usuarios")
    st.write("Agregar nuevo usuario:")
    with st.form("form_usuario"):
        nuevo_usuario = st.text_input("Usuario")
        clave_usuario = st.text_input("Clave", type="password")
        rol_usuario = st.selectbox("Rol", ["admin", "vendedor", "bodeguero"])
        enviar = st.form_submit_button("Agregar Usuario")
        if enviar:
            if nuevo_usuario in usuarios:
                st.error("El usuario ya existe.")
            else:
                usuarios[nuevo_usuario] = {"clave": clave_usuario, "rol": rol_usuario}
                guardar_usuarios(usuarios)
                st.success(f"Usuario {nuevo_usuario} agregado correctamente.")
