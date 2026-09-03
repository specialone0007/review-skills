#!/usr/bin/env python3
"""Validate this repository's skills against the Agent Skills spec and its own conventions.

Maintainer tool. Standard library only, so it runs anywhere without setup:

    python tools/validate_skills.py

Exits non-zero when any error is found. Warnings do not fail the run.
Every diagnostic is printed as `path:line: message` so editors can jump to it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO / "skills"

# Spec limits (platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices).
NAME_MAX = 64
DESCRIPTION_MAX = 1024
BODY_MAX_LINES = 500
BODY_WARN_LINES = 400

# Our own budget: all descriptions are resident in the system prompt on every request.
DESCRIPTIONS_TOTAL_MAX = 5000

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
RESERVED_WORDS = ("anthropic", "claude")

# Words that must not be naively title-cased when deriving a display name from a folder.
ACRONYMS = {"pr": "PR", "api": "API", "ui": "UI", "ux": "UX", "cli": "CLI"}

REPORT_HEADER_RE = re.compile(r"^\*\*(?P<title>[^*:]+): <[^>]+>\*\*$")
RELATED_RE = re.compile(r"^- Use `(?P<skill>[a-z0-9-]+)`")
BUNDLED_PATH_RE = re.compile(r"`((?:scripts|references|assets)/[A-Za-z0-9_./-]+)`")
MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

errors: list[str] = []
warnings: list[str] = []


def error(path: Path, line: int, message: str) -> None:
    errors.append(f"{path.relative_to(REPO).as_posix()}:{line}: {message}")


def warn(path: Path, line: int, message: str) -> None:
    warnings.append(f"{path.relative_to(REPO).as_posix()}:{line}: {message}")


def expected_display_name(folder: str) -> str:
    return " ".join(ACRONYMS.get(part, part.capitalize()) for part in folder.split("-"))


def parse_frontmatter(path: Path, lines: list[str]) -> dict[str, str] | None:
    """Parse the leading `---` block. Returns None when it is missing or malformed."""
    if not lines or lines[0].strip() != "---":
        error(path, 1, "file must begin with a `---` YAML frontmatter block")
        return None
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        error(path, 1, "frontmatter block is never closed with `---`")
        return None

    fields: dict[str, str] = {}
    for i in range(1, end):
        raw = lines[i]
        if not raw.strip():
            continue
        if raw[0] in " \t":
            error(path, i + 1, "frontmatter must be flat `key: value` pairs; nested/continued lines are not allowed")
            continue
        if ":" not in raw:
            error(path, i + 1, f"frontmatter line is not `key: value`: {raw.strip()!r}")
            continue
        key, value = raw.split(":", 1)
        key = key.strip()
        if key in fields:
            error(path, i + 1, f"duplicate frontmatter key `{key}`")
        fields[key] = value.strip()

    # The spec defines exactly two fields. Unknown keys risk host validation failures.
    for key in fields:
        if key not in ("name", "description"):
            error(path, 1, f"unsupported frontmatter key `{key}`; the spec defines only `name` and `description`")
    for key in ("name", "description"):
        if key not in fields:
            error(path, 1, f"missing required frontmatter key `{key}`")

    fields["__body_start__"] = str(end + 1)
    return fields


def parse_openai_yaml(path: Path) -> dict[str, str]:
    """Read the three `interface.*` values. These files are flat, so a tiny parser is enough."""
    values: dict[str, str] = {}
    in_interface = False
    for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.rstrip() == "interface:":
            in_interface = True
            continue
        if not raw[0].isspace():
            in_interface = False
            continue
        if in_interface and ":" in raw:
            key, value = raw.split(":", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
            values[f"__line__{key.strip()}"] = str(i)
    return values


def check_skill(folder: Path, all_names: set[str]) -> str | None:
    """Validate one skill. Returns its description for the shared budget check."""
    name = folder.name
    skill_md = folder / "SKILL.md"
    if not skill_md.is_file():
        errors.append(f"skills/{name}: missing SKILL.md")
        return None

    text = skill_md.read_text(encoding="utf-8")
    lines = text.splitlines()

    fields = parse_frontmatter(skill_md, lines)
    if fields is None:
        return None

    # 2. name
    declared = fields.get("name", "")
    if declared != name:
        error(skill_md, 2, f"frontmatter name {declared!r} does not match folder name {name!r}")
    if not NAME_RE.match(declared):
        error(skill_md, 2, f"name {declared!r} must be lowercase letters, numbers and single hyphens")
    if len(declared) > NAME_MAX:
        error(skill_md, 2, f"name is {len(declared)} chars, limit {NAME_MAX}")
    for word in RESERVED_WORDS:
        if word in declared:
            error(skill_md, 2, f"name must not contain the reserved word {word!r}")

    # 3. description
    description = fields.get("description", "")
    if not description:
        error(skill_md, 3, "description must not be empty")
    if len(description) > DESCRIPTION_MAX:
        error(skill_md, 3, f"description is {len(description)} chars, limit {DESCRIPTION_MAX}")
    if "<" in description and ">" in description:
        warn(skill_md, 3, "description appears to contain angle brackets; XML tags are not allowed")

    # 4. body length
    body_start = int(fields["__body_start__"])
    body_lines = len(lines) - body_start
    if body_lines > BODY_MAX_LINES:
        error(skill_md, body_start, f"body is {body_lines} lines, limit {BODY_MAX_LINES}")
    elif body_lines > BODY_WARN_LINES:
        warn(skill_md, body_start, f"body is {body_lines} lines, approaching the {BODY_MAX_LINES} limit")

    # 5. agents/openai.yaml
    oy = folder / "agents" / "openai.yaml"
    display_name = None
    if not oy.is_file():
        errors.append(f"skills/{name}: missing agents/openai.yaml")
    else:
        values = parse_openai_yaml(oy)
        for key in ("display_name", "short_description", "default_prompt"):
            if key not in values:
                error(oy, 1, f"missing `interface.{key}`")
        display_name = values.get("display_name")
        if display_name is not None:
            expected = expected_display_name(name)
            if display_name != expected:
                error(
                    oy,
                    int(values.get("__line__display_name", 1)),
                    f"display_name {display_name!r} should be {expected!r} (title-case of the folder name)",
                )
        prompt = values.get("default_prompt", "")
        if prompt and f"${declared}" not in prompt:
            error(
                oy,
                int(values.get("__line__default_prompt", 1)),
                f"default_prompt should reference `${declared}`",
            )

    # 6. the emitted report header must match the display name
    for i, raw in enumerate(lines, start=1):
        m = REPORT_HEADER_RE.match(raw.strip())
        if m and display_name is not None:
            title = m.group("title").strip()
            if title != display_name:
                error(skill_md, i, f"report header {title!r} does not match display_name {display_name!r}")

    # 7. referenced bundled paths must exist
    for i, raw in enumerate(lines, start=1):
        for rel in BUNDLED_PATH_RE.findall(raw):
            if not (folder / rel).exists():
                error(skill_md, i, f"references bundled path `{rel}` which does not exist in this skill")

    # 8. required sections
    if "## Agent Portability Notes" not in text:
        error(skill_md, 1, "missing required section `## Agent Portability Notes`")
    if "## Report Format" not in text and "## Required Output" not in text:
        error(skill_md, 1, "missing an output contract: add `## Report Format` or `## Required Output`")

    # 9. Related Skills must resolve
    for i, raw in enumerate(lines, start=1):
        m = RELATED_RE.match(raw)
        if m and m.group("skill") not in all_names:
            error(skill_md, i, f"`## Related Skills` points at `{m.group('skill')}`, which is not a skill in this repo")

    return description


def check_paths_and_links() -> None:
    """11. No machine-specific paths anywhere, and relative Markdown links must resolve."""
    bad_path = re.compile(r"[A-Za-z]:\\|/Users/[a-z]|/home/[a-z]|\\Users\\")
    this_file = Path(__file__).resolve()
    for path in sorted(REPO.rglob("*")):
        if ".git" in path.parts or not path.is_file():
            continue
        if path.suffix not in (".md", ".yaml", ".yml", ".py"):
            continue
        # This file defines the forbidden patterns, so scanning it would always self-report.
        if path.resolve() == this_file:
            continue
        for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if bad_path.search(raw):
                error(path, i, "contains a machine-specific absolute path; use repo-relative forward-slash paths")
            if path.suffix == ".md":
                for target in MD_LINK_RE.findall(raw):
                    target = target.split("#")[0].strip()
                    if not target or target.startswith(("http://", "https://", "mailto:", "#", "<")):
                        continue
                    if not (path.parent / target).exists():
                        error(path, i, f"relative link `{target}` does not resolve")


def check_readme(all_names: set[str]) -> None:
    """10. The README's skill table must list exactly the skills that exist."""
    readme = REPO / "README.md"
    if not readme.is_file():
        errors.append("README.md: missing")
        return
    listed = set(re.findall(r"^\|\s*`([a-z0-9-]+)`\s*\|", readme.read_text(encoding="utf-8"), re.MULTILINE))
    for missing in sorted(all_names - listed):
        errors.append(f"README.md: skill `{missing}` exists but is not listed in the skills table")
    for extra in sorted(listed - all_names):
        errors.append(f"README.md: table lists `{extra}`, which is not a skill directory")


