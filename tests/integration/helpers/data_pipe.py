import csv
import datetime
import json
import os
import random
import uuid as uuid_pkg
from io import StringIO

from fastapi import UploadFile

from app.dto.enum import ProcessingPolicyType

CSV_DIR = "tmp/csv"


def pipe_rows(policy: ProcessingPolicyType) -> list[dict]:
    """Rows accepted by StreamingCSVValidator for the integration yaml configs"""
    now = datetime.datetime.now(datetime.UTC).replace(
        tzinfo=None, second=0, microsecond=0
    )
    data = []
    match policy:
        case ProcessingPolicyType.AGGREGATION:
            step = datetime.timedelta(minutes=1)
            for i in range(2000):
                end_window = now - i * step
                start_window = end_window - datetime.timedelta(seconds=60)
                data.append(
                    {
                        "state": round(random.uniform(-20.0, 10.0), 2),
                        "create_datetime": end_window,
                        "start_window_datetime": start_window,
                        "end_window_datetime": end_window,
                    }
                )
        case ProcessingPolicyType.N_RECORDS:
            step = datetime.timedelta(minutes=60)
            for i in range(100):
                data.append(
                    {
                        "state": round(random.uniform(1, 10.0), 2),
                        "create_datetime": now - i * step,
                    }
                )
        case ProcessingPolicyType.TIME_WINDOW:
            # create_datetime must stay inside time_window_size of the config
            step = datetime.timedelta(seconds=2)
            for i in range(100):
                data.append(
                    {
                        "state": json.dumps(
                            {
                                "level": random.choice(["error", "info", "warning"]),
                                "TitleMessage": random.choice(
                                    ["Test Info One", "Test Info Two"]
                                ),
                            }
                        ),
                        "create_datetime": now - i * step,
                    }
                )

    data.sort(key=lambda item: item["create_datetime"])
    return data


def save_pipe_csv(policy: ProcessingPolicyType) -> str:
    data = pipe_rows(policy)
    if not data:
        raise Exception(f"No rows generated for {policy}")

    csv_data = StringIO()
    writer = csv.writer(csv_data)
    writer.writerow(data[0].keys())
    for item in data:
        writer.writerow(item.values())

    os.makedirs(CSV_DIR, exist_ok=True)
    file_path = f"{CSV_DIR}/{policy.value}_{uuid_pkg.uuid4()}.csv"
    with open(file_path, "w") as handle:
        handle.write(csv_data.getvalue())

    return file_path


async def upload_pipe_csv(
    service, unit_node_uuid, policy: ProcessingPolicyType
) -> None:
    """Fills a node through the user CSV import, unlike the live MQTT flow it
    writes to ClickHouse synchronously
    """
    file_path = save_pipe_csv(policy)
    try:
        with open(file_path, "rb") as handle:
            await service.set_data_pipe_data_csv(
                uuid=unit_node_uuid,
                data_csv=UploadFile(
                    filename=os.path.basename(file_path), file=handle
                ),
            )
    finally:
        os.remove(file_path)
