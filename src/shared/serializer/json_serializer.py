import json
from typing import Any

from .serializer import Serializer
from .exceptions import SerializationError


class JsonSerializer(Serializer):

    def dumps(self, obj: Any) -> str:
        try:
            return json.dumps(obj)
        except Exception as exc:
            raise SerializationError(str(exc)) from exc

    def loads(self, data: str) -> Any:
        try:
            return json.loads(data)
        except Exception as exc:
            raise SerializationError(str(exc)) from exc