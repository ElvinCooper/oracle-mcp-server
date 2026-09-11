# Propósito y Beneficios

Documento dirigido a quien pregunte sobre el proyecto: devs, DBAs, product
owners o managers. Explica qué es, qué problema resuelve y qué potencial tiene
al combinar Oracle con un agente de IA.

---

## 1. Elevator pitch (resumen ejecutivo)

> Este proyecto convierte tu base de datos **Oracle 11g** en una herramienta que
> el agente de IA puede consultar de forma segura y directa. En vez de que
> escribas SQL a mano, pegues resultados y pases por varias herramientas, le
> preguntas al agente en lenguaje natural y él explora, consulta y analiza la
> base por ti, con controles de seguridad que evitan escrituras accidentales.

## 2. Qué es

Un servidor MCP (Model Context Protocol) que conecta un agente de IA con una o
varias bases de datos Oracle 11g. El protocolo MCP es un estándar: funciona con
cualquier cliente compatible (opencode, Claude Code, Cursor, Codex, etc.).

Las capacidades que expone al agente:

| Capacidad | Qué hace |
|---|---|
| `list_tables` | Descubre las tablas de un schema |
| `describe_table` | Ve columnas, tipos de dato, nulabilidad |
| `run_query` | Ejecuta consultas de solo lectura |
| `execute_statement` | Ejecuta escritura/DDL (bloqueado por defecto) |
| `list_connections` | Enumera las bases a las que tiene acceso |

Con estas tools, el agente no "adivina" la base de datos: la ve y la consulta
como parte de su razonamiento.

## 3. El problema que resuelve

Hoy, las tareas de consulta y administración de Oracle suelen hacerse a mano:

- Abrir SQL Developer / SQL*Plus, escribir la consulta, copiar el resultado.
- Ir probando queries una y otra vez porque no recordabas el nombre exacto de
  una columna o tabla.
- Alternar entre varias bases (producción, pruebas, desarrollo) con conexiones
  distintas en cada herramienta.
- El miedo a escribir un `UPDATE` o `DELETE` mal construido contra datos reales.

Este proyecto ataca cada uno de esos puntos: el agente explora el schema,
construye las sentencias con nombres correctos, consulta varias bases en la
misma sesión y, por diseño, empieza en modo solo lectura.

## 4. Beneficios clave

- **Menos alucinaciones en el SQL:** antes de responder, el agente puede llamar
  a `list_tables` y `describe_table`. Genera consultas con nombres reales de
  tablas y columnas, no inventados.
- **Análisis y reportes en conversación:** consulta → interpreta → refina. En
  pasos, como lo haría un analista, sin moverte de la conversación.
- **Autoservicio para no-DBAs:** quien no domina SQL puede preguntar "¿cuántos
  clientes están atrasados?" y recibir la respuesta, no una instrucción.
- **Multi-conexión en una sola sesión:** producción, desarrollo y pruebas (u
  otras bases) disponibles en la misma llamada, con una sola config.
- **Menos copy-paste:** los resultados llegan estructurados al contexto del
  agente, listos para ser analizados, resumidos o convertidos en tablas/gráficos.
- **Delegación con control:** puedes soltar tareas repetitivas al agente sabiendo
  que las consultas son de solo lectura y la escritura exige doble confirmación.

## 5. Casos de uso reales (tareas DBA asistidas)

- **Descubrimiento de esquema:** "lista las tablas del schema VENTAS" o "¿qué
  columnas tiene la tabla FACTURAS?".
- **Investigación de datos:** ante un incidente, "¿hay pedidos duplicados hoy?"
  — el agente explora y construye la query correcta.
- **Generación y revisión de scripts:** el agente escribe el `UPDATE`/`DDL` que
  necesitas y, tras revisarlo tú, se ejecuta con confirmación explícita.
- **Comparación entre entornos:** mismas consultas contra dev y producción para
  detectar diferencias de datos o esquema.
- **Documentación:** describir tablas del negocio a partir de metadatos reales.
- **Consultas puntuales para el negocio:** responder con datos reales y el
  detalle del SQL usado, de forma auditable en la misma conversación.

## 6. Seguridad y gobernanza

Puntos de diseño que permiten delegar en un agente sin perder el control:

- **Solo lectura por defecto:** `run_query` solo acepta `SELECT`/`WITH` y
  rechaza múltiples sentencias separadas por `;`.
- **Escritura con doble seguro:** `execute_statement` exige
  `ALLOW_WRITE=true` en el entorno **y** `confirm=true` en la llamada. Nada de
  escrituras accidentales.
- **Límite de filas:** cada conexión limita las filas devueltas, protegiendo
  tanto el contexto del modelo como al servidor de consultas descontroladas.
- **Credenciales fuera del código:** usuario y contraseña viven en variables de
  entorno o en `.env` (ignorado por git), nunca hardcodeadas.
- **Pooling con timeout:** conexiones reutilizables y con timeout, sin abrir y
  cerrar sesiones de base constantemente.

## 7. Potencial y hoja de ruta

El proyecto ya resuelve la capa base (descubrir y consultar). Su potencial
crece con tools orientadas al día a día del DBA:

- Paginación real (cursor/offset) para recorrer resultados grandes en varias
  llamadas.
- Acotar escrituras con `ALLOWED_TABLES` (solo tablas permitidas) para
  entornos compartidos.
- Tools de operación: `EXPLAIN PLAN`, monitoreo de sesiones/locks, estadísticas
  de tablas, tamaño de segmentos, etc.
- Auditoría de las acciones que el agente ejecuta contra la base.

## 8. Resumen beneficio → impacto

| Beneficio | Impacto |
|---|---|
| El agente descubre el schema antes de escribir SQL | Menos errores y sentencias correctas a la primera |
| Consultas y reportes en lenguaje natural | Menos dependencia de SQL manual y copy-paste |
| Múltiples bases en una sesión | Comparación dev/prod/pruebas sin cambiar de herramienta |
| Solo lectura por defecto + doble confirmación para escritura | Se puede delegar en el agente sin riesgo |
| Límite de filas y pooling | Rendimiento y contexto del modelo protegidos |
| Estándar MCP | Funciona con cualquier cliente de IA actual |
