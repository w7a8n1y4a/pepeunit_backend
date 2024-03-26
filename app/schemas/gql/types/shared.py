import strawberry

from app.schemas.gql.type_input_mixin import TypeInputMixin


@strawberry.type()
class NoneType(TypeInputMixin):
    is_none: bool = True
