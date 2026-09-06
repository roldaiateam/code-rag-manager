"""CLI `crm`: fachada delgada sobre los casos de uso — parsea argumentos,
construye vía composition_root, ejecuta y formatea la salida. Sin lógica de
negocio."""

from __future__ import annotations

import os
import subprocess

import typer

from coderagmanager.adapters.formatting import (
    format_chunks,
    format_included,
    format_search_results,
    format_stats,
)
from coderagmanager.domain.errors import ProjectNotFoundError
from coderagmanager.domain.models import SearchQuery

GROUP_HELP_NOTE = (
    "Nota: este --help es de nivel de grupo y solo lista subcomandos. Para ver "
    "las opciones de uno concreto, baja un nivel más: 'crm <subcomando> --help'."
)

app = typer.Typer(
    name="crm",
    no_args_is_help=True,
    add_completion=False,
    epilog=(
        "Nota: cada grupo (project, index, mcp, config) tiene su propio --help, "
        "y cada subcomando el suyo. Para ver todas las opciones de un comando, "
        "baja hasta el nivel hoja, p.ej. 'crm project add --help'."
    ),
)
project_app = typer.Typer(no_args_is_help=True, epilog=GROUP_HELP_NOTE)
index_app = typer.Typer(epilog=GROUP_HELP_NOTE)
mcp_app = typer.Typer(no_args_is_help=True, epilog=GROUP_HELP_NOTE)
config_app = typer.Typer(no_args_is_help=True, epilog=GROUP_HELP_NOTE)
app.add_typer(project_app, name="project", help="Gestión del registro de proyectos")
app.add_typer(index_app, name="index", help="Indexado (siempre completo) y sincronización")
app.add_typer(mcp_app, name="mcp", help="Servidor MCP e integración con clientes")
app.add_typer(config_app, name="config", help="Configuración global")

PROJECT_OPTION = typer.Option(..., "--project", help="Id del proyecto registrado")


