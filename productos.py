import streamlit as st
import pandas as pd
from supabase import create_client

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def render():
    st.title("🛠️ Gestión de Productos")

    if st.session_state.get("rol") != "admin":
        st.error("❌ Solo el administrador puede editar precios.")
        st.stop()

    # Cargar inventario
    response = supabase.table("inventario").select("*").execute()
    df = pd.DataFrame(response.data)

    if df.empty:
        st.info("No hay productos en inventario.")
        return

    # Buscador general
    busqueda = st.text_input("🔎 Buscar producto (por código, nombre, stock o precio)").strip().lower()

    # Filtro de precio
    col1, col2 = st.columns(2)
    precio_min = col1.number_input("Precio mínimo", min_value=0.0, value=0.0, step=100.0)
    precio_max = col2.number_input("Precio máximo", min_value=0.0, value=100000.0, step=100.0)

    # Preparar columnas
    for col in ["codigo_proveedor", "descripcion_item", "cantidad_real", "precio_producto"]:
        if col in df.columns:
            df[col] = df[col].astype(str).fillna("")

    # Aplicar filtros
    df_filtrado = df[
        df["precio_producto"].astype(float).between(precio_min, precio_max)
    ]

    if busqueda:
        df_filtrado = df_filtrado[
            df_filtrado["codigo_proveedor"].str.lower().str.contains(busqueda) |
            df_filtrado["descripcion_item"].str.lower().str.contains(busqueda) |
            df_filtrado["cantidad_real"].str.contains(busqueda) |
            df_filtrado["precio_producto"].str.contains(busqueda)
        ]

    # Renombrar columnas
    nombres_columnas = {
        "codigo_proveedor": "Código de barras",
        "descripcion_item": "Nombre producto",
        "valor_unitario": "Costo producto",
        "cantidad_real": "Stock",
        "precio_producto": "Precio de venta"
    }
    df_filtrado = df_filtrado.rename(columns=nombres_columnas)

    # Mostrar tabla
    st.subheader("📋 Productos en inventario")
    st.dataframe(df_filtrado[list(nombres_columnas.values())], use_container_width=True)

   st.subheader("✏️ Modificar precio de venta")

    # Campo de búsqueda por código de barras
    codigo_busqueda = st.text_input("🔎 Ingresa o escanea el código de barras").strip()
    
    # Filtrar producto según código ingresado
    producto_sel = None
    if codigo_busqueda:
        producto = df_filtrado[df_filtrado["Código de barras"].astype(str) == codigo_busqueda]
        if not producto.empty:
            producto_sel = producto.iloc[0]
            st.write("📦 Producto encontrado:", producto_sel.get("Nombre del producto", "Sin nombre"))
            st.write("💲 Precio actual:", producto_sel.get("Precio de venta", "No definido"))
        else:
            st.warning("⚠️ No se encontró producto con ese código.")
    
    # Input para nuevo precio
    nuevo_precio = st.number_input("Nuevo precio de venta", min_value=0.0, step=100.0)
    
    # Botón para actualizar
    if st.button("Actualizar precio"):
        if producto_sel is not None:
            try:
                supabase.table("inventario").update({"precio_producto": float(nuevo_precio)}).eq("codigo_proveedor", codigo_busqueda).execute()
                st.success(f"✅ Precio actualizado para el producto con código {codigo_busqueda}.")
                st.experimental_rerun()
            except Exception as e:
                st.error(f"❌ Error al actualizar precio: {e}")
        else:
            st.error("❌ Debes ingresar un código válido antes de actualizar.")
