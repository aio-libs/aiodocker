from typing import Any, TypedDict


class _Data(TypedDict):
    message: str


class DockerError(Exception):
    def __init__(self, status: int, data: _Data, *args: Any) -> None:
        super().__init__(status, data, *args)
        self.status = status
        self.message = data["message"]

    def __repr__(self) -> str:
        return "DockerError({self.status}, {self.message!r})".format(self=self)

    def __str__(self) -> str:
        return "DockerError({self.status}, {self.message!r})".format(self=self)


class DockerContainerError(DockerError):
    def __init__(self, status: int, data: _Data, container_id: str, *args: Any) -> None:
        super().__init__(status, data, container_id, *args)
        self.container_id = container_id

    def __repr__(self) -> str:
        return (
            "DockerContainerError("
            "{self.status}, {self.message!r}, "
            "{self.container_id!r})"
        ).format(self=self)

    def __str__(self) -> str:
        return (
            "DockerContainerError("
            "{self.status}, {self.message!r}, "
            "{self.container_id!r})"
        ).format(self=self)
