from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, List, Optional

from httpx import Request, Response, Headers, Cookies, QueryParams, URL

from .types import StreamTypes


@dataclass
class HeaderDependency:
    name: str

    def __call__(self, headers: Headers) -> str:
        return headers[self.name]


@dataclass
class CookieDependency:
    name: str

    def __call__(self, cookies: Cookies) -> str:
        return cookies[self.name]


def charset_encoding(response: Response) -> Optional[str]:
    return response.charset_encoding


def content(response: Response) -> bytes:
    return response.content


def cookies(response: Response) -> Cookies:
    return response.cookies


def elapsed(response: Response) -> timedelta:
    return response.elapsed


def encoding(response: Response) -> Optional[str]:
    return response.encoding


def has_redirect_location(response: Response) -> bool:
    return response.has_redirect_location


def headers(response: Response) -> Headers:
    return response.headers


def history(response: Response) -> List[Response]:
    return response.history


def http_version(response: Response) -> str:
    return response.http_version


def is_client_error(response: Response) -> bool:
    return response.is_client_error


def is_closed(response: Response) -> bool:
    return response.is_closed


def is_error(response: Response) -> bool:
    return response.is_error


def is_informational(response: Response) -> bool:
    return response.is_informational


def is_redirect(response: Response) -> bool:
    return response.is_redirect


def is_server_error(response: Response) -> bool:
    return response.is_server_error


def is_stream_consumed(response: Response) -> bool:
    return response.is_stream_consumed


def is_success(response: Response) -> bool:
    return response.is_success


def json(response: Response) -> Any:
    return response.json()


def links(response: Response) -> Dict[Optional[str], Dict[str, str]]:
    return response.links


def next_request(response: Response) -> Optional[Request]:
    return response.next_request


def num_bytes_downloaded(response: Response) -> int:
    return response.num_bytes_downloaded


def reason_phrase(response: Response) -> str:
    return response.reason_phrase


def request(response: Response) -> Request:
    return response.request


def response(response: Response) -> Response:
    return response


def status_code(response: Response) -> int:
    return response.status_code


def stream(response: Response) -> StreamTypes:
    return response.stream


def text(response: Response) -> str:
    return response.text


def url(response: Response) -> URL:
    return response.url


def request_content(request: Request) -> bytes:
    return request.content


def request_headers(request: Request) -> Headers:
    return request.headers


def request_method(request: Request) -> str:
    return request.method


def request_params(request: Request) -> QueryParams:
    return request.url.params


def request_stream(request: Request) -> StreamTypes:
    return request.stream


def request_url(request: Request) -> URL:
    return request.url
