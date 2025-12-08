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
        cols = ["codigo_proveedor", "descripcion_item", "cantidad_sugerida", "valor_unitario", "valor_total"]
        cols_validas = [c for c in cols if c in df_prod.columns]
        st.dataframe(df_prod[cols_validas])

        if st.button("Autorizar factura"):
            # Actualizar inventario
            df = cargar_datos()
            for _, row in df_prod.iterrows():
                codigo = str(row.get("codigo_proveedor", "")).strip()
                descripcion = str(row.get("descripcion_item", "")).strip()
                cantidad = int(row.get("cantidad_factura", 0))
                valor_unitario = float(row.get("valor_unitario", 0.0))
            
                registrar_historial(
                    st.session_state["usuario"], "entrada",
                    codigo, descripcion, cantidad,
                    proveedor=factura_sel["proveedor"],
                    nota=f"Factura {factura_sel['num_factura']} autorizada"
                )
            
                if codigo in df["codigo"].values:
                    df.loc[df["codigo"] == codigo, "cantidad"] += cantidad
                else:
                    nueva_fila = pd.DataFrame([{
                        "codigo": codigo,
                        "nombre": descripcion,
                        "descripcion": "",
                        "categoria": "General",
                        "cantidad": cantidad,
                        "precio_costo": valor_unitario,
                        "precio_venta": round(valor_unitario * 1.2, 2),
                        "fecha_ingreso": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "proveedor": factura_sel["proveedor"]
                    }])
                    df = pd.concat([df, nueva_fila], ignore_index=True)
            
            guardar_datos(df)

            # Cambiar estado a autorizada
            supabase.table("detalle_factura_tmp").update({"estado":"autorizada"}).eq("id", factura_sel["id"]).execute()

            st.success("Factura autorizada y stock actualizado.")
