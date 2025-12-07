# app.py
import streamlit as st
import pandas as pd
from datetime import datetime
import os
import json
from io import BytesIO
from PIL import Image
from pyzbar.pyzbar import decode
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
# Intento de import para lector de códigos de barras (pyzbar)
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
def asegurar_usuarios_iniciales():
    """Si no existe usuarios.json, crea uno con usuarios por defecto (opción B: diccionario hardcode)."""
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
        df = pd.DataFrame(columns=[
            "codigo", "nombre", "descripcion", "categoria",
            "cantidad", "precio_costo", "precio_venta", "fecha_ingreso"
        ])
        df.to_excel(DATA_FILE, index=False)
    # Asegurar columnas necesarias
    expected_cols = ["codigo", "nombre", "descripcion", "categoria", "cantidad", "precio_costo", "precio_venta", "fecha_ingreso"]
    for col in expected_cols:
        if col not in df.columns:
            if col in ["cantidad"]:
                df[col] = 0
            elif col in ["precio_costo", "precio_venta"]:
                df[col] = 0.0
            else:
                df[col] = ""
    # Forzar tipos
    try:
        df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(0).astype(int)
    except Exception:
        df["cantidad"] = df["cantidad"].apply(lambda x: int(x) if pd.notna(x) and str(x).isdigit() else 0)
    for pcol in ["precio_costo", "precio_venta"]:
        try:
            df[pcol] = pd.to_numeric(df[pcol], errors="coerce").fillna(0.0).astype(float)
        except Exception:
            df[pcol] = df[pcol].apply(lambda x: float(x) if pd.notna(x) and is_number(str(x)) else 0.0)
    return df

def is_number(s):
    try:
        float(s)
        return True
    except:
        return False

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

def registrar_movimiento(tipo, codigo, nombre, cantidad, usuario_actual=None, precio_costo=None, precio_venta=None, descripcion=None, categoria=None):
    """
    tipo: "entrada" o "salida"
    cantidad: int (si es salida, debe ser positiva; la función restará)
    """
    df = cargar_datos()
    df["codigo"] = df["codigo"].astype(str)
    codigo = str(codigo).strip()

    if tipo == "entrada":
        if codigo in df["codigo"].values:
            df.loc[df["codigo"] == codigo, "cantidad"] = df.loc[df["codigo"] == codigo, "cantidad"].astype(int) + int(cantidad)
            # si se entregan precios/desc, actualizarlos si vienen
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
        registrar_historial(usuario_actual or "desconocido", "entrada", codigo, nombre, int(cantidad))

    elif tipo == "salida":
        if codigo in df["codigo"].values:
            idx = df.index[df["codigo"] == codigo]
            df.loc[idx, "cantidad"] = df.loc[idx, "cantidad"].astype(int) - int(cantidad)
            if df.loc[idx, "cantidad"].iloc[0] <= 0:
                df = df[df["codigo"] != codigo]
            guardar_datos(df)
            registrar_historial(usuario_actual or "desconocido", "salida", codigo, nombre, int(cantidad))
        else:
            st.error("❌ El producto no existe en inventario.")
            return

# ==============================
# Lector de código de barras desde PIL.Image usando pyzbar (si está disponible)
# ==============================
def decode_barcode_from_pil(pil_img):
    """
    Devuelve el primer código encontrado como string o '' si no encuentra.
    Usa pyzbar si está instalado.
    """
    if not _HAS_PYZBAR:
        return ""
    try:
        decoded = zbar_decode(pil_img)
        if not decoded:
            return ""
        # Retornar data del primer barcode
        data = decoded[0].data.decode("utf-8")
        return data
    except Exception:
        return ""

# ==============================
# Helpers para navegación (evitan problemas de doble clic)
# ==============================
def go_to(page):
    st.session_state["pagina"] = page
    st.rerun()

