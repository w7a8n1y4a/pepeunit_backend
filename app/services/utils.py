import json
import uuid
import uuid as uuid_pkg
from typing import Annotated

import toml
import yaml
from fastapi import Depends
from fastapi.security import APIKeyHeader
from starlette.datastructures import UploadFile as StarletteUploadFile

from app import settings
from app.dto.enum import GlobalPrefixTopic, VisibilityLevel


def token_depends(
    jwt_token: Annotated[
        str | None,
        Depends(APIKeyHeader(name="x-auth-token", auto_error=False)),
    ] = None,
):
    return jwt_token


def merge_two_dict_first_priority(first: dict, two: dict) -> dict:
    return {**two, **first}


def remove_none_value_dict(data: dict) -> dict:
    return {k: v for k, v in data.items() if v is not None}


def get_topic_name(node_uuid: uuid_pkg.UUID, topic_name: str):
    main_topic = f"{settings.pu_domain}/{node_uuid}"
    main_topic += (
        GlobalPrefixTopic.BACKEND_SUB_PREFIX
        if topic_name[-len(GlobalPrefixTopic.BACKEND_SUB_PREFIX) :]
        == GlobalPrefixTopic.BACKEND_SUB_PREFIX
        else ""
    )

    return main_topic


def get_visibility_level_priority(visibility_level: VisibilityLevel) -> int:
    priority_dict = {
        VisibilityLevel.PUBLIC: 0,
        VisibilityLevel.INTERNAL: 1,
        VisibilityLevel.PRIVATE: 2,
    }

    return priority_dict[visibility_level]


async def yml_file_to_dict(yml_file) -> dict:
    content = ""
    if isinstance(yml_file, StarletteUploadFile):
        content = await yml_file.read()
    elif hasattr(yml_file, "read"):
        # Handle Upload type from strawberry
        content = await yml_file.read()

    if isinstance(content, bytes):
        content = content.decode("utf-8")

    return yaml.safe_load(content)


def dict_to_yml_file(yml_dict: dict) -> str:
    yaml_content = yaml.safe_dump(
        yml_dict, allow_unicode=True, default_flow_style=False, sort_keys=False
    )

    filename = f"tmp/data_pipe_yml_{uuid.uuid4()}"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(yaml_content)

    return filename


