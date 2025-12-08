import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime
from core.facturas import normalizar_tabla
from streamlit_app import cargar_datos, guardar_datos, registrar_historial

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def render():
    st.title("✅ Autorizar Facturas")

    # Solo bodeguero puede autorizar
    if st.session_state["rol"] != "bodeguero":
        st.error("❌ Solo bodega puede autorizar facturas.")
        st.stop()

    # Traer facturas pendientes
    facturas = supabase.table("detalle_factura_tmp").select("*").eq("estado", "pendiente").execute().data

    if not facturas:
        st.info("No hay facturas pendientes de autorización.")
        return

    # Seleccionar factura
    opciones = [f"Factura {f['num_factura']} - {f['proveedor']}" for f in facturas]
    seleccion = st.selectbox("Selecciona una factura pendiente", opciones)

    if seleccion:
        factura_sel = facturas[opciones.index(seleccion)]
        st.write("Resumen factura:", factura_sel)

        # Traer productos asociados
        productos = supabase.table("productos_tmp").select("*").eq("factura_id", factura_sel["id"]).execute().data
        df_prod = pd.DataFrame(productos)
        cols = ["codigo_proveedor", "descripcion_item", "cantidad_factura", "valor_unitario", "valor_total"]
        cols_validas = [c for c in cols if c in df_prod.columns]
        st.dataframe(df_prod[cols_validas])

        if st.button("Autorizar factura"):
            # Cargar productos asociados
            productos = supabase.table("productos_tmp").select("*").eq("factura_id", factura_sel["id"]).execute().data
            df_prod = pd.DataFrame(productos)
        
            if df_prod.empty:
                st.error("❌ No se encontraron productos asociados a esta factura.")
                st.stop()
        
            registros_inventario = []
            for _, row in df_prod.iterrows():
                registros_inventario.append({
                    "factura_id": factura_sel["id"],
                    "codigo_proveedor": str(row.get("codigo_proveedor", "")).strip(),
                    "descripcion_item": str(row.get("descripcion_item", "")).strip(),
                    "cantidad_factura": int(row.get("cantidad_factura", 0)),
                    "valor_unitario": float(row.get("valor_unitario", 0.0)),
                    "valor_total": float(row.get("valor_total", 0.0)),
                    "cantidad_real": row.get("cantidad_real", None),
                    "precio_producto": int(row.get("precio_producto", 0.0))
                })
        
            # Insertar en inventario
            supabase.table("inventario").upsert(registros_inventario).execute()
        
            # Actualizar estado de la factura
            supabase.table("detalle_factura_tmp").update({"estado": "autorizada"}).eq("id", factura_sel["id"]).execute()
        
            st.success("✅ Factura autorizada y productos traspasados al inventario.")
