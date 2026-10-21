import ast
import re
from pathlib import Path

from app.configs.error_codes import ErrorCode
from app.dto.enum import JsonPayload, NotFoundEntity, UuidEntity

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
GO_ROOT = ROOT / "data_pipe"
GO_CODE = re.compile(r"^\s*(\w+)\s+Code\s*=\s*(\d+)\s*$", re.MULTILINE)

USER_EXCEPTIONS = {
    "NoAccessError",
    "ValidationError",
    "UserError",
    "CustomPermissionError",
    "GitRepoError",
    "RepoError",
    "UnitError",
    "UnitIOError",
    "DataPipeError",
    "CustomJSONDecodeError",
    "MqttError",
    "UpdateError",
    "CipherError",
    "GitPlatformClientError",
    "GrafanaError",
    "FeatureFlagError",
    "ReadmeGenerationError",
    "InstanceError",
    "OperationTaskError",
    "NotificationError",
    "LokiError",
    "UnitGroupError",
}


def _python_codes() -> dict[int, str]:
    return {int(code): code.name for code in ErrorCode}


def _go_codes() -> dict[int, str]:
    found: dict[int, str] = {}
    for path in GO_ROOT.rglob("*.go"):
        for name, raw in GO_CODE.findall(path.read_text()):
            number = int(raw)
            assert number not in found, (
                f"Go code {number} is {found[number]} and {name}"
            )
            found[number] = f"{path.relative_to(ROOT)}:{name}"
    return found


def _split(number: int) -> tuple[int, int]:
    return divmod(number, 1000)


def test_error_code_route_returns_the_cached_catalog():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers.v1.error_code_router import router

    app = FastAPI()
    app.include_router(router, prefix="/error_codes")
    response = TestClient(app).get("/error_codes")
    assert response.status_code == 200
    assert response.json() == ErrorCode.catalog()


def test_console_text_has_the_puer_prefix_and_the_api_keeps_the_number():
    from app.configs.errors import ValidationError

    error = ValidationError("missing", code=ErrorCode.UNIT_NOT_FOUND)
    number = str(error.error_code)
    assert error.error_code == int(ErrorCode.UNIT_NOT_FOUND)
    assert error.message.split(": ", 2)[1] == number
    assert str(error).split(": ", 2)[1] == f"PUER{number}"
    assert ErrorCode.catalog()["UNIT_NOT_FOUND"] == error.error_code
    go_text = (GO_ROOT / "internal" / "apperr" / "codes.go").read_text()
    assert "PUER%d" in go_text


def test_error_code_catalog_is_computed_once_and_lists_every_code():
    first = ErrorCode.catalog()
    assert ErrorCode.catalog() is first
    assert first["ACCESS_TOKEN_EXPIRED"] == int(ErrorCode.ACCESS_TOKEN_EXPIRED)
    assert set(first) == set(ErrorCode.__members__)
    assert ErrorCode.not_found["User"] is ErrorCode.USER_NOT_FOUND
    assert ErrorCode.uuid_invalid["Unit"] is ErrorCode.UNIT_UUID_INVALID
    assert (
        ErrorCode.json_invalid["env.json"]
        is ErrorCode.GIT_REPO_ENV_JSON_INVALID
    )


def test_letter_bands_cover_the_domain_range():
    bands = ErrorCode.letter_bands()
    covered = [number for band in bands.values() for number in band]
    assert covered == list(
        range(ErrorCode.domain_min, ErrorCode.domain_max + 1)
    )


def test_each_entity_has_its_own_domain_inside_the_letter_band():
    bands = ErrorCode.letter_bands()
    assert all(bands.values())
    domains = [
        domain for _letter, domain in ErrorCode.entity_domains().values()
    ]
    assert len(domains) == len(set(domains))

    used: dict[str, set[int]] = {}
    for entity, (letter, domain) in ErrorCode.entity_domains().items():
        assert entity[0] == letter
        assert domain in bands[letter], (
            f"{entity} domain {domain} is outside {letter}"
        )
        used.setdefault(letter, set()).add(domain)

    for letter, owned in used.items():
        assert len(bands[letter]) > len(owned)


def test_python_and_go_error_codes_are_unique_and_well_formed():
    python_codes = _python_codes()
    go_codes = _go_codes()
    assert go_codes, "Go error codes were not found"
    overlap = set(python_codes) & set(go_codes)
    assert not overlap, f"shared codes: {sorted(overlap)}"

    datapipe = ErrorCode.entity_domains()["DataPipe"][1]
    for number, name in go_codes.items():
        domain, local = _split(number)
        assert ErrorCode.domain_min <= domain <= ErrorCode.domain_max, (
            f"{name} domain {domain}"
        )
        assert ErrorCode.local_min <= local <= ErrorCode.local_max, (
            f"{name} local {local}"
        )
        assert domain == datapipe, f"{name} is not on the DataPipe domain"

    for number, name in python_codes.items():
        domain, local = _split(number)
        assert ErrorCode.domain_min <= domain <= ErrorCode.domain_max, (
            f"{name} domain {domain}"
        )
        assert ErrorCode.local_min <= local <= ErrorCode.local_max, (
            f"{name} local {local}"
        )
        entity = _entity_of(name)
        expected = ErrorCode.entity_domains()[entity][1]
        assert domain == expected, (
            f"{name} is on {domain}, {entity} owns {expected}"
        )


