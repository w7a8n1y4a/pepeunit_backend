import enum


class ClickHouseBaseMixin:
    def to_dict(self) -> dict:
        result = {}
        for k, v in self.dict().items():
            if isinstance(v, enum.Enum):
                result[k] = v.value
            else:
                result[k] = v

        return result

    @classmethod
    def get_keys(cls) -> str:
        return ', '.join(cls.model_fields.keys())
