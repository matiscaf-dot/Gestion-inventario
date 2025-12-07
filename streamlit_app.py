import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from PIL import Image
from io import BytesIO
from paddleocr import PaddleOCR

# -----------------------------------------
# CONFIGURACIÓN GENERAL
# -----------------------------------------
st.set_page_config(page_title="Gestión Inventario", layout="wide")

ocr = PaddleOCR(use_angle_cls=True, lang='es')

# -----------------------------------------
# CONEXIÓN A BASE DE DATOS
# -----------------------------------------
def get_conn():
    return sqlite3.connect("inventario.db", check_same_thread=False)

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # Usuarios
    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE,
            password TEXT,
            rol TEXT
        )
    """)

    # Productos
    cur.execute("""
        CREATE TABLE IF NOT EXISTS productos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE,
            nombre TEXT,
            descripcion TEXT,
            precio_compra REAL,
            precio_venta REAL,
            cantidad INTEGER DEFAULT 0
        )
    """)

    # Movimientos
    cur.execute("""
        CREATE TABLE IF NOT EXISTS movimientos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT,
            tipo TEXT,
            cantidad INTEGER,
            fecha TEXT,
            usuario TEXT
        )
    """)

    # Crear admin si no existe
    cur.execute("SELECT * FROM usuarios WHERE usuario='admin'")
    if not cur.fetchone():
        cur.execute("INSERT INTO usuarios(usuario,password,rol) VALUES('admin','admin','admin')")

    conn.commit()
    conn.close()

init_db()

# -----------------------------------------
# SESIÓN
# -----------------------------------------
if "page" not in st.session_state:
    st.session_state.page = "login"

if "usuario" not in st.session_state:
    st.session_state.usuario = None

if "rol" not in st.session_state:
    st.session_state.rol = None

def ir(p):
    st.session_state.page = p
    st.rerun()

# -----------------------------------------
# LOGIN
# -----------------------------------------
def login():
    st.title("Ingreso al sistema")

    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")

    if st.button("Ingresar"):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE usuario=? AND password=?", (u, p))
        row = cur.fetchone()
        conn.close()

        if row:
            st.session_state.usuario = row[1]
            st.session_state.rol = row[3]
            ir("menu")
        else:
            st.error("Usuario o contraseña incorrectos")

# -----------------------------------------
# REGISTRAR MOVIMIENTOS
# -----------------------------------------
def registrar_movimiento(codigo, tipo, cantidad, usuario):
    conn = get_conn()
    cur = conn.cursor()
    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        "INSERT INTO movimientos(codigo,tipo,cantidad,fecha,usuario) VALUES(?,?,?,?,?)",
        (codigo, tipo, cantidad, fecha, usuario)
    )
    conn.commit()
    conn.close()

# -----------------------------------------
# ENTRADAS
# -----------------------------------------
def pagina_entradas():
    st.header("Ingreso de productos")

    codigo = st.text_input("Código de barras")

    # Cámara ON/OFF
    if "cam_entradas" not in st.session_state:
        st.session_state.cam_entradas = False

    if st.button("📷 Activar / Desactivar Cámara (Entradas)"):
        st.session_state.cam_entradas = not st.session_state.cam_entradas
        st.rerun()

    cam_img = None
    if st.session_state.cam_entradas:
        cam_img = st.camera_input("Toma una foto del código o producto")

    # --- Procesamiento OCR opcional ---
    if cam_img is not None:
        st.success("Imagen capturada correctamente.")

    cantidad = st.number_input("Cantidad a ingresar", min_value=1, step=1)

    if st.button("Registrar ingreso"):
        registrar_movimiento(codigo, "ENTRADA", cantidad, st.session_state.usuario)

        # Actualizar stock
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE productos SET cantidad = cantidad + ? WHERE codigo=?", (cantidad, codigo))
        conn.commit()
        conn.close()

        st.success("Ingreso registrado.")

# -----------------------------------------
# SALIDAS
# -----------------------------------------
def pagina_salidas():
    st.header("Salida de productos")

    codigo = st.text_input("Código de barras")

    # Cámara ON/OFF
    if "cam_salidas" not in st.session_state:
        st.session_state.cam_salidas = False

    if st.button("📷 Activar / Desactivar Cámara (Salidas)"):
        st.session_state.cam_salidas = not st.session_state.cam_salidas
        st.rerun()

    cam_img = None
    if st.session_state.cam_salidas:
        cam_img = st.camera_input("Toma una foto del código o producto")

    if cam_img is not None:
        st.success("Imagen capturada correctamente.")

    cantidad = st.number_input("Cantidad a retirar", min_value=1, step=1)

    if st.button("Registrar salida"):
        registrar_movimiento(codigo, "SALIDA", cantidad, st.session_state.usuario)

        # Actualizar stock
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE productos SET cantidad = cantidad - ? WHERE codigo=?", (cantidad, codigo))
        conn.commit()
        conn.close()

        st.success("Salida registrada.")

# -----------------------------------------
# NUEVO PRODUCTO (CON CÓDIGO DE BARRAS Y CÁMARA)
# -----------------------------------------
def pagina_nuevo_producto():
    st.header("Agregar nuevo producto")

    codigo = st.text_input("Código de barras")

    # Cámara
    if "cam_nuevo" not in st.session_state:
        st.session_state.cam_nuevo = False

    if st.button("📷 Activar cámara para leer código"):
        st.session_state.cam_nuevo = not st.session_state.cam_nuevo
        st.rerun()

    cam_img = None
    if st.session_state.cam_nuevo:
        cam_img = st.camera_input("Fotografía el código de barras")

    nombre = st.text_input("Nombre")
    descripcion = st.text_area("Descripción")
    precio_c = st.number_input("Precio compra", min_value=0.0)
    precio_v = st.number_input("Precio venta", min_value=0.0)
    cantidad = st.number_input("Cantidad inicial", min_value=0)

    if st.button("Registrar producto"):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO productos(codigo,nombre,descripcion,precio_compra,precio_venta,cantidad)
            VALUES(?,?,?,?,?,?)
        """, (codigo, nombre, descripcion, precio_c, precio_v, cantidad))
        conn.commit()
        conn.close()

        # Movimiento especial
        registrar_movimiento(codigo, "INGRESO_INICIAL", cantidad, st.session_state.usuario)

        st.success("Producto registrado correctamente.")

