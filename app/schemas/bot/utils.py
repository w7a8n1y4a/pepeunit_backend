def make_monospace_table_with_title(data: list[list], title: str = None) -> str:
    if not data:
        return ""

    str_data = [[str(item) if item is not None else "-" for item in row] for row in data]

    max_per_column = [max(len(row[col_idx]) for row in str_data) for col_idx in range(len(str_data[0]))]

    total_width = sum(max_per_column) + 3 * len(max_per_column) - 1

    horizontal_line = '+' + '+'.join('-' * (length + 2) for length in max_per_column) + '+\n'

    result = [horizontal_line]

    if title:
        title_line = '|' + title.center(total_width) + '|\n'
        result.append(title_line)
        result.append(horizontal_line)

    for row in str_data:
        # Строим строку с данными
        row_line = (
            '|'
            + '|'.join(f' {cell} {" " * (max_len - len(cell))}' for cell, max_len in zip(row, max_per_column))
            + '|\n'
        )
        result.append(row_line)
        result.append(horizontal_line)

    return ''.join(result)
