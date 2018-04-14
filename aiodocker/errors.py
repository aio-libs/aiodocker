import json


class DockerException(Exception):
    """
    A base class from which all other exceptions inherit.

    If you want to catch all errors that the Docker SDK might raise,
    catch this base exception.
    """


async def create_api_error_from_response(response):
    """
    Create a suitable APIError from ClientResponse.
    """
    what = await response.read()
    content_type = response.headers.get('content-type', '')
    response.close()
    if content_type == 'application/json':
        explanation = json.loads(what.decode('utf8'))['message']
    else:
        explanation = what.decode('utf8')
    cls = APIError
    if response.status == 404:
        if explanation and ('No such image' in str(explanation) or
                            'not found: does not exist or no pull access'
                            in str(explanation) or
                            'repository does not exist' in str(explanation)):
            cls = ImageNotFound
        else:
            cls = NotFound
    raise cls(response=response, explanation=explanation)


class APIError(DockerException):
    """
    An HTTP error from the API.
    """
    def __init__(self, response=None, explanation=None):
        self.response = response
        self.explanation = explanation

    def __str__(self):
        message = super(APIError, self).__str__()

        if self.is_client_error():
            message = '{0} Client Error: {1}'.format(self.response.status, self.response.reason)

        elif self.is_server_error():
            message = '{0} Server Error: {1}'.format(self.response.status, self.response.reason)

        if self.explanation:
            message = '{0} ("{1}")'.format(message, self.explanation)

        return message

    @property
    def status_code(self):
        if self.response is not None:
            return self.response.status

    def is_client_error(self):
        if self.status_code is None:
            return False
        return 400 <= self.status_code < 500

    def is_server_error(self):
        if self.status_code is None:
            return False
        return 500 <= self.status_code < 600


class NotFound(APIError):
    pass


class ImageNotFound(NotFound):
    pass


class InvalidVersion(DockerException):
    pass


class ContainerError(DockerException):
    """
    Represents a container that has exited with a non-zero exit code.
    """
    def __init__(self, container, exit_status, command, image, stderr):
        self.container = container
        self.exit_status = exit_status
        self.command = command
        self.image = image
        self.stderr = stderr

        err = ": {}".format(stderr) if stderr is not None else ""
        msg = ("Command '{}' in image '{}' returned non-zero exit "
               "status {}{}").format(command, image, exit_status, err)

        super(ContainerError, self).__init__(msg)


class BuildError(DockerException):
    def __init__(self, reason, build_log):
        super(BuildError, self).__init__(reason)
        self.msg = reason
        self.build_log = build_log


def create_unexpected_kwargs_error(name, kwargs):
    quoted_kwargs = ["'{}'".format(k) for k in sorted(kwargs)]
    text = ["{}() ".format(name)]
    if len(quoted_kwargs) == 1:
        text.append("got an unexpected keyword argument ")
    else:
        text.append("got unexpected keyword arguments ")
    text.append(', '.join(quoted_kwargs))
    return TypeError(''.join(text))
