from typing import Any, Dict


class Exec:
    def __init__(self, id: str) -> None:
        self._id = id

    async def inspect(self) -> Dict[str, Any]:
        return await self.docker._query_json(f'/exec/{{self._id}}/json')
