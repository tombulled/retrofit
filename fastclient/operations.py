import dataclasses
import inspect
import urllib.parse
from dataclasses import dataclass
from typing import Any, Callable, Dict, Generic, Optional, Protocol, Set, TypeVar, Union

import fastapi.encoders
import httpx
import param
import param.models
from param.sentinels import Missing, MissingType
import pydantic
from httpx import Client, Response
from pydantic import BaseModel
from typing_extensions import ParamSpec

from . import resolvers, api, utils
from .enums import ParamType
from .errors import (
    IncompatiblePathParameters,
    NotAnOperation,
    InvalidParameterSpecification,
)
from .models import OperationSpecification, RequestOptions
from .parameters import (
    Body,
    Depends,
    Param,
    Params,
    Header,
    Headers,
    Path,
    QueryParams,
    Query,
    Cookie,
    Cookies,
    PathParams,
)
from .types import HeaderTypes, QueryParamTypes, CookieTypes

PS = ParamSpec("PS")
RT = TypeVar("RT")

class Composer(Protocol):
    def __call__(
        self,
        request: RequestOptions,
        parameter: param.Parameter,
        value: Any
    ) -> None:
        ...


def _parse_obj(annotation: Union[MissingType, Any], obj: Any) -> Any:
    if type(obj) is annotation or annotation in (inspect._empty, Missing):
        return obj

    return pydantic.parse_obj_as(annotation, obj)


def get_operation(obj: Any, /) -> "Operation":
    if not has_operation(obj):
        raise NotAnOperation(f"{obj!r} is not an operation")

    return getattr(obj, "operation")


def has_operation(obj: Any, /) -> bool:
    return hasattr(obj, "operation")


def set_operation(obj: Any, operation: "Operation", /) -> None:
    setattr(obj, "operation", operation)


def del_operation(obj: Any, /) -> None:
    delattr(obj, "operation")


def feed_request_query_param(request: RequestOptions, param: Query, value: str) -> None:
    if param.alias is None:
        raise Exception(f"Cannot feed param {param!r} if it has no alias")

    resolved_value: str = value if value is not Missing else param.get_default()

    request.add_query_param(param.alias, resolved_value)


def feed_request_header(request: RequestOptions, param: Header, value: str) -> None:
    if param.alias is None:
        raise Exception(f"Cannot feed param {param!r} if it has no alias")

    resolved_value: str = value if value is not Missing else param.get_default()

    request.add_header(param.alias, resolved_value)


def feed_request_cookie(request: RequestOptions, param: Cookie, value: str) -> None:
    if param.alias is None:
        raise Exception(f"Cannot feed param {param!r} if it has no alias")

    resolved_value: str = value if value is not Missing else param.get_default()

    request.add_cookie(param.alias, resolved_value)


def feed_request_path_param(request: RequestOptions, param: Path, value: str) -> None:
    if param.alias is None:
        raise Exception(f"Cannot feed param {param!r} if it has no alias")

    resolved_value: str = value if value is not Missing else param.get_default()

    request.add_path_param(param.alias, resolved_value)


def feed_request_body(request: RequestOptions, param: Body, value: Any) -> None:
    resolved_value: Any = fastapi.encoders.jsonable_encoder(
        value if value is not None else param.get_default()
    )

    if param.embed:
        if param.alias is None:
            raise Exception(f"Cannot embed body param {param!r} if it has no alias")

        resolved_value = {param.alias: resolved_value}

    # If there's only one body param, or this param shouln't be embedded in any pre-existing json,
    # make it the entire JSON request body
    if request.json is None or not param.embed:
        request.json = resolved_value
    else:
        request.json.update(resolved_value)


def feed_request_query_params(
    request: RequestOptions,
    param: QueryParams,
    value: QueryParamTypes,
) -> None:
    resolved_value: httpx.QueryParams = (
        httpx.QueryParams(value) if value is not Missing else param.get_default()
    )

    request.add_query_params(resolved_value)


def feed_request_headers(
    request: RequestOptions,
    param: Headers,
    value: HeaderTypes,
) -> None:
    resolved_value: httpx.Headers = (
        httpx.Headers(value) if value is not Missing else param.get_default()
    )

    request.add_headers(resolved_value)


def feed_request_cookies(
    request: RequestOptions,
    param: Cookies,
    value: CookieTypes,
) -> None:
    resolved_value: httpx.Cookies = (
        httpx.Cookies(value) if value is not Missing else param.get_default()
    )

    request.add_cookies(resolved_value)


def feed_request_path_params(
    request: RequestOptions,
    param: Cookies,
    value: Dict[str, Any],
) -> None:
    resolved_value: Dict[str, Any] = (
        value if value is not Missing else param.get_default()
    )

    request.add_path_params(resolved_value)