def _fail(message: str) -> None:
    typer.secho(f"Error: {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(code=1)


def _use_cases(project: str) -> dict:
    from coderagmanager.composition_root import build_use_cases

    try:
        return build_use_cases(project)
    except ProjectNotFoundError as e:
        _fail(f"{e} Usa 'crm project list' para ver los disponibles.")


def _run_index(project: str) -> None:
    from coderagmanager.application.manifest import read_manifest

    uc = _use_cases(project)
    typer.echo(f"Indexando '{project}' (reconstrucción completa)...")
    stats = uc["index_project"].execute()
    manifest = read_manifest(uc["project"].root_path)
    uc["registry"].mark_indexed(
        project, commit=manifest.last_indexed_commit if manifest else None
    )
    typer.echo(f"Indexado: {stats.total_chunks} chunks, {stats.total_edges} aristas")
    extra_line = format_included(stats.included)
    if extra_line:
        typer.echo(extra_line)


@app.command()
def init() -> None:
    """Crea ~/.crm/ y el registro de proyectos si no existen."""
    from coderagmanager.composition_root import build_registry

    registry = build_registry()
    registry.set_default(
        "embedding_provider", registry.defaults().get("embedding_provider", "local")
    )
    typer.echo("Registro global inicializado en ~/.crm/projects.yaml")


@project_app.command("add")
def project_add(
    name: str,
    path: str,
    language: list[str] = typer.Option(
        [], "--language", "-l", help="Lenguajes del proyecto (informativo)"
    ),
    include: list[str] = typer.Option(
        [],
        "--include",
        help="Glob (relativo a la raíz) a indexar aunque esté gitignorado; repetible",
    ),
    no_auto_include: bool = typer.Option(
        False,
        "--no-auto-include",
        help="No detectar código generado (target/generated-sources, build/generated)",
    ),
    no_role_classification: bool = typer.Option(
        False,
        "--no-role-classification",
        help="No clasificar chunks por capa/rol arquitectónico (domain/controller/entity...)",
    ),
) -> None:
    """Registra un proyecto en el registro global (re-registrar un nombre existente
    sobreescribe su configuración)."""
    from coderagmanager.composition_root import build_registry_use_cases

    try:
        project = build_registry_use_cases()["register_project"].execute(
            name,
            path,
            list(language),
            extra_index_paths=list(include),
            auto_include=not no_auto_include,
            role_classification=not no_role_classification,
        )
    except ValueError as e:
        _fail(str(e))
    typer.echo(f"Proyecto '{project.id}' registrado en {project.root_path}")
    if project.extra_index_paths:
        typer.echo(f"  incluye además: {', '.join(project.extra_index_paths)}")
    if not project.auto_include:
        typer.echo("  auto-detección de código generado: desactivada")
    if not project.role_classification:
        typer.echo("  clasificación de capa/rol: desactivada")


@project_app.command("list")
def project_list() -> None:
    """Lista los proyectos registrados y su estado de indexado."""
    from coderagmanager.composition_root import build_registry_use_cases

    projects = build_registry_use_cases()["list_projects"].execute()
    if not projects:
        typer.echo("No hay proyectos registrados. Usa 'crm project add <nombre> <ruta>'.")
        return
    for p in projects:
        indexed = p.last_indexed_at or "nunca indexado"
        typer.echo(f"{p.id:<20} {p.root_path}  ({indexed})")


@project_app.command("remove")
def project_remove(name: str) -> None:
    """Elimina un proyecto del registro (no borra su índice .crm/)."""
    from coderagmanager.composition_root import build_registry_use_cases

    try:
        build_registry_use_cases()["remove_project"].execute(name)
    except ProjectNotFoundError as e:
        _fail(str(e))
    typer.echo(f"Proyecto '{name}' eliminado del registro.")


@index_app.callback(invoke_without_command=True)
def index_main(
    ctx: typer.Context,
    project: str = typer.Option(None, "--project", help="Id del proyecto registrado"),
) -> None:
    """`crm index --project <id>`: indexado completo (drop-and-rebuild)."""
    if ctx.invoked_subcommand is not None:
        return
    if project is None:
        _fail("falta --project. Uso: crm index --project <id>")
    _run_index(project)


@index_app.command("pull")
def index_pull(project: str = PROJECT_OPTION) -> None:
    """Trae el índice publicado por CI (rama crm-index) al árbol de trabajo local."""
    from coderagmanager.composition_root import build_registry

    try:
        root = build_registry().get(project).root_path
    except ProjectNotFoundError as e:
        _fail(str(e))
    fetch = subprocess.run(
        ["git", "-C", root, "fetch", "origin", "crm-index"],
        capture_output=True, text=True,
    )
    if fetch.returncode != 0:
        _fail(
            "no se pudo hacer fetch de la rama 'crm-index' "
            f"(¿existe en el remoto? ¿es un repo git?):\n{fetch.stderr.strip()}"
        )
    restore = subprocess.run(
        ["git", "-C", root, "restore", "--source=FETCH_HEAD", "--worktree", "--", ".crm"],
        capture_output=True, text=True,
    )
    if restore.returncode != 0:
        _fail(f"la rama crm-index no contiene .crm/:\n{restore.stderr.strip()}")
    typer.echo(f"Índice actualizado desde origin/crm-index en {os.path.join(root, '.crm')}")


@app.command()
def reindex(project: str = PROJECT_OPTION) -> None:
    """Alias de 'crm index': el reindexado es siempre completo."""
    _run_index(project)


@app.command()
def search(
    query: str,
    project: str = PROJECT_OPTION,
    top_k: int = typer.Option(10, "--top-k"),
    language: str = typer.Option(None, "--language"),
    kind: str = typer.Option(None, "--kind"),
    role: str = typer.Option(
        None,
        "--role",
        help="Filtrar por rol arquitectónico (controller, entity, use_case, adapter, mapper, config, utility)",
    ),
    layer: str = typer.Option(
        None,
        "--layer",
        help="Filtrar por capa arquitectónica (domain, application, infrastructure...)",
    ),
) -> None:
    """Búsqueda híbrida de depuración, sin pasar por MCP. Filtros opcionales:
    language, kind, role, layer."""
    uc = _use_cases(project)
    outcome = uc["search_code"].execute(
        SearchQuery(
            text=query, top_k=top_k, language=language, kind=kind, role=role, layer=layer
        )
    )
    typer.echo(format_search_results(outcome.results, outcome.low_confidence))


@app.command()
def stats(project: str = PROJECT_OPTION) -> None:
    """Equivalente CLI de la tool MCP get_index_stats."""
    uc = _use_cases(project)
    typer.echo(format_stats(uc["get_index_stats"].execute()))


@app.command()
def chunks(
    project: str = PROJECT_OPTION,
    language: str = typer.Option(None, "--language"),
    kind: str = typer.Option(None, "--kind"),
    role: str = typer.Option(
        None,
        "--role",
        help="Filtrar por rol arquitectónico (controller, entity, use_case, adapter, mapper, config, utility)",
    ),
    layer: str = typer.Option(
        None,
        "--layer",
        help="Filtrar por capa arquitectónica (domain, application, infrastructure...)",
    ),
) -> None:
    """Inventario de chunks indexados (equivalente CLI de list_chunks). Filtros
    opcionales: language, kind, role, layer."""
    uc = _use_cases(project)
    typer.echo(format_chunks(uc["list_chunks"].execute(language, kind, role, layer)))


@mcp_app.command("serve")
def mcp_serve(project: str = PROJECT_OPTION) -> None:
    """Arranca el servidor MCP por stdio, atado a un único proyecto."""
    from coderagmanager.adapters.mcp.server import serve
    from coderagmanager.composition_root import build_registry

    try:
        build_registry().get(project)  # falla pronto si no está registrado
    except ProjectNotFoundError as e:
        _fail(str(e))
    serve(project)


@mcp_app.command("install")
def mcp_install(
    client: str = typer.Option(..., "--client", help="claude | codex | copilot"),
    project: str = PROJECT_OPTION,
    skip_claude_md: bool = typer.Option(
        False,
        "--skip-claude-md",
        help="No añadir el bloque de adopción al CLAUDE.md del repo (solo cliente claude)",
    ),
) -> None:
    """Genera/actualiza la configuración MCP del cliente elegido para este proyecto.

    Con --client claude añade además un bloque (idempotente) al CLAUDE.md del
    repo indicando al agente que prefiera las tools del índice para explorar código."""
    from coderagmanager.adapters.mcp.client_configs.writers import (
        build_writer,
        resolve_crm_executable,
    )
    from coderagmanager.composition_root import build_registry

    try:
        registered = build_registry().get(project)
        writer = build_writer(client, registered.root_path)
    except (ProjectNotFoundError, ValueError) as e:
        _fail(str(e))
    path = writer.install(project)
    typer.echo(f"Configuración MCP '{'crm-' + project}' escrita en {path}")
    if not os.path.isabs(resolve_crm_executable()):
        typer.secho(
            "Aviso: no se pudo resolver una ruta absoluta para 'crm' (ni en el "
            "directorio de scripts del intérprete ni en el PATH); se ha escrito "
            "el comando 'crm' a secas. Si el cliente MCP no hereda el PATH de "
            "este entorno (p.ej. GitHub Copilot CLI), el servidor no arrancará: "
            "reemplaza manualmente 'command' en la config por la salida de "
            "'which crm'.",
            fg=typer.colors.YELLOW,
            err=True,
        )
    if client == "claude" and not skip_claude_md:
        from coderagmanager.adapters.mcp.client_configs.claude_md import (
            upsert_claude_md_block,
        )

        md_path = upsert_claude_md_block(registered.root_path, project)
        typer.echo(f"Bloque de adopción actualizado en {md_path}")


@config_app.command("show")
def config_show() -> None:
    """Muestra la configuración global efectiva."""
    from coderagmanager.composition_root import build_registry

    for key, value in sorted(build_registry().defaults().items()):
        typer.echo(f"{key} = {value}")


@config_app.command("set")
def config_set(key: str, value: str) -> None:
    """Fija un valor de configuración global (p.ej. embedding.provider local)."""
    from coderagmanager.composition_root import build_registry

    build_registry().set_default(key.replace(".", "_"), value)
    typer.echo(f"{key} = {value}")


if __name__ == "__main__":
    app()
