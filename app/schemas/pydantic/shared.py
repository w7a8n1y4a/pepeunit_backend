from pydantic import BaseModel


class Root(BaseModel):
    name: str
    version: str
    description: str
    swagger: str
    graphql: str
