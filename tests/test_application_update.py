"""Tests for application record updates.

The rules being enforced -- legal transitions, append-only history, a timestamp
on every change -- are exactly the kind that get quietly re-derived and gotten
wrong when a person or a model edits JSON by hand.
"""
import json
from datetime import datetime

import pytest

import application_update as au


@pytest.fixture
def record():
    return {
        "person": "jane-doe",
        "company": "Acme Corp",
        "role": "Backend Engineer",
        "job_description_file": "output/output-job-descriptions/acme_be_2030-01-01.json",
        "resume_file": "output/output-generated-resumes/Jane_Doe_acme_be_2030-01-01.docx",
        "status": "draft",
        "status_history": [{"status": "draft", "date": "2030-01-01T00:00:00Z"}],
        "created_date": "2030-01-01",
    }


@pytest.fixture
def record_file(tmp_path, record):
    path = tmp_path / "2030-01-01_acme_backend-engineer.json"
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return path


class TestTransitionGraph:
    def test_every_status_in_the_schema_has_a_rule(self):
        schema = json.loads(
            (au.Path(__file__).resolve().parent.parent
             / "schemas" / "application.schema.json").read_text(encoding="utf-8")
        )
        for status in schema["properties"]["status"]["enum"]:
            assert status in au.TRANSITIONS, f"no transition rule for '{status}'"

    def test_every_destination_is_a_known_status(self):
        for source, targets in au.TRANSITIONS.items():
            for target in targets:
                assert target in au.TRANSITIONS, f"{source} -> unknown {target}"

    def test_terminal_states_are_what_we_expect(self):
        assert au.TERMINAL == {"accepted", "rejected", "withdrawn"}

    def test_ghosted_can_revive(self):
        # Employers do resurface; that should not need --force.
        assert au.TRANSITIONS["ghosted"], "ghosted must be recoverable"

    def test_no_status_transitions_to_itself(self):
        for source, targets in au.TRANSITIONS.items():
            assert source not in targets


class TestCheckTransition:
    def test_normal_move_is_allowed(self):
        assert au.check_transition("applied", "screening") is None

    def test_skipping_ahead_is_refused(self):
        with pytest.raises(ValueError, match="not a normal transition"):
            au.check_transition("draft", "accepted")

    def test_leaving_a_terminal_state_is_refused(self):
        with pytest.raises(ValueError, match="terminal"):
            au.check_transition("rejected", "offer")

    def test_force_allows_it_but_warns(self):
        warning = au.check_transition("rejected", "offer", force=True)
        assert warning and "forced" in warning

    def test_same_status_is_refused(self):
        with pytest.raises(ValueError, match="already at status"):
            au.check_transition("applied", "applied")

    def test_unknown_target_is_refused(self):
        with pytest.raises(ValueError, match="unknown status"):
            au.check_transition("applied", "banana")

    def test_unknown_current_is_refused(self):
        with pytest.raises(ValueError, match="unknown current status"):
            au.check_transition("banana", "applied")


class TestApplyStatus:
    def test_history_is_appended_never_rewritten(self, record):
        original = list(record["status_history"])
        au.apply_status(record, "ready")
        assert record["status_history"][: len(original)] == original
        assert len(record["status_history"]) == len(original) + 1

    def test_current_status_moves(self, record):
        au.apply_status(record, "ready")
        assert record["status"] == "ready"

    def test_every_entry_is_timestamped(self, record):
        au.apply_status(record, "ready")
        stamp = record["status_history"][-1]["date"]
        datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ")  # raises if malformed

    def test_notes_are_carried_through(self, record):
        au.apply_status(record, "ready", notes="looks good")
        assert record["status_history"][-1]["notes"] == "looks good"
        assert "looks good" in record["activity_log"][-1]["entry"]

    def test_status_change_is_journalled(self, record):
        au.apply_status(record, "ready")
        assert "draft" in record["activity_log"][-1]["entry"]
        assert "ready" in record["activity_log"][-1]["entry"]

    def test_last_updated_is_refreshed(self, record):
        au.apply_status(record, "ready")
        assert record["last_updated"] == record["status_history"][-1]["date"]

    def test_a_refused_move_leaves_the_record_untouched(self, record):
        snapshot = json.dumps(record, sort_keys=True)
        with pytest.raises(ValueError):
            au.apply_status(record, "accepted")
        assert json.dumps(record, sort_keys=True) == snapshot


class TestApplyLog:
    def test_entry_is_appended_with_a_timestamp(self, record):
        au.apply_log(record, "Recruiter called")
        assert record["activity_log"][-1]["entry"] == "Recruiter called"
        datetime.strptime(record["activity_log"][-1]["date"], "%Y-%m-%dT%H:%M:%SZ")

    def test_logging_does_not_touch_status(self, record):
        au.apply_log(record, "note")
        assert record["status"] == "draft"
        assert len(record["status_history"]) == 1


class TestAtomicWrite:
    def test_round_trips(self, tmp_path, record):
        path = tmp_path / "rec.json"
        au.write_atomically(path, record)
        assert json.loads(path.read_text(encoding="utf-8")) == record

    def test_no_temp_file_is_left_behind(self, tmp_path, record):
        path = tmp_path / "rec.json"
        au.write_atomically(path, record)
        assert list(tmp_path.iterdir()) == [path]

    def test_unicode_survives(self, tmp_path, record):
        record["activity_log"] = [{"date": "2030-01-01T00:00:00Z",
                                   "entry": "Status changed — café"}]
        path = tmp_path / "rec.json"
        au.write_atomically(path, record)
        assert "café" in path.read_text(encoding="utf-8")


class TestLoad:
    def test_missing_file_is_a_clear_error(self, tmp_path):
        with pytest.raises(ValueError, match="not found"):
            au.load(tmp_path / "absent.json")

    def test_malformed_json_is_a_clear_error(self, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text("{nope", encoding="utf-8")
        with pytest.raises(ValueError, match="invalid JSON"):
            au.load(path)

    def test_a_written_record_still_validates(self, record_file):
        from validate import validate_file
        record = au.load(record_file)
        au.apply_status(record, "ready")
        au.write_atomically(record_file, record)
        assert validate_file(record_file)["valid"], validate_file(record_file).get("errors")
