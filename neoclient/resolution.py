from typing import Any, Callable

from .dependence import DependencyParameter
from .models import RequestOptions, Response


def resolve_response(func: Callable, response: Response) -> Any:
    dependency: DependencyParameter = DependencyParameter(dependency=func)

    return dependency.resolve_response(response)


def resolve_request(func: Callable, request: RequestOptions) -> Any:
    dependency: DependencyParameter = DependencyParameter(dependency=func)

    return dependency.resolve_request(request)
