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
# Intento de import para lector de códigos de barras (pyzbar)
# No se importa al inicio con from pyzbar... para evitar romper la app cuando falta zbar.
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

# --- Helpers para Excel con múltiples hojas (productos + proveedores) ---
def cargar_datos():
    """
    Carga la hoja 'productos' desde DATA_FILE. Si no existe, intenta leer la primera hoja.
    Devuelve DataFrame con columnas mínimas garantizadas.
    """
    if os.path.exists(DATA_FILE):
        # Intentar leer hoja 'productos'
        try:
            df = pd.read_excel(DATA_FILE, sheet_name="productos")
        except Exception:
            # fallback: primera hoja
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
    # Normalizar columnas
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
    # Asegurar codigo como string
    df["codigo"] = df["codigo"].astype(str)
    return df

def cargar_proveedores():
    """
    Lee la hoja 'proveedores' del excel si existe. Si no, devuelve df vacío con columnas esperadas.
    """
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
    """
    Guarda ambas hojas (productos y proveedores) en DATA_FILE.
    Reescribe el archivo completo (ambas hojas).
    """
    try:
        # Usar openpyxl (asegúrate que esté instalado)
        with pd.ExcelWriter(DATA_FILE, engine="openpyxl") as writer:
            product_df.to_excel(writer, sheet_name="productos", index=False)
            prov_df.to_excel(writer, sheet_name="proveedores", index=False)
    except Exception as e:
        # fallback simple: guardar solo productos (no recomendable pero evita fallo total)
        product_df.to_excel(DATA_FILE, index=False)

def guardar_datos(df):
    """
    Guarda productos en la hoja 'productos', manteniendo la hoja 'proveedores' actual.
    """
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

# ==============================
# HISTORIAL (CSV) - ahora con proveedor y nota
# ==============================
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

