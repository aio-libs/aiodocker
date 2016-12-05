class DockerError(Exception):

    def __init__(self, status, data, *args):
        super().__init__(*args)
        self.status = status
        self.message = data['message']

    def __repr__(self):
        return 'DockerError({}, {!r})'.format(self.status, self.message)
