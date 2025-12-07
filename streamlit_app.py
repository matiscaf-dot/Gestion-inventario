# app.py
import streamlit as st
import pandas as pd
from datetime import datetime
import os
import json
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
def is_number(s):
    try:
        float(s)
        return True
    except:
        return False

# ==============================
# USUARIOS
# ==============================
def cargar_usuarios():
    response = supabase.table("usuarios").select("*").execute()
    usuarios = {u["usuario"]: {"clave": u["clave"], "rol": u["rol"]} for u in response.data}
    return usuarios

def guardar_usuario(usuario, clave, rol):
    supabase.table("usuarios").insert({
        "usuario": usuario,
        "clave": clave,
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
# SECCIÓN HISTORIAL
# ==============================
elif opcion == "Historial":
    st.title("📜 Historial de Movimientos")
    df_hist = cargar_historial()
    if not df_hist.empty:
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
                guardar_usuario(nuevo_usuario, clave_usuario, rol_usuario)
                st.success(f"Usuario {nuevo_usuario} agregado correctamente.")
