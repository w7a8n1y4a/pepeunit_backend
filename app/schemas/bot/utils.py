from datetime import UTC, datetime


def make_monospace_table_with_title(
    data: list[list], title: str = None, lengths: list | None = None
) -> str:
    if not data:
        return ""

    num_columns = len(data[0]) if data else 0
    if lengths is None:
        lengths = [None] * num_columns
    else:
        lengths = lengths[:num_columns] + [None] * (num_columns - len(lengths))

    str_data = [
        [str(item) if item is not None else "-" for item in row]
        for row in data
    ]

    def wrap_text(text: str, max_len: int | None) -> list[str]:
        if max_len is None:
            return [text]
        if len(text) <= max_len:
            return [text]

        lines = []
        current_line = []
        current_length = 0

        for word in text.split(" "):
            word_length = len(word)
            if current_length + word_length <= max_len:
                current_line.append(word)
                current_length += word_length + 1
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                if word_length > max_len:
                    lines.extend(
                        [
                            word[i : i + max_len]
                            for i in range(0, len(word), max_len)
                        ]
                    )
                    current_line = []
                    current_length = 0
                else:
                    current_line = [word]
                    current_length = word_length + 1

        if current_line:
            lines.append(" ".join(current_line))

        return lines

    wrapped_data = []
    for row in str_data:
        wrapped_row = []
        for cell, max_len in zip(row, lengths, strict=False):
            wrapped_row.append(wrap_text(cell, max_len))
        wrapped_data.append(wrapped_row)

    max_lines_per_row = [
        max(len(cell) for cell in row) for row in wrapped_data
    ]

    column_widths = []
    for col_idx in range(num_columns):
        actual_max = max(
            len(line) for row in wrapped_data for line in row[col_idx]
        )
        if lengths[col_idx] is not None:
            column_width = min(lengths[col_idx], actual_max)
        else:
            column_width = actual_max
        column_widths.append(column_width)

    horizontal_line = (
        "+" + "+".join("-" * (width + 2) for width in column_widths) + "+\n"
    )

    result = [horizontal_line]

    if title:
        total_width = sum(column_widths) + 3 * len(column_widths) - 1
        title_line = "|" + title.center(total_width) + "|\n"
        result.append(title_line)
        result.append(horizontal_line)

    for row, max_lines in zip(wrapped_data, max_lines_per_row, strict=False):
        for line_idx in range(max_lines):
            row_line = "|"
            for cell, width in zip(row, column_widths, strict=False):
                if line_idx < len(cell):
                    line = cell[line_idx][:width]
                    row_line += f" {line.ljust(width)} |"
                else:
                    row_line += f" {''.ljust(width)} |"
            row_line += "\n"
            result.append(row_line)
        result.append(horizontal_line)

    return "".join(result)


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
        date = datetime.fromtimestamp(timestamp / 1000, tz=UTC)
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
    _, f_frsize, f_blocks, f_bfree = (
        statvfs[0],
        statvfs[1],
        statvfs[2],
        statvfs[3],
    )

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