def feed_request_param(
    request: RequestOptions, parameter: param.Parameter, value: Any
) -> None:
    spec: Param

    if not isinstance(parameter.spec, Param):
        raise Exception("Parameter is not a Param")
    else:
        spec = parameter.spec

    field_name: str = (
        spec.alias if spec.alias is not None else spec.generate_alias(parameter.name)
    )

    # Ensure the parameter has an alias
    spec = dataclasses.replace(spec, alias=field_name)

    # The field is not required, it can be omitted
    if value is None and not spec.required:
        return

    if spec.type is ParamType.QUERY:
        # Convert the value
        value = _parse_obj(str, value)

        feed_request_query_param(request, spec, value)
    elif spec.type is ParamType.HEADER:
        # Convert the value
        value = _parse_obj(str, value)

        feed_request_header(request, spec, value)
    elif spec.type is ParamType.COOKIE:
        # Convert the value
        value = _parse_obj(str, value)

        feed_request_cookie(request, spec, value)
    elif spec.type is ParamType.PATH:
        # Convert the value
        value = _parse_obj(str, value)

        feed_request_path_param(request, spec, value)
    elif spec.type is ParamType.BODY:
        feed_request_body(request, spec, value)
    else:
        raise Exception(f"Unknown ParamType: {spec.type!r}")


def feed_request_params(
    request: RequestOptions, parameter: param.Parameter, value: Any
) -> None:
    spec: Params

    if not isinstance(parameter.spec, Params):
        raise Exception("Parameter is not a Params")
    else:
        spec = parameter.spec

    if spec.type is ParamType.QUERY:
        feed_request_query_params(request, spec, value)
    elif spec.type is ParamType.HEADER:
        feed_request_headers(request, spec, value)
    elif spec.type is ParamType.COOKIE:
        feed_request_cookies(request, spec, value)
    elif spec.type is ParamType.PATH:
        feed_request_path_params(request, spec, value)
    else:
        raise Exception(f"Unknown multi-param: {spec.type!r}")


whitelisted_operation_params: Dict[
    type, Composer
] = {
    Query: feed_request_param,
    Header: feed_request_param,
    Cookie: feed_request_param,
    Path: feed_request_param,
    Body: feed_request_param,
    QueryParams: feed_request_params,
    Headers: feed_request_params,
    Cookies: feed_request_params,
    PathParams: feed_request_params,
}


def get_operation_params(
    func: Callable, /, *, request: Optional[RequestOptions] = None
) -> Dict[str, param.Parameter]:
    params: Dict[str, param.Parameter] = api.get_params(func, request=request)

    parameter: param.Parameter
    for parameter in params.values():
        if not isinstance(parameter.spec, tuple(whitelisted_operation_params)):
            raise InvalidParameterSpecification(
                f"Invalid operation parameter specification: {parameter.spec!r}"
            )

    return params


@dataclass
class Operation(Generic[PS, RT]):
    func: Callable[PS, RT]
    specification: OperationSpecification
    client: Optional[Client]

    def __call__(self, *args: PS.args, **kwargs: PS.kwargs) -> Any:
        arguments: Dict[str, Any] = self._get_arguments(*args, **kwargs)

        new_request_options: RequestOptions = self.build_request_options(arguments)
        request_options: RequestOptions = self.specification.request.merge(
            new_request_options
        )

        request: httpx.Request = request_options.build_request(self.client)

        return_annotation: Any = inspect.signature(self.func).return_annotation

        if return_annotation is RequestOptions:
            return request_options
        if return_annotation is httpx.Request:
            return request

        client: Client = self.client if self.client is not None else Client()

        response: Response = client.send(request)

        if self.specification.response is not None:
            return resolvers.resolve_dependency(response, Depends(dependency=self.specification.response), annotation=return_annotation)

        if return_annotation is inspect._empty:
            return response.json()
        if return_annotation is None:
            return None
        if return_annotation is Response:
            return response
        if isinstance(return_annotation, type) and issubclass(
            return_annotation, BaseModel
        ):
            return return_annotation.parse_obj(response.json())

        return pydantic.parse_raw_as(return_annotation, response.text)

    def build_request_options(self, arguments: Dict[str, Any], /) -> RequestOptions:
        request: RequestOptions = RequestOptions(
            method=self.specification.request.method,
            url=self.specification.request.url,
        )

        params: Dict[str, param.Parameter] = get_operation_params(
            self.func, request=self.specification.request
        )

        parameter_name: str
        parameter: param.Parameter
        for parameter_name, parameter in params.items():
            value: Any = arguments[parameter_name]

            spec_type: type
            feeder_function: Composer
            for spec_type, feeder_function in whitelisted_operation_params.items():
                if isinstance(parameter.spec, spec_type):
                    feeder_function(request, parameter, value)

                    break
            else:
                raise InvalidParameterSpecification(
                    f"Invalid operation parameter specification: {parameter.spec!r}"
                )

        self._validate_request_options(request)

        return request

    def _validate_request_options(self, request: RequestOptions, /) -> None:
        missing_path_params: Set[str] = utils.get_path_params(
            urllib.parse.unquote(str(request.url))
        )

        # Validate path params are correct
        if missing_path_params:
            raise IncompatiblePathParameters(
                f"Incompatible path params. Missing: {missing_path_params}"
            )

    def _get_arguments(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        arguments: Dict[str, Any] = utils.bind_arguments(self.func, args, kwargs)

        # TODO: Find a better fix for instance methods
        if arguments and list(arguments)[0] == "self":
            arguments.pop("self")

        argument_name: str
        argument: Any
        for argument_name, argument in arguments.items():
            if isinstance(argument, param.models.Param):
                if not argument.has_default():
                    raise ValueError(
                        f"{self.func.__name__}() missing argument: {argument_name!r}"
                    )

                arguments[argument_name] = argument.get_default()

        return arguments
