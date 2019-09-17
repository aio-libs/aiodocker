from typing import Any, List, Mapping

from .utils import clean_filters


class DockerTasks(object):
    def __init__(self, docker):
        self.docker = docker

    async def list(self, *, filters: Mapping = None) -> List[Mapping]:
        """
        Return a list of tasks

        Args:
            filters: a collection of filters

        Available filters:
        desired-state=(running | shutdown | accepted)
        id=<task id>
        label=key or label="key=value"
        name=<task name>
        node=<node id or name>
        service=<service name>

        """

        params = {"filters": clean_filters(filters)}

        response = await self.docker._query_json("tasks", method="GET", params=params)
        return response

    async def inspect(self, task_id: str) -> Mapping[str, Any]:
        """
        Return info about a task

        Args:
            task_id: is ID of the task

        """

        response = await self.docker._query_json(
            "tasks/{task_id}".format(task_id=task_id), method="GET"
        )
        return response