# ==============================
# INICIALIZACIÓN DE SESSION_STATE (UNA SOLA VEZ)
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
# LOGIN SIMPLE (con usuarios.json - opción B)
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
            st.button("📦 Tabla Inventario", use_container_width=True, on_click=go_to, args=("dashboard",))
            st.button("➖ Registrar Salida", use_container_width=True, on_click=go_to, args=("salidas",))

    # Opciones bodeguero
    with col2:
        if rol in ["admin", "bodeguero"]:
            st.button("🗂️ Productos", use_container_width=True, on_click=go_to, args=("productos",))
            st.button("➕ Registrar Entrada", use_container_width=True, on_click=go_to, args=("entradas",))

    # Botones adicionales para todos (ocultamos copia de seguridad del menú principal)
    st.markdown("---")
    col3, col4, col5 = st.columns(3)
    with col3:
        st.button("📝 Historial de movimientos", use_container_width=True, on_click=go_to, args=("historial",))
    with col4:
        # espacio reservado (botón oculto intencionalmente)
        st.write("") 
    with col5:
        # Gestión y configuración solo admin
        if rol == "admin":
            st.button("⚙️ Configuración", use_container_width=True, on_click=go_to, args=("configuracion",))

    st.markdown("---")
    if st.button("🚪 Cerrar sesión", use_container_width=True):
        st.session_state["logueado"] = False
        st.session_state["pagina"] = "inicio"
        st.session_state["rol"] = None
        st.session_state["usuario"] = None
        st.success("Sesión cerrada correctamente 👋")
        st.rerun()

# ==============================
# DASHBOARD (Tabla Inventario)
# ==============================
if st.session_state["pagina"] == "dashboard":
    st.title("📦 Tabla Inventario")
    df = cargar_datos()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total de Productos", int(len(df)))
    with col2:
        st.metric("Stock Total", int(df["cantidad"].sum()))

    st.markdown("### Inventario actual")
    st.dataframe(df, use_container_width=True)

    if st.button("⬅️ Volver al menú principal"):
        go_to("menu")

# ==============================
# PRODUCTOS (agregar/editar) - incluye opción cámara para capturar código
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
    st.subheader("Agregar o editar producto (nuevo)")

    # Opción cámara para capturar el código de barra
    st.markdown("**Capturar código con la cámara (recomendado para códigos físicos)**")
    cam_img = st.camera_input("Toma una foto del código o producto (si tu navegador lo permite)")

    detected_code = ""
    if cam_img:
        # Guardar imagen temporal
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        cam_path = os.path.join(CAPTURAS_DIR, f"producto_{timestamp}.jpg")
        with open(cam_path, "wb") as f:
            f.write(cam_img.getbuffer())
        st.success("Imagen capturada correctamente.")
        # Intentar decodificar código de barras si pyzbar está presente
        try:
            pil_img = Image.open(cam_path).convert("RGB")
            detected_code = decode_barcode_from_pil(pil_img)
            if detected_code:
                st.info(f"Código detectado: {detected_code}")
            else:
                if not _HAS_PYZBAR:
                    st.warning("No se pudo decodificar: pyzbar no está instalado. Para habilitar lector de códigos, instala pyzbar y zbar (ver instrucciones abajo).")
                else:
                    st.info("No se detectó código en la imagen (intenta acercar la cámara o enfocar el código).")
        except Exception as e:
            st.error(f"No se pudo procesar la imagen: {e}")

    st.markdown("**O ingresa manualmente los datos:**")
    codigo = st.text_input("Código del producto", value=detected_code)
    nombre = st.text_input("Nombre del producto")
    descripcion = st.text_area("Descripción (opcional)")
    categoria = st.text_input("Categoría", value="General")
    cantidad = st.number_input("Cantidad inicial", min_value=0, step=1, value=0)
    precio_costo = st.number_input("Precio costo", min_value=0.0, step=0.1, format="%.2f", value=0.0)
    precio_venta = st.number_input("Precio venta", min_value=0.0, step=0.1, format="%.2f", value=0.0)

    if st.button("💾 Guardar producto"):
        if codigo and nombre:
            df = cargar_datos()
            codigo = str(codigo).strip()
            if codigo in df["codigo"].astype(str).values:
                # editar
                df.loc[df["codigo"].astype(str) == codigo, "nombre"] = nombre
                df.loc[df["codigo"].astype(str) == codigo, "descripcion"] = descripcion
                df.loc[df["codigo"].astype(str) == codigo, "categoria"] = categoria
                df.loc[df["codigo"].astype(str) == codigo, "cantidad"] = int(cantidad)
                df.loc[df["codigo"].astype(str) == codigo, "precio_costo"] = float(precio_costo)
                df.loc[df["codigo"].astype(str) == codigo, "precio_venta"] = float(precio_venta)
                st.success("✅ Producto actualizado correctamente.")
            else:
                nueva_fila = pd.DataFrame({
                    "codigo": [codigo],
                    "nombre": [nombre],
                    "descripcion": [descripcion],
                    "categoria": [categoria],
                    "cantidad": [int(cantidad)],
                    "precio_costo": [float(precio_costo)],
                    "precio_venta": [float(precio_venta)],
                    "fecha_ingreso": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                })
                df = pd.concat([df, nueva_fila], ignore_index=True)
                st.success("✅ Producto agregado correctamente.")
            guardar_datos(df)
            go_to("productos")  # recargar la página productos
        else:
            st.warning("Completa al menos Código y Nombre antes de guardar.")

    st.markdown("---")
    if st.button("⬅️ Volver al menú principal"):
        go_to("menu")

    # Instrucciones para instalar pyzbar si no está
    if not _HAS_PYZBAR:
        st.info("Para habilitar lectura automática de códigos necesitas instalar `pyzbar` y el binario `zbar` en tu sistema.")
        st.markdown("""
**Instalación sugerida (ejemplos):**
- Linux (Debian/Ubuntu): `sudo apt-get install -y libzbar0 && pip install pyzbar`
- Mac (Homebrew): `brew install zbar && pip install pyzbar`
- Windows: instalar ZBar (busca instalador) y luego `pip install pyzbar`
""")

