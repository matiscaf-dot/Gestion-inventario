# app.py
import streamlit as st
import pandas as pd
from datetime import datetime
import os
import json
from io import BytesIO

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

os.makedirs(FACTURAS_DIR, exist_ok=True)
os.makedirs(BOLETAS_DIR, exist_ok=True)
os.makedirs(BACKUPS_DIR, exist_ok=True)

# ==============================
# FUNCIONES AUXILIARES
# ==============================
def asegurar_usuarios_iniciales():
    """Si no existe usuarios.json, crea uno con usuarios por defecto."""
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
    """Carga inventario desde excel y garantiza columnas mínimas en minúsculas."""
    if os.path.exists(DATA_FILE):
        df = pd.read_excel(DATA_FILE)
        # Normalizar columnas
        df.columns = df.columns.str.lower().str.replace(" ", "_")
    else:
        df = pd.DataFrame(columns=["codigo", "nombre", "categoria", "cantidad", "fecha_ingreso"])
        df.to_excel(DATA_FILE, index=False)
    # Asegurar columnas necesarias
    for col in ["codigo", "nombre", "categoria", "cantidad", "fecha_ingreso"]:
        if col not in df.columns:
            df[col] = "" if col != "cantidad" else 0
    # Forzar tipos
    try:
        df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(0).astype(int)
    except Exception:
        df["cantidad"] = df["cantidad"].apply(lambda x: int(x) if pd.notna(x) and str(x).isdigit() else 0)
    return df

def guardar_datos(df):
    # Normalizar columnas antes de guardar (sin espacios, en minúsculas)
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

def registrar_movimiento(tipo, codigo, nombre, cantidad, usuario_actual=None):
    """
    tipo: "entrada" o "salida"
    cantidad: int (si es salida, debe ser positiva; la función restará)
    usuario_actual: nombre de usuario que realiza la acción (string)
    """
    df = cargar_datos()
    df["codigo"] = df["codigo"].astype(str)
    codigo = str(codigo).strip()

    if tipo == "entrada":
        if codigo in df["codigo"].values:
            df.loc[df["codigo"] == codigo, "cantidad"] = df.loc[df["codigo"] == codigo, "cantidad"].astype(int) + int(cantidad)
        else:
            nueva_fila = pd.DataFrame({
                "codigo": [codigo],
                "nombre": [nombre if nombre else "Sin nombre"],
                "categoria": ["general"],
                "cantidad": [int(cantidad)],
                "fecha_ingreso": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
            })
            df = pd.concat([df, nueva_fila], ignore_index=True)
        guardar_datos(df)
        registrar_historial(usuario_actual or "desconocido", "entrada", codigo, nombre, int(cantidad))

    elif tipo == "salida":
        if codigo in df["codigo"].values:
            idx = df.index[df["codigo"] == codigo]
            # Asegurar cantidad numérica
            df.loc[idx, "cantidad"] = df.loc[idx, "cantidad"].astype(int) - int(cantidad)
            # Si queda en 0 o negativo, eliminar el registro
            if df.loc[idx, "cantidad"].iloc[0] <= 0:
                df = df[df["codigo"] != codigo]
            guardar_datos(df)
            registrar_historial(usuario_actual or "desconocido", "salida", codigo, nombre, int(cantidad))
        else:
            # Producto no existe
            st.error("❌ El producto no existe en inventario.")
            return

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
# LOGIN SIMPLE (con usuarios.json)
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
            st.experimental_rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")
    st.stop()

