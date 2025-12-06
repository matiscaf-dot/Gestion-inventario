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
        df = pd.DataFrame(columns=["codigo", "nombre", "categoria", "cantidad", "fecha_ingreso"])
        df.to_excel(DATA_FILE, index=False)
        return df

def guardar_datos(df):
    df.to_excel(DATA_FILE, index=False)

def registrar_movimiento(tipo, codigo, nombre, cantidad):
    df = cargar_datos()

    # Normalizar columnas
    df.columns = df.columns.str.lower()

    if tipo == "entrada":
        if codigo in df["codigo"].values:
            df.loc[df["codigo"] == codigo, "cantidad"] += cantidad
        else:
            nueva_fila = pd.DataFrame({
                "codigo": [codigo],
                "nombre": [nombre],
                "categoria": ["General"],
                "cantidad": [cantidad],
                "fecha_ingreso": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
            })
            df = pd.concat([df, nueva_fila], ignore_index=True)

    elif tipo == "salida":
        if codigo in df["codigo"].values:
            df.loc[df["codigo"] == codigo, "cantidad"] -= cantidad

            # Eliminar si queda en cero o negativo
            if df.loc[df["codigo"] == codigo, "cantidad"].iloc[0] <= 0:
                df = df[df["codigo"] != codigo]
        else:
            st.error("❌ El producto no existe en inventario.")
            return

    guardar_datos(df)

# ==============================
# LOGIN + ROLES
# ==============================
usuarios = {
    "admin": {"clave": "1234", "rol": "admin"},
    "hector": {"clave": "fulltime", "rol": "bodeguero"},
    "vendedor1": {"clave": "1234", "rol": "vendedor"}
}

if "logueado" not in st.session_state:
    st.session_state["logueado"] = False

if "pagina" not in st.session_state:
    st.session_state["pagina"] = "inicio"

if not st.session_state["logueado"]:
    st.title("🔐 Sistema de Inventario FullTime")
    usuario = st.text_input("Usuario")
    clave = st.text_input("Contraseña", type="password")

    if st.button("Iniciar sesión"):
        if usuario in usuarios and usuarios[usuario]["clave"] == clave:
            st.session_state["logueado"] = True
            st.session_state["rol"] = usuarios[usuario]["rol"]
            st.session_state["pagina"] = "menu"
            st.success("Inicio de sesión exitoso ✔")
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")
    st.stop()

# ==============================
# MENÚ PRINCIPAL (SEGÚN ROL)
# ==============================
if st.session_state["pagina"] == "menu":
    st.title("📦 Menú Principal")

    rol = st.session_state["rol"]

    # ----- VENDEDOR -----
    if rol in ["admin", "vendedor"]:
        st.subheader("🟦 Opciones de Vendedor")
        col1, col2 = st.columns(2)

        with col1:
            if st.button("📊 Dashboard", use_container_width=True):
                st.session_state["pagina"] = "dashboard"
                st.rerun()

        with col2:
            if st.button("➖ Registrar Salida", use_container_width=True):
                st.session_state["pagina"] = "salidas"
                st.rerun()

    # ----- BODEGUERO -----
    if rol in ["admin", "bodeguero"]:
        st.subheader("🟩 Opciones de Bodeguero")
        col3, col4 = st.columns(2)

        with col3:
            if st.button("🗂️ Productos", use_container_width=True):
                st.session_state["pagina"] = "productos"
                st.rerun()

        with col4:
            if st.button("➕ Registrar Entrada", use_container_width=True):
                st.session_state["pagina"] = "entradas"
                st.rerun()

    st.markdown("---")

    # Botón común
    if st.button("🚪 Cerrar sesión", use_container_width=True):
        st.session_state.clear()
        st.success("Sesión cerrada 👋")
        st.rerun()

# ==============================
# PÁGINAS RESTRINGIDAS
# ==============================

# ---------- DASHBOARD ----------
if st.session_state["pagina"] == "dashboard":
    st.title("📊 Dashboard")

    df = cargar_datos()
    st.dataframe(df, use_container_width=True)

    st.button("⬅️ Volver", on_click=lambda: st.session_state.update({"pagina": "menu"}))

# ---------- PRODUCTOS (Solo Bodeguero/Admin) ----------
if st.session_state["pagina"] == "productos":
    if st.session_state["rol"] not in ["admin", "bodeguero"]:
        st.error("No tienes permiso para acceder aquí ❌")
        st.stop()

    st.title("🗂️ Gestión de Productos")
    df = cargar_datos()
    st.dataframe(df, use_container_width=True)

    st.subheader("Agregar nuevo producto")
    codigo = st.text_input("Código")
    nombre = st.text_input("Nombre")
    categoria = st.text_input("Categoría", "General")
    cantidad = st.number_input("Cantidad inicial", min_value=0, step=1)

    if st.button("💾 Guardar"):
        if codigo and nombre:
            nueva_fila = pd.DataFrame({
                "codigo": [codigo],
                "nombre": [nombre],
                "categoria": [categoria],
                "cantidad": [cantidad],
                "fecha_ingreso": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
            })
            df = pd.concat([df, nueva_fila], ignore_index=True)
            guardar_datos(df)
            st.success("Producto guardado ✔")
            st.rerun()
        else:
            st.warning("Completa todos los campos.")

    st.button("⬅️ Volver", on_click=lambda: st.session_state.update({"pagina": "menu"}))

# ---------- ENTRADAS (Solo Bodeguero/Admin) ----------
if st.session_state["pagina"] == "entradas":
    if st.session_state["rol"] not in ["admin", "bodeguero"]:
        st.error("No tienes permiso ❌")
        st.stop()

    st.title("📦 Registrar Entrada")

    codigo = st.text_input("Código del producto")
    nombre = st.text_input("Nombre")
    cantidad = st.number_input("Cantidad", min_value=1)

    if st.button("Registrar"):
        registrar_movimiento("entrada", codigo, nombre, cantidad)
        st.success("Entrada registrada ✔")
        st.rerun()

    st.button("⬅️ Volver", on_click=lambda: st.session_state.update({"pagina": "menu"}))

# ---------- SALIDAS (Solo Vendedor/Admin) ----------
if st.session_state["pagina"] == "salidas":
    if st.session_state["rol"] not in ["admin", "vendedor"]:
        st.error("No tienes permiso ❌")
        st.stop()

    st.title("📤 Registrar Salida")

    codigo = st.text_input("Código del producto")
    cantidad = st.number_input("Cantidad", min_value=1)

    if st.button("Registrar"):
        registrar_movimiento("salida", codigo, "", cantidad)
        st.success("Salida registrada ✔")
        st.rerun()

    st.button("⬅️ Volver", on_click=lambda: st.session_state.update({"pagina": "menu"}))
