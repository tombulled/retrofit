from http import HTTPStatus
from typing import Sequence

from neoclient.enums import HTTPMethod
from neoclient.models import RequestOptions, Request, Response

__all__: Sequence[str] = (
    "build_request",
    "build_response",
)


def build_pre_request(
    *,
    method: str = HTTPMethod.GET,
    url: str = "https://foo.com/",
    **kwargs,
) -> RequestOptions:
    return RequestOptions(method, url, **kwargs)


def build_request(
    *,
    method: str = HTTPMethod.GET,
    url: str = "https://foo.com/",
    **kwargs,
) -> Request:
    return Request(method, url, **kwargs)


def build_response(
    *,
    status_code: int = HTTPStatus.OK,
    request: Request = build_request(),
    **kwargs,
) -> Response:
    return Response(status_code, request=request, **kwargs)
