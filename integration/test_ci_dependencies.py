"""CI jobs must install the local dependencies their tests import."""

from pathlib import Path
import shlex
import tomllib

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("job_id", ("deepseek-connector", "jimeng-connector", "security"))
def test_error_sanitizer_jobs_install_connector_sdk_dependency_closure(job_id: str) -> None:
    workflow = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )
    installed_packages: set[str] = set()
    for step in workflow["jobs"][job_id]["steps"]:
        arguments = shlex.split(step.get("run", ""))
        installed_packages.update(
            value.split("[", 1)[0]
            for flag, value in zip(arguments, arguments[1:])
            if flag == "-e"
        )

    required_packages = {
        "packages/compliance",
        "packages/content-package",
        "packages/campaign-draft",
        "packages/connector-sdk",
    }
    assert required_packages <= installed_packages


def test_api_dev_dependencies_include_pinned_schema_validator() -> None:
    project = tomllib.loads(
        (REPO_ROOT / "apps" / "api" / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert any(
        requirement.startswith("jsonschema==")
        for requirement in project["project"]["optional-dependencies"]["dev"]
    )
