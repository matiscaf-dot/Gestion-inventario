# app.py
import streamlit as st
import pandas as pd
from datetime import datetime
import os
import json
from io import BytesIO
from PIL import Image
from supabase import create_client
from productos import render
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
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

    # Conexión a Supabase
    from supabase import create_client
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Consultar inventario desde Supabase
    response = supabase.table("inventario").select("*").execute()
    df = pd.DataFrame(response.data)

    # Mostrar métricas generales
    st.metric("Total de Productos", len(df))
    if "cantidad_real" in df.columns:
        st.metric("Stock Total", int(df["cantidad_real"].sum()))

    # Barra de búsqueda
    busqueda = st.text_input("🔎 Buscar producto (por código, nombre, stock o precio)")

    if busqueda:
        busqueda = busqueda.strip().lower()
        # Convertir columnas a string seguro
        for col in ["codigo_proveedor","descripcion_item","cantidad_real","precio_producto"]:
            if col in df.columns:
                df[col] = df[col].astype(str).fillna("")
        mask = (
            df["codigo_proveedor"].str.lower().str.contains(busqueda) |
            df["descripcion_item"].str.lower().str.contains(busqueda) |
            df["cantidad_real"].str.contains(busqueda) |
            df["precio_producto"].str.contains(busqueda)
        )
        df_filtrado = df[mask]
    else:
        df_filtrado = df

    # Diccionario de nombres amigables
    nombres_columnas = {
        "codigo_proveedor": "Código de barras",
        "descripcion_item": "Nombre del producto",
        "cantidad_real": "Stock disponible",
        "precio_producto": "Precio de venta"
    }

    rol = st.session_state.get("rol")

    if rol == "vendedor":
        # Vista simplificada para vendedores
        cols_vendedores = ["codigo_proveedor","descripcion_item","cantidad_real","precio_producto"]
        cols_validas = [c for c in cols_vendedores if c in df_filtrado.columns]
        df_vendedores = df_filtrado[cols_validas].rename(columns=nombres_columnas)
        st.dataframe(df_vendedores, use_container_width=True)
    else:
        # Vista completa para bodeguero/admin
        df_admin = df_filtrado.rename(columns=nombres_columnas)
        st.dataframe(df_admin, use_container_width=True)

    if st.button("⬅️ Volver al menú principal"):
        go_to("menu")

# ==============================
# PRODUCTOS (solo manual)
# ==============================
if st.session_state["pagina"] == "productos":
    if st.session_state.get("rol") == "admin":
        render()   # ← aquí llamas al módulo productos para administrador
        if st.button("⬅️ Volver al menú principal"):
            go_to("menu")
    else:
        st.error("❌ Solo el administrador puede acceder a este módulo.")
    if st.session_state["rol"] not in ["bodeguero"]:
        st.error("No tienes permiso para acceder a esta sección.")
        st.stop()
    st.title("🗂️ Gestión de Productos")
    df = cargar_datos()
    prov_df = cargar_proveedores()
    st.subheader("Listado actual")
    # Diccionario de nombres amigables para bodeguero en módulo productos
    nombres_bodeguero_productos = {
        "codigo_proveedor": "Código de barras",
        "descripcion_item": "Nombre producto",
        "valor_unitario": "Costo producto",
        "cantidad_real": "Stock"
    }
    
    # Consultar productos desde inventario
    response = supabase.table("inventario").select("*").execute()
    df = pd.DataFrame(response.data)
    
    # Renombrar columnas solo para bodeguero
    if st.session_state.get("rol") == "bodeguero":
        df = df.rename(columns=nombres_bodeguero_productos)
   
    # Mostrar tabla
    st.dataframe(df, use_container_width=True)

    st.divider()
    
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
    st.button("✅ Autorizar Facturas", use_container_width=True, on_click=go_to, args=("autorizar_facturas",))
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
        if not codigo:
            st.warning("Ingresa un código antes de registrar.")
        else:
            df_check = cargar_datos()
            if str(codigo).strip() not in df_check["codigo"].astype(str).values:
                st.error("❌ El producto no existe en inventario.")
            else:
                current_qty = int(df_check.loc[df_check["codigo"].astype(str) == str(codigo).strip(), "cantidad"].iloc[0])
                if cantidad > current_qty:
                    st.warning(f"⚠️ Stock insuficiente. Stock actual: {current_qty}")
                else:
                    proveedor_actual = df_check.loc[df_check["codigo"].astype(str) == str(codigo).strip(), "proveedor"].iloc[0] if "proveedor" in df_check.columns else ""
                    registrar_movimiento("salida", codigo, "", int(cantidad),
                                         usuario_actual=st.session_state.get("usuario"),
                                         proveedor=proveedor_actual)
                    if boleta_file:
                        boleta_path = os.path.join(BOLETAS_DIR, boleta_file.name)
                        with open(boleta_path, "wb") as f:
                            f.write(boleta_file.getbuffer())
                        st.session_state["boleta_subida"] = boleta_path
                    st.success("Salida registrada correctamente.")
                    go_to("salidas")

    if st.button("⬅️ Volver al menú principal"):
        go_to("menu")

