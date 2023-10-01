from neomodel import (
    ZeroOrMore,
    OneOrMore,
    StructuredRel, DateTimeProperty, UniqueIdProperty
)


class VariablesRel(StructuredRel):
    """ Unit to variable and variable to Unit """

    # uuid4 - unique id
    uuid = UniqueIdProperty()
    # datetime of creation relationship
    create_datetime = DateTimeProperty()
