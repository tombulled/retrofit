import dataclasses
from typing import Any, Callable, Mapping, MutableMapping, Tuple, Type

from httpx import Response, Request, Headers, Cookies, QueryParams, URL
from pydantic import BaseModel
from pydantic.fields import ModelField, FieldInfo

from .. import api
from ..parameters import (
    BaseParameter,
    BodyParameter,
    QueryParameter,
    RequestParameter,
    ResponseParameter,
    URLParameter,
    QueriesParameter,
    HeadersParameter,
    CookiesParameter,
)
from ..validation import ValidatedFunction


def _get_fields(func: Callable, /) -> Mapping[str, Tuple[Any, BaseParameter]]:
    class Config:
        allow_population_by_field_name: bool = True
        arbitrary_types_allowed: bool = True

    fields: MutableMapping[str, Tuple[Any, BaseParameter]] = {}

    field_name: str
    model_field: ModelField
    for field_name, model_field in ValidatedFunction(func, config=Config).model.__fields__.items():
        field_info: FieldInfo = model_field.field_info

        # Parameter Inference
        if not isinstance(field_info, BaseParameter):
            # TODO: Better inference (e.g. path params)

            if (
                isinstance(model_field.annotation, type)
                and issubclass(model_field.annotation, (BaseModel, dict))
                or dataclasses.is_dataclass(model_field.annotation)
            ):
                field_info = BodyParameter(
                    default=BaseParameter.get_default(field_info),
                )
            elif model_field.annotation is Request:
                field_info = RequestParameter()
            elif model_field.annotation is Response:
                field_info = ResponseParameter()
            elif model_field.annotation is URL:
                field_info = URLParameter()
            elif model_field.annotation is QueryParams:
                field_info = QueriesParameter()
            elif model_field.annotation is Headers:
                field_info = HeadersParameter()
            elif model_field.annotation is Cookies:
                field_info = CookiesParameter()
            else:
                field_info = QueryParameter(
                    default=BaseParameter.get_default(field_info),
                )

        # if isinstance(field_info, BaseSingleParameter) and field_info.alias is None:
        if field_info.alias is None:
            field_info = dataclasses.replace(
                field_info, alias=field_info.generate_alias(field_name)
            )

        fields[field_name] = (model_field.annotation, field_info)

    # TODO: Validation? (e.g. no duplicate parameters?)

    return fields


def resolve(
    func: Callable,
    response: Response,
) -> Any:
    fields: Mapping[str, Tuple[Any, BaseParameter]] = _get_fields(func)

    model_cls: Type[BaseModel] = api.create_model_cls(func, fields)

    arguments: MutableMapping[str, Any] = {}

    field_name: str
    model_field: ModelField
    for field_name, model_field in model_cls.__fields__.items():
        # TODO: Fix typing of this vvv (FieldInfo is not a BaseParameter)
        parameter: BaseParameter = model_field.field_info

        arguments[field_name] = parameter.resolve(response)

    model: BaseModel = model_cls(**arguments)

    validated_arguments: Mapping[str, Any] = model.dict()

    return func(**validated_arguments)
