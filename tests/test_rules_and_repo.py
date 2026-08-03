"""Repo-consistency checks.

Rules attach to work by path glob. A typo in a glob means the rule silently
stops applying and nothing anywhere reports it, so these assert the wiring
actually points at things that exist.
"""
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
RULES = REPO / ".claude" / "rules"
SKILLS = REPO / ".claude" / "skills"
AGENTS = REPO / ".claude" / "agents"


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    _, block, _ = text.split("---", 2)
    data, key = {}, None
    for line in block.splitlines():
        if not line.strip():
            continue
        if re.match(r"^\s*-\s", line):
            data.setdefault(key, []).append(line.split("-", 1)[1].strip().strip('"\''))
        elif ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            data[key] = value.strip().strip('"\'') or []
    return data


def rule_files():
    return sorted(RULES.glob("*.md"))


class TestRuleGlobs:
    def test_rules_exist(self):
        assert rule_files(), "no rule files found"

    @pytest.mark.parametrize("rule", rule_files(), ids=lambda p: p.name)
    def test_every_rule_declares_paths(self, rule):
        assert frontmatter(rule).get("paths"), f"{rule.name} has no paths frontmatter"

    @pytest.mark.parametrize("rule", rule_files(), ids=lambda p: p.name)
    def test_every_glob_matches_something(self, rule):
        # A glob matching nothing is almost always a typo or a stale path from
        # a rename -- the rule then quietly never attaches.
        for pattern in frontmatter(rule)["paths"]:
            cleaned = pattern.rstrip("/*")
            matches = list(REPO.glob(pattern)) or list(REPO.glob(cleaned + "*"))
            if not matches:
                # Directory may legitimately be empty (gitignored profile data);
                # accept the parent existing.
                parent = REPO / Path(pattern.split("*")[0])
                matches = [parent] if parent.exists() else []
            assert matches, f"{rule.name}: glob '{pattern}' matches nothing"


class TestSkillsAndAgents:
    @pytest.mark.parametrize("skill", sorted(SKILLS.glob("*/SKILL.md")), ids=lambda p: p.parent.name)
    def test_skill_name_matches_its_directory(self, skill):
        assert frontmatter(skill).get("name") == skill.parent.name

    @pytest.mark.parametrize("skill", sorted(SKILLS.glob("*/SKILL.md")), ids=lambda p: p.parent.name)
    def test_skill_has_a_description(self, skill):
        assert frontmatter(skill).get("description")

    @pytest.mark.parametrize("agent", sorted(AGENTS.glob("*.md")), ids=lambda p: p.stem)
    def test_agent_name_matches_its_filename(self, agent):
        assert frontmatter(agent).get("name") == agent.stem

    def test_referenced_tools_exist(self):
        # Skills and rules cite tools by path; a rename would leave a dangling
        # instruction that fails only when someone runs the workflow.
        pattern = re.compile(r"tools/([a-z_]+\.py)")
        for doc in list(SKILLS.glob("*/SKILL.md")) + list(RULES.glob("*.md")) + [REPO / "CLAUDE.md"]:
            for name in set(pattern.findall(doc.read_text(encoding="utf-8"))):
                assert (REPO / "tools" / name).exists(), f"{doc.name} references missing tools/{name}"

    def test_referenced_schemas_exist(self):
        pattern = re.compile(r"schemas/([a-z-]+\.schema\.json)")
        for doc in list(SKILLS.glob("*/SKILL.md")) + list(RULES.glob("*.md")) + [REPO / "CLAUDE.md"]:
            for name in set(pattern.findall(doc.read_text(encoding="utf-8"))):
                assert (REPO / "schemas" / name).exists(), f"{doc.name} references missing schemas/{name}"


class TestConfidentiality:
    def test_no_profile_data_is_tracked_by_git(self):
        # Profile data lives on disk locally; what matters is that git does not
        # track it. Ask git rather than the filesystem.
        import subprocess
        try:
            out = subprocess.run(
                ["git", "ls-files", "data/profiles/"],
                cwd=REPO, capture_output=True, text=True, timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            pytest.skip("git unavailable")
        if out.returncode != 0:
            pytest.skip("not a git repository")
        tracked = [line for line in out.stdout.splitlines() if line.strip()]
        offenders = [t for t in tracked if not t.endswith(".gitkeep")]
        assert not offenders, f"personal data tracked by git: {offenders}"