# ==============================
# ENTRADAS (con cámara + lector de código)
# ==============================
if st.session_state["pagina"] == "entradas":
    if st.session_state["rol"] not in ["admin", "bodeguero"]:
        st.error("No tienes permiso para acceder a esta sección.")
        st.stop()

    st.title("📦 Registrar Entrada de Inventario")

    # Captura por cámara (opcional) para obtener código
    st.subheader("Capturar imagen con la cámara (opcional) para leer código de barras)")
    camera_image = st.camera_input("Toma una foto del producto o código")

    pre_codigo = ""
    if camera_image:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        camera_path = os.path.join(CAPTURAS_DIR, f"entrada_{timestamp}.jpg")
        with open(camera_path, "wb") as f:
            f.write(camera_image.getbuffer())
        st.success("Imagen guardada.")
        try:
            pil_img = Image.open(camera_path).convert("RGB")
            detected = decode_barcode_from_pil(pil_img)
            if detected:
                st.info(f"Código detectado: {detected}")
                pre_codigo = detected
            else:
                if not _HAS_PYZBAR:
                    st.warning("pyzbar no está instalado: no se pudo decodificar automáticamente.")
                else:
                    st.info("No se detectó código en la imagen.")
        except Exception as e:
            st.error(f"No se pudo procesar la imagen: {e}")

    st.markdown("---")
    codigo = st.text_input("Código del producto", value=pre_codigo)
    nombre = st.text_input("Nombre del producto (opcional)")
    cantidad = st.number_input("Cantidad a ingresar", min_value=1, step=1, value=1)
    precio_costo = st.number_input("Precio costo (opcional)", min_value=0.0, step=0.1, format="%.2f", value=0.0)
    precio_venta = st.number_input("Precio venta (opcional)", min_value=0.0, step=0.1, format="%.2f", value=0.0)

    factura_file = st.file_uploader("Subir factura (opcional)", type=["pdf", "png", "jpg", "jpeg"])

    if st.button("✅ Registrar entrada"):
        if not codigo:
            st.warning("Ingresa o captura un código antes de registrar.")
        else:
            registrar_movimiento("entrada", codigo, nombre, int(cantidad), usuario_actual=st.session_state.get("usuario"),
                                precio_costo=precio_costo if precio_costo > 0 else None,
                                precio_venta=precio_venta if precio_venta > 0 else None)
            if factura_file:
                factura_path = os.path.join(FACTURAS_DIR, factura_file.name)
                with open(factura_path, "wb") as f:
                    f.write(factura_file.getbuffer())
                st.session_state["factura_subida"] = factura_path
            st.success("Entrada registrada correctamente.")
            go_to("entradas")

    if st.button("⬅️ Volver al menú principal"):
        go_to("menu")