def main() -> int:
    if not SKILLS_DIR.is_dir():
        print(f"error: {SKILLS_DIR} not found", file=sys.stderr)
        return 2

    folders = sorted(p for p in SKILLS_DIR.iterdir() if p.is_dir())
    if not folders:
        print("error: no skills found", file=sys.stderr)
        return 2
    all_names = {p.name for p in folders}

    descriptions: dict[str, str] = {}
    for folder in folders:
        description = check_skill(folder, all_names)
        if description:
            descriptions[folder.name] = description

    # 3b. shared always-resident budget
    total = sum(len(d) for d in descriptions.values())
    if total > DESCRIPTIONS_TOTAL_MAX:
        errors.append(
            f"descriptions total {total} chars across {len(descriptions)} skills, "
            f"budget {DESCRIPTIONS_TOTAL_MAX}. These are resident in the system prompt on every request."
        )

    check_readme(all_names)
    check_paths_and_links()

    for line in warnings:
        print(f"warning: {line}")
    for line in errors:
        print(f"error: {line}")

    print()
    print(f"{len(folders)} skills checked. Descriptions total {total}/{DESCRIPTIONS_TOTAL_MAX} chars.")
    if errors:
        print(f"FAILED: {len(errors)} error(s), {len(warnings)} warning(s).")
        return 1
    print(f"OK: 0 errors, {len(warnings)} warning(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
