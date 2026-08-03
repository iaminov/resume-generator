"""Tests for schema versioning, profile isolation, diffing, and analytics."""
import json
from datetime import datetime, timedelta, timezone

import application_status as st
import common
import diff_content
import pytest
import validate

NOW = datetime(2030, 6, 1, tzinfo=timezone.utc)


def days_ago(n):
    return (NOW - timedelta(days=n)).strftime("%Y-%m-%dT%H:%M:%SZ")


def minimal_jd(**extra):
    record = {
        "company": "Acme Corp",
        "title": "Engineer",
        "required_skills": [{"skill": "Python"}],
        "captured_date": "2030-01-01",
    }
    record.update(extra)
    return record


class TestSchemaVersion:
    def test_every_schema_declares_the_field(self):
        for name in validate.SCHEMAS:
            assert "schema_version" in validate.load_schema(name)["properties"], name

    def test_version_is_major_minor(self):
        major, _, minor = common.SCHEMA_VERSION.partition(".")
        assert major.isdigit() and minor.isdigit()

    def test_missing_version_warns_but_does_not_fail(self, tmp_path):
        # Refusing to validate an unversioned document would block the very edit
        # that would add the version.
        path = tmp_path / "jd.json"
        path.write_text(json.dumps(minimal_jd()), encoding="utf-8")
        result = validate.validate_file(path, "job-description")
        assert result["valid"]
        assert "schema_version" in result["schema_version_warning"]

    def test_matching_version_produces_no_warning(self, tmp_path):
        path = tmp_path / "jd.json"
        path.write_text(
            json.dumps(minimal_jd(schema_version=common.SCHEMA_VERSION)), encoding="utf-8"
        )
        assert "schema_version_warning" not in validate.validate_file(path, "job-description")

    def test_major_mismatch_is_warned(self, tmp_path):
        path = tmp_path / "jd.json"
        path.write_text(json.dumps(minimal_jd(schema_version="99.0")), encoding="utf-8")
        result = validate.validate_file(path, "job-description")
        assert "99.0" in result["schema_version_warning"]

    def test_minor_difference_is_tolerated(self, tmp_path):
        major = common.SCHEMA_VERSION.split(".")[0]
        path = tmp_path / "jd.json"
        path.write_text(json.dumps(minimal_jd(schema_version=f"{major}.99")), encoding="utf-8")
        assert "schema_version_warning" not in validate.validate_file(path, "job-description")


class TestProfileIsolation:
    def test_env_var_overrides_the_file(self, tmp_path, monkeypatch):
        active = tmp_path / ".active-profile"
        active.write_text("from-file", encoding="utf-8")
        monkeypatch.setattr(common, "ACTIVE_PROFILE_FILE", active)
        monkeypatch.setenv(common.PROFILE_ENV_VAR, "from-env")
        assert common.get_active_slug() == "from-env"

    def test_file_is_used_when_env_is_unset(self, tmp_path, monkeypatch):
        active = tmp_path / ".active-profile"
        active.write_text("from-file", encoding="utf-8")
        monkeypatch.setattr(common, "ACTIVE_PROFILE_FILE", active)
        monkeypatch.delenv(common.PROFILE_ENV_VAR, raising=False)
        assert common.get_active_slug() == "from-file"

    def test_blank_env_falls_through_to_the_file(self, tmp_path, monkeypatch):
        active = tmp_path / ".active-profile"
        active.write_text("from-file", encoding="utf-8")
        monkeypatch.setattr(common, "ACTIVE_PROFILE_FILE", active)
        monkeypatch.setenv(common.PROFILE_ENV_VAR, "   ")
        assert common.get_active_slug() == "from-file"

    def test_explicit_slug_beats_everything(self, monkeypatch):
        monkeypatch.setenv(common.PROFILE_ENV_VAR, "from-env")
        assert common.resolve_slug("explicit") == "explicit"

    def test_sole_profile_is_used_when_nothing_is_set(self, tmp_path, monkeypatch):
        profiles = tmp_path / "profiles"
        (profiles / "only-one").mkdir(parents=True)
        monkeypatch.setattr(common, "PROFILES_DIR", profiles)
        monkeypatch.setattr(common, "ACTIVE_PROFILE_FILE", tmp_path / "absent")
        monkeypatch.delenv(common.PROFILE_ENV_VAR, raising=False)
        assert common.resolve_slug() == "only-one"

    def test_ambiguity_raises_with_guidance(self, tmp_path, monkeypatch):
        profiles = tmp_path / "profiles"
        for name in ("one", "two"):
            (profiles / name).mkdir(parents=True)
        monkeypatch.setattr(common, "PROFILES_DIR", profiles)
        monkeypatch.setattr(common, "ACTIVE_PROFILE_FILE", tmp_path / "absent")
        monkeypatch.delenv(common.PROFILE_ENV_VAR, raising=False)
        with pytest.raises(ValueError, match="pass --slug"):
            common.resolve_slug()

    def test_no_profiles_raises(self, tmp_path, monkeypatch):
        profiles = tmp_path / "profiles"
        profiles.mkdir()
        monkeypatch.setattr(common, "PROFILES_DIR", profiles)
        monkeypatch.setattr(common, "ACTIVE_PROFILE_FILE", tmp_path / "absent")
        monkeypatch.delenv(common.PROFILE_ENV_VAR, raising=False)
        with pytest.raises(ValueError, match="no profiles exist"):
            common.resolve_slug()


