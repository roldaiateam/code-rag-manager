"""Servidor MCP de CodeRagManager: un servidor por proyecto.

El project_id se fija una vez al arrancar el proceso (--project); las tools
no lo exponen. En stdio, stdout es SOLO el canal JSON-RPC — cualquier log va
a stderr.
"""

from __future__ import annotations

import argparse

try:  # SDK MCP >= 2.0
    from mcp.server.mcpserver import MCPServer
except ImportError:  # SDK MCP 1.x (FastMCP, misma API de decoradores)
    from mcp.server.fastmcp import FastMCP as MCPServer

from coderagmanager.adapters.formatting import (
    format_chain,
    format_chunks,
    format_search_results,
    format_stats,
)
from coderagmanager.domain.models import SearchQuery


def build_server(project_id: str, registry_path: str | None = None) -> MCPServer:
    from coderagmanager.composition_root import build_use_cases

    uc = build_use_cases(project_id, registry_path=registry_path)
    mcp = MCPServer(f"crm-{project_id}")

    @mcp.tool()
    def search_code(
        query: str,
        top_k: int = 10,
        language: str | None = None,
        kind: str | None = None,
    ) -> str:
        """Busca código relevante por significado y por coincidencia léxica en ESTE proyecto.

        Úsalo como PRIMER paso al explorar el código, antes de leer ficheros
        directamente. Acepta lenguaje natural ("dónde se valida el email") o
        nombres de símbolo. Filtros opcionales: language ("python",
        "javascript", "java", "text") y kind ("function", "class", "method"...).
        """
        results = uc["search_code"].execute(
            SearchQuery(text=query, top_k=top_k, language=language, kind=kind)
        )
        return format_search_results(results)

    @mcp.tool()
    def get_dependency_chain(
        symbol: str, max_depth: int = 3, direction: str = "both"
    ) -> str:
        """Recorre el grafo de dependencias desde `symbol` (qué implementa, qué
        le llama, qué extiende...). direction: "out" (de quién depende),
        "in" (quién depende de él) o "both". NO sirve para búsqueda por
        significado — para eso usa search_code."""
        return format_chain(
            uc["get_dependency_chain"].execute(symbol, max_depth, direction)
        )

    @mcp.tool()
    def get_source(
        symbol: str | None = None,
        file_path: str | None = None,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> str:
        """Lee el código fuente real de un chunk indexado. Usar DESPUÉS de
        search_code o get_dependency_chain. Indica 'symbol' o 'file_path'
        (con rango de líneas opcional).

        Las clases largas se devuelven como ESQUELETO (firmas y anotaciones,
        cuerpos omitidos) y el resto de chunks largos, truncados — en ambos
        casos la respuesta incluye la llamada exacta (con start_line/end_line)
        para pedir el fragmento completo que necesites. Sigue esa instrucción
        tal cual cuando necesites más contexto."""
        if symbol is None and file_path is None:
            raise ValueError("Debes indicar 'symbol' o 'file_path'.")
        return uc["get_source"].execute(symbol, file_path, start_line, end_line)

    @mcp.tool()
    def list_chunks(language: str | None = None, kind: str | None = None) -> str:
        """Inventario filtrado de los chunks indexados en este proyecto.
        Útil para ver qué hay indexado; para buscar por significado usa
        search_code. Se muestran como máximo 200 filas — usa los filtros
        language/kind para acotar listados grandes."""
        return format_chunks(uc["list_chunks"].execute(language, kind))

    @mcp.tool()
    def get_index_stats() -> str:
        """Tamaño del índice y commit indexado de este proyecto. Primer
        contacto recomendado antes de buscar."""
        return format_stats(uc["get_index_stats"].execute())

    @mcp.tool()
    def reindex() -> str:
        """Reconstruye el índice completo de este proyecto (recoge también
        cambios locales sin commitear). Puede tardar en repos grandes."""
        from coderagmanager.application.manifest import read_manifest

        from coderagmanager.adapters.formatting import format_included

        stats = uc["index_project"].execute()
        manifest = read_manifest(uc["project"].root_path)
        uc["registry"].mark_indexed(
            project_id, commit=manifest.last_indexed_commit if manifest else None
        )
        summary = f"Reindexado: {stats.total_chunks} chunks, {stats.total_edges} aristas"
        return summary + format_included(stats.included)

    return mcp


def main() -> None:
    parser = argparse.ArgumentParser(prog="crm-mcp-server")
    parser.add_argument("--project", required=True)
    args, _ = parser.parse_known_args()
    serve(args.project)


def serve(project_id: str, registry_path: str | None = None) -> None:
    build_server(project_id, registry_path=registry_path).run(transport="stdio")


if __name__ == "__main__":
    main()
