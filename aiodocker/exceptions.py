class DockerError(Exception):

    def __init__(self, status, data, container_id=None, *args):
        super().__init__(*args)
        self.status = status
        self.message = data['message']
        self.container_id = container_id

    def __repr__(self):
        return 'DockerError({self.status}, {self.message!r})'.format(self=self)

    def __str__(self):
        return 'DockerError({self.status}, {self.message!r})'.format(self=self)
