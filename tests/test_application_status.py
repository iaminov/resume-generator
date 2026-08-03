"""Tests for the job-search status report."""
import json
from datetime import datetime, timedelta, timezone

import application_status as st
import common
import pytest

NOW = datetime(2030, 6, 1, tzinfo=timezone.utc)


def days_ago(n):
    return (NOW - timedelta(days=n)).strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def profile_root(tmp_path, monkeypatch):
    root = tmp_path / "profiles" / "jane-doe"
    for sub in ("applications", "output/output-generated-resumes", "output/output-cover-letters"):
        (root / sub).mkdir(parents=True)
    (root / "profile.json").write_text(
        json.dumps({"last_updated": "2030-05-01T00:00:00Z"}), encoding="utf-8"
    )
    monkeypatch.setattr(st, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(common, "PROFILES_DIR", tmp_path / "profiles")
    return root


def add_application(root, name, **fields):
    record = {
        "company": "Acme Corp",
        "role": "Backend Engineer",
        "status": "applied",
        "status_history": [{"status": "applied", "date": days_ago(5)}],
        "created_date": "2030-01-01",
    }
    record.update(fields)
    (root / "applications" / name).write_text(json.dumps(record), encoding="utf-8")
    return record


class TestQuietDetection:
    def test_recent_activity_is_not_quiet(self, profile_root):
        add_application(profile_root, "a.json",
                        status_history=[{"status": "applied", "date": days_ago(3)}])
        s = st.summarise("jane-doe", now=NOW)
        assert s["totals"]["quiet"] == 0

    def test_old_activity_is_quiet(self, profile_root):
        add_application(profile_root, "a.json",
                        status_history=[{"status": "applied", "date": days_ago(60)}])
        s = st.summarise("jane-doe", now=NOW)
        assert s["totals"]["quiet"] == 1
        assert s["applications"][0]["days_idle"] == 60

    def test_terminal_statuses_are_never_quiet(self, profile_root):
        for i, status in enumerate(("accepted", "rejected", "withdrawn")):
            add_application(profile_root, f"{i}.json", status=status,
                            status_history=[{"status": status, "date": days_ago(200)}])
        s = st.summarise("jane-doe", now=NOW)
        assert s["totals"]["quiet"] == 0
        assert s["totals"]["active"] == 0

    def test_already_dormant_statuses_are_not_double_reported(self, profile_root):
        add_application(profile_root, "a.json", status="ghosted",
                        status_history=[{"status": "ghosted", "date": days_ago(200)}])
        assert st.summarise("jane-doe", now=NOW)["totals"]["quiet"] == 0

    def test_threshold_is_configurable(self, profile_root):
        add_application(profile_root, "a.json",
                        status_history=[{"status": "applied", "date": days_ago(20)}])
        assert st.summarise("jane-doe", stale_days=30, now=NOW)["totals"]["quiet"] == 0
        assert st.summarise("jane-doe", stale_days=14, now=NOW)["totals"]["quiet"] == 1

    def test_the_most_recent_signal_wins(self, profile_root):
        # An old status change plus a recent log entry is not a quiet application.
        add_application(
            profile_root, "a.json",
            status_history=[{"status": "applied", "date": days_ago(90)}],
            activity_log=[{"date": days_ago(2), "entry": "Recruiter called"}],
        )
        s = st.summarise("jane-doe", now=NOW)
        assert s["totals"]["quiet"] == 0
        assert s["applications"][0]["days_idle"] == 2


class TestFollowUps:
    def test_overdue_is_reported(self, profile_root):
        add_application(profile_root, "a.json",
                        follow_ups=[{"due_date": days_ago(10), "action": "Send thank-you"}])
        s = st.summarise("jane-doe", now=NOW)
        assert s["totals"]["overdue_follow_ups"] == 1
        assert s["applications"][0]["overdue_follow_ups"][0]["days_overdue"] == 10

    def test_future_is_not_overdue(self, profile_root):
        future = (NOW + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        add_application(profile_root, "a.json",
                        follow_ups=[{"due_date": future, "action": "Check in"}])
        assert st.summarise("jane-doe", now=NOW)["totals"]["overdue_follow_ups"] == 0

    def test_completed_is_not_overdue(self, profile_root):
        add_application(profile_root, "a.json",
                        follow_ups=[{"due_date": days_ago(10), "action": "Done",
                                     "completed": True}])
        assert st.summarise("jane-doe", now=NOW)["totals"]["overdue_follow_ups"] == 0


class TestStaleDocuments:
    def test_document_older_than_the_profile_is_flagged(self, profile_root):
        (profile_root / "output/output-generated-resumes"
         / "Jane_Doe_acme_be_2030-04-01.docx").write_bytes(b"x")
        s = st.summarise("jane-doe", now=NOW)
        assert s["totals"]["stale_documents"] == 1
        assert s["stale_documents"][0]["days_behind_profile"] == 30

    def test_document_newer_than_the_profile_is_fine(self, profile_root):
        (profile_root / "output/output-generated-resumes"
         / "Jane_Doe_acme_be_2030-05-20.docx").write_bytes(b"x")
        assert st.summarise("jane-doe", now=NOW)["totals"]["stale_documents"] == 0

    def test_cover_letters_are_checked_too(self, profile_root):
        (profile_root / "output/output-cover-letters"
         / "Jane_Doe_acme_be_2030-04-01_cover-letter.docx").write_bytes(b"x")
        assert st.summarise("jane-doe", now=NOW)["totals"]["stale_documents"] == 1

    def test_a_file_without_a_date_is_ignored(self, profile_root):
        (profile_root / "output/output-generated-resumes" / "no_date_here.docx").write_bytes(b"x")
        assert st.summarise("jane-doe", now=NOW)["totals"]["stale_documents"] == 0


class TestRobustness:
    def test_unreadable_record_is_reported_not_fatal(self, profile_root):
        (profile_root / "applications" / "broken.json").write_text("{nope", encoding="utf-8")
        add_application(profile_root, "good.json")
        s = st.summarise("jane-doe", now=NOW)
        assert len(s["unreadable"]) == 1
        assert s["totals"]["applications"] == 1

    def test_empty_profile_produces_an_empty_report(self, profile_root):
        s = st.summarise("jane-doe", now=NOW)
        assert s["totals"]["applications"] == 0
        assert "Nothing needs attention" in st.render(s)

    def test_unknown_profile_raises(self, profile_root):
        with pytest.raises(ValueError, match="profile not found"):
            st.summarise("nobody", now=NOW)

    def test_render_produces_text(self, profile_root):
        add_application(profile_root, "a.json",
                        status_history=[{"status": "applied", "date": days_ago(60)}])
        text = st.render(st.summarise("jane-doe", now=NOW))
        assert "Acme Corp" in text and "gone quiet" in text


class TestDateParsing:
    @pytest.mark.parametrize("value", [
        "2030-01-01T00:00:00Z", "2030-01-01T00:00:00+00:00", "2030-01-01", "2030-01-01T12:30:00",
    ])
    def test_accepted_forms(self, value):
        assert st._parse(value) is not None

    @pytest.mark.parametrize("value", [None, "", "not a date"])
    def test_rejected_forms(self, value):
        assert st._parse(value) is None

    def test_naive_timestamps_are_treated_as_utc(self):
        assert st._parse("2030-01-01T00:00:00").tzinfo is not None
