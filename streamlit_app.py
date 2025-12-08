# app.py
import streamlit as st
import pandas as pd
from datetime import datetime
import bcrypt
from supabase import create_client, Client
import pdfplumber
import pytesseract
from PIL import Image
import io
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
    st.title("➕ Registrar Entrada desde Factura")

    # --- Datos de cabecera ---
    numero = st.text_input("Número de factura")
    proveedor = st.text_input("Proveedor")
    fecha = st.date_input("Fecha", datetime.now().date())
    st.text("Hola")
    # --- Opción 1: Subir factura en PDF ---
    st.subheader("Subir factura en PDF")
    factura_file = st.file_uploader("Selecciona factura en PDF", type=["pdf"])
    st.text("Hola2")
    if factura_file is not None and st.button("Procesar Factura PDF"):
        st.text("Hola3")
        try:
            st.text("Hola4")
            import re, uuid

            safe_filename = re.sub(r'[^a-zA-Z0-9._-]', '_', factura_file.name)
            unique_filename = f"{uuid.uuid4()}_{safe_filename}"

            supabase.storage.from_("facturas").upload(
                unique_filename,
                factura_file.getvalue()
            )
            url_publica = supabase.storage.from_("facturas").get_public_url(unique_filename)
            st.text("Hola5")
            factura = supabase.table("facturas").insert({
                "numero": numero,
                "proveedor": proveedor,
                "fecha": fecha.isoformat(),
                "archivo_url": url_publica
            }).execute()
            factura_id = factura.data[0]["id"]

            productos = []
            with pdfplumber.open(io.BytesIO(factura_file.getvalue())) as pdf:
                st.txt("Hola11")
                for page in pdf.pages:
                    st.text("Hola12")
                    tables = page.extract_tables()
                    for table in tables:
                        st.text("Hola13")
                        for row in table:
                            st.text("Hola14")
                            if row and len(row) >= 4:
                                st.text("Hola15")
                                codigo = str(row[0]).strip()
                                descripcion = str(row[1]).strip()
                                try:
                                    st.text("Hola16")
                                    cantidad = int(str(row[2]).replace(".", "").replace(",", ""))
                                    precio_costo = float(str(row[3]).replace(".", "").replace(",", "."))
                                except:
                                    continue
                                productos.append({
                                    "codigo": codigo,
                                    "nombre": descripcion,
                                    "cantidad": cantidad,
                                    "precio_costo": precio_costo
                                })
            st.text("Hola7")
            for p in productos:
                st.text("Hola8")
                supabase.table("factura_detalle").insert({
                    "factura_id": factura_id,
                    "codigo": p["codigo"],
                    "nombre": p["nombre"],
                    "cantidad": p["cantidad"],
                    "precio_costo": p["precio_costo"]
                }).execute()
                st.text("Hola9")
                supabase.table("inventario").upsert({
                    "codigo": p["codigo"],
                    "nombre": p["nombre"],
                    "cantidad": p["cantidad"],
                    "tipo_movimiento": "entrada",
                    "descripcion": p["nombre"],
                    "categoria": "sin_categoria",
                    "precio_costo": p["precio_costo"],
                    "fecha_ingreso": datetime.now().isoformat(),
                    "proveedor": proveedor
                }).execute()
                st.text("Hlola8")
                registrar_historial(
                    usuario=st.session_state["usuario"],
                    tipo="entrada",
                    codigo=p["codigo"],
                    nombre=p["nombre"],
                    cantidad=p["cantidad"]
                )

            st.success("✅ Productos ingresados desde factura PDF")
            st.rerun()

        except Exception as e:
            st.error(f"❌ Error al procesar factura PDF: {e}")

    st.divider()

    # --- Opción 2: Capturar factura con cámara ---
    st.subheader("Capturar factura con cámara")
    foto = st.camera_input("📸 Toma una foto de la factura")

    if foto is not None and st.button("Procesar Factura Foto"):
        try:
            import re, uuid
            from PIL import Image
            import pytesseract

            safe_filename = f"{uuid.uuid4()}_captura.jpg"
            supabase.storage.from_("facturas").upload(
                safe_filename,
                foto.getvalue()
            )
            url_publica = supabase.storage.from_("facturas").get_public_url(safe_filename)

            factura = supabase.table("facturas").insert({
                "numero": numero,
                "proveedor": proveedor,
                "fecha": fecha.isoformat(),
                "archivo_url": url_publica
            }).execute()
            factura_id = factura.data[0]["id"]

            # OCR para extraer texto de la foto
            img = Image.open(foto)
            texto = pytesseract.image_to_string(img, lang="spa")

            productos = []
            for line in texto.split("\n"):
                parts = line.split()
                if len(parts) >= 4 and parts[2].isdigit():
                    codigo = parts[0]
                    nombre = parts[1]
                    cantidad = int(parts[2])
                    try:
                        precio_costo = float(parts[3].replace(",", "."))
                    except:
                        precio_costo = 0.0
                    productos.append({
                        "codigo": codigo,
                        "nombre": nombre,
                        "cantidad": cantidad,
                        "precio_costo": precio_costo
                    })

            for p in productos:
                supabase.table("factura_detalle").insert({
                    "factura_id": factura_id,
                    "codigo": p["codigo"],
                    "nombre": p["nombre"],
                    "cantidad": p["cantidad"],
                    "precio_costo": p["precio_costo"]
                }).execute()

                supabase.table("inventario").upsert({
                    "codigo1": p["codigo"],
                    "nombre": p["nombre"],
                    "cantidad": p["cantidad"],
                    "tipo_movimiento": "entrada",
                    "descripcion": p["nombre"],
                    "categoria": "sin_categoria",
                    "precio_costo": p["precio_costo"],
                    "fecha_ingreso": datetime.now().isoformat(),
                    "proveedor": proveedor
                }).execute()

                registrar_historial(
                    usuario=st.session_state["usuario"],
                    tipo="entrada",
                    codigo=p["codigo"],
                    nombre=p["nombre"],
                    cantidad=p["cantidad"]
                )

            st.success("✅ Productos ingresados desde factura Foto")
            st.rerun()

        except Exception as e:
            st.error(f"❌ Error al procesar factura Foto: {e}")

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

