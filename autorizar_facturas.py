import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime
from streamlit_app import registrar_historial

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Helpers
def safe_int(x):
    try:
        return int(float(x))
    except:
        return 0

def safe_float(x):
    try:
        return round(float(x), 2)
    except:
        return 0

def es_codigo_barras_valido(codigo: str) -> bool:
    return codigo.isdigit() and len(codigo) in [12, 13]

def calcular_cantidad_real(row):
    try:
        valor_total = float(row.get("valor_total", 0.0))
        valor_unitario = float(row.get("valor_unitario", 0.0))
        cantidad_factura = safe_int(row.get("cantidad_factura"))

        if valor_unitario > 0 and valor_total > 0:
            cantidad_calculada = round((valor_total * 1.19) / valor_unitario)
            if cantidad_calculada == cantidad_factura:
                return cantidad_factura
            else:
                return cantidad_calculada
        else:
            return cantidad_factura
    except:
        return cantidad_factura

def render():
    st.title("✅ Autorizar Facturas")

    if st.session_state["rol"] != "bodeguero":
        st.error("❌ Solo bodega puede autorizar facturas.")
        st.stop()

    facturas = supabase.table("detalle_factura_tmp").select("*").eq("estado", "pendiente").execute().data
    if not facturas:
        st.info("No hay facturas pendientes de autorización.")
        return

    opciones = [f"Factura {f['num_factura']} - {f['proveedor']}" for f in facturas]
    seleccion = st.selectbox("Selecciona una factura pendiente", opciones)

    if seleccion:
        factura_sel = facturas[opciones.index(seleccion)]
        st.write("Resumen factura:", factura_sel)

        productos = supabase.table("productos_tmp").select("*").eq("factura_id", factura_sel["id"]).execute().data
        df_prod = pd.DataFrame(productos)

        if df_prod.empty:
            st.error("❌ No se encontraron productos asociados a esta factura.")
            st.stop()

        st.subheader("Productos asociados")
        st.dataframe(df_prod[["codigo_proveedor","descripcion_item","cantidad_factura","valor_unitario","valor_total"]])

        # Inputs para códigos inválidos
        nuevos_codigos = {}
        for idx, row in df_prod.iterrows():
            codigo_actual = str(row.get("codigo_proveedor", "")).strip()
            descripcion = row.get("descripcion_item", "")
            if not es_codigo_barras_valido(codigo_actual):
                st.warning(f"⚠️ El producto '{descripcion}' no tiene un código de barras válido.")
                nuevos_codigos[idx] = st.text_input(
                    f"Ingrese/escanee código de barras para: {descripcion}",
                    value=""
                )
                cam_input = st.camera_input(f"Capturar código para: {descripcion}")
                if cam_input is not None:
                    st.info("📸 Código capturado, pendiente de procesamiento OCR/barcode reader.")

        if st.button("Autorizar factura"):
            # Validar códigos
            for idx, nuevo_codigo in nuevos_codigos.items():
                if not es_codigo_barras_valido(nuevo_codigo.strip()):
                    st.error(f"❌ El producto '{df_prod.at[idx, 'descripcion_item']}' aún no tiene un código válido (12–13 dígitos).")
                    st.stop()
                df_prod.at[idx, "codigo_proveedor"] = nuevo_codigo.strip()

            registros_inventario = []
            for _, row in df_prod.iterrows():
                registros_inventario.append({
                    "factura_id": factura_sel["id"],
                    "codigo_proveedor": str(row.get("codigo_proveedor", "")).strip(),
                    "descripcion_item": str(row.get("descripcion_item", "")).strip(),
                    "cantidad_factura": safe_int(row.get("cantidad_factura")),
                    "valor_unitario": safe_float(row.get("valor_unitario")),
                    "valor_total": safe_float(row.get("valor_total")),
                    "cantidad_real": calcular_cantidad_real(row),
                    "precio_producto": safe_float(row.get("precio_producto"))
                })

                registrar_historial(
                    st.session_state["usuario"], "entrada",
                    row.get("codigo_proveedor",""), row.get("descripcion_item",""),
                    safe_int(row.get("cantidad_factura")),
                    proveedor=factura_sel["proveedor"],
                    nota=f"Factura {factura_sel['num_factura']} autorizada"
                )

            supabase.table("inventario").upsert(registros_inventario).execute()
            supabase.table("detalle_factura_tmp").update({"estado":"autorizada"}).eq("id", factura_sel["id"]).execute()

            st.success("✅ Factura autorizada y productos traspasados al inventario con códigos corregidos y cantidad real calculada.")
