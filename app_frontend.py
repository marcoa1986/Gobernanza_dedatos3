import os
import sqlite3
import pandas as pd
import streamlit as st
import requests

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8003")

st.set_page_config(page_title="SMARTPROMARCO Gobernanza", page_icon="🛡️", layout="wide")

st.sidebar.title("🛡️ SMARTPROMARCO")
menu = st.sidebar.radio("Navegación", ["📊 Dashboard", "👥 Gestión de Usuarios", "🤖 Auditoría IA"])

if menu == "📊 Dashboard":
    st.title("Panel de Control y Trazabilidad ISO")
    st.metric("Tenants Activos", "4", "+1 este mes")
    
    st.divider()
    st.subheader("📜 Log Inmutable de Evidencias (ISO 20000, 27001, 42001)")
    
    # Consulta dinámica a la base de datos
    try:
        conn = sqlite3.connect('demo.db')
        query = "SELECT fecha, operacion, evidencia, estado FROM log_auditoria ORDER BY id DESC"
        df_logs = pd.read_sql_query(query, conn)
        conn.close()
        
        if not df_logs.empty:
            st.dataframe(df_logs, use_container_width=True, hide_index=True)
        else:
            st.info("El log de auditoría está vacío. Realiza una operación en 'Auditoría IA' para generar evidencias.")
    except Exception as e:
        st.warning("La tabla de auditoría se generará automáticamente con la primera transacción.")

elif menu == "👥 Gestión de Usuarios":
    st.title("Alta de Usuarios Multi-Tenant")
    with st.form("registro_form"):
        tenant_id = st.text_input("ID del Tenant", value="3fa85f64-5717-4562-b3fc-2c963f66afa6")
        username = st.text_input("Nombre de Usuario")
        email = st.text_input("Correo Electrónico")
        password = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Registrar Usuario")
        
    if submit:
        if tenant_id and username and email and password:
            try:
                res = requests.post(f"{API_BASE_URL}/auth/registro", json={
                    "tenant_id": tenant_id, "username": username, "email": email, "password": password
                }, timeout=5)
                
                if res.status_code in [200, 201]:
                    st.success("✅ ¡Usuario guardado exitosamente!")
                    st.json(res.json())
                else:
                    st.error(f"❌ Error del Backend ({res.status_code}): {res.text}")
            except Exception as e:
                st.error(f"🚨 Error conectando a {API_BASE_URL}")

elif menu == "🤖 Auditoría IA":
    st.title("Evaluación de Transacciones (Agentes IA)")
    
    with st.form("ia_eval_form"):
        st.write("Simulación de orquestación: **Decisor** (Analiza) vs **Auditor** (Valida Umbrales)")
        operacion = st.selectbox("Operación CRUD a evaluar", ["INSERT INTO config_seguridad", "UPDATE roles_usuario", "DELETE registro_financiero"])
        datos = st.text_area("Carga útil (Datos de la transacción)")
        
        # Selección del framework de autonomía
        modelo_ia = st.radio("Modelo de Autonomía (Governance)", ["HITL (Human in the Loop)", "HOTL (Human on the Loop)", "HOOTL (Human out of the Loop)"])
        
        submit_ia = st.form_submit_button("Analizar Transacción")
        
    if submit_ia:
        try:
            # Extraer solo las siglas (HITL, HOTL, HOOTL) para el backend
            modelo_corto = modelo_ia.split(" ")[0] 
            
            # Llamada HTTP REAL al backend
            res = requests.post(f"{API_BASE_URL}/audit/evaluate", json={
                "tenant_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "operacion": operacion,
                "datos": datos,
                "modelo_ia": modelo_corto
            }, timeout=5)
            
            if res.status_code == 200:
                data = res.json()
                st.success("✅ Evaluación IA Completada en Tiempo Real")
                
                col1, col2 = st.columns(2)
                col1.info(f"🧠 **Agente Decisor:**\n\n{data['decision_decisor']}")
                col2.warning(f"🛡️ **Agente Auditor:**\n\n{data['estado_auditor']}")
                
                st.code(f"Evidencia ISO Generada:\n{data['evidencia_generada']}", language="text")
            else:
                st.error(f"Error de API: {res.text}")
        except Exception as e:
            st.error(f"Fallo de conexión: {e}")