# ==============================
# SALIDAS (con cámara)
# ==============================
if st.session_state["pagina"] == "salidas":
    if st.session_state["rol"] not in ["admin", "vendedor"]:
        st.error("No tienes permiso para acceder a esta sección.")
        st.stop()

    st.title("📤 Registrar Salida de Inventario")

    st.markdown("Puedes tomar una foto para intentar detectar el código, o ingresar el código manualmente.")
    camera_image = st.camera_input("Toma una foto del producto o código (opcional)")

    pre_codigo = ""
    if camera_image:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        camera_path = os.path.join(CAPTURAS_DIR, f"salida_{timestamp}.jpg")
        with open(camera_path, "wb") as f:
            f.write(camera_image.getbuffer())
        st.success("Imagen guardada.")
        try:
            pil_img = Image.open(camera_path).convert("RGB")
            detected = decode_barcode_from_pil(pil_img)
            if detected:
                st.info(f"Código detectado: {detected}")
                pre_codigo = detected
            else:
                if not _HAS_PYZBAR:
                    st.warning("pyzbar no está instalado: no se pudo decodificar automáticamente.")
                else:
                    st.info("No se detectó código en la imagen.")
        except Exception as e:
            st.error(f"No se pudo procesar la imagen: {e}")

    st.markdown("---")
    codigo = st.text_input("Código del producto", value=pre_codigo)
    cantidad = st.number_input("Cantidad a descontar", min_value=1, step=1, value=1)
    boleta_file = st.file_uploader("Subir boleta (opcional)", type=["pdf", "png", "jpg", "jpeg"])

    if st.button("✅ Registrar salida"):
        if not codigo:
            st.warning("Ingresa o captura un código antes de registrar.")
        else:
            df_check = cargar_datos()
            if str(codigo).strip() not in df_check["codigo"].astype(str).values:
                st.error("❌ El producto no existe en inventario.")
            else:
                current_qty = int(df_check.loc[df_check["codigo"].astype(str) == str(codigo).strip(), "cantidad"].iloc[0])
                if cantidad > current_qty:
                    st.warning(f"⚠️ Stock insuficiente. Stock actual: {current_qty}")
                else:
                    registrar_movimiento("salida", codigo, "", int(cantidad), usuario_actual=st.session_state.get("usuario"))
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
# OCR PAGE (opcional, mantenido separado) - no aparece en menú principal
# (si deseas mantenerlo, la página queda accesible si setéas st.session_state['pagina']='ocr')
# ==============================
if st.session_state["pagina"] == "ocr":
    st.title("🖼️ OCR - Extraer texto de una imagen (opcional)")
    st.write("Esta página es opcional. Si quieres que el OCR esté integrado en el flujo principal, dime y lo integro.")
    st.markdown("Nota: el OCR real necesita modelos/paquetes externos (ej. pytesseract o modelos transformers).")

    uploaded_image = st.file_uploader("Sube una imagen (jpg/png) para extraer texto", type=["png", "jpg", "jpeg"])
    if uploaded_image:
        try:
            pil_img = Image.open(uploaded_image).convert("RGB")
            st.image(pil_img, caption="Imagen subida", use_column_width=True)
            st.success("Imagen cargada. Implementa tu motor OCR (pytesseract / LightOnOCR) para extraer texto.")
        except Exception as e:
            st.error(f"No se pudo abrir la imagen: {e}")

    if st.button("⬅️ Volver al menú principal"):
        go_to("menu")

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
        go_to("menu")

# ==============================
# COPIA DE SEGURIDAD (Disponible en su propia página, no en menú principal)
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

    st.markdown("_Nota: este botón está oculto del menú principal. La copia crea un archivo Excel con el inventario actual en la carpeta `backups`._")

    if st.button("⬅️ Volver al menú principal"):
        go_to("menu")