# ==============================
# registrar movimiento (usa guardar_all internamente)
# ==============================
def registrar_movimiento(tipo, codigo, nombre, cantidad, usuario_actual=None,
                         precio_costo=None, precio_venta=None, descripcion=None, categoria=None, proveedor=""):
    """
    tipo: "entrada" o "salida" o "nuevo" (si se crea manualmente desde productos)
    cantidad: int
    """
    df = cargar_datos()
    df["codigo"] = df["codigo"].astype(str)
    codigo = str(codigo).strip()
    usuario_actual = usuario_actual or "desconocido"

    if tipo == "entrada":
        if codigo in df["codigo"].values:
            # actualizar cantidad y campos opcionales
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
            # producto nuevo -> crear y marcar en historial como 'nuevo'
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
            # Si queda en 0 o negativo, eliminar el registro (o lo dejamos con 0 según preferencia)
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
        registrar_historial(usuario_actual, "nuevo", codigo, nombre, int(cantidad), proveedor=proveedor, nota="Producto creado manualmente")

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
        data = decoded[0].data.decode("utf-8")
        return data
    except Exception:
        return ""

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
    with col4:
        st.write("")
    with col5:
        if rol == "admin":
            st.button("⚙️ Configuración", use_container_width=True, on_click=go_to, args=("configuracion",))
            # Mostrar acceso directo a proveedores (admin)
            st.button("📇 Proveedores", use_container_width=True, on_click=go_to, args=("proveedores",))

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
# PRODUCTOS (agregar/editar)
# ==============================
if st.session_state["pagina"] == "productos":
    if st.session_state["rol"] not in ["admin", "bodeguero"]:
        st.error("No tienes permiso para acceder a esta sección.")
        st.stop()

    st.title("🗂️ Gestión de Productos")
    df = cargar_datos()
    prov_df = cargar_proveedores()

    st.subheader("Listado actual")
    st.dataframe(df, use_column_width=True)

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

    # Proveedor (seleccionar o crear)
    prov_options = [""] + prov_df["nombre"].astype(str).tolist()
    proveedor_sel = st.selectbox("Proveedor (opcional)", prov_options)
    nuevo_proveedor_txt = st.text_input("O crea un nuevo proveedor (nombre) - opcional")

    if st.button("💾 Guardar producto"):
        if codigo and nombre:
            producto_df = cargar_datos()
            codigo = str(codigo).strip()
            prov_choice = nuevo_proveedor_txt.strip() if nuevo_proveedor_txt.strip() else proveedor_sel
            if codigo in producto_df["codigo"].astype(str).values:
                # editar
                producto_df.loc[producto_df["codigo"].astype(str) == codigo, "nombre"] = nombre
                producto_df.loc[producto_df["codigo"].astype(str) == codigo, "descripcion"] = descripcion
                producto_df.loc[producto_df["codigo"].astype(str) == codigo, "categoria"] = categoria
                producto_df.loc[producto_df["codigo"].astype(str) == codigo, "cantidad"] = int(cantidad)
                producto_df.loc[producto_df["codigo"].astype(str) == codigo, "precio_costo"] = float(precio_costo)
                producto_df.loc[producto_df["codigo"].astype(str) == codigo, "precio_venta"] = float(precio_venta)
                producto_df.loc[producto_df["codigo"].astype(str) == codigo, "proveedor"] = prov_choice
                st.success("✅ Producto actualizado correctamente.")
                # registrar historial de edición como 'entrada' si cantidad aumentó? (dejamos fuera)
            else:
                # crear nuevo producto y registrar historial tipo 'nuevo'
                nueva_fila = pd.DataFrame({
                    "codigo": [codigo],
                    "nombre": [nombre],
                    "descripcion": [descripcion],
                    "categoria": [categoria],
                    "cantidad": [int(cantidad)],
                    "precio_costo": [float(precio_costo)],
                    "precio_venta": [float(precio_venta)],
                    "fecha_ingreso": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
                    "proveedor": [prov_choice]
                })
                producto_df = pd.concat([producto_df, nueva_fila], ignore_index=True)
                st.success("✅ Producto agregado correctamente.")
                registrar_historial(st.session_state.get("usuario"), "nuevo", codigo, nombre, int(cantidad), proveedor=prov_choice, nota="Producto creado desde pantalla Productos")
            # Si se creó un nuevo proveedor por el campo, lo agregamos a proveedores
            if nuevo_proveedor_txt.strip():
                prov_df_local = cargar_proveedores()
                new_id = 1 if prov_df_local.empty else (prov_df_local["id"].max() + 1 if "id" in prov_df_local.columns and pd.api.types.is_numeric_dtype(prov_df_local["id"]) else len(prov_df_local) + 1)
                prov_df_local = prov_df_local.append({
                    "id": new_id,
                    "nombre": nuevo_proveedor_txt.strip(),
                    "contacto": "",
                    "email": "",
                    "telefono": "",
                    "direccion": "",
                    "notas": ""
                }, ignore_index=True)
                guardar_proveedores(prov_df_local)
                st.success(f"Proveedor '{nuevo_proveedor_txt.strip()}' agregado.")
            guardar_datos(producto_df)
            go_to("productos")
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
# ENTRADAS (con cámara + proveedor + factura PDF mejorado)
# ==============================
if st.session_state["pagina"] == "entradas":
    if st.session_state["rol"] not in ["admin", "bodeguero"]:
        st.error("No tienes permiso para acceder a esta sección.")
        st.stop()

    st.title("📦 Registrar Entrada de Inventario")
    prov_df = cargar_proveedores()

    # Captura por cámara (opcional) para obtener código
    st.subheader("Capturar imagen con la cámara (opcional) para leer código de barras")
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

    # Proveedor en entrada: seleccionar
    prov_options = [""] + prov_df["nombre"].astype(str).tolist()
    proveedor_sel = st.selectbox("Proveedor asociado (opcional)", prov_options)
    nuevo_proveedor_txt = st.text_input("O crea nuevo proveedor (nombre) - opcional")

    # --- Subida de factura PDF ---
    st.subheader("Subir factura en PDF")
    factura_file = st.file_uploader("Selecciona factura en PDF", type=["pdf"])

    if factura_file is not None and st.button("Procesar Factura PDF"):
        try:
            import re, uuid, pdfplumber, io
            from PIL import Image
            import pytesseract

            safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', factura_file.name)
            unique_filename = f"{uuid.uuid4()}_{safe_filename}"
            factura_path = os.path.join(FACTURAS_DIR, unique_filename)
            with open(factura_path, "wb") as f:
                f.write(factura_file.getbuffer())

            productos = []

            # 1. Intentar con pdfplumber
            with pdfplumber.open(io.BytesIO(factura_file.getvalue())) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    tables = page.extract_tables()
                    st.write(f"Página {page_num} → Tablas detectadas: {len(tables)}")
                    for table in tables:
                        st.write("Tabla detectada:", table)
                        for row in table:
                            st.write("Fila:", row)
                            # Ajusta este umbral si tu tabla tiene 3 columnas (p.ej., código, desc, cantidad y el precio/valor en otra tabla)
                            if row and len(row) > 6:
                                codigo_row = str(row[0]).strip()
                                descripcion_row = str(row[1]).strip()
                                try:
                                    cantidad_row = int(str(row[2]).replace(".", "").replace(",", ""))
                                except:
                                    cantidad_row = None
                                try:
                                    precio_row = float(str(row[3]).replace(".", "").replace(",", "."))
                                except:
                                    precio_row = None

                                if codigo_row and descripcion_row and cantidad_row is not None and precio_row is not None:
                                    productos.append({
                                        "codigo": codigo_row,
                                        "nombre": descripcion_row,
                                        "cantidad": cantidad_row,
                                        "precio_costo": precio_row
                                    })

            # 2. Fallback OCR si productos está vacío
            if not productos:
                st.warning("⚠️ No se detectaron productos con pdfplumber. Intentando con OCR...")
                img = Image.open(io.BytesIO(factura_file.getvalue()))
                texto = pytesseract.image_to_string(img, lang="spa")
                st.text_area("Texto detectado por OCR", texto, height=200)

                # Heurística simple: líneas con estructura [CODIGO] [DESCRIPCION...] [CANTIDAD] [PRECIO]
                for line in texto.split("\n"):
                    raw = line.strip()
                    if not raw:
                        continue
                    parts = raw.split()
                    # Buscar un patrón mínimo. Ajusta según tu documento real.
                    if len(parts) >= 4 and parts[-2].replace(",", "").replace(".", "").isdigit():
                        # Suponemos:
                        # parts[0] = código
                        # parts[1: -2] = nombre/descripcion
                        # parts[-2] = cantidad
                        # parts[-1] = precio unitario (con coma decimal)
                        codigo_row = parts[0]
                        try:
                            cantidad_row = int(parts[-2].replace(".", "").replace(",", ""))
                        except:
                            cantidad_row = None
                        try:
                            precio_row = float(parts[-1].replace(".", "").replace(",", "."))
                        except:
                            precio_row = None
                        nombre_row = " ".join(parts[1:-2]).strip()
                        if codigo_row and nombre_row and cantidad_row is not None and precio_row is not None:
                            productos.append({
                                "codigo": codigo_row,
                                "nombre": nombre_row,
                                "cantidad": cantidad_row,
                                "precio_costo": precio_row
                            })

            # 3. Registrar si se detectaron productos
            if productos:
                st.success(f"✅ Productos detectados: {len(productos)}")
                st.dataframe(productos)
                prov_choice = nuevo_proveedor_txt.strip() if nuevo_proveedor_txt.strip() else proveedor_sel
                for p in productos:
                    registrar_movimiento("entrada", p["codigo"], p["nombre"], p["cantidad"],
                                         usuario_actual=st.session_state.get("usuario"),
                                         precio_costo=p["precio_costo"], proveedor=prov_choice)
                st.success("✅ Productos ingresados desde factura PDF")
            else:
                st.error("❌ No se detectaron productos válidos en la factura.")

        except Exception as e:
            st.error(f"❌ Error al procesar factura PDF: {e}")

    # --- Captura de factura con cámara ---
    st.subheader("Capturar factura con cámara")
    foto = st.camera_input("📸 Toma una foto de la factura")

    if foto is not None and st.button("Procesar Factura Foto"):
        try:
            import uuid
            from PIL import Image
            import pytesseract

            # Guardar la foto en carpeta de facturas
            safe_filename = f"{uuid.uuid4()}_captura.jpg"
            factura_path = os.path.join(FACTURAS_DIR, safe_filename)
            with open(factura_path, "wb") as f:
                f.write(foto.getbuffer())

            img = Image.open(foto)
            texto = pytesseract.image_to_string(img, lang="spa")
            st.text_area("Texto detectado por OCR (foto)", texto, height=200)

            productos = []
            for line in texto.split("\n"):
                raw = line.strip()
                if not raw:
                    continue
                parts = raw.split()
                if len(parts) >= 4 and parts[-2].replace(",", "").replace(".", "").isdigit():
                    codigo_row = parts[0]
                    try:
                        cantidad_row = int(parts[-2].replace(".", "").replace(",", ""))
                    except:
                        cantidad_row = None
                    try:
                        precio_row = float(parts[-1].replace(".", "").replace(",", "."))
                    except:
                        precio_row = None
                    nombre_row = " ".join(parts[1:-2]).strip()
                    if codigo_row and nombre_row and cantidad_row is not None and precio_row is not None:
                        productos.append({
                            "codigo": codigo_row,
                            "nombre": nombre_row,
                            "cantidad": cantidad_row,
                            "precio_costo": precio_row
                        })

            if productos:
                st.success(f"✅ Productos detectados: {len(productos)}")
                st.dataframe(productos)
                prov_choice = nuevo_proveedor_txt.strip() if nuevo_proveedor_txt.strip() else proveedor_sel
                for p in productos:
                    registrar_movimiento(
                        "entrada",
                        p["codigo"],
                        p["nombre"],
                        p["cantidad"],
                        usuario_actual=st.session_state.get("usuario"),
                        precio_costo=p["precio_costo"],
                        proveedor=prov_choice
                    )
                st.success("✅ Productos ingresados desde factura Foto")
            else:
                st.error("❌ No se detectaron productos válidos en la foto.")

        except Exception as e:
            st.error(f"❌ Error al procesar factura Foto: {e}")

    # --- Registrar entrada manual ---
    if st.button("✅ Registrar entrada"):
        if not codigo:
            st.warning("Ingresa o captura un código antes de registrar.")
        else:
            prov_choice = nuevo_proveedor_txt.strip() if nuevo_proveedor_txt.strip() else proveedor_sel
            registrar_movimiento("entrada", codigo, nombre, int(cantidad), usuario_actual=st.session_state.get("usuario"),
                                precio_costo=precio_costo if precio_costo > 0 else None,
                                precio_venta=precio_venta if precio_venta > 0 else None,
                                descripcion=None, categoria=None, proveedor=prov_choice)
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
                    proveedor_actual = df_check.loc[df_check["codigo"].astype(str) == str(codigo).strip(), "proveedor"].iloc[0] if "proveedor" in df_check.columns else ""
                    registrar_movimiento("salida", codigo, "", int(cantidad), usuario_actual=st.session_state.get("usuario"), proveedor=proveedor_actual)
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
            new_id = 1 if prov_df.empty else (prov_df["id"].max() + 1 if "id" in prov_df.columns and pd.api.types.is_numeric_dtype(prov_df["id"]) else len(prov_df) + 1)
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

    st.markdown("---")
    if st.button("⬅️ Volver al menú principal"):
        go_to("menu")

