class DockerError(Exception):
    def __init__(self, status, data, *args):
        super().__init__(status, data, *args)
        self.status = status
        self.message = data["message"]

    def __repr__(self):
        return "DockerError({self.status}, {self.message!r})".format(self=self)

    def __str__(self):
        return "DockerError({self.status}, {self.message!r})".format(self=self)


class DockerContainerError(DockerError):
    def __init__(self, status, data, container_id, *args):
        super().__init__(status, data, container_id, *args)
        self.container_id = container_id

    def __repr__(self):
        return (
            "DockerContainerError("
            "{self.status}, {self.message!r}, "
            "{self.container_id!r})"
        ).format(self=self)

    def __str__(self):
        return (
            "DockerContainerError("
            "{self.status}, {self.message!r}, "
            "{self.container_id!r})"
        ).format(self=self)