# ==============================
# MENÚ PRINCIPAL (SEGÚN ROL)
# ==============================
if st.session_state["pagina"] == "menu":
    st.title("📦 Bienvenido a Inventario FullTime")
    st.markdown(f"**Usuario:** {st.session_state.get('usuario')} — **Rol:** {st.session_state.get('rol')}")
    rol = st.session_state.get("rol")

    # Columnas por rol
    col1, col2 = st.columns(2)

    # Opciones comunes / vendedor
    with col1:
        if rol in ["admin", "vendedor"]:
            if st.button("📊 Dashboard", use_container_width=True):
                st.session_state["pagina"] = "dashboard"
                st.experimental_rerun()

            if st.button("➖ Registrar Salida", use_container_width=True):
                st.session_state["pagina"] = "salidas"
                st.experimental_rerun()

    # Opciones bodeguero
    with col2:
        if rol in ["admin", "bodeguero"]:
            if st.button("🗂️ Productos", use_container_width=True):
                st.session_state["pagina"] = "productos"
                st.experimental_rerun()

            if st.button("➕ Registrar Entrada", use_container_width=True):
                st.session_state["pagina"] = "entradas"
                st.experimental_rerun()

    # Botones adicionales para todos
    st.markdown("---")
    col3, col4, col5 = st.columns(3)
    with col3:
        if st.button("📝 Historial de movimientos", use_container_width=True):
            st.session_state["pagina"] = "historial"
            st.experimental_rerun()
    with col4:
        if st.button("📦 Copia de seguridad (Descargar inventario)", use_container_width=True):
            st.session_state["pagina"] = "backup"
            st.experimental_rerun()
    with col5:
        if rol == "admin":
            if st.button("⚙️ Configuración", use_container_width=True):
                st.session_state["pagina"] = "configuracion"
                st.experimental_rerun()
            if st.button("👤 Gestión de usuarios", use_container_width=True):
                st.session_state["pagina"] = "usuarios"
                st.experimental_rerun()

    st.markdown("---")
    if st.button("🚪 Cerrar sesión", use_container_width=True):
        st.session_state["logueado"] = False
        st.session_state["pagina"] = "inicio"
        st.session_state["rol"] = None
        st.session_state["usuario"] = None
        st.success("Sesión cerrada correctamente 👋")
        st.experimental_rerun()

# ==============================
# DASHBOARD
# ==============================
if st.session_state["pagina"] == "dashboard":
    st.title("📊 Panel de Control")
    df = cargar_datos()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total de Productos", int(len(df)))
    with col2:
        st.metric("Stock Total", int(df["cantidad"].sum()))

    st.markdown("### Inventario actual")
    st.dataframe(df, use_container_width=True)

    if st.button("⬅️ Volver al menú principal"):
        st.session_state["pagina"] = "menu"
        st.experimental_rerun()

# ==============================
# PRODUCTOS
# ==============================
if st.session_state["pagina"] == "productos":
    if st.session_state["rol"] not in ["admin", "bodeguero"]:
        st.error("No tienes permiso para acceder a esta sección.")
        st.stop()

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
            codigo = str(codigo).strip()
            # Si existe, editar; si no, agregar
            if codigo in df["codigo"].astype(str).values:
                df.loc[df["codigo"].astype(str) == codigo, "nombre"] = nombre
                df.loc[df["codigo"].astype(str) == codigo, "categoria"] = categoria
                df.loc[df["codigo"].astype(str) == codigo, "cantidad"] = int(cantidad)
            else:
                nueva_fila = pd.DataFrame({
                    "codigo": [codigo],
                    "nombre": [nombre],
                    "categoria": [categoria],
                    "cantidad": [int(cantidad)],
                    "fecha_ingreso": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                })
                df = pd.concat([df, nueva_fila], ignore_index=True)
            guardar_datos(df)
            st.success("✅ Producto guardado correctamente.")
            st.experimental_rerun()
        else:
            st.warning("Completa todos los campos antes de guardar.")

    st.markdown("---")
    if st.button("⬅️ Volver al menú principal"):
        st.session_state["pagina"] = "menu"
        st.experimental_rerun()

# ==============================
# ENTRADAS
# ==============================
if st.session_state["pagina"] == "entradas":
    if st.session_state["rol"] not in ["admin", "bodeguero"]:
        st.error("No tienes permiso para acceder a esta sección.")
        st.stop()

    st.title("📦 Registrar Entrada de Inventario")

    # Código manual / futuro lector
    st.subheader("Código de producto")
    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("📷 Código de barra (pendiente)"):
            st.info("Lectura de código de barras/QR pendiente de implementación.")
    with col2:
        codigo = st.text_input("O ingrese el código manualmente (nuevo o existente):")

    # Subir factura opcional
    st.subheader("📄 Subir factura (PDF o imagen) - opcional")
    factura_file = st.file_uploader("Selecciona la factura relacionada", type=["pdf", "png", "jpg", "jpeg"])

    factura_path = None
    if factura_file:
        factura_path = os.path.join(FACTURAS_DIR, factura_file.name)
        with open(factura_path, "wb") as f:
            f.write(factura_file.getbuffer())
        st.success(f"Factura guardada correctamente: {factura_file.name}")
        st.info("Procesamiento automático de factura aún no implementado.")

    st.markdown("---")
    nombre = st.text_input("Nombre del producto")
    cantidad = st.number_input("Cantidad a ingresar", min_value=1, step=1)

    if st.button("✅ Registrar entrada"):
        registrar_movimiento("entrada", codigo, nombre, int(cantidad), usuario_actual=st.session_state.get("usuario"))
        # Guardar referencia a la factura si se subió una
        if factura_path:
            st.session_state["factura_subida"] = factura_path
        st.success(f"Entrada registrada correctamente. Producto: {nombre} (+{cantidad})")
        st.experimental_rerun()

    if st.button("⬅️ Volver al menú principal"):
        st.session_state["pagina"] = "menu"
        st.experimental_rerun()

