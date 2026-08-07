"""Tests for the mechanical codebase inventory.

All fixture data is fictional, per the confidentiality rule -- these are
committed.

The contract this file mostly defends is a negative one: scan_codebase produces
counts and never judgments. A regression that started emitting skill names or
prose would break the "Claude IS the parser" rule in CLAUDE.md without breaking
anything that obviously looks like a test.
"""
import json
import shutil
import subprocess

import pytest
import scan_codebase as sc

HAS_GIT = shutil.which("git") is not None


def write(path, text=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def make_repo(root):
    """A small, plausible Python project."""
    write(root / "app.py", "def main():\n    return 1\n")
    write(root / "core" / "engine.py", "class Engine:\n    pass\n\n\nX = 1\n")
    write(
        root / "tests" / "test_engine.py",
        "def test_one():\n    assert True\n\n\ndef test_two():\n    assert True\n",
    )
    write(root / "README.md", "# Widget\n\nA widget service.\n")
    write(root / "requirements.txt", "flask~=3.0\nrequests>=2.0\n# comment\n")
    return root


class TestIsTestPath:
    @pytest.mark.parametrize(
        "relative",
        [
            "tests/test_thing.py",
            "test_thing.py",
            "thing_test.go",
            "src/__tests__/thing.js",
            "spec/thing_spec.rb",
            "thing.test.ts",
            "thing.spec.ts",
        ],
    )
    def test_recognized(self, tmp_path, relative):
        assert sc.is_test_path(tmp_path / relative)

    @pytest.mark.parametrize("relative", ["app.py", "src/latest.py", "contest.py"])
    def test_not_recognized(self, tmp_path, relative):
        assert not sc.is_test_path(tmp_path / relative)


class TestWalkSource:
    def test_skips_vendored_trees(self, tmp_path):
        make_repo(tmp_path)
        write(tmp_path / "node_modules" / "left-pad" / "index.js", "x\n")
        write(tmp_path / ".venv" / "lib" / "thing.py", "x\n")
        write(tmp_path / "__pycache__" / "app.cpython-311.pyc", "x\n")

        found = {p.name for p in sc.walk_source(tmp_path)}
        assert "app.py" in found
        assert "index.js" not in found
        assert "thing.py" not in found

    def test_skips_oversized_files(self, tmp_path):
        write(tmp_path / "small.py", "x = 1\n")
        write(tmp_path / "huge.py", "x\n" * (sc.MAX_FILE_BYTES // 2 + 10))
        found = {p.name for p in sc.walk_source(tmp_path)}
        assert found == {"small.py"}


class TestScanRepo:
    def test_counts_languages_and_lines(self, tmp_path):
        make_repo(tmp_path)
        result = sc.scan_repo(tmp_path)

        assert result["name"] == tmp_path.name
        assert result["languages"]["Python"]["files"] == 3
        assert result["languages"]["Python"]["lines"] > 0
        assert result["totals"]["files"] == 5

    def test_counts_test_files_and_symbols(self, tmp_path):
        make_repo(tmp_path)
        totals = sc.scan_repo(tmp_path)["totals"]
        assert totals["test_files"] == 1
        assert totals["test_symbols_approx"] == 2

    def test_code_lines_exclude_docs_and_config(self, tmp_path):
        make_repo(tmp_path)
        write(tmp_path / "big.md", "line\n" * 500)
        totals = sc.scan_repo(tmp_path)["totals"]
        assert totals["lines"] > totals["code_lines"]
        assert totals["code_lines"] < 100

    def test_reports_signal_files(self, tmp_path):
        make_repo(tmp_path)
        write(tmp_path / "Dockerfile", "FROM python:3.12\n")
        write(tmp_path / "manage.py", "# django\n")
        signals = sc.scan_repo(tmp_path)["signal_files"]
        assert "Dockerfile" in signals
        assert "manage.py" in signals

    def test_detects_github_actions(self, tmp_path):
        make_repo(tmp_path)
        write(tmp_path / ".github" / "workflows" / "ci.yml", "on: push\n")
        assert "GitHub Actions" in sc.scan_repo(tmp_path)["signal_files"]

    def test_readme_excerpt_is_truncated(self, tmp_path):
        make_repo(tmp_path)
        write(tmp_path / "README.md", "y" * (sc.README_CHARS + 500))
        assert len(sc.scan_repo(tmp_path)["readme_excerpt"]) == sc.README_CHARS

    def test_largest_files_are_ranked(self, tmp_path):
        make_repo(tmp_path)
        write(tmp_path / "big.py", "x = 1\n" * 200)
        largest = sc.scan_repo(tmp_path)["largest_files"]
        assert largest[0]["path"] == "big.py"
        assert largest[0]["lines"] >= largest[-1]["lines"]

    def test_binary_files_do_not_crash_the_scan(self, tmp_path):
        make_repo(tmp_path)
        (tmp_path / "logo.py").write_bytes(b"\xff\xfe\x00\x01binary")
        assert sc.scan_repo(tmp_path)["totals"]["files"] >= 5


class TestDependencies:
    def test_requirements_strips_specifiers_and_comments(self, tmp_path):
        make_repo(tmp_path)
        deps = sc.scan_repo(tmp_path)["dependencies"]
        assert deps["requirements.txt"] == ["flask", "requests"]

    def test_pyproject_reads_only_dependency_arrays(self, tmp_path):
        # Regression: matching every quoted string in the file also collected
        # console-script names and classifiers, reporting them as dependencies.
        write(
            tmp_path / "pyproject.toml",
            '[project]\n'
            'name = "widget"\n'
            'dependencies = [\n'
            '    "flask~=3.0",\n'
            '    "pydantic~=2.0",\n'
            ']\n\n'
            '[project.scripts]\n'
            'widget_cli = "widget.cli:main"\n',
        )
        deps = sc.parse_dependencies(tmp_path)
        assert deps["pyproject.toml"] == ["flask", "pydantic"]

    def test_package_json_merges_dev_dependencies(self, tmp_path):
        write(
            tmp_path / "package.json",
            json.dumps(
                {"dependencies": {"react": "^18"}, "devDependencies": {"vite": "^5"}}
            ),
        )
        assert sc.parse_dependencies(tmp_path)["package.json"] == ["react", "vite"]

    def test_malformed_package_json_is_survivable(self, tmp_path):
        write(tmp_path / "package.json", "{not json")
        assert "package.json" not in sc.parse_dependencies(tmp_path)

    def test_no_manifests_yields_nothing(self, tmp_path):
        write(tmp_path / "app.py", "x = 1\n")
        assert sc.parse_dependencies(tmp_path) == {}


@pytest.mark.skipif(not HAS_GIT, reason="git not available")
class TestGitAttribution:
    def commit(self, root, name, email, message):
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True,
                       capture_output=True)
        subprocess.run(
            ["git", "-C", str(root), "-c", f"user.name={name}",
             "-c", f"user.email={email}", "commit", "-m", message],
            check=True, capture_output=True,
        )

    def init(self, root):
        subprocess.run(["git", "-C", str(root), "init", "-q"], check=True,
                       capture_output=True)

    def test_non_repo_is_reported_not_guessed(self, tmp_path):
        make_repo(tmp_path)
        info = sc.scan_repo(tmp_path)["git"]
        assert info["is_repo"] is False
        assert info["authorship"] == "unestablished-no-git"

    def test_missing_git_does_not_imply_not_a_project(self, tmp_path):
        # Plenty of real work never gets `git init`. Treating those directories
        # as non-projects would silently drop them from the scan.
        make_repo(tmp_path)
        result = sc.scan_repo(tmp_path)
        assert result["totals"]["files"] == 5
        assert result["languages"]["Python"]["files"] == 3
        assert "ask the user" in result["git"]["note"]

    def test_counts_commits_per_author(self, tmp_path):
        make_repo(tmp_path)
        self.init(tmp_path)
        self.commit(tmp_path, "Jane Doe", "jane@example.com", "one")
        write(tmp_path / "more.py", "y = 2\n")
        self.commit(tmp_path, "Jane Doe", "jane@example.com", "two")
        write(tmp_path / "other.py", "z = 3\n")
        self.commit(tmp_path, "Sam Roe", "sam@example.com", "three")

        info = sc.scan_repo(tmp_path)["git"]
        assert info["commits"] == 3
        assert info["authors"][0] == {"name": "Jane Doe", "commits": 2}
        assert info["first_commit"] <= info["last_commit"]

    def test_author_share_is_computed_for_the_filter(self, tmp_path):
        make_repo(tmp_path)
        self.init(tmp_path)
        self.commit(tmp_path, "Jane Doe", "jane@example.com", "one")
        write(tmp_path / "more.py", "y = 2\n")
        self.commit(tmp_path, "Sam Roe", "sam@example.com", "two")

        info = sc.scan_repo(tmp_path, author="jane")["git"]
        assert info["author_commits"] == 1
        assert info["author_share"] == 0.5

    def test_author_match_is_case_insensitive_substring(self, tmp_path):
        make_repo(tmp_path)
        self.init(tmp_path)
        self.commit(tmp_path, "Jane Q. Doe", "jane@example.com", "one")
        assert sc.scan_repo(tmp_path, author="JANE")["git"]["author_commits"] == 1

    def test_multiple_identities_are_all_counted(self, tmp_path):
        # One person routinely commits under a full name on one machine and a
        # handle on another. Counting only one reports 0 commits for work they
        # entirely wrote, which reads as "not theirs".
        make_repo(tmp_path)
        self.init(tmp_path)
        self.commit(tmp_path, "Jane Doe", "jane@example.com", "one")
        write(tmp_path / "more.py", "y = 2\n")
        self.commit(tmp_path, "jdoe", "jane@example.com", "two")

        info = sc.scan_repo(tmp_path, author=["Jane Doe", "jdoe"])["git"]
        assert info["author_commits"] == 2
        assert info["author_share"] == 1.0
        assert "author_warning" not in info

    def test_zero_matches_emits_a_warning(self, tmp_path):
        make_repo(tmp_path)
        self.init(tmp_path)
        self.commit(tmp_path, "Sam Roe", "sam@example.com", "one")

        info = sc.scan_repo(tmp_path, author=["Jane Doe"])["git"]
        assert info["author_commits"] == 0
        assert "confirm authorship" in info["author_warning"]

    def test_out_creates_missing_parent_directories(self, tmp_path, monkeypatch, capsys):
        # A large --all run takes real time; losing it to a missing directory is
        # a bad trade for a check that costs nothing.
        make_repo(tmp_path)
        target = tmp_path / "nested" / "deeper" / "scan.json"
        monkeypatch.setattr(
            "sys.argv",
            ["scan_codebase.py", str(tmp_path), "--out", str(target)],
        )
        sc.main()
        capsys.readouterr()
        assert json.loads(target.read_text(encoding="utf-8"))["repo_count"] == 1


class TestFindRepos:
    def test_returns_project_subdirectories(self, tmp_path):
        for name in ("alpha", "beta"):
            write(tmp_path / name / "app.py", "x = 1\n")
        write(tmp_path / "node_modules" / "pkg" / "index.js", "x\n")
        (tmp_path / ".hidden").mkdir()

        names = [p.name for p in sc.find_repos(tmp_path)]
        assert names == ["alpha", "beta"]

    def test_includes_directories_without_git(self, tmp_path):
        # --all must not filter on the presence of .git; a project without one
        # is still a project and dropping it loses real work silently.
        write(tmp_path / "tracked" / "app.py", "x = 1\n")
        write(tmp_path / "untracked" / "app.py", "y = 2\n")
        assert [p.name for p in sc.find_repos(tmp_path)] == ["tracked", "untracked"]


class TestCollectAuthors:
    def test_aggregates_across_repos_with_appearances(self):
        repos = [
            {"name": "alpha", "git": {"authors": [
                {"name": "jdoe", "commits": 10},
                {"name": "Jane Doe", "commits": 4},
            ]}},
            {"name": "beta", "git": {"authors": [{"name": "jdoe", "commits": 5}]}},
        ]
        roster = sc.collect_authors(repos)
        assert roster[0] == {
            "name": "jdoe", "commits": 15, "repos": ["alpha", "beta"]
        }
        assert roster[1]["name"] == "Jane Doe"

    def test_repos_without_git_contribute_nothing(self):
        repos = [{"name": "alpha", "git": {"is_repo": False}}]
        assert sc.collect_authors(repos) == []


class TestScanOutput:
    def run_main(self, tmp_path, capsys, monkeypatch, *args):
        monkeypatch.setattr("sys.argv", ["scan_codebase.py", str(tmp_path), *args])
        sc.main()
        return json.loads(capsys.readouterr().out)

    def test_all_authors_roster_is_emitted(self, tmp_path, capsys, monkeypatch):
        write(tmp_path / "alpha" / "app.py", "x = 1\n")
        result = self.run_main(tmp_path, capsys, monkeypatch, "--all")
        assert "all_authors" in result

    def test_projects_without_git_are_listed(self, tmp_path, capsys, monkeypatch):
        for name in ("alpha", "beta"):
            write(tmp_path / name / "app.py", "x = 1\n")
        result = self.run_main(tmp_path, capsys, monkeypatch, "--all")
        assert result["repo_count"] == 2
        assert result["without_git_history"] == ["alpha", "beta"]


class TestMechanicalContract:
    """The script must never emit judgments -- that is Claude's job."""

    def test_output_carries_its_own_disclaimer(self, tmp_path, capsys, monkeypatch):
        make_repo(tmp_path)
        monkeypatch.setattr("sys.argv", ["scan_codebase.py", str(tmp_path)])
        sc.main()
        result = json.loads(capsys.readouterr().out)
        assert "Mechanical counts only" in result["note"]

    def test_no_skill_or_proficiency_fields_anywhere(self, tmp_path):
        make_repo(tmp_path)
        result = sc.scan_repo(tmp_path)
        # name and path echo back what the caller passed in, so they can contain
        # anything; everything else is generated and must stay judgment-free.
        for echoed in ("name", "path", "readme_excerpt"):
            result.pop(echoed, None)
        blob = json.dumps(result).lower()
        for forbidden in ("proficiency", "skill", "expert", "advanced", "resume"):
            assert forbidden not in blob, f"scan output contains judgment: {forbidden}"
