from .result import Result


def Failure(message: str) -> Result:
    return Result(error=message)