# ==============================
# CONFIGURACIÓN (Solo Admin/Jefe) + GESTIÓN DE USUARIOS integrada
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
        df_vacio = pd.DataFrame(columns=["codigo", "nombre", "descripcion", "categoria", "cantidad", "precio_costo", "precio_venta", "fecha_ingreso"])
        guardar_datos(df_vacio)
        st.success("Inventario reiniciado correctamente.")
        st.rerun()

    # Exportar historial completo (solo admin)
    if os.path.exists(HISTORIAL_FILE):
        with open(HISTORIAL_FILE, "rb") as f:
            hist_bytes = f.read()
        st.download_button("📥 Descargar Historial (CSV)", hist_bytes, "historial.csv", "text/csv")
    else:
        st.info("No hay historial para descargar todavía.")

    st.markdown("---")
    # ----------------------------
    # Gestión de usuarios integrada
    # ----------------------------
    st.subheader("👥 Gestión de Usuarios")
    usuarios = cargar_usuarios()

    st.markdown("**Usuarios actuales**")
    usuarios_data = [{"Usuario": u, "Rol": info["rol"]} for u, info in usuarios.items()]
    if usuarios_data:
        df_usuarios_display = pd.DataFrame(usuarios_data)
        st.table(df_usuarios_display)
    else:
        st.info("No hay usuarios definidos.")

    st.divider()
    st.subheader("Agregar nuevo usuario")
    nuevo_user = st.text_input("Nombre de usuario", key="cfg_nuevo_user")
    nueva_clave = st.text_input("Contraseña", type="password", key="cfg_nueva_clave")
    nuevo_rol = st.selectbox("Rol", ["admin", "bodeguero", "vendedor"], key="cfg_nuevo_rol")

    if st.button("➕ Crear usuario", key="cfg_crear_user"):
        if not nuevo_user or not nueva_clave:
            st.warning("Completa nombre y contraseña.")
        elif nuevo_user in usuarios:
            st.error("El usuario ya existe.")
        else:
            usuarios[nuevo_user] = {"clave": nueva_clave, "rol": nuevo_rol}
            guardar_usuarios(usuarios)
            st.success("Usuario creado correctamente.")
            st.rerun()

    st.divider()
    st.subheader("Modificar usuario existente")
    usuario_sel = st.selectbox("Seleccionar usuario", list(usuarios.keys()), key="cfg_usuario_sel")
    nueva_clave_mod = st.text_input("Nueva contraseña (dejar vacío para no cambiar)", type="password", key="cfg_clave_mod")
    nuevo_rol_mod = st.selectbox("Nuevo rol", ["admin", "bodeguero", "vendedor"], index=["admin", "bodeguero", "vendedor"].index(usuarios[usuario_sel]["rol"]), key="cfg_rol_mod")

    if st.button("💾 Guardar cambios", key="cfg_guardar_cambios"):
        if usuario_sel == "admin" and nuevo_rol_mod != "admin":
            st.warning("No puedes cambiar el rol del administrador principal.")
        else:
            if nueva_clave_mod:
                usuarios[usuario_sel]["clave"] = nueva_clave_mod
            usuarios[usuario_sel]["rol"] = nuevo_rol_mod
            guardar_usuarios(usuarios)
            st.success("Usuario modificado correctamente.")
            st.rerun()

    st.divider()
    st.subheader("Eliminar usuario")
    eliminar_user = st.selectbox("Seleccionar usuario a eliminar", [u for u in usuarios.keys() if u != "admin"], key="cfg_eliminar_user")
    if st.button("🗑️ Eliminar usuario", key="cfg_eliminar_btn"):
        if eliminar_user in usuarios:
            del usuarios[eliminar_user]
            guardar_usuarios(usuarios)
            st.success("Usuario eliminado.")
            st.rerun()
        else:
            st.error("Usuario no encontrado.")

    st.markdown("---")
    if st.button("⬅️ Volver al menú principal", key="cfg_volver"):
        go_to("menu")