def test_every_declared_code_is_used():
    blob = "\n".join(path.read_text() for path in APP.rglob("*.py"))
    missing = [
        name
        for name in ErrorCode.__members__
        if f"ErrorCode.{name}" not in blob
    ]
    assert not missing, f"unused Python codes: {missing}"

    go_text = "\n".join(path.read_text() for path in GO_ROOT.rglob("*.go"))
    const_text = (GO_ROOT / "internal" / "apperr" / "codes.go").read_text()
    for name, _raw in GO_CODE.findall(const_text):
        assert go_text.count(name) > 1, f"unused Go code {name}"


def test_user_facing_raises_use_catalog_codes():
    missing: list[str] = []
    for path in APP.rglob("*.py"):
        source = path.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Raise) or not isinstance(
                node.exc, ast.Call
            ):
                continue
            func = node.exc.func
            name = func.id if isinstance(func, ast.Name) else None
            if name not in USER_EXCEPTIONS:
                continue
            codes = [
                kw.value
                for kw in node.exc.keywords
                if kw.arg == "code" and _is_catalog_code(kw.value)
            ]
            if not codes:
                missing.append(
                    f"{path.relative_to(ROOT)}:{node.lineno} {name}"
                )
    assert not missing, "\n".join(missing)


def test_generic_validators_name_the_entity():
    bad: list[str] = []
    for path in list(APP.rglob("*.py")) + list((ROOT / "tests").rglob("*.py")):
        if "alembic" in path.parts:
            continue
        source = path.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(
                node.func, ast.Name
            ):
                continue
            where = f"{path.relative_to(ROOT)}:{node.lineno}"
            if node.func.id == "is_valid_object":
                _require_known(node, "NotFoundEntity", where, bad)
            elif node.func.id == "is_valid_uuid":
                _require_known(node, "UuidEntity", where, bad)
            elif node.func.id == "is_valid_json":
                _require_json(node, where, bad)
    assert not bad, "\n".join(bad)


_CODE_ENTITY = (
    ("ACCESS_", "Access"),
    ("CIPHER_", "Cipher"),
    ("DATAPIPE_", "DataPipe"),
    ("FEATURE_", "FeatureFlag"),
    ("GIT_PLATFORM_", "GitPlatform"),
    ("GIT_REPO_", "GitRepo"),
    ("GRAFANA_", "Grafana"),
    ("DASHBOARD_", "Dashboard"),
    ("PANELS_", "Dashboard"),
    ("ICON_", "Icon"),
    ("INSTANCE_", "Instance"),
    ("MQTT_", "Mqtt"),
    ("NOTIFICATION_", "Notification"),
    ("OPERATION_TASK_", "OperationTask"),
    ("PERMISSION_", "Permission"),
    ("PAGINATION_", "Pagination"),
    ("README_", "Readme"),
    ("REPO_", "Repo"),
    ("UNIT_IO_", "UnitIO"),
    ("UNIT_GROUP_", "UnitGroup"),
    ("UNIT_", "Unit"),
    ("USER_", "User"),
)


def _entity_of(name: str) -> str:
    for prefix, entity in _CODE_ENTITY:
        if name.startswith(prefix):
            return entity
    message = f"{name} has no entity"
    raise AssertionError(message)


def _is_catalog_code(node: ast.AST) -> bool:
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        code_member = (
            node.value.id == "ErrorCode" and node.attr in ErrorCode.__members__
        )
        lookup = node.value.id == "ErrorCode" and node.attr in {
            "not_found",
            "uuid_invalid",
            "json_invalid",
        }
        return code_member or lookup
    if isinstance(node, ast.Subscript):
        return _is_catalog_code(node.value)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        func = node.func
        return (
            func.attr == "code_from_validation"
            and isinstance(func.value, ast.Name)
            and func.value.id == "ErrorCode"
        )
    if isinstance(node, ast.BoolOp):
        return any(_is_catalog_code(value) for value in node.values)
    return isinstance(node, ast.Name) and node.id == "resolved"


def _require_known(
    node: ast.Call, enum_name: str, where: str, bad: list[str]
) -> None:
    if len(node.args) < 2:
        bad.append(f"{where} needs an entity")
        return
    if not _is_enum_arg(node.args[1], enum_name):
        bad.append(f"{where} entity must be {enum_name}")


def _require_json(node: ast.Call, where: str, bad: list[str]) -> None:
    if len(node.args) < 2:
        bad.append(f"{where} needs a data name")
        return
    if not _is_enum_arg(node.args[1], "JsonPayload"):
        bad.append(f"{where} data name must be JsonPayload")


def _is_enum_arg(node: ast.AST, enum_name: str) -> bool:
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        enum = {
            "NotFoundEntity": NotFoundEntity,
            "UuidEntity": UuidEntity,
            "JsonPayload": JsonPayload,
        }[enum_name]
        return node.value.id == enum_name and node.attr in enum.__members__
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == enum_name
        and bool(node.args)
    )