# ==============================
# PROVEEDORES (solo admin)
# ==============================
if st.session_state["pagina"] == "proveedores":
    if st.session_state["rol"] != "admin":
        st.error("No tienes permiso para acceder a esta sección.")
        st.stop()

    st.title("📇 Gestión de Proveedores")
    prov_df = cargar_proveedores()
    st.subheader("Listado de proveedores")
    st.dataframe(prov_df, use_container_width=True)

    st.divider()
    st.subheader("Agregar nuevo proveedor")
    p_nombre = st.text_input("Nombre proveedor", key="prov_nombre")
    p_contacto = st.text_input("Contacto", key="prov_contacto")
    p_email = st.text_input("Email", key="prov_email")
    p_telefono = st.text_input("Teléfono", key="prov_telefono")
    p_direccion = st.text_input("Dirección", key="prov_direccion")
    p_notas = st.text_area("Notas", key="prov_notas")

    if st.button("➕ Agregar proveedor"):
        if not p_nombre.strip():
            st.warning("El nombre del proveedor es obligatorio.")
        else:
            prov_df = cargar_proveedores()
            new_id = 1 if prov_df.empty else (
                prov_df["id"].max() + 1
                if "id" in prov_df.columns and pd.api.types.is_numeric_dtype(prov_df["id"])
                else len(prov_df) + 1
            )
            prov_df = prov_df.append({
                "id": new_id,
                "nombre": p_nombre.strip(),
                "contacto": p_contacto.strip(),
                "email": p_email.strip(),
                "telefono": p_telefono.strip(),
                "direccion": p_direccion.strip(),
                "notas": p_notas.strip()
            }, ignore_index=True)
            guardar_proveedores(prov_df)
            st.success("Proveedor agregado correctamente.")
            go_to("proveedores")

    st.divider()
    st.subheader("Modificar / Eliminar proveedor")
    if not prov_df.empty:
        sel = st.selectbox("Seleccionar proveedor", prov_df["nombre"].astype(str).tolist())
        if sel:
            prov_row = prov_df[prov_df["nombre"].astype(str) == sel].iloc[0]
            edit_contacto = st.text_input("Contacto", value=prov_row.get("contacto", ""), key="edit_contacto")
            edit_email = st.text_input("Email", value=prov_row.get("email", ""), key="edit_email")
            edit_telefono = st.text_input("Teléfono", value=prov_row.get("telefono", ""), key="edit_telefono")
            edit_direccion = st.text_input("Direccion", value=prov_row.get("direccion", ""), key="edit_direccion")
            edit_notas = st.text_area("Notas", value=prov_row.get("notas", ""), key="edit_notas")

            if st.button("💾 Guardar cambios proveedor"):
                prov_df.loc[prov_df["nombre"].astype(str) == sel, "contacto"] = edit_contacto
                prov_df.loc[prov_df["nombre"].astype(str) == sel, "email"] = edit_email
                prov_df.loc[prov_df["nombre"].astype(str) == sel, "telefono"] = edit_telefono
                prov_df.loc[prov_df["nombre"].astype(str) == sel, "direccion"] = edit_direccion
                prov_df.loc[prov_df["nombre"].astype(str) == sel, "notas"] = edit_notas
                guardar_proveedores(prov_df)
                st.success("Proveedor modificado.")
                go_to("proveedores")

            if st.button("🗑️ Eliminar proveedor"):
                prov_df = prov_df[prov_df["nombre"].astype(str) != sel]
                guardar_proveedores(prov_df)
                st.success("Proveedor eliminado.")
                go_to("proveedores")
    else:
        st.info("No hay proveedores definidos todavía.")

    if st.button("⬅️ Volver al menú principal"):
        go_to("menu")

