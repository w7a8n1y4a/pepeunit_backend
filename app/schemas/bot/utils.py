from datetime import datetime


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


def byte_converter(size_in_bytes: float) -> str:
    units = ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]
    size = size_in_bytes

    for unit in units:
        if size < 1000:
            return f"{size:.2f} {unit}"
        size /= 1024

    return f"{size:.2f} YB"


def format_millis(time: int | float) -> str:

    if isinstance(time, float):
        time = int(time)

    def format_date(timestamp: int) -> str:
        date = datetime.fromtimestamp(timestamp / 1000)
        return date.strftime("%Y-%m-%d %H:%M:%S")

    def format_uptime(milliseconds: int) -> str:
        seconds = milliseconds // 1000
        minutes = seconds // 60
        hours = minutes // 60
        days = hours // 24

        return f"{days}d {hours % 24:02}:{minutes % 60:02}:{seconds % 60:02}"

    is_unix_timestamp = time > 1000000000000

    return format_date(time) if is_unix_timestamp else format_uptime(time)


def calculate_flash_mem(statvfs: list[float]) -> tuple[float, float, float]:
    _, f_frsize, f_blocks, f_bfree = statvfs[0], statvfs[1], statvfs[2], statvfs[3]

    total = f_blocks * f_frsize
    used = (f_blocks - f_bfree) * f_frsize
    free = f_bfree * f_frsize

    return total, free, used


def reformat_table(table):
    columns = len(table) // 4
    table_parts = [table[i * 4 : (i + 1) * 4] for i in range(columns)]

    new_table = []
    max_rows = max(len(part) for part in table_parts)

    for row_idx in range(max_rows):
        new_row = []
        for part in table_parts:
            if row_idx < len(part):
                new_row.extend(part[row_idx])
            else:
                new_row.extend([None, None])
        new_table.append(new_row)

    return new_table