class TomlToMdConverter:
    def __init__(self, data: dict) -> None:
        self.general = data.get("general") or {}
        self.images = data.get("images") or {}
        self.files = data.get("files") or {}
        self.physical_io = data.get("physical_io") or {}
        self.env_description = data.get("env_description") or {}
        self.topic_assignment = data.get("topic_assignment") or {}
        self.work_algorithm = data.get("work_algorithm") or {}
        self.installation = data.get("installation")
        self.lines: list[str] = []

    def generate(self) -> str:
        self._append_general_section()
        self._append_images_section()
        self._append_files_section()
        self._append_physical_io_section()
        self._append_env_description_section()
        self._append_topic_assignment_section()
        self._append_work_algorithm_section()
        self._append_installation_section()

        return "\n".join(self.lines).rstrip() + "\n"

    def _fmt_mixed_list(self, items):
        formatted = []
        for item in items:
            if isinstance(item, dict):
                name = (item.get("name") or "").strip()
                link = (item.get("link") or "").strip()
                if name and link:
                    formatted.append(f"[{name}]({link})")
                elif link:
                    formatted.append(f"[{link}]({link})")
                elif name:
                    formatted.append(name)
                else:
                    formatted.append(json.dumps(item, ensure_ascii=False))
            else:
                formatted.append(f"`{item}`")
        return ", ".join(formatted)

    def _label_for_general_key(self, key: str) -> str:
        mapping = {
            "description": "Description",
            "language": "Lang",
            "hardware": "Hardware",
            "firmware": "Firmware",
            "stack": "Stack",
            "version": "Version",
            "license": "License",
            "authors": "Authors",
        }
        return mapping.get(key, key)

    def _format_general_value(self, key: str, value):
        if value is None:
            return None

        if key in ("hardware", "firmware", "stack"):
            return self._format_hw_fw_stack_value(value)

        if key == "language":
            return self._format_language_value(value)

        if key == "authors":
            return self._format_authors_value(value)

        return self._format_default_general_value(value)

    def _format_hw_fw_stack_value(self, value):
        if not isinstance(value, list) or not value:
            return None
        return self._fmt_mixed_list(value)

    def _format_language_value(self, value):
        if not isinstance(value, str):
            return None
        v = value.strip()
        return f"`{v}`" if v else None

    def _format_authors_value(self, value):
        if not isinstance(value, list) or not value:
            return None
        authors = []
        for author in value:
            if not isinstance(author, dict):
                continue
            name = (author.get("name") or "").strip()
            email = (author.get("email") or "").strip()
            if name and email:
                authors.append(f"{name} <{email}>")
            elif name:
                authors.append(name)
            elif email:
                authors.append(f"<{email}>")
        if not authors:
            return None
        return ", ".join(authors)

    def _format_default_general_value(self, value):
        if isinstance(value, str):
            v = value.strip()
            return v or None
        return str(value)

    def _append_general_section(self) -> None:
        raw_name = self.general.get("name")
        if isinstance(raw_name, str):
            name = raw_name.strip()
            if name:
                self.lines.append(f"# {name}")
                self.lines.append("")

        table_rows: list[tuple[str, str]] = []
        for key, value in self.general.items():
            formatted_value = self._format_general_value(key, value)
            if formatted_value is None or key == "name":
                continue
            label = self._label_for_general_key(key)
            table_rows.append((label, formatted_value))

        if table_rows:
            self.lines.append("Parameter | Implementation")
            self.lines.append("-- | --")
            for label, val in table_rows:
                self.lines.append(f"{label} | {val}")
            self.lines.append("")

    def _append_images_section(self) -> None:
        if not self.images:
            return

        for title, urls in self.images.items():
            heading = (str(title) or "").strip()
            if not heading:
                continue
            if not heading.startswith("#"):
                heading = "## " + heading.capitalize()
            self.lines.append(heading)
            self.lines.append("")

            if isinstance(urls, list):
                self.lines.extend(
                    f'<div align="center"><img align="center" src="{url}"></div>'
                    for url in urls
                )
            else:
                self.lines.append(
                    f'<div align="center"><img align="center" src="{urls}"></div>'
                )
            self.lines.append("")

    def _append_files_section(self) -> None:
        if not self.files:
            return

        items = []
        for name, url in self.files.items():
            name_str = (str(name) or "").strip()
            url_str = (str(url) or "").strip()
            if not url_str:
                continue
            if not name_str:
                name_str = url_str
            items.append((name_str, url_str))

        if items:
            self.lines.append("## Files")
            self.lines.append("")
            for i, (name_str, url_str) in enumerate(items, start=1):
                self.lines.append(f"{i}. [{name_str}]({url_str})")
            self.lines.append("")

    def _append_physical_io_section(self) -> None:
        if not self.physical_io:
            return

        self.lines.append("## Physical IO")
        self.lines.append("")
        for key, desc in self.physical_io.items():
            self.lines.append(f"- `{key}` - {desc}")
        self.lines.append("")

    def _append_env_description_section(self) -> None:
        if not self.env_description:
            return

        self.lines.append("## Env variable assignment")
        self.lines.append("")
        for i, (key, desc) in enumerate(self.env_description.items(), start=1):
            self.lines.append(f"{i}. `{key}` - {desc}")
        self.lines.append("")

    def _append_topic_assignment_section(self) -> None:
        if not self.topic_assignment:
            return

        self.lines.append("## Assignment of Device Topics")
        self.lines.append("")
        for topic, desc in self.topic_assignment.items():
            self.lines.append(f"- `{topic}` - {desc}")
        self.lines.append("")

    def _append_work_algorithm_section(self) -> None:
        steps = self.work_algorithm.get("steps") or []
        if not steps:
            return

        self.lines.append("## Work algorithm")
        self.lines.append("")
        for i, step in enumerate(steps, start=1):
            self.lines.append(f"{i}. {step}")
        self.lines.append("")

    def _append_installation_section(self) -> None:
        install_steps = (
            self.installation.get("steps") or []
            if isinstance(self.installation, dict)
            else []
        )
        if not install_steps:
            return

        self.lines.append("## Installation")
        self.lines.append("")
        for i, step in enumerate(install_steps, start=1):
            self.lines.append(f"{i}. {step}")
        self.lines.append("")


def toml_to_md(data: dict) -> str:
    converter = TomlToMdConverter(data)
    return converter.generate()


async def toml_file_to_md(toml_file) -> str:
    content: str | bytes = ""
    if isinstance(toml_file, StarletteUploadFile):
        content = await toml_file.read()
    elif hasattr(toml_file, "read"):
        # Handle Upload type from strawberry
        content = await toml_file.read()

    if isinstance(content, bytes):
        content = content.decode("utf-8")

    data = toml.loads(content)
    return toml_to_md(data)
