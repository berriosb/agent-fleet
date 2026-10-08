---
name: session-handoff
description: "Cierre de sesión y traspaso estructurado entre agentes. Vuelca el estado a working-context.md y notas diarias antes de compactación de contexto, cambio de agente o fin de sesión."
version: 1.0.0
author: Bastián Berrios
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [fleet, handoff, session, context, memoria, continuidad]
---

# session-handoff

Disciplina de cierre de sesión y traspaso de contexto entre agentes.

El contexto de la ventana de chat es volátil: se compacta, se reinicia o se pierde al cambiar de agente (de Hermes a Claude Code, Antigravity agy, Codex, etc.). Esta skill garantiza que el próximo agente o sesión arranque con contexto completo y sin reconstruir la historia a ciegas.

## Cuándo usar esta skill

Cargar y ejecutar esta skill **siempre** antes de:
- Declarar una sesión terminada o decir "listo" / "done".
- Ejecutar una compactación de contexto (`/compact` o advertencia de contexto lleno).
- Pausar una tarea a medio implementar.
- Traspasar la tarea a otro agente o subagente.

## Regla de hierro

```
NINGÚN CIERRE DE SESIÓN SIN VOLCADO DE ESTADO EN DISCO
```

Si no quedó escrito en `working-context.md` o en las memorias del proyecto, el trabajo no ocurrió para el siguiente agente.

## Estructura de `working-context.md`

Cuando una tarea queda en curso o requiere continuidad, genera o actualiza `working-context.md` en la raíz del repo (o en el directorio de trabajo del proyecto) con esta estructura:

```markdown
# Working Context — <Nombre del Proyecto o Tarea>

Última actualización: YYYY-MM-DD HH:MM (por <Agente/Modelo>)
Rama: <nombre-de-rama> | HEAD: <hash-corto>

## 1. Objetivo activo
<Qué se estaba construyendo o resolviendo en esta sesión.>

## 2. Qué cambió
- `<ruta/al/archivo>`: <qué se modificó o agregó y por qué>
- `<ruta/al/archivo>`: <qué se modificó o agregó y por qué>

## 3. Evidencia de verificación
<Comandos exactos ejecutados y salida observada.>
```bash
# Ejemplo:
pytest tests/unit/test_auth.py
# Salida: 12 passed in 0.45s (exit 0)
```

## 4. Qué falta / Decisiones abiertas
- [ ] <Tarea pendiente concreta>
- [ ] <Decisión pendiente de confirmación con el usuario>

## 5. Próxima acción inmediata (Next Step)
<El comando o paso exacto que el próximo agente debe ejecutar primero al retomar.>
```

## Protocolo de Handoff entre Agentes

1. **Revisar estado git:**
   ```bash
   git status --short
   git log -1 --oneline
   ```
   Si hay cambios sin commitear, documenta explícitamente por qué están pendientes en la sección "Qué falta".

2. **Ejecutar verificación de cierre:**
   Corre los tests o linters relevantes y anota la salida en la evidencia. No reportes "todo pasa" sin el comando reciente.

3. **Registrar lecciones durables:**
   - Si se tomó una decisión de arquitectura → registra en `docs/adr/` o registro de decisiones.
   - Si se descubrió una lección técnica o trampa del codebase → usa la memoria persistente (`mem_save`) o anota en lecciones aprendidas.

4. **Entregable visible al usuario:**
   Tu último mensaje antes de cerrar debe resumir en tres puntos:
   - **Qué cambió:** lista corta de cambios.
   - **Qué se verificó:** evidencia con comando y resultado.
   - **Qué falta / siguiente paso:** acción con la que se retoma.
