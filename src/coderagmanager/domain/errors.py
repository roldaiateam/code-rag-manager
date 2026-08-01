class ProjectNotFoundError(Exception):
    def __init__(self, project_id: str):
        super().__init__(f"Proyecto '{project_id}' no registrado.")
        self.project_id = project_id


class ChunkNotFoundError(Exception):
    pass
