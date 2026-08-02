# 09 · Integración con clientes

Una vez el servidor MCP del capítulo 08 funciona por stdio, conectarlo a un cliente es cuestión de decirle **cómo arrancar el proceso** — cada cliente guarda esa información en su propio fichero de configuración, con un formato ligeramente distinto. Esta es la única parte del sistema que varía por cliente; el servidor en sí no cambia una línea.

> Los formatos de configuración de estas CLIs evolucionan con cierta frecuencia. Lo de aquí está verificado contra la documentación oficial vigente a fecha de esta guía (2026); si algo no funciona, revisa la documentación oficial de cada herramienta antes de asumir que el problema está en tu servidor.

## 1. Claude Code

Claude Code admite tres ámbitos de configuración MCP:

| Ámbito | Dónde vive | Cuándo usarlo |
|---|---|---|
| **Local** (por defecto) | `~/.claude.json`, bajo la entrada del proyecto actual | Configuración personal, no compartida |
| **Project** | `.mcp.json` en la raíz del proyecto | Se versiona en git — todo el equipo obtiene el mismo servidor automáticamente |
| **User** | `~/.claude.json`, global | Disponible en todos tus proyectos |

Vía CLI (recomendado — separa las opciones de Claude Code de los argumentos del propio servidor con `--`):

```bash
claude mcp add --env VOYAGE_API_KEY=tu_clave --transport stdio codehex \
  --scope project \
  -- codehex mcp serve --project backend-java
```

O editando `.mcp.json` directamente:

```json
{
  "mcpServers": {
    "codehex": {
      "type": "stdio",
      "command": "codehex",
      "args": ["mcp", "serve", "--project", "backend-java"],
      "env": {
        "VOYAGE_API_KEY": "${VOYAGE_API_KEY}"
      }
    }
  }
}
```

Si usas `--scope project` (fichero `.mcp.json` versionado), Claude Code pedirá aprobación la primera vez que lo detecte en un repo — es una medida de seguridad intencionada, no un fallo. Gestión posterior: `claude mcp list`, `claude mcp get codehex`, `claude mcp remove codehex`.

## 2. Codex CLI (OpenAI)

Codex CLI guarda la configuración MCP en TOML, en `~/.codex/config.toml` (global) o `.codex/config.toml` a nivel de proyecto (solo para proyectos marcados como de confianza):

```toml
[mcp_servers.codehex]
command = "codehex"
args = ["mcp", "serve", "--project", "backend-java"]
startup_timeout_sec = 10

[mcp_servers.codehex.env]
VOYAGE_API_KEY = "tu_clave"
```

O vía CLI:

```bash
codex mcp add codehex --env VOYAGE_API_KEY=tu_clave -- codehex mcp serve --project backend-java
```

Gestión: `codex mcp list` para ver los servidores configurados.

## 3. GitHub Copilot CLI

Copilot CLI guarda su configuración en `~/.copilot/mcp-config.json` (la ruta se puede redirigir con la variable de entorno `COPILOT_HOME`), y también descubre configuración a nivel de proyecto en `.github/mcp.json`:

```json
{
  "mcpServers": {
    "codehex": {
      "type": "local",
      "command": "codehex",
      "args": ["mcp", "serve", "--project", "backend-java"],
      "env": {
        "VOYAGE_API_KEY": "tu_clave"
      },
      "tools": ["*"]
    }
  }
}
```

O vía CLI:

```bash
copilot mcp add codehex --env VOYAGE_API_KEY=tu_clave -- codehex mcp serve --project backend-java
```

El campo `"tools": ["*"]` habilita todas las tools del servidor; puedes restringir a un subconjunto (`["search_code", "get_source"]`) si por ejemplo quieres que un cliente concreto no pueda disparar `reindex`.

## 4. Comparación rápida

| | Claude Code | Codex CLI | Copilot CLI |
|---|---|---|---|
| Fichero | `.mcp.json` / `~/.claude.json` | `config.toml` | `mcp-config.json` |
| Formato | JSON | TOML | JSON |
| Clave del servidor | `mcpServers.<nombre>` | `[mcp_servers.<nombre>]` | `mcpServers.<nombre>` |
| Config. por proyecto versionable | Sí (`.mcp.json`) | Sí (`.codex/config.toml`, solo proyectos de confianza) | Sí (`.github/mcp.json`) |
| Comando de alta | `claude mcp add` | `codex mcp add` | `copilot mcp add` |

La estructura conceptual es la misma en los tres (nombre → comando + args + variables de entorno) porque todos hablan el mismo protocolo subyacente; solo cambia el envoltorio.

## 5. Comando de conveniencia: generar la configuración automáticamente

Para no obligar a nadie a memorizar tres formatos distintos, `codehex` puede incluir un comando que genere (o inserte) el bloque de configuración correcto para el cliente elegido:

```bash
codehex mcp install --client claude   # escribe/actualiza .mcp.json
codehex mcp install --client codex    # escribe/actualiza .codex/config.toml
codehex mcp install --client copilot  # escribe/actualiza ~/.copilot/mcp-config.json
```

Implementación: un pequeño adaptador por cliente (`ClaudeConfigWriter`, `CodexConfigWriter`, `CopilotConfigWriter`) que sabe leer el fichero existente (si lo hay), fusionar la entrada `codehex` sin pisar otros servidores ya configurados, y escribirlo de vuelta en el formato correspondiente (JSON o TOML). Añadir un cliente futuro es, de nuevo, un adaptador nuevo — el patrón se repite en todo el proyecto por diseño (capítulo 03).

## 6. Solución de problemas comunes

| Síntoma | Causa probable |
|---|---|
| El cliente no lista ninguna tool | El comando configurado no arranca (ruta relativa en vez de absoluta, o el paquete no está instalado en el `PATH` que ve el cliente) — prueba a ejecutar el mismo comando a mano en una terminal |
| El servidor arranca pero se cierra inmediatamente | Algo se escribió en stdout que no es JSON-RPC válido (p.ej. un `print()` de depuración) — en stdio, stdout es **solo** el canal del protocolo; cualquier log debe ir a stderr |
| `reindex` tarda mucho la primera vez pero es rápido después | Comportamiento esperado — primera vez es indexado completo, las siguientes son incrementales (capítulo 07) |
| El cliente pide aprobación cada vez | Normal para servidores de ámbito proyecto (`.mcp.json`, `.codex/config.toml` de confianza) — es una medida de seguridad del cliente, no un fallo del servidor |

## Ideas reutilizables de los proyectos existentes

- **De `kairosai`**: la "materialización" de configuración (`install.py`, que escribe `.claude/` + `.mcp.json` a partir de un modelo interno) es exactamente el patrón que la sección 5 propone generalizar a tres clientes en vez de uno.

## Siguiente paso

[10 · GitHub Actions](10-github-actions.md): cómo hacer que el índice se mantenga al día solo, sin que nadie tenga que acordarse de ejecutar `reindex`.