elif opcion == "Facturas":
    st.title("🧾 Historial de Facturas Registradas")

    def cargar_facturas():
        resp = supabase.table("facturas").select("*").order("fecha", desc=True).execute()
        return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()

    def cargar_detalle_factura(factura_id: str):
        resp = supabase.table("factura_detalle").select("*").eq("factura_id", factura_id).execute()
        return pd.DataFrame(resp.data) if resp.data else pd.DataFrame()

    df_facturas = cargar_facturas()

    if df_facturas.empty:
        st.info("No hay facturas registradas.")
    else:
        for _, row in df_facturas.iterrows():
            with st.expander(f"Factura {row['numero']} — Proveedor: {row['proveedor']} — Fecha: {row['fecha']}"):
                st.markdown(f"[📄 Ver documento PDF]({row['archivo_url']})")

                df_det = cargar_detalle_factura(row["id"])
                if df_det.empty:
                    st.info("Sin detalle.")
                else:
                    st.dataframe(df_det, use_container_width=True)

# ==============================
# SECCIÓN HISTORIAL
# ==============================
elif opcion == "Historial":
    st.title("📜 Historial de Movimientos")
    df_hist = cargar_historial()
    if not df_hist.empty:
        # Ordenar por fecha descendente
        if "fecha" in df_hist.columns:
            try:
                df_hist["fecha"] = pd.to_datetime(df_hist["fecha"])
                df_hist = df_hist.sort_values("fecha", ascending=False)
            except:
                pass
        st.dataframe(df_hist, use_container_width=True)
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
            usuarios = cargar_usuarios()  # refrescar
            if nuevo_usuario in usuarios:
                st.error("El usuario ya existe.")
            else:
                try:
                    guardar_usuario(nuevo_usuario, clave_usuario, rol_usuario)
                    st.success(f"Usuario {nuevo_usuario} agregado correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error al agregar usuario: {e}")