# ==============================
# SALIDAS
# ==============================
if st.session_state["pagina"] == "salidas":
    if st.session_state["rol"] not in ["admin", "vendedor"]:
        st.error("No tienes permiso para acceder a esta sección.")
        st.stop()

    st.title("📤 Registrar Salida de Inventario")

    # Subir boleta opcional
    st.subheader("📄 Subir boleta (PDF o imagen) - opcional")
    boleta_file = st.file_uploader("Selecciona la boleta asociada", type=["pdf", "png", "jpg", "jpeg"])

    boleta_path = None
    if boleta_file:
        boleta_path = os.path.join(BOLETAS_DIR, boleta_file.name)
        with open(boleta_path, "wb") as f:
            f.write(boleta_file.getbuffer())
        st.success(f"Boleta guardada correctamente: {boleta_file.name}")
        st.info("Procesamiento automático de boleta aún no implementado.")

    st.markdown("---")
    codigo = st.text_input("Código del producto")
    cantidad = st.number_input("Cantidad a descontar", min_value=1, step=1)

    if st.button("✅ Registrar salida"):
        # Antes de restar, verificar existencia y stock suficiente
        df_check = cargar_datos()
        if str(codigo).strip() not in df_check["codigo"].astype(str).values:
            st.error("❌ El producto no existe en inventario.")
        else:
            current_qty = int(df_check.loc[df_check["codigo"].astype(str) == str(codigo).strip(), "cantidad"].iloc[0])
            if cantidad > current_qty:
                st.warning(f"⚠️ Stock insuficiente. Stock actual: {current_qty}")
            else:
                registrar_movimiento("salida", codigo, "", int(cantidad), usuario_actual=st.session_state.get("usuario"))
                if boleta_path:
                    st.session_state["boleta_subida"] = boleta_path
                st.success(f"Salida registrada correctamente. Producto: {codigo} (-{cantidad})")
                st.experimental_rerun()

    if st.button("⬅️ Volver al menú principal"):
        st.session_state["pagina"] = "menu"
        st.experimental_rerun()

# ==============================
# HISTORIAL (Visible para todos)
# ==============================
if st.session_state["pagina"] == "historial":
    st.title("📝 Historial de Movimientos")
    if os.path.exists(HISTORIAL_FILE):
        df_hist = pd.read_csv(HISTORIAL_FILE)
        st.dataframe(df_hist, use_container_width=True)
        # Filtros simples
        st.markdown("#### Filtros rápidos")
        cols = st.columns(3)
        with cols[0]:
            filtro_usuario = st.text_input("Usuario (exacto)", "")
        with cols[1]:
            filtro_tipo = st.selectbox("Tipo", ["todos", "entrada", "salida"])
        with cols[2]:
            filtro_codigo = st.text_input("Código (exacto)", "")

        df_filtrado = df_hist.copy()
        if filtro_usuario:
            df_filtrado = df_filtrado[df_filtrado["usuario"] == filtro_usuario]
        if filtro_tipo != "todos":
            df_filtrado = df_filtrado[df_filtrado["tipo"] == filtro_tipo]
        if filtro_codigo:
            df_filtrado = df_filtrado[df_filtrado["codigo"] == filtro_codigo]

        st.markdown("#### Resultados filtrados")
        st.dataframe(df_filtrado, use_container_width=True)
    else:
        st.info("No hay movimientos registrados todavía.")

    if st.button("⬅️ Volver al menú principal"):
        st.session_state["pagina"] = "menu"
        st.experimental_rerun()

# ==============================
# COPIA DE SEGURIDAD (Disponible para todos desde menú o aquí)
# ==============================
if st.session_state["pagina"] == "backup":
    st.title("📦 Copia de Seguridad del Inventario")
    df = cargar_datos()

    fecha = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_name = f"backup_inventario_{fecha}.xlsx"
    buffer = BytesIO()
    df.to_excel(buffer, index=False)
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

    if st.button("⬅️ Volver al menú principal"):
        st.session_state["pagina"] = "menu"
        st.experimental_rerun()

