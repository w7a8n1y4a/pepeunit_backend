from strawberry import Info


def has_selected_field(selected_fields: Info.selected_fields, target_name: str) -> bool:
    for field in selected_fields:
        if field.name == target_name:
            return True
        if field.selections:  # если есть вложенные поля
            if has_selected_field(field.selections, target_name):
                return True
    return False