# ==============================
# OCR PAGE (opcional)
# ==============================
if st.session_state["pagina"] == "ocr":
    st.title("🖼️ OCR - Extraer texto de una imagen (opcional)")
    st.write("Esta página es opcional. Si quieres que el OCR esté integrado en el flujo principal, dime y lo integro.")
    st.markdown("Nota: el OCR real necesita paquetes externos (pytesseract/paddleocr o modelos transformers).")

    uploaded_image = st.file_uploader("Sube una imagen (jpg/png) para extraer texto", type=["png", "jpg", "jpeg"])
    if uploaded_image:
        try:
            pil_img = Image.open(uploaded_image).convert("RGB")
            st.image(pil_img, caption="Imagen subida", use_column_width=True)
            st.success("Imagen cargada. Implementa tu motor OCR (pytesseract / PaddleOCR / LightOnOCR) para extraer texto.")
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
        st.markdown("#### Filtros rápidos")
        cols = st.columns(3)
        with cols[0]:
            filtro_usuario = st.text_input("Usuario (exacto)", "")
        with cols[1]:
            filtro_tipo = st.selectbox("Tipo", ["todos", "nuevo", "entrada", "salida"])
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
# BACKUP (página separada)
# ==============================
if st.session_state["pagina"] == "backup":
    st.title("📦 Copia de Seguridad del Inventario")
    df = cargar_datos()
    prov_df = cargar_proveedores()

    fecha = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup_name = f"backup_inventario_{fecha}.xlsx"
    buffer = BytesIO()
    # guardar ambas hojas al buffer
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

    st.markdown("_Nota: este botón está oculto del menú principal. La copia crea un archivo Excel con las hojas `productos` y `proveedores` en la carpeta `backups`._")

    if st.button("⬅️ Volver al menú principal"):
        go_to("menu")