# ==============================
# CONFIGURACIÓN (Solo Admin/Jefe)
# ==============================
if st.session_state["pagina"] == "configuracion":
    if st.session_state["rol"] not in ["admin"]:
        st.error("❌ No tienes permiso para acceder a esta sección.")
        st.stop()

    st.title("⚙️ Configuración del Sistema")
    st.write("Desde aquí puedes descargar el inventario completo o gestionar datos del sistema.")

    df = cargar_datos()

    # Descargar inventario (admin)
    buffer = BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)
    st.download_button(
        "📥 Descargar Inventario (Excel)",
        buffer.getvalue(),
        "inventario.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.divider()
    st.subheader("🧨 Opciones avanzadas")

    if st.button("🗑️ Reiniciar inventario (vaciar todo)"):
        df_vacio = pd.DataFrame(columns=["codigo", "nombre", "categoria", "cantidad", "fecha_ingreso"])
        guardar_datos(df_vacio)
        st.success("Inventario reiniciado correctamente.")
        st.experimental_rerun()

    # Exportar historial completo (solo admin)
    if os.path.exists(HISTORIAL_FILE):
        with open(HISTORIAL_FILE, "rb") as f:
            hist_bytes = f.read()
        st.download_button("📥 Descargar Historial (CSV)", hist_bytes, "historial.csv", "text/csv")
    else:
        st.info("No hay historial para descargar todavía.")

    st.markdown("---")
    if st.button("⬅️ Volver al menú principal"):
        st.session_state["pagina"] = "menu"
        st.experimental_rerun()

# ==============================
# GESTIÓN DE USUARIOS (Admin/Jefe)
# ==============================
if st.session_state["pagina"] == "usuarios":
    if st.session_state["rol"] != "admin":
        st.error("❌ No tienes permiso para acceder a esta sección.")
        st.stop()

    st.title("👥 Gestión de Usuarios")
    usuarios = cargar_usuarios()

    st.subheader("Usuarios actuales")
    usuarios_display = {k: {"rol": v["rol"]} for k, v in usuarios.items()}
    st.json(usuarios_display)

    st.divider()
    st.subheader("Agregar nuevo usuario")
    nuevo_user = st.text_input("Nombre de usuario", key="nuevo_user")
    nueva_clave = st.text_input("Contraseña", type="password", key="nueva_clave")
    nuevo_rol = st.selectbox("Rol", ["admin", "bodeguero", "vendedor"], key="nuevo_rol")

    if st.button("➕ Crear usuario"):
        if not nuevo_user or not nueva_clave:
            st.warning("Completa nombre y contraseña.")
        elif nuevo_user in usuarios:
            st.error("El usuario ya existe.")
        else:
            usuarios[nuevo_user] = {"clave": nueva_clave, "rol": nuevo_rol}
            guardar_usuarios(usuarios)
            st.success("Usuario creado correctamente.")
            st.experimental_rerun()

    st.divider()
    st.subheader("Modificar usuario existente")
    usuario_sel = st.selectbox("Seleccionar usuario", list(usuarios.keys()), key="usuario_sel")
    nueva_clave_mod = st.text_input("Nueva contraseña (dejar vacío para no cambiar)", type="password", key="clave_mod")
    nuevo_rol_mod = st.selectbox("Nuevo rol", ["admin", "bodeguero", "vendedor"], index=["admin", "bodeguero", "vendedor"].index(usuarios[usuario_sel]["rol"]), key="rol_mod")

    if st.button("💾 Guardar cambios"):
        if usuario_sel == "admin" and nuevo_rol_mod != "admin":
            st.warning("No puedes cambiar el rol del administrador principal.")
        else:
            if nueva_clave_mod:
                usuarios[usuario_sel]["clave"] = nueva_clave_mod
            usuarios[usuario_sel]["rol"] = nuevo_rol_mod
            guardar_usuarios(usuarios)
            st.success("Usuario modificado correctamente.")
            st.experimental_rerun()

    st.divider()
    st.subheader("Eliminar usuario")
    eliminar_user = st.selectbox("Seleccionar usuario a eliminar", [u for u in usuarios.keys() if u != "admin"], key="eliminar_user")
    if st.button("🗑️ Eliminar usuario"):
        if eliminar_user in usuarios:
            del usuarios[eliminar_user]
            guardar_usuarios(usuarios)
            st.success("Usuario eliminado.")
            st.experimental_rerun()
        else:
            st.error("Usuario no encontrado.")

    if st.button("⬅️ Volver al menú principal"):
        st.session_state["pagina"] = "menu"
        st.experimental_rerun()
