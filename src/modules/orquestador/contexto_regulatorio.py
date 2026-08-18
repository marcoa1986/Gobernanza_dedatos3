"""
src/modules/orquestador/contexto_regulatorio.py
==================================================
Contexto regulatorio REAL (no ficticio) para que el Decisor y el
Auditor razonen con fundamento cuando la propuesta toca un sector
regulado. Cada bloque se basa en fuentes verificadas — no es una lista
inventada de "buenas prácticas genéricas".

IMPORTANTE — mantenimiento: la regulación cambia. Estos bloques reflejan
el estado verificado a julio 2026. Antes de usarlos en producción para
asesorar una decisión real, contrasta contra la fuente primaria vigente
(DOF, CNBV, EMA, SAT) — este módulo es contexto de apoyo para el agente,
no asesoría legal ni fiscal.

Claves válidas para `sectores`: "comercio_exterior", "banca", "retail",
"auditoria_interna", "certificacion_iso".
"""

from __future__ import annotations

CONTEXTO_COMERCIO_EXTERIOR = """\
COMERCIO EXTERIOR / AGENTES ADUANALES (México — Reforma a la Ley Aduanera,
vigente desde el 1 de enero de 2026, DOF 19 nov 2025):
- Se derogaron las exenciones de responsabilidad del agente aduanal antes
  previstas en el Artículo 54. Ahora agente aduanal e importador comparten
  responsabilidad DIRECTA Y CONJUNTA por la información declarada.
- El agente aduanal debe certificarse cada 3 años para mantener vigente su
  patente — ya no es vitalicia.
- Se crea un Consejo Aduanero con facultad para decidir sobre suspensión o
  cancelación de patentes y autorizaciones.
- Obligación de mantener un expediente electrónico POR CLIENTE, con
  documentación que acredite la materialidad de cada operación — esto es
  exactamente lo que un sistema de evidencia inmutable con trazabilidad
  (como el que audita este Decisor/Auditor) puede sustentar.
- Los sistemas de control de inventarios deben ser automatizados Y
  permanentes, con acceso ininterrumpido de la autoridad durante revisión.
- El agente aduanal debe informar por escrito a la autoridad si una
  operación de comercio exterior contraviene criterios normativos o no
  vinculativos del SAT.
- Autoridad: Agencia Nacional de Aduanas de México (ANAM), bajo el marco
  del Reglamento de la Ley Aduanera reformado en febrero 2026."""

CONTEXTO_BANCA = """\
BANCA (México — Comisión Nacional Bancaria y de Valores, CNBV):
- La CNBV es un órgano desconcentrado de la SHCP con autonomía técnica;
  supervisa capital, liquidez y solvencia de instituciones de crédito, y
  puede sancionar, intervenir gerencialmente o revocar autorizaciones.
- Marzo 2026: la CNBV endureció las Disposiciones de carácter general
  aplicables a instituciones de crédito en materia de capital regulatorio
  y límites de exposición, alineándose con Basilea III — limita reducir
  requerimientos de capital vía modelos internos.
- Julio 2026: reforma a la Circular Única de Bancos (CUB) incorpora la
  biometría facial como método oficial de identificación de clientes;
  exige validación anual de los mecanismos de seguridad biométricos y
  reporte a la CNBV de desviaciones dentro de 20 días hábiles.
- La CNBV y la UIF (Unidad de Inteligencia Financiera) tienen un convenio
  de colaboración activo (marzo 2026) para prevención de lavado de
  dinero — supervisión con enfoque basado en riesgo.
- Implicación directa para un Decisor: cualquier propuesta de arquitectura
  que toque KYC, biometría, o cálculo de capital regulatorio debe poder
  demostrar trazabilidad y evidencia verificable ante la CNBV — no basta
  con "funciona", debe ser auditable."""

CONTEXTO_RETAIL = """\
RETAIL (México — consideraciones de cumplimiento relevantes):
- Normas Oficiales Mexicanas (NOM) de información comercial aplican a
  productos y su etiquetado; el incumplimiento puede derivar en embargo
  bajo la Ley Aduanera reformada (no solo retención) cuando el producto
  proviene de comercio exterior.
- Protección de datos de clientes (retail con e-commerce o programas de
  lealtad) cae bajo la Ley Federal de Protección de Datos Personales en
  Posesión de los Particulares — cualquier sistema que almacene datos de
  clientes debe justificar base legal de tratamiento y mecanismos de
  acceso/cancelación.
- Trazabilidad de inventario y control de mermas es frecuentemente el
  punto de auditoría interna más débil — coincide directamente con lo que
  la tabla Evidencia + Matriz de Trazabilidad de esta plataforma ya
  resuelve para Suministros Industriales."""

