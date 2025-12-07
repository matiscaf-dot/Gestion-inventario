# app.py
import streamlit as st
import pandas as pd
from datetime import datetime
import bcrypt
from supabase import create_client, Client

# ==============================
# CONFIGURACIÓN GENERAL
# ==============================
st.set_page_config(page_title="Inventario FullTime", layout="wide")

# Conexión a Supabase
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# ==============================
# FUNCIONES AUXILIARES
# ==============================
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

# ==============================
# USUARIO POR DEFECTO
# ==============================
def crear_usuario_por_defecto():
    response = supabase.table("usuarios").select("*").eq("usuario", "admin").execute()
    if not response.data:
        hashed = hash_password("1234")
        supabase.table("usuarios").insert({
            "usuario": "admin",
            "clave": hashed,
            "rol": "admin"
        }).execute()
        print("✅ Usuario admin creado por defecto con clave 1234")

try:
    crear_usuario_por_defecto()
except Exception as e:
    st.warning(f"No se pudo crear usuario por defecto: {e}")

# ==============================
# USUARIOS
# ==============================
def cargar_usuarios():
    response = supabase.table("usuarios").select("*").execute()
    usuarios = {u["usuario"]: {"clave": u["clave"], "rol": u["rol"]} for u in response.data}
    return usuarios

def guardar_usuario(usuario, clave, rol):
    hashed = hash_password(clave)
    supabase.table("usuarios").insert({
        "usuario": usuario,
        "clave": hashed,
        "rol": rol
    }).execute()

# ==============================
# INVENTARIO
# ==============================
def cargar_datos():
    response = supabase.table("inventario").select("*").execute()
    df = pd.DataFrame(response.data)
    return df

def registrar_movimiento(tipo, codigo, nombre, cantidad, usuario_actual=None,
                         precio_costo=None, precio_venta=None,
                         descripcion=None, categoria=None):

    codigo = str(codigo).strip()

    if tipo == "entrada":
        supabase.table("inventario").upsert({
            "codigo": codigo,
            "nombre": nombre or "Sin nombre",
            "descripcion": descripcion or "",
            "categoria": categoria or "general",
            "cantidad": int(cantidad),
            "precio_costo": float(precio_costo) if precio_costo else 0.0,
            "precio_venta": float(precio_venta) if precio_venta else 0.0,
            "fecha_ingreso": datetime.now().isoformat()
        }).execute()

        registrar_historial(usuario_actual or "desconocido", "entrada", codigo, nombre, cantidad)

    elif tipo == "salida":
        current = supabase.table("inventario").select("cantidad").eq("codigo", codigo).execute()
        if current.data:
            nueva_cantidad = current.data[0]["cantidad"] - int(cantidad)
            if nueva_cantidad > 0:
                supabase.table("inventario").update({"cantidad": nueva_cantidad}).eq("codigo", codigo).execute()
            else:
                supabase.table("inventario").delete().eq("codigo", codigo).execute()

            registrar_historial(usuario_actual or "desconocido", "salida", codigo, nombre, cantidad)
        else:
            st.error("❌ El producto no existe en inventario.")

# ==============================
# HISTORIAL
# ==============================
def registrar_historial(usuario, tipo, codigo, nombre, cantidad):
    supabase.table("historial").insert({
        "fecha": datetime.now().isoformat(),
        "usuario": usuario,
        "tipo": tipo,
        "codigo": codigo,
        "nombre": nombre,
        "cantidad": int(cantidad)
    }).execute()

def cargar_historial():
    response = supabase.table("historial").select("*").execute()
    df = pd.DataFrame(response.data)
    return df

# ==============================
# FACTURAS
# ==============================
def registrar_factura(numero, proveedor, fecha, productos, usuario_actual):
    factura = supabase.table("facturas").insert({
        "numero": numero,
        "proveedor": proveedor,
        "fecha": fecha.isoformat()
    }).execute()
    factura_id = factura.data[0]["id"]

    for p in productos:
        supabase.table("factura_detalle").insert({
            "factura_id": factura_id,
            "codigo": p["codigo"],
            "nombre": p["nombre"],
            "cantidad": p["cantidad"],
            "precio_costo": p["precio_costo"]
        }).execute()

        registrar_movimiento("entrada", p["codigo"], p["nombre"], p["cantidad"],
                             usuario_actual=usuario_actual,
                             precio_costo=p["precio_costo"])

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
        if usuario_input in usuarios and check_password(clave_input, usuarios[usuario_input]["clave"]):
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
menu = ["Productos", "Entradas", "Salidas", "Facturas", "Historial", "Configuración"]
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
            registrar_movimiento("entrada", codigo, nombre, cantidad, st.session_state["usuario"],
                                 precio_costo, precio_venta, descripcion, categoria)
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
# SECCIÓN FACTURAS
# ==============================
elif opcion == "Facturas":
    st.title("🧾 Ingreso de Facturas")
    with st.form("form_factura"):
        numero = st.text_input("Número de factura")
        proveedor = st.text_input("Proveedor")
        fecha = st.date_input("Fecha", datetime.now().date())

        st.write("Detalle de productos")
        cantidad_items = st.number_input("Cantidad de productos", min_value=1, step=1, value=1)

        productos = []
        for i in range(cantidad_items):
            st.write(f"Producto {i+1}")
            codigo = st.text_input(f"Código producto {i+1}", key=f
