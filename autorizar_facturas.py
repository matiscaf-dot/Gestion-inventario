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
        st.dataframe(df_prod[["codigo_proveedor","descripcion_item","cantidad_sugerida","valor_unitario","valor_total"]])

        if st.button("Autorizar factura"):
            # Actualizar inventario
            df = cargar_datos()
            for _, row in df_prod.iterrows():
                registrar_historial(st.session_state["usuario"], "entrada",
                                    row["codigo_proveedor"], row["descripcion_item"],
                                    row["cantidad_sugerida"], proveedor=factura_sel["proveedor"],
                                    nota=f"Factura {factura_sel['num_factura']} autorizada")
                # Actualizar stock
                if row["codigo_proveedor"] in df["codigo"].values:
                    df.loc[df["codigo"] == row["codigo_proveedor"], "cantidad"] += int(row["cantidad_sugerida"])
                else:
                    nueva_fila = pd.DataFrame([{
                        "codigo": row["codigo_proveedor"],
                        "nombre": row["descripcion_item"],
                        "descripcion": "",
                        "categoria": "General",
                        "cantidad": int(row["cantidad_sugerida"]),
                        "precio_costo": float(row["valor_unitario"]),
                        "precio_venta": float(row["valor_unitario"]*1.2), # ejemplo markup
                        "fecha_ingreso": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "proveedor": factura_sel["proveedor"]
                    }])
                    df = pd.concat([df, nueva_fila], ignore_index=True)

            guardar_datos(df)

            # Cambiar estado a autorizada
            supabase.table("detalle_factura_tmp").update({"estado":"autorizada"}).eq("id", factura_sel["id"]).execute()

            st.success("Factura autorizada y stock actualizado.")
