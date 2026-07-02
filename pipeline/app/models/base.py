from enum import Enum

from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def enum_values(enum_cls: type[Enum]) -> list[str]:
    return [member.value for member in enum_cls]


def pg_enum(enum_cls: type[Enum], name: str) -> SAEnum:
    return SAEnum(enum_cls, name=name, values_callable=enum_values, native_enum=True)