CONTEXTO_AUDITORIA_INTERNA = """\
AUDITORÍA INTERNA (ISO 19011 — Directrices para la auditoría de sistemas
de gestión, última revisión ISO 19011:2026):
- Establece principios de auditoría, gestión de programas de auditoría, y
  competencia de los auditores — aplica a auditorías de primera parte
  (internas), segunda parte (a proveedores) y tercera parte (certificación).
- Mantenida por el comité técnico ISO/TC 176.
- Principios clave que el Auditor de este sistema debe respetar: integridad,
  presentación imparcial de hallazgos, debido cuidado profesional,
  confidencialidad, independencia, y enfoque basado en evidencia —
  las conclusiones deben poder trazarse a evidencia verificable, no a
  opinión.
- Aplica directamente a organizaciones certificadas o en proceso de
  certificación bajo ISO 9001, ISO 27001, ISO 42001, entre otras — el
  Auditor de este sistema, al evaluar decisiones de arquitectura o
  negocio, debe operar bajo el mismo estándar de evidencia que un
  auditor humano ISO 19011 exigiría."""

CONTEXTO_CERTIFICACION_ISO = """\
CERTIFICACIÓN ISO EN MÉXICO (EMA — Entidad Mexicana de Acreditación):
- La EMA NO certifica directamente — acredita (evalúa la competencia
  técnica de) a los Organismos de Certificación que sí emiten certificados
  ISO. Opera bajo la norma ISO/IEC 17011:2017.
- Para sistemas de gestión (ISO 9001, ISO 27001, ISO 42001, ISO 45001,
  etc.), la EMA acredita organismos de certificación bajo la norma
  ISO/IEC 17021-1 — esta es la acreditación relevante para el roadmap de
  certificación de SMARTPROMARCO.
- Otras acreditaciones de la EMA (no aplican a sistemas de gestión, pero
  sí a otros servicios del ecosistema de calidad): ISO/IEC 17025
  (laboratorios de ensayo/calibración), ISO 15189 (laboratorios clínicos),
  ISO/IEC 17020 (organismos de inspección), ISO/IEC 17065 (certificación
  de producto), ISO/IEC 17024 (certificación de personal), ISO/IEC 17043
  (proveedores de ensayos de aptitud).
- Implicación práctica: cuando SMARTPROMARCO busque certificarse en
  ISO 27001 o ISO 42001, debe contratar a un Organismo de Certificación
  acreditado por la EMA bajo ISO/IEC 17021-1 — verificable en el Catálogo
  de Acreditados de www.ema.org.mx, filtrando por Alcance = Sistemas."""

_REGISTRO: dict[str, str] = {
    "comercio_exterior": CONTEXTO_COMERCIO_EXTERIOR,
    "banca": CONTEXTO_BANCA,
    "retail": CONTEXTO_RETAIL,
    "auditoria_interna": CONTEXTO_AUDITORIA_INTERNA,
    "certificacion_iso": CONTEXTO_CERTIFICACION_ISO,
}

SECTORES_DISPONIBLES = list(_REGISTRO.keys())


def construir_contexto_regulatorio(sectores: list[str]) -> str:
    """
    Concatena los bloques de contexto real para los sectores solicitados.
    Sectores no reconocidos se ignoran silenciosamente (no rompen el flujo)
    pero se registran para detectarlos en revisión de código.
    """
    bloques = [_REGISTRO[s] for s in sectores if s in _REGISTRO]
    desconocidos = [s for s in sectores if s not in _REGISTRO]
    if desconocidos:
        import logging
        logging.getLogger(__name__).warning(
            "Sectores no reconocidos en contexto_regulatorio: %s (disponibles: %s)",
            desconocidos, SECTORES_DISPONIBLES,
        )
    return "\n\n".join(bloques) if bloques else ""
