"""
dashboard/app.py
==================
Dashboard operador de SMARTPROMARCO Gobernanza. Consume la API real vía
api_client.py — ningún dato se inventa ni se simula aquí.

Secciones (Entregable 3 original): Calidad · IA · HITL · Auditoría · Operación
+ Decisor/Auditor (debate) y generación de QR.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

import streamlit as st

import api_client as api

st.set_page_config(page_title="SMARTPROMARCO Gobernanza", page_icon="🛡️", layout="wide")

# ══════════════════════════════════════════════════════════════
# ESTILO
# ══════════════════════════════════════════════════════════════
st.markdown("""
<style>
.stApp { background-color: #0f1117; }
.metric-card { background: #1a1d29; border-radius: 10px; padding: 16px; border: 1px solid #2a2e3f; }
div[data-testid="stMetric"] { background: #1a1d29; border-radius: 10px; padding: 12px; border: 1px solid #2a2e3f; }
.risk-alto { color: #ff4d4f; font-weight: 700; }
.risk-medio { color: #faad14; font-weight: 700; }
.risk-bajo { color: #52c41a; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# ESTADO DE SESIÓN
# ══════════════════════════════════════════════════════════════
for key, default in [
    ("token", None), ("temp_token", None), ("tenant_id", None),
    ("username", None), ("rol", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default


def _logout():
    for key in ["token", "temp_token", "tenant_id", "username", "rol"]:
        st.session_state[key] = None


# ══════════════════════════════════════════════════════════════
# LOGIN (2 pasos: credenciales → PIN)
# ══════════════════════════════════════════════════════════════

def pantalla_login():
    st.markdown("## 🛡️ SMARTPROMARCO Gobernanza")
    st.caption("Plataforma de Auditoría Inteligente de Calidad de Datos")

    if st.session_state.temp_token is None:
        with st.form("login_form"):
            st.markdown("#### Paso 1 · Credenciales")
            tenant_id = st.text_input("Tenant ID", help="El UUID que te dio bootstrap_usuario_demo.py")
            username = st.text_input("Usuario", value="marco.admin")
            password = st.text_input("Contraseña", type="password")
            enviado = st.form_submit_button("Continuar", use_container_width=True)

        if enviado:
            try:
                resultado = api.login(tenant_id, username, password)
                st.session_state.temp_token = resultado["temp_token"]
                st.session_state.tenant_id = tenant_id
                st.session_state.username = username
                st.rerun()
            except api.APIError as e:
                st.error(f"❌ {e.detail}")
    else:
        st.markdown("#### Paso 2 · PIN de seguridad (MFA)")
        with st.form("pin_form"):
            pin = st.text_input("PIN de 6 dígitos", max_chars=6, type="password")
            col1, col2 = st.columns(2)
            confirmar = col1.form_submit_button("Verificar", use_container_width=True)
            volver = col2.form_submit_button("← Volver", use_container_width=True)

        if volver:
            st.session_state.temp_token = None
            st.rerun()

        if confirmar:
            try:
                resultado = api.verificar_pin(st.session_state.temp_token, pin)
                st.session_state.token = resultado["access_token"]
                st.session_state.rol = resultado["rol"]
                st.session_state.temp_token = None
                st.success("✅ Autenticado")
                st.rerun()
            except api.APIError as e:
                st.error(f"❌ {e.detail}")


# ══════════════════════════════════════════════════════════════
# BADGES DE RIESGO (mensajes ligados a reglas de negocio, no genéricos)
# ══════════════════════════════════════════════════════════════

def badge_riesgo(riesgo: str) -> str:
    return {"Alto": "🔴 Alto", "Medio": "🟡 Medio", "Bajo": "🟢 Bajo"}.get(riesgo, riesgo)


def mensaje_estado(evidencia: dict):
    """Cada estado dispara el mensaje Streamlit que le corresponde — no un solo estilo genérico."""
    decision = evidencia.get("decision")
    tipo_loop = evidencia.get("tipo_loop")
    if decision == "rechazar":
        st.error("❌ RN-ORQ-001 aplicada: transacción rechazada por el operador.")
    elif decision == "aprobar" and tipo_loop == "HOOTL":
        st.success("✅ Aprobado automáticamente (HOOTL) — riesgo bajo, sin intervención humana.")
    elif decision == "aprobar":
        st.success(f"✅ Aprobado por {evidencia.get('operador', 'operador')}.")
    elif tipo_loop == "HITL":
        st.warning("⚠️ Pendiente de decisión humana (HITL) — riesgo alto o DELETE (RN-ORQ-001).")
    else:
        st.info(f"ℹ️ Estado: {tipo_loop}")


# ══════════════════════════════════════════════════════════════
# SECCIÓN: KPIs (5 bloques del Entregable 3 original)
# ══════════════════════════════════════════════════════════════

def seccion_kpis(kpis: dict, pendientes: list, hallazgos: list):
    total = kpis.get("total", 0)
    por_riesgo = kpis.get("por_riesgo", {})
    por_loop = kpis.get("por_loop", {})
    por_validacion = kpis.get("por_validacion", {})

    st.markdown("### Calidad de Datos")
    c1, c2, c3, c4 = st.columns(4)
    pass_pct = round(100 * por_validacion.get("PASS", 0) / total, 1) if total else 0
    c1.metric("Score de validación", f"{pass_pct}%")
    c2.metric("Total auditado", total)
    no_conformidades = sum(1 for h in hallazgos if h.get("tipo") == "No Conformidad")
    c3.metric("No conformidades", no_conformidades)
    c4.metric("Observaciones", sum(1 for h in hallazgos if h.get("tipo") == "Observación"))

    st.markdown("### IA — Desempeño del Agente Auditor")
    c1, c2, c3 = st.columns(3)
    c1.metric("Riesgo Alto detectado", por_riesgo.get("Alto", 0))
    c2.metric("Riesgo Medio detectado", por_riesgo.get("Medio", 0))
    c3.metric("Riesgo Bajo detectado", por_riesgo.get("Bajo", 0))

    st.markdown("### HITL — Supervisión Humana")
    c1, c2, c3 = st.columns(3)
    c1.metric("Pendientes ahora", len(pendientes))
    c2.metric("Total HITL histórico", por_loop.get("HITL", 0))
    pct_hitl = round(100 * por_loop.get("HITL", 0) / total, 1) if total else 0
    c3.metric("% de transacciones que requieren humano", f"{pct_hitl}%")

    st.markdown("### Auditoría Interna")
    c1, c2 = st.columns(2)
    c1.metric("Hallazgos totales del período", len(hallazgos))
    c2.metric("Hallazgos abiertos", sum(1 for h in hallazgos if h.get("estado") == "abierto"))

    st.markdown("### Operación")
    c1, c2, c3 = st.columns(3)
    c1.metric("HOOTL (automático)", por_loop.get("HOOTL", 0))
    c2.metric("HOTL (autónomo, revisable)", por_loop.get("HOTL", 0))
    c3.metric("Total transacciones", total)


# ══════════════════════════════════════════════════════════════
# SECCIÓN: Alertas pendientes (HITL) — aprobar/rechazar/modificar real
# ══════════════════════════════════════════════════════════════

def seccion_pendientes(pendientes: list):
    if not pendientes:
        st.success("✅ No hay transacciones pendientes de decisión humana.")
        return

    for ev in pendientes:
        riesgo = ev.get("riesgo", "")
        with st.expander(f"{badge_riesgo(riesgo)} · {ev['operacion']} · {ev['transaction_id'][:8]}…", expanded=False):
            mensaje_estado(ev)
            col_izq, col_der = st.columns([2, 1])
            with col_izq:
                st.json(ev.get("agente_auditor", {}), expanded=False)
                st.caption(f"Explicación del Agente Auditor: {ev.get('explicacion', '—')}")
            with col_der:
                st.markdown(f"**Hash:** `{ev['hash'][:16]}…`")
                st.markdown(f"**Empresa:** {ev.get('empresa', '—')}")

            b1, b2, b3 = st.columns(3)
            if b1.button("✅ Aprobar", key=f"ap_{ev['transaction_id']}", use_container_width=True):
                try:
                    api.decidir_transaccion(st.session_state.token, ev["transaction_id"], "approve")
                    st.success("Aprobado.")
                    st.rerun()
                except api.APIError as e:
                    st.error(f"❌ {e.detail}")
            if b2.button("🚫 Rechazar", key=f"rc_{ev['transaction_id']}", use_container_width=True):
                try:
                    api.decidir_transaccion(st.session_state.token, ev["transaction_id"], "reject")
                    st.warning("Rechazado.")
                    st.rerun()
                except api.APIError as e:
                    st.error(f"❌ {e.detail}")
            if b3.button("✏️ Modificar", key=f"md_{ev['transaction_id']}", use_container_width=True):
                st.session_state[f"modificando_{ev['transaction_id']}"] = True

            if st.session_state.get(f"modificando_{ev['transaction_id']}"):
                nuevo_payload = st.text_area("Payload modificado (JSON)", value=str(ev.get("payload_original", {})),
                                              key=f"payload_{ev['transaction_id']}")
                if st.button("Confirmar modificación", key=f"confirmar_{ev['transaction_id']}"):
                    import json
                    try:
                        datos = json.loads(nuevo_payload.replace("'", '"'))
                        api.decidir_transaccion(st.session_state.token, ev["transaction_id"], "modify", datos)
                        st.success("Modificado y aprobado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ JSON inválido o error: {e}")


# ══════════════════════════════════════════════════════════════
# SECCIÓN: Decisor / Auditor (debate general, con contexto regulatorio)
# ══════════════════════════════════════════════════════════════

def seccion_debate():
    st.caption("Audita cualquier propuesta de arquitectura, negocio o código — no solo transacciones CRUD.")
    try:
        sectores_disponibles = api.listar_sectores(st.session_state.token)
    except api.APIError:
        sectores_disponibles = []

    problema = st.text_area("Problema o propuesta a evaluar", height=100,
                             placeholder="Ej. Conectar la app directo a RDS sin gateway intermedio")
    contexto = st.text_area("Contexto adicional (opcional)", height=60)
    sectores = st.multiselect("Contexto regulatorio a aplicar (opcional)", sectores_disponibles)
    max_intentos = st.slider("Máximo de reintentos antes de escalar a HITL", 1, 5, 3)

    if st.button("▶️ Iniciar debate", type="primary"):
        if not problema.strip():
            st.warning("Escribe un problema primero.")
        else:
            with st.spinner("El Decisor propone, el Auditor audita — esto llama a Bedrock, puede tardar…"):
                try:
                    resultado = api.ejecutar_debate(st.session_state.token, problema, contexto, sectores, max_intentos)
                    if resultado["escalado_a_humano"]:
                        st.warning(f"⚠️ Guardrail activado: {resultado['intentos_usados']} intentos sin llegar a 'Aprobado' — requiere tu revisión.")
                    else:
                        st.success(f"✅ Aprobado en {resultado['intentos_usados']} intento(s).")

                    st.markdown("**Propuesta final del Decisor:**")
                    st.write(resultado["propuesta_final"]["contenido"])

                    auditoria = resultado["auditoria_final"]
                    st.markdown(f"**Auditoría final:** {auditoria['estado_auditoria']}")
                    st.caption(auditoria["resumen_auditoria"])
                    for riesgo in auditoria["riesgos_encontrados"]:
                        color = {"Alta": "🔴", "Media": "🟡", "Baja": "🟢"}.get(riesgo["severidad"], "⚪")
                        st.markdown(f"{color} **[{riesgo['categoria']}]** {riesgo['descripcion']} → *exige:* {riesgo['accion_mitigacion']}")
                except api.APIError as e:
                    st.error(f"❌ {e.detail}")


# ══════════════════════════════════════════════════════════════
# SECCIÓN: Ciclo de Auditoría Interna (rol Auditor Interno)
# ══════════════════════════════════════════════════════════════

def seccion_auditor_interno(tenant_id: str):
    st.caption("Ciclo de 8 pasos (ver SOW, Sección 3.6) — muestra sugerida, no una tabla genérica.")
    periodo_actual = datetime.now(timezone.utc).strftime("%Y-%m")

    st.markdown("#### 1-2 · Muestra sugerida (riesgo Alto primero)")
    muestra = api.listar_evidencia(st.session_state.token, tenant_id, riesgo="Alto", limit=10)
    if not muestra:
        st.success("✅ No hay evidencia de riesgo Alto pendiente de revisión en este período.")
    for ev in muestra:
        with st.expander(f"🔴 {ev['operacion']} · `{ev['transaction_id'][:8]}…`"):
            st.markdown(f"**Thread ID:** `{ev['thread_id']}`")
            col1, col2 = st.columns(2)
            if col1.button("3-5 · Verificar integridad", key=f"ver_{ev['transaction_id']}"):
                try:
                    resultado = api.verificar_integridad(st.session_state.token, ev["transaction_id"])
                    if resultado.get("integra"):
                        st.success("✅ Hash verificado — evidencia íntegra.")
                    else:
                        st.error("❌ El hash no coincide — posible manipulación.")
                except api.APIError as e:
                    st.error(f"❌ {e.detail}")

            with col2.form(f"hallazgo_{ev['transaction_id']}"):
                st.markdown("**7 · Registrar hallazgo**")
                tipo = st.selectbox("Tipo", ["Observación", "No Conformidad", "Hallazgo"], key=f"tipo_{ev['transaction_id']}")
                descripcion = st.text_area("Descripción", key=f"desc_{ev['transaction_id']}")
                if st.form_submit_button("Registrar"):
                    try:
                        api.registrar_hallazgo(
                            st.session_state.token, tenant_id, tipo, descripcion,
                            auditor_id=st.session_state.username, evidencia_id=ev["transaction_id"],
                            periodo=periodo_actual,
                        )
                        st.success("✅ Hallazgo registrado.")
                        st.rerun()
                    except api.APIError as e:
                        st.error(f"❌ {e.detail}")

    st.markdown("#### 7-8 · Hallazgos del período — cerrar")
    hallazgos = api.listar_hallazgos(st.session_state.token, tenant_id, periodo_actual)
    abiertos = [h for h in hallazgos if h.get("estado") == "abierto"]
    if not abiertos:
        st.info("Sin hallazgos abiertos este período.")
    for h in abiertos:
        col1, col2 = st.columns([4, 1])
        col1.markdown(f"**[{h['tipo']}]** {h['descripcion']}")
        if col2.button("Cerrar", key=f"cerrar_{h['id']}"):
            try:
                api.cerrar_hallazgo(st.session_state.token, h["id"])
                st.success("Cerrado.")
                st.rerun()
            except api.APIError as e:
                st.error(f"❌ {e.detail}")




if st.session_state.token is None:
    pantalla_login()
else:
    with st.sidebar:
        st.markdown(f"**Usuario:** {st.session_state.username}")
        st.markdown(f"**Rol:** {st.session_state.rol}")
        st.markdown(f"**Tenant:** `{st.session_state.tenant_id[:8]}…`")
        if st.button("🔄 Actualizar datos"):
            st.rerun()
        if st.button("Cerrar sesión"):
            _logout()
            st.rerun()

    st.markdown("## 🛡️ SMARTPROMARCO Gobernanza — Dashboard")

    try:
        kpis = api.get_kpis(st.session_state.token, st.session_state.tenant_id)
        pendientes = api.listar_pendientes_hitl(st.session_state.token, st.session_state.tenant_id)
        periodo_actual = datetime.now(timezone.utc).strftime("%Y-%m")
        hallazgos = api.listar_hallazgos(st.session_state.token, st.session_state.tenant_id, periodo_actual)
    except api.APIError as e:
        st.error(f"❌ Error consultando la API: {e.detail}")
        st.stop()

    tab_kpis, tab_pendientes, tab_evidencia, tab_auditor, tab_debate = st.tabs(
        ["📊 KPIs", f"⚠️ Pendientes ({len(pendientes)})", "📄 Evidencia", "🔍 Ciclo de Auditoría", "⚖️ Decisor / Auditor"]
    )

    with tab_kpis:
        seccion_kpis(kpis, pendientes, hallazgos)

    with tab_pendientes:
        seccion_pendientes(pendientes)

    with tab_evidencia:
        evidencias = api.listar_evidencia(st.session_state.token, st.session_state.tenant_id, limit=20)
        for ev in evidencias:
            col1, col2, col3, col4 = st.columns([1, 3, 1, 1])
            col1.markdown(badge_riesgo(ev["riesgo"]))
            col2.markdown(f"`{ev['transaction_id'][:8]}…` — {ev['operacion']}")
            col3.markdown(ev["tipo_loop"])
            if col4.button("QR", key=f"qr_{ev['transaction_id']}"):
                try:
                    png_bytes = api.generar_qr(st.session_state.token, ev["transaction_id"])
                    st.image(io.BytesIO(png_bytes), width=150, caption=ev["transaction_id"])
                except api.APIError as e:
                    st.error(f"❌ {e.detail}")

    with tab_auditor:
        seccion_auditor_interno(st.session_state.tenant_id)

    with tab_debate:
        seccion_debate()