# ==============================
# HISTORIAL
# ==============================
if st.session_state["pagina"] == "historial":
    st.title("📝 Historial de Movimientos")
    if os.path.exists(HISTORIAL_FILE):
        df_hist = pd.read_csv(HISTORIAL_FILE)
        st.dataframe(df_hist, use_container_width=True)
    else:
        st.info("No hay movimientos registrados todavía.")
    if st.button("⬅️ Volver al menú principal"):
        go_to("menu")

# ==============================
# BACKUP
# ==============================
if st.session_state["pagina"] == "backup":
    st.title("📦 Copia de Seguridad del Inventario")
    df = cargar_datos()
    prov_df = cargar_proveedores()
    fecha = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_name = f"backup_inventario_{fecha}.xlsx"
    buffer = BytesIO()
    try:
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="productos", index=False)
            prov_df.to_excel(writer, sheet_name="proveedores", index=False)
        buffer.seek(0)
        backup_path = os.path.join(BACKUPS_DIR, backup_name)
        with open(backup_path, "wb") as f:
            f.write(buffer.getvalue())
        st.success(f"Copia de seguridad creada: {backup_name}")
        st.download_button(
            "📥 Descargar copia de seguridad",
            data=buffer.getvalue(),
            file_name=backup_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        st.error(f"Error creando copia de seguridad: {e}")
    if st.button("⬅️ Volver al menú principal"):
        go_to("menu")

# ==============================
# CONFIGURACIÓN
# ==============================
if st.session_state["pagina"] == "configuracion":
    if st.session_state["rol"] not in ["admin"]:
        st.error("❌ No tienes permiso para acceder a esta sección.")
        st.stop()
    st.title("⚙️ Configuración del Sistema")
    st.write("Descarga inventario y gestiona datos del sistema.")
    df = cargar_datos()
    prov_df = cargar_proveedores()
    buffer = BytesIO()
    try:
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="productos", index=False)
            prov_df.to_excel(writer, sheet_name="proveedores", index=False)
        buffer.seek(0)
        st.download_button(
            "📥 Descargar Inventario (Excel)",
            buffer.getvalue(),
            "inventario.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        st.error(f"No se pudo preparar el archivo de descarga: {e}")
    if st.button("⬅️ Volver al menú principal"):
        go_to("menu")

# ==============================
# Subir facturas (página externa)
# ==============================
# ==============================
# Subir facturas (solo admin)
# ==============================
if st.session_state["pagina"] == "subir_facturas":
    if st.session_state["rol"] != "admin":
        st.error("❌ No tienes permiso para acceder a esta sección.")
        st.stop()

    import tempfile
    from supabase import create_client
    from core.facturas import procesar_factura, normalizar_tabla

    # Conexión a Supabase
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    st.title("📄 Cargar Factura")

    uploaded_file = st.file_uploader("Sube archivo PDF", type=["pdf"])

    if uploaded_file is not None:
        # Guardar temporalmente para enviarlo a tu parser
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.read())
            pdf_path = tmp.name

        # 1) Procesar factura con tu código
        df_raw = procesar_factura(pdf_path)
        df_norm = normalizar_tabla(df_raw)

        st.subheader("Productos identificados")
        st.dataframe(df_norm[["descripcion_item", "cantidad_final", "valor_unitario"]])

        # 2) Botón para enviar a bodega
        # Inicializar lista de facturas rechazadas en memoria
        if "facturas_rechazadas" not in st.session_state:
            st.session_state["facturas_rechazadas"] = set()
        
        if st.button("Enviar a Bodega"):
            num_factura = str(df_norm["num_factura"].iloc[0] or "").strip()
        
            # Validar contra memoria local
            if num_factura in st.session_state["facturas_rechazadas"]:
                st.error(f"❌ La factura N° {num_factura} ya fue rechazada previamente. No se puede volver a subir.")
                # Resetear memoria local
                if "df_norm" in st.session_state:
                    del st.session_state["df_norm"]
                st.session_state["uploaded_file"] = None
                st.stop()
        
            # Validar contra Supabase
            factura_existente = supabase.table("detalle_factura_tmp").select("id").eq("num_factura", num_factura).execute()
            if factura_existente.data and len(factura_existente.data) > 0:
                st.error(f"❌ La factura N° {num_factura} ya existe en el sistema. No se puede volver a subir.")
                st.session_state["facturas_rechazadas"].add(num_factura)
                # Resetear memoria local
                if "df_norm" in st.session_state:
                    del st.session_state["df_norm"]
                st.session_state["uploaded_file"] = None
                st.stop()
        
            # Si pasa ambas validaciones → insertar
            factura_info = {
                "proveedor": str(df_norm["proveedor"].iloc[0] or "").strip(),
                "num_factura": num_factura,
                "fecha_emision": str(df_norm["fecha_emision"].iloc[0] or "").strip(),
                "estado": "pendiente",
            }
            factura_insert = supabase.table("detalle_factura_tmp").insert(factura_info).execute()
            factura_id = factura_insert.data[0]["id"]
        
            # Asegurar códigos de proveedor
            df_norm["codigo_proveedor"] = df_norm["codigo_proveedor"].fillna("")
            for idx, row in df_norm.iterrows():
                if row["codigo_proveedor"] in [None, "", " "]:
                    correlativo = str(idx + 1).zfill(4)
                    df_norm.at[idx, "codigo_proveedor"] = f"GEN-{factura_id}-{correlativo}"
        
            # Funciones de sanitización
            def safe_int(x):
                try:
                    return int(float(x))
                except:
                    return 0
        
            def safe_float(x):
                try:
                    return round(float(str(x).replace(",", ".").replace(" ", "").strip()), 2)
                except:
                    return 0.0
        
            # Insertar productos
            productos = []
            for _, row in df_norm.iterrows():
                productos.append({
                    "factura_id": factura_id,
                    "codigo_proveedor": str(row.get("codigo_proveedor", "")).strip(),
                    "descripcion_item": str(row.get("descripcion_item", "")).strip(),
                    "cantidad_factura": safe_int(row.get("cantidad")),
                    "valor_unitario": safe_float(row.get("valor_unitario")),
                    "valor_total": safe_float(row.get("valor_tot")),
                    "cantidad_real": None,
                    "precio_producto": None
                })
        
            st.write("Productos a insertar:", productos)
            supabase.table("productos_tmp").insert(productos).execute()
            st.success("Factura enviada a bodega exitosamente.")

    if st.button("⬅️ Volver al menú principal"):
        go_to("menu")


# ==============================
# Autorizar facturas (página externa)
# ==============================
if st.session_state["pagina"] == "autorizar_facturas":
    try:
        import autorizar_facturas as autorizar_facturas
        autorizar_facturas.render()
    except Exception as e:
        st.error(f"No se pudo cargar la página de Autorizar Facturas: {e}")
    if st.button("⬅️ Volver al menú principal"):
        go_to("menu")