class TestDiffContent:
    def test_identical_documents_report_nothing(self, short_resume):
        rendered = diff_content.render(
            diff_content.compare(short_resume, short_resume), "a", "b"
        )
        assert rendered.strip().endswith("No differences.")

    def test_summary_change_is_detected(self, short_resume):
        changed = dict(short_resume, summary="Something else entirely.")
        assert diff_content.compare(short_resume, changed)["summary"]

    def test_added_skill_is_detected(self, short_resume):
        changed = json.loads(json.dumps(short_resume))
        changed["skills"][0]["items"].append("Rust")
        result = diff_content.compare(short_resume, changed)
        assert "Rust" in result["skills"]["Languages"]["added"]

    def test_removed_bullet_is_detected(self, short_resume):
        changed = json.loads(json.dumps(short_resume))
        dropped = changed["experience"][0]["bullets"].pop()
        entry = diff_content.compare(short_resume, changed)["sections"]["experience"][
            "Software Engineer — Acme Corp"
        ]
        assert dropped in entry["removed"]

    def test_a_reworded_bullet_pairs_rather_than_double_counting(self, short_resume):
        changed = json.loads(json.dumps(short_resume))
        changed["experience"][0]["bullets"][0] = "Built a thing, and shipped it."
        entry = diff_content.compare(short_resume, changed)["sections"]["experience"][
            "Software Engineer — Acme Corp"
        ]
        assert entry.get("reworded"), "a small edit should read as a rewording"

    def test_removed_role_is_detected(self, short_resume):
        changed = json.loads(json.dumps(short_resume))
        changed["experience"] = []
        entry = diff_content.compare(short_resume, changed)["sections"]["experience"]
        assert entry["Software Engineer — Acme Corp"]["status"] == "removed"

    def test_layout_change_is_detected(self, short_resume):
        changed = dict(short_resume, layout={"target_pages": 2})
        assert diff_content.compare(short_resume, changed)["layout"]

    def test_cover_letter_bodies_compare(self, cover_letter):
        changed = json.loads(json.dumps(cover_letter))
        changed["body"].append("A third paragraph.")
        result = diff_content.compare(cover_letter, changed)
        assert "A third paragraph." in result["sections"]["body"]["added"]

    def test_missing_file_is_a_clear_error(self, tmp_path):
        with pytest.raises(ValueError, match="not found"):
            diff_content.load(tmp_path / "absent.json")

    def test_malformed_json_is_a_clear_error(self, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text("{nope", encoding="utf-8")
        with pytest.raises(ValueError, match="invalid JSON"):
            diff_content.load(path)


class TestAnalytics:
    @pytest.fixture
    def profile_root(self, tmp_path, monkeypatch):
        root = tmp_path / "profiles" / "jane-doe"
        (root / "applications").mkdir(parents=True)
        monkeypatch.setattr(st, "PROFILES_DIR", tmp_path / "profiles")
        return root

    @staticmethod
    def add(root, name, status, history, **extra):
        record = {
            "company": "Acme Corp", "role": "Engineer", "status": status,
            "status_history": history, "created_date": "2030-01-01",
        }
        record.update(extra)
        (root / "applications" / name).write_text(json.dumps(record), encoding="utf-8")

    def test_empty_profile_produces_no_rates(self, profile_root):
        result = st.analytics("jane-doe", now=NOW)
        assert result["counts"]["submitted"] == 0
        assert result["rates"]["interview_per_submission"] is None

    def test_interview_rate(self, profile_root):
        self.add(profile_root, "a.json", "phone_interview", [
            {"status": "applied", "date": days_ago(30)},
            {"status": "phone_interview", "date": days_ago(20)}])
        self.add(profile_root, "b.json", "rejected", [
            {"status": "applied", "date": days_ago(30)},
            {"status": "rejected", "date": days_ago(25)}])
        result = st.analytics("jane-doe", now=NOW)
        assert result["counts"]["submitted"] == 2
        assert result["rates"]["interview_per_submission"] == 0.5

    def test_days_to_first_response(self, profile_root):
        self.add(profile_root, "a.json", "rejected", [
            {"status": "applied", "date": days_ago(30)},
            {"status": "rejected", "date": days_ago(20)}])
        assert st.analytics("jane-doe", now=NOW)["days_to_first_response"]["median"] == 10

    def test_draft_records_are_not_counted_as_submitted(self, profile_root):
        self.add(profile_root, "a.json", "draft", [{"status": "draft", "date": days_ago(5)}])
        assert st.analytics("jane-doe", now=NOW)["counts"]["submitted"] == 0

    def test_source_breakdown(self, profile_root):
        self.add(profile_root, "a.json", "phone_interview", [
            {"status": "applied", "date": days_ago(30)},
            {"status": "phone_interview", "date": days_ago(20)}], source="referral")
        assert st.analytics("jane-doe", now=NOW)["by_source"]["referral"]["interviewed"] == 1

    def test_unreadable_record_does_not_break_analytics(self, profile_root):
        (profile_root / "applications" / "broken.json").write_text("{nope", encoding="utf-8")
        assert st.analytics("jane-doe", now=NOW)["counts"]["records"] == 0

    def test_unknown_profile_raises(self, profile_root):
        with pytest.raises(ValueError, match="profile not found"):
            st.analytics("nobody", now=NOW)

    def test_the_caveat_travels_with_the_numbers(self, profile_root):
        # These figures must never reach a resume; resume-writing.md forbids it.
        assert "never appear on a resume" in st.analytics("jane-doe", now=NOW)["caveat"]


class TestDryRun:
    def test_resume_dry_run_writes_nothing(self, tmp_path, short_resume, monkeypatch):
        import sys

        import generate_resume
        content = tmp_path / "c.json"
        content.write_text(json.dumps(short_resume), encoding="utf-8")
        out = tmp_path / "should-not-exist.docx"
        monkeypatch.setattr(sys, "argv",
                            ["generate_resume.py", str(content), str(out), "--dry-run"])
        generate_resume.main()
        assert not out.exists()

    def test_cover_letter_dry_run_writes_nothing(self, tmp_path, cover_letter, monkeypatch):
        import sys

        import generate_cover_letter
        content = tmp_path / "c.json"
        content.write_text(json.dumps(cover_letter), encoding="utf-8")
        out = tmp_path / "should-not-exist.docx"
        monkeypatch.setattr(sys, "argv",
                            ["generate_cover_letter.py", str(content), str(out), "--dry-run"])
        generate_cover_letter.main()
        assert not out.exists()

    def test_dry_run_reports_the_density_it_would_use(self, tmp_path, capsys, short_resume, monkeypatch):
        import sys

        import generate_resume
        content = tmp_path / "c.json"
        content.write_text(json.dumps(short_resume), encoding="utf-8")
        monkeypatch.setattr(sys, "argv", [
            "generate_resume.py", str(content), str(tmp_path / "x.docx"),
            "--dry-run", "--target-pages", "1",
        ])
        generate_resume.main()
        report = json.loads(capsys.readouterr().out)
        assert report["status"] == "dry_run"
        assert report["layout"]["density"] in ("normal", "compact", "dense")
