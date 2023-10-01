from neomodel import (
    StructuredNode,
    StringProperty,
    RelationshipTo,
    ZeroOrMore,
    OneOrMore,
    UniqueIdProperty,
    DateTimeProperty
)

from app.modules.devices.relations import VariablesRel


class Unit(StructuredNode):
    """ Micropython Device in Pepeunit """

    # uuid4 - unique id - Unit in system
    uuid = UniqueIdProperty()
    # User set name for the Unit, example: my_best_heater_relay
    name = StringProperty(index=True)
    # full url to repository with Unit, example: https://git.pepemoss.com/pepe/pepeunit/units/wifi_relay
    repository_link = StringProperty()
    # all the metadata for Unit, this is the "unit_state" section in schema.json, is in repository_link
    unit_state_variable = StringProperty()
    # cipher json.dumps AES and initial vector, all in base64
    encrypted_env_variables = StringProperty()
    # datetime of creation Unit
    create_datetime = DateTimeProperty()


class InputVariables(StructuredNode):
    """ Control variables for the Unit """

    # uuid4 - unique id, for control
    uuid = UniqueIdProperty()
    # User set name for Input Variable, example: my_best_flag_activate_my_pc
    name = StringProperty(index=True)
    # System automatic set variables name, this for schema.json, example: input_relay_state
    unit_variable_name = StringProperty(index=True)

    # state variable, example: 0 or 1000.00 or 0.0001 or "normal"
    state = StringProperty()
    # only for the mask on the frontend
    state_type = StringProperty()
    # datetime when the value was assigned
    set_datetime = DateTimeProperty()

    # Can other User Units overwrite this variable?
    is_rewrite = StringProperty()

    # many variables to one unit
    unit = RelationshipTo(Unit, 'UNIT_IN', model=VariablesRel)


class OutputVariables(StructuredNode):
    """ Data variables from the Unit """

    # uuid4 - unique id, for data
    uuid = UniqueIdProperty()
    # User set name for Output Variable, example: house_humidity
    name = StringProperty(index=True)
    # System automatic set variables name, this from schema.json, example: output_relay_state
    unit_variable_name = StringProperty(index=True)

    # state variable, example: 24.32 or 1000.00 or 0.0001 or "normal" or 0
    state = StringProperty()
    # only for the mask on the frontend
    state_type = StringProperty()
    # datetime when the value was assigned
    set_datetime = DateTimeProperty()

    # many variables to one unit
    unit = RelationshipTo(Unit, 'UNIT_OUT', model=VariablesRel)
