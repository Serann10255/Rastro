# CLAUDE.md — Reglas del proyecto Rastro

Estas reglas son obligatorias para cualquier trabajo que se haga en este repositorio.

---

## 1. Toda la documentación va en `documentacion/`

Cualquier documento, nota, diagrama, especificación, registro de cambios o guía que
se genere **debe** guardarse dentro de la carpeta `documentacion/`, nunca sueltos en
la raíz del proyecto ni mezclados con el código.

### Organización por subcarpetas

La documentación se organiza en subcarpetas **según el tipo de trabajo realizado**.
Si la subcarpeta adecuada no existe, se crea:

```
documentacion/
├── arquitectura/        # Diseño general, diagramas, estructura del sistema
├── modulos/             # Un subdirectorio por módulo (ver abajo)
│   └── <nombre-modulo>/
├── base-de-datos/       # Esquemas, modelos, migraciones, diccionario de datos
├── api/                 # Endpoints, contratos, ejemplos de request/response
├── guias/               # Instalación, configuración, uso, onboarding
├── decisiones/          # Decisiones técnicas y su justificación (ADR)
├── pruebas/             # Planes de prueba, casos, resultados
├── despliegue/          # Entornos, pipelines, pasos de publicación
└── cambios/             # Bitácora de cambios por fecha
```

### Reglas de nombres

- Archivos y carpetas en **kebab-case** y sin tildes: `registro-usuarios.md`.
- Formato **Markdown** (`.md`) por defecto.
- Fechas en formato ISO: `2026-09-10`.
- Los recursos (imágenes, capturas, diagramas) van en una carpeta `assets/`
  dentro de la subcarpeta que los usa.

### Qué documentar de cada módulo

Al crear o modificar un módulo, `documentacion/modulos/<nombre-modulo>/` debe
contener al menos:

- `README.md` — qué hace el módulo, para qué sirve y cómo se usa.
- Dependencias y su relación con otros módulos.
- Decisiones tomadas y alternativas descartadas.
- Comportamiento responsive: breakpoints usados y cómo cambia el layout.

---

## 2. Todo módulo debe ser responsive

Ningún módulo con interfaz se considera terminado si no funciona correctamente en
móvil, tablet y escritorio.

### Enfoque

- **Mobile-first**: se escriben primero los estilos para pantalla pequeña y se
  amplía hacia arriba con `min-width`.
- Anchos **fluidos** (`%`, `rem`, `fr`, `clamp()`, `min()`, `max()`).
  Prohibidos los anchos fijos en píxeles para contenedores de layout.
- Layout con **Flexbox** o **CSS Grid**, nunca con posicionamiento absoluto
  para estructurar la página.

### Breakpoints estándar del proyecto

| Nombre  | Ancho mínimo | Objetivo   |
|---------|--------------|------------|
| `sm`    | 640px        | Móvil grande |
| `md`    | 768px        | Tablet     |
| `lg`    | 1024px       | Escritorio |
| `xl`    | 1280px       | Pantalla amplia |

### Comprobaciones mínimas antes de dar por hecho un módulo

- Se ve bien y es usable a **360px** de ancho.
- **No hay scroll horizontal** en el `body` en ninguna resolución.
- Tablas y bloques anchos scrollean dentro de su propio contenedor
  (`overflow-x: auto`), no en la página.
- Imágenes con `max-width: 100%`.
- Áreas táctiles de al menos **44×44px**.
- El texto no se desborda ni se corta; se usa `word-break`/`overflow-wrap`
  donde haga falta.
- Menús y navegación tienen su versión colapsada en móvil.

---

## 3. Flujo de trabajo

1. Antes de escribir código, revisar si ya existe documentación del módulo
   en `documentacion/modulos/`.
2. Al terminar un cambio, actualizar la documentación correspondiente en la
   misma entrega. Código sin documentar se considera incompleto.
3. Registrar cambios relevantes en `documentacion/cambios/`.
