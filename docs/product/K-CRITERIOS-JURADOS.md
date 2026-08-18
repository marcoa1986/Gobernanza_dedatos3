# K. Criterios de Aceptación para Jurados

A diferencia de los `AC-` técnicos (verificados por pytest), estos son
**demostrables en vivo** — algo que un jurado puede ver pasar frente a
ellos, no una aserción de código. Cada uno cita el test real que ya lo
respalda — nada aquí es aspiracional.

| ID | Criterio demostrable | Respaldado por |
|---|---|---|
| **DEMO-001** | Un DELETE real, sin importar el riesgo, siempre pausa para decisión humana — el jurado puede intentar forzarlo y no se salta | `TC-AUD-006` |
| **DEMO-002** | Al pedir "muéstrame la evidencia", el sistema responde con un hash SHA-256 verificable, no una promesa de palabra | `TC-AUD-004` |
| **DEMO-003** | Si se manipula un dato después de generado, la verificación de integridad lo detecta y lo dice explícitamente | `TC-AUD-005` |
| **DEMO-004** | Un QR generado en vivo, escaneado con el celular del jurado, resuelve a la evidencia correcta sin apps adicionales | `TC-QR-001`, `TC-QR-007` |
| **DEMO-005** | Si el Decisor y el Auditor no llegan a acuerdo en 3 intentos, el sistema escala a un humano en vez de forzar una decisión | `TC-DEB-002` |
| **DEMO-006** | El Resumen Ejecutivo del Copiloto nunca cita evidencia que no exista realmente — filtrado en código, no solo prometido en el prompt | `TC-COP-002` |
| **DEMO-007** | Los datos mostrados son de una corrida real (164 transacciones de Suministros Industriales), no cifras de ejemplo | `scripts/seed_catalogo.py` |
| **DEMO-008** | Cada uno de los 5 roles ve una experiencia distinta y relevante a su función al iniciar sesión — no el mismo panel para todos | Ver `B-UX-POR-ROLES.md` |
| **DEMO-009** | El Supervisor puede actuar sobre cualquier pendiente del tenant, pero no puede administrar usuarios ni configurar el tenant | `TC-SEC-011`, `TC-SEC-012` |

**Estado al momento de escribir esto:** 56/56 pruebas automatizadas en
verde, 25 endpoints documentados en `/docs`. Cualquiera de estos 9
criterios se puede reproducir corriendo `pytest tests/ -v` o levantando
el stack con `docker compose up -d`.
