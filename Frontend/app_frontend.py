import streamlit as st
import requests
import pandas as pd

# 1. Configuración de la página
st.set_page_config(page_title="SMARTPROMARCO PoC", layout="wide")

st.title("📊 Consola de Operaciones - SMARTPROMARCO")
st.markdown("### Monitor de Validación de Compras")

# 2. Ruta de tu API (Backend)
API_URL = "http://127.0.0.1:8000/compras/"

# 3. Función para consumir la API
def obtener_compras():
    try:
        # Hacemos la petición GET a FastAPI
        respuesta = requests.get(API_URL)
        if respuesta.status_code == 200:
            return respuesta.json()
        else:
            st.error(f"Error en la API: {respuesta.status_code}")
            return []
    except requests.exceptions.ConnectionError:
        st.error("No se pudo conectar con FastAPI. ¿Está corriendo uvicorn?")
        return []

# 4. Obtener y mostrar la información
datos = obtener_compras()

if datos:
    # Convertimos el JSON que mandó FastAPI a una tabla visual de Streamlit
    df = pd.DataFrame(datos)
    
    # Mostramos un par de métricas rápidas arriba
    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="Total de Órdenes", value=len(df))
    with col2:
        pendientes = len(df[df['factura_vs_oc'] == 'Pendiente'])
        st.metric(label="⚠️ Facturas Pendientes", value=pendientes)
    
    # Mostramos la tabla interactiva
    st.write("**Detalle de la Matriz:**")
    st.dataframe(df, use_container_width=True)
else:
    st.info("No hay datos para mostrar.")