# ==============================
# CONFIGURACIÓN (Solo Admin)
# ==============================
if st.session_state["pagina"] == "configuracion":
    if st.session_state["rol"] not in ["admin"]:
        st.error("❌ No tienes permiso para acceder a esta sección.")
        st.stop()

    st.title("⚙️ Configuración del Sistema")
    st.write("Desde aquí puedes descargar el inventario completo o gestionar datos del sistema.")
    df = cargar_datos()
    prov_df = cargar_proveedores()

    # Descargar inventario (admin)
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

    st.divider()
    st.subheader("🧨 Opciones avanzadas")
    if st.button("🗑️ Reiniciar inventario (vaciar todo)"):
        df_vacio = pd.DataFrame(columns=["codigo", "nombre", "descripcion", "categoria", "cantidad", "precio_costo", "precio_venta", "fecha_ingreso", "proveedor"])
        prov_vacio = pd.DataFrame(columns=["id", "nombre", "contacto", "email", "telefono", "direccion", "notas"])
        guardar_all(df_vacio, prov_vacio)
        st.success("Inventario y proveedores reiniciados correctamente.")
        st.rerun()

    # Exportar historial completo (solo admin)
    if os.path.exists(HISTORIAL_FILE):
        with open(HISTORIAL_FILE, "rb") as f:
            hist_bytes = f.read()
        st.download_button("📥 Descargar Historial (CSV)", hist_bytes, "historial.csv", "text/csv")
    else:
        st.info("No hay historial para descargar todavía.")

    st.markdown("---")
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
