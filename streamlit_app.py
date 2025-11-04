# streamlit_app.py
"""
Inventario Fulltime - single-file Streamlit app (CSV backend)
Funciones:
 - Login básico (usuarios en el código)
 - CRUD productos (CSV)
 - Registrar movimientos (Ingreso / Salida) (CSV)
 - Export CSV / Excel
 - Generar y descargar QR y Código de barras (Code128)
 - Sin uso de cámara (lo dejamos para más adelante)
"""

import streamlit as st
import pandas as pd
import os
from datetime import datetime
from io import BytesIO
from PIL import Image
import qrcode
import barcode
from barcode.writer import ImageWriter

# -----------------------
# Config & paths
# -----------------------
st.set_page_config(page_title="Inventario Fulltime", page_icon="📦", layout="wide")
DATA_DIR = "data"
PRODUCTS_CSV = os.path.join(DATA_DIR, "products.csv")
MOVS_CSV = os.path.join(DATA_DIR, "movements.csv")

# -----------------------
# Usuarios (login simple)
# -----------------------
USERS = {
    "admin": "1234",
    "hector": "fulltime"
}
# Puedes agregar más usuarios aquí: "usuario":"contraseña"

# -----------------------
# Helpers: FS (CSV)
# -----------------------
def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    if not os.path.exists(PRODUCTS_CSV):
        df = pd.DataFrame(columns=["codigo","nombre","categoria","stock","precio","minstock","created_at","updated_at"])
        df.to_csv(PRODUCTS_CSV, index=False)
    if not os.path.exists(MOVS_CSV):
        df = pd.DataFrame(columns=["id","codigo","tipo","cantidad","fecha","usuario","notas"])
        df.to_csv(MOVS_CSV, index=False)

def load_products():
    ensure_data_dir()
    return pd.read_csv(PRODUCTS_CSV, dtype={"codigo":str}).fillna("")

def save_products(df):
    df.to_csv(PRODUCTS_CSV, index=False)

def load_movements():
    ensure_data_dir()
    return pd.read_csv(MOVS_CSV, dtype={"codigo":str}).fillna("")

def save_movements(df):
    df.to_csv(MOVS_CSV, index=False)

# -----------------------
# Utilidades
# -----------------------
def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def uid(prefix="id"):
    return f"{prefix}_{int(datetime.now().timestamp()*1000)}"