# -----------------------------------------
# INVENTARIO
# -----------------------------------------
def pagina_inventario():
    st.header("Tabla Inventario")
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM productos", conn)
    conn.close()
    st.dataframe(df)

# -----------------------------------------
# CONFIGURACIÓN
# -----------------------------------------
def pagina_config():
    st.header("Configuración del sistema")

    # SOLO ADMIN
    if st.session_state.rol != "admin":
        st.info("Solo administradores pueden acceder a esta sección.")
        return

    st.subheader("Gestión de usuarios")

    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM usuarios", conn)
    conn.close()
    st.dataframe(df)

# -----------------------------------------
# MENÚ PRINCIPAL
# -----------------------------------------
def menu():
    st.sidebar.title(f"Bienvenido, {st.session_state.usuario}")

    opcion = st.sidebar.radio("Menú", [
        "Entradas",
        "Salidas",
        "Nuevo producto",
        "Inventario",
        "Configuración",
        "Cerrar sesión"
    ])

    if opcion == "Entradas":
        pagina_entradas()
    elif opcion == "Salidas":
        pagina_salidas()
    elif opcion == "Nuevo producto":
        pagina_nuevo_producto()
    elif opcion == "Inventario":
        pagina_inventario()
    elif opcion == "Configuración":
        pagina_config()
    elif opcion == "Cerrar sesión":
        st.session_state.page = "login"
        st.session_state.usuario = None
        st.session_state.rol = None
        st.rerun()


# -----------------------------------------
# RENDER
# -----------------------------------------
if st.session_state.page == "login":
    login()
else:
    menu()

