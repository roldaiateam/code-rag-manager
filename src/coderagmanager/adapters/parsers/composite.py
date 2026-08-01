from __future__ import annotations

from coderagmanager.ports.language_parser import LanguageParser


class CompositeLanguageParser:
    """Prueba los parsers en orden y usa el primero cuyo supports() acepte el
    fichero. El GenericTextParser va siempre al final como red de seguridad."""

    def __init__(self, parsers: list[LanguageParser]):
        self._parsers = parsers

    def supports(self, file_path: str) -> bool:
        return any(p.supports(file_path) for p in self._parsers)

    def parse(self, project_id: str, file_path: str, source: str):
        for parser in self._parsers:
            if parser.supports(file_path):
                return parser.parse(project_id, file_path, source)
        return [], []