# -----------------------
# Generadores de imagen (QR y barcode)
# -----------------------
def generate_qr_bytes(data: str, box_size=6):
    qr = qrcode.QRCode(box_size=box_size, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    bio = BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio

def generate_code128_bytes(data: str):
    # Usa python-barcode Code128 con ImageWriter para PNG
    try:
        code = barcode.get("code128", data, writer=ImageWriter())
    except Exception as e:
        # fallback: generar imagen básica con texto
        img = Image.new("RGB", (400,100), color="white")
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(img)
        draw.text((10,30), data, fill="black")
        bio = BytesIO()
        img.save(bio, format="PNG")
        bio.seek(0)
        return bio

    bio = BytesIO()
    code.write(bio, options={"write_text": False})  # sin texto debajo
    bio.seek(0)
    return bio

# -----------------------
# Registro movimiento (ingreso/salida)
# -----------------------
def register_movement(codigo, tipo, cantidad, usuario, notas=""):
    dfp = load_products()
    # crear si no existe en productos (registro mínimo)
    if codigo not in dfp["codigo"].astype(str).tolist():
        newp = {
            "codigo": codigo,
            "nombre": "(nuevo)",
            "categoria": "",
            "stock": 0,
            "precio": 0.0,
            "minstock": 0,
            "created_at": now_str(),
            "updated_at": now_str()
        }
        dfp = pd.concat([dfp, pd.DataFrame([newp])], ignore_index=True)
    # actualizar stock
    idx = dfp.index[dfp["codigo"].astype(str) == str(codigo)][0]
    current_stock = float(dfp.at[idx, "stock"] or 0)
    if tipo.lower() == "ingreso":
        new_stock = current_stock + float(cantidad)
    else:
        new_stock = current_stock - float(cantidad)
        if new_stock < 0:
            return False, "Stock insuficiente"
    dfp.at[idx, "stock"] = new_stock
    dfp.at[idx, "updated_at"] = now_str()
    save_products(dfp)

    # guardar movimiento
    movs = load_movements()
    mov = {
        "id": uid("mov"),
        "codigo": str(codigo),
        "tipo": tipo.capitalize(),
        "cantidad": cantidad,
        "fecha": now_str(),
        "usuario": usuario,
        "notas": notas
    }
    movs = pd.concat([pd.DataFrame([mov]), movs], ignore_index=True)  # prepend
    save_movements(movs)
    return True, f"Movimiento registrado. Stock actual: {new_stock}"

# -----------------------
# Interfaz: Login
# -----------------------
def do_login_area():
    st.sidebar.title("🔒 Acceso")
    user = st.sidebar.text_input("Usuario")
    pwd = st.sidebar.text_input("Contraseña", type="password")
    if st.sidebar.button("Ingresar"):
        if user in USERS and USERS[user] == pwd:
            st.session_state["autenticado"] = True
            st.session_state["usuario"] = user
            st.experimental_rerun()
        else:
            st.sidebar.error("Usuario o contraseña incorrectos")
    # logout
    if st.sidebar.button("Cerrar sesión"):
        st.session_state.clear()
        st.experimental_rerun()

if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    do_login_area()
    st.title("Inventario Fulltime")
    st.markdown("Por favor inicia sesión desde la barra lateral.")
    st.stop()

USER = st.session_state.get("usuario", "admin")  # usuario conectado

# -----------------------
# UI principal (menu)
# -----------------------
st.title("📦 Inventario Fulltime")
st.sidebar.success(f"Conectado como: {USER}")

# -----------------------
# Menú visual en página principal
# -----------------------

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

st.sidebar.success(f"Conectado como: {USER}")
if st.sidebar.button("Cerrar sesión"):
    st.session_state.clear()
    st.experimental_rerun()

st.title("📦 Inventario Fulltime")
st.caption("Sistema de gestión de inventario - FullTime")

if st.session_state.page == "Dashboard":
    st.subheader("Panel principal de gestión")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🧾 Productos"):
            st.session_state.page = "Productos"
            st.experimental_rerun()
        if st.button("📥 Ingreso"):
            st.session_state.page = "Ingreso"
            st.experimental_rerun()
        if st.button("📤 Salida"):
            st.session_state.page = "Salida"
            st.experimental_rerun()

    with col2:
        if st.button("📜 Movimientos"):
            st.session_state.page = "Movimientos"
            st.experimental_rerun()
        if st.button("⬇️ Exportar / Descargar"):
            st.session_state.page = "Exportar"
            st.experimental_rerun()
        if st.button("🔖 Generar QR / Barcode"):
            st.session_state.page = "QR"
            st.experimental_rerun()

    with col3:
        if st.button("⚙️ Ajustes"):
            st.session_state.page = "Ajustes"
            st.experimental_rerun()
        if st.button("🏠 Volver al Dashboard"):
            st.session_state.page = "Dashboard"
            st.experimental_rerun()

    st.markdown("---")
    st.write("Selecciona una opción para comenzar a gestionar tu inventario.")

# -----------------------
# Dashboard
# -----------------------
if menu == "Dashboard":
    st.header("📊 Panel principal")
    prods = load_products()
    movs = load_movements()

    col1, col2, col3 = st.columns(3)
    col1.metric("Productos registrados", len(prods))
    total_stock = prods["stock"].astype(float).sum() if len(prods)>0 else 0
    col2.metric("Stock total (unidades)", int(total_stock))
    col3.metric("Movimientos registrados", len(movs))

    st.subheader("Stock por producto")
    if prods.empty:
        st.info("No hay productos. Ve a 'Productos (CRUD)' para crear.")
    else:
        df_view = prods[["codigo","nombre","categoria","stock","minstock","precio","updated_at"]].copy()
        df_view = df_view.sort_values("stock", ascending=True)
        st.dataframe(df_view, use_container_width=True)

    st.subheader("Últimos movimientos")
    if movs.empty:
        st.info("No hay movimientos registrados.")
    else:
        st.dataframe(movs.head(20), use_container_width=True)

# -----------------------
# Productos CRUD
# -----------------------
elif menu == "Productos (CRUD)":
    st.header("🧾 Productos (Crear / Editar / Eliminar)")
    prods = load_products()
    with st.expander("Crear nuevo producto"):
        with st.form("form_create"):
            c_codigo = st.text_input("Código (SKU, EAN, QR data)", key="new_codigo")
            c_nombre = st.text_input("Nombre", key="new_nombre")
            c_cat = st.text_input("Categoría", key="new_cat")
            c_stock = st.number_input("Stock inicial", min_value=0, step=1, value=0, key="new_stock")
            c_price = st.number_input("Precio unitario", min_value=0.0, step=0.1, value=0.0, key="new_price")
            c_minstock = st.number_input("Stock mínimo (alerta)", min_value=0, step=1, value=0, key="new_minstock")
            submitted = st.form_submit_button("Crear producto")
            if submitted:
                if not c_codigo.strip():
                    st.error("Código es requerido")
                else:
                    if c_codigo in prods["codigo"].astype(str).tolist():
                        st.warning("El código ya existe. Usa editar.")
                    else:
                        newp = {
                            "codigo": c_codigo,
                            "nombre": c_nombre,
                            "categoria": c_cat,
                            "stock": c_stock,
                            "precio": c_price,
                            "minstock": c_minstock,
                            "created_at": now_str(),
                            "updated_at": now_str()
                        }
                        prods = pd.concat([prods, pd.DataFrame([newp])], ignore_index=True)
                        save_products(prods)
                        st.success("Producto creado")

    st.markdown("---")
    st.subheader("Editar / Eliminar producto")
    if prods.empty:
        st.info("No hay productos para editar.")
    else:
        codes = prods["codigo"].astype(str).tolist()
        sel = st.selectbox("Selecciona código", [""] + codes)
        if sel:
            row = prods[prods["codigo"].astype(str) == sel].iloc[0]
            with st.form("form_edit"):
                e_nombre = st.text_input("Nombre", value=row["nombre"])
                e_cat = st.text_input("Categoría", value=row["categoria"])
                e_stock = st.number_input("Stock", min_value=0, value=int(float(row["stock"])), step=1)
                e_price = st.number_input("Precio", min_value=0.0, value=float(row["precio"] or 0.0), step=0.1)
                e_minstock = st.number_input("Stock mínimo", min_value=0, value=int(float(row.get("minstock",0) or 0)), step=1)
                btn_edit = st.form_submit_button("Guardar cambios")
                if btn_edit:
                    prods.loc[prods["codigo"].astype(str) == sel, ["nombre","categoria","stock","precio","minstock","updated_at"]] = [
                        e_nombre, e_cat, e_stock, e_price, e_minstock, now_str()
                    ]
                    save_products(prods)
                    st.success("Producto actualizado")
                if st.button("Eliminar producto"):
                    prods = prods[prods["codigo"].astype(str) != sel]
                    save_products(prods)
                    st.success("Producto eliminado")

    st.markdown("---")
    st.subheader("Vista rápida de productos")
    st.dataframe(load_products(), use_container_width=True)

# -----------------------
# Ingreso
# -----------------------
elif menu == "Ingreso de inventario":
    st.header("📥 Registrar Ingreso")
    with st.form("form_ingreso"):
        codigo = st.text_input("Código del producto (o SKU):")
        nombre = st.text_input("Nombre producto (si no existe se creará):")
        cantidad = st.number_input("Cantidad a ingresar", min_value=1, step=1, value=1)
        notas = st.text_area("Notas (opcional)")
        send = st.form_submit_button("Registrar ingreso")
        if send:
            if not codigo:
                st.error("Código requerido")
            else:
                ok,msg = register_movement(codigo, "ingreso", cantidad, USER, notas)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

# -----------------------
# Salida
# -----------------------
elif menu == "Salida de inventario":
    st.header("📤 Registrar Salida")
    with st.form("form_salida"):
        codigo = st.text_input("Código del producto (o SKU):")
        nombre = st.text_input("Nombre producto (opcional):")
        cantidad = st.number_input("Cantidad a retirar", min_value=1, step=1, value=1)
        notas = st.text_area("Notas (opcional)")
        send = st.form_submit_button("Registrar salida")
        if send:
            if not codigo:
                st.error("Código requerido")
            else:
                ok,msg = register_movement(codigo, "salida", cantidad, USER, notas)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

# -----------------------
# Movimientos
# -----------------------
elif menu == "Movimientos":
    st.header("📜 Historial de Movimientos")
    movs = load_movements()
    if movs.empty:
        st.info("No hay movimientos registrados")
    else:
        st.dataframe(movs, use_container_width=True)
        if st.button("Limpiar historial (elimina todo)"):
            if st.confirm("¿Seguro que deseas borrar todo el historial?"):
                pd.DataFrame(columns=movs.columns).to_csv(MOVS_CSV, index=False)
                st.success("Historial borrado")

# -----------------------
# Exportar / Descargar
# -----------------------
elif menu == "Exportar / Descargar":
    st.header("⬇️ Exportar datos")
    prods = load_products()
    movs = load_movements()

    st.subheader("Exportar inventario")
    csv_prods = prods.to_csv(index=False).encode("utf-8")
    st.download_button("Descargar inventario (CSV)", data=csv_prods, file_name="inventario.csv", mime="text/csv")
    # Excel
    towrite = BytesIO()
    with pd.ExcelWriter(towrite, engine="xlsxwriter") as writer:
        prods.to_excel(writer, index=False, sheet_name="Productos")
    towrite.seek(0)
    st.download_button("Descargar inventario (XLSX)", data=towrite.getvalue(), file_name="inventario.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.subheader("Exportar movimientos")
    csv_movs = movs.to_csv(index=False).encode("utf-8")
    st.download_button("Descargar movimientos (CSV)", data=csv_movs, file_name="movimientos.csv", mime="text/csv")

# -----------------------
# Generar QR / Barcode
# -----------------------
elif menu == "Generar QR / Barcode":
    st.header("🔖 Generar QR / Código de barras (PNG)")

    prods = load_products()
    codes = prods["codigo"].astype(str).tolist()
    sel_code = st.selectbox("Selecciona un producto (o ingresa un código nuevo)", options=[""]+codes)
    if sel_code:
        info = prods[prods["codigo"].astype(str) == sel_code].iloc[0].to_dict()
        st.write("Nombre:", info.get("nombre",""))
        st.write("Stock:", info.get("stock",""))
    custom_code = st.text_input("O escribe un código personalizado (toma prioridad si no está vacío):")
    final_code = custom_code.strip() or sel_code.strip()
    if final_code:
        if st.button("Generar y descargar QR"):
            bio = generate_qr_bytes(final_code)
            st.download_button("Descargar QR PNG", data=bio.getvalue(), file_name=f"qr_{final_code}.png", mime="image/png")
            st.image(Image.open(bio), caption=f"QR: {final_code}", use_column_width=False)
        if st.button("Generar y descargar Code128 (barcode)"):
            bio2 = generate_code128_bytes(final_code)
            st.download_button("Descargar barcode PNG", data=bio2.getvalue(), file_name=f"barcode_{final_code}.png", mime="image/png")
            st.image(Image.open(bio2), caption=f"Barcode: {final_code}", use_column_width=False)

# -----------------------
# Ajustes
# -----------------------
elif menu == "Ajustes":
    st.header("⚙️ Ajustes")
    st.write("Rutas de archivos (local):")
    st.write(PRODUCTS_CSV)
    st.write(MOVS_CSV)
    st.markdown("**Usuarios definidos (en el código)**")
    st.json(list(USERS.keys()))
    if st.button("Reinicializar datos (borrar todo)"):
        if st.confirm("¿Seguro que quieres borrar productos y movimientos? Esta acción es irreversible."):
            pd.DataFrame(columns=["codigo","nombre","categoria","stock","precio","minstock","created_at","updated_at"]).to_csv(PRODUCTS_CSV, index=False)
            pd.DataFrame(columns=["id","codigo","tipo","cantidad","fecha","usuario","notas"]).to_csv(MOVS_CSV, index=False)
            st.success("Datos reiniciados")

# -----------------------
# END
# -----------------------
st.sidebar.caption("Inventario Fulltime - prototipo")
