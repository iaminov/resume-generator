"""Tests for shared path helpers, slug generation, and cover-letter counting."""
import common
import pytest
from generate_cover_letter import word_count
from profile_create import name_to_slug


@pytest.fixture
def isolated_data(tmp_path, monkeypatch):
    """Point the active-profile helpers at a temp dir, never the real one."""
    active = tmp_path / ".active-profile"
    monkeypatch.setattr(common, "ACTIVE_PROFILE_FILE", active)
    monkeypatch.setattr(common, "PROFILES_DIR", tmp_path / "profiles")
    return active


class TestActiveSlug:
    def test_missing_file_reads_as_unset(self, isolated_data):
        assert common.get_active_slug() is None

    def test_empty_file_reads_as_unset(self, isolated_data):
        # profile_delete blanks the file rather than removing it, so absent and
        # empty must be indistinguishable to callers.
        isolated_data.write_text("", encoding="utf-8")
        assert common.get_active_slug() is None

    def test_whitespace_only_reads_as_unset(self, isolated_data):
        isolated_data.write_text("   \n", encoding="utf-8")
        assert common.get_active_slug() is None

    def test_round_trip(self, isolated_data):
        common.set_active_slug("jane-doe")
        assert common.get_active_slug() == "jane-doe"

    def test_trailing_newline_is_stripped(self, isolated_data):
        isolated_data.write_text("jane-doe\n", encoding="utf-8")
        assert common.get_active_slug() == "jane-doe"

    def test_clearing_unsets(self, isolated_data):
        common.set_active_slug("jane-doe")
        common.set_active_slug("")
        assert common.get_active_slug() is None

    def test_set_creates_missing_parent(self, tmp_path, monkeypatch):
        nested = tmp_path / "does" / "not" / "exist" / ".active-profile"
        monkeypatch.setattr(common, "ACTIVE_PROFILE_FILE", nested)
        common.set_active_slug("jane-doe")
        assert common.get_active_slug() == "jane-doe"


class TestNameToSlug:
    @pytest.mark.parametrize("name,expected", [
        ("Jane Doe", "jane-doe"),
        ("JANE DOE", "jane-doe"),
        ("  Jane   Doe  ", "jane-doe"),
        ("Jane O'Doe", "jane-odoe"),
        ("Jane Doe-Smith", "jane-doe-smith"),
        ("Jane Doe 3rd", "jane-doe-3rd"),
        ("Jane.Doe", "janedoe"),
    ])
    def test_slugs(self, name, expected):
        assert name_to_slug(name) == expected

    def test_slug_has_no_path_separators(self):
        # A slug becomes a directory name; separators would escape the profile root.
        for name in ("Jane/Doe", "Jane\\Doe", "../Jane"):
            slug = name_to_slug(name)
            assert "/" not in slug and "\\" not in slug and ".." not in slug


class TestRelativeToRoot:
    def test_path_inside_root_is_relativised(self):
        result = common.relative_to_root(common.PROJECT_ROOT / "tools" / "common.py")
        assert "tools" in result
        assert str(common.PROJECT_ROOT) not in result

    def test_path_outside_root_is_returned_whole(self, tmp_path):
        assert common.relative_to_root(tmp_path) == str(tmp_path)


class TestCoverLetterWordCount:
    def test_counts_across_paragraphs(self):
        assert word_count({"body": ["one two", "three four five"]}) == 5

    def test_accepts_a_plain_string(self):
        assert word_count({"body": "one two three"}) == 3

    def test_missing_body_is_zero(self):
        assert word_count({}) == 0
