"""Tests for schema validation and its schema inference."""
import json

import pytest
import validate


@pytest.fixture
def minimal_job_description():
    return {
        "company": "Acme Corp",
        "title": "Software Engineer",
        "required_skills": [{"skill": "Python"}],
        "captured_date": "2030-01-01",
    }


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class TestInferSchema:
    def test_profile_by_filename(self, tmp_path):
        assert validate.infer_schema(tmp_path / "profile.json") == "profile"

    def test_application_by_directory(self, tmp_path):
        path = tmp_path / "profiles" / "jane-doe" / "applications" / "rec.json"
        assert validate.infer_schema(path) == "application"

    def test_job_description_by_directory(self, tmp_path):
        path = tmp_path / "output" / "output-job-descriptions" / "acme_swe_2030-01-01.json"
        assert validate.infer_schema(path) == "job-description"

    def test_falls_back_to_content(self, tmp_path, minimal_job_description):
        path = write(tmp_path / "somewhere.json", minimal_job_description)
        assert validate.infer_schema(path) == "job-description"

    def test_unrecognisable_returns_none(self, tmp_path):
        path = write(tmp_path / "mystery.json", {"unrelated": True})
        assert validate.infer_schema(path) is None

    def test_unreadable_file_returns_none(self, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text("{not json", encoding="utf-8")
        assert validate.infer_schema(path) is None


class TestValidateFile:
    def test_valid_document_passes(self, tmp_path, minimal_job_description):
        path = write(tmp_path / "jd.json", minimal_job_description)
        result = validate.validate_file(path, "job-description")
        assert result["valid"], result.get("errors")

    def test_missing_file_reports_cleanly(self, tmp_path):
        result = validate.validate_file(tmp_path / "absent.json", "profile")
        assert not result["valid"]
        assert "not found" in result["error"]

    def test_malformed_json_reports_cleanly(self, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text("{not json", encoding="utf-8")
        result = validate.validate_file(path, "profile")
        assert not result["valid"]
        assert "invalid JSON" in result["error"]

    def test_undecidable_schema_asks_for_one(self, tmp_path):
        path = write(tmp_path / "mystery.json", {"unrelated": True})
        result = validate.validate_file(path)
        assert not result["valid"]
        assert "--schema" in result["error"]

    def test_wrong_type_is_reported_with_its_path(self, tmp_path, minimal_job_description):
        # The regression this tool exists for: a wrong type reaching a real
        # profile because nothing enforced validation. Note job_url is NOT the
        # example to use -- the schema explicitly permits null there.
        bad = dict(minimal_job_description, company=123)
        path = write(tmp_path / "jd.json", bad)
        result = validate.validate_file(path, "job-description")
        assert not result["valid"]
        assert any("company" in e["path"] for e in result["errors"])

    def test_nullable_field_accepts_null(self, tmp_path, minimal_job_description):
        # job_url is typed ["string", "null"]; a null there must NOT be an error.
        path = write(tmp_path / "jd.json", dict(minimal_job_description, job_url=None))
        assert validate.validate_file(path, "job-description")["valid"]

    def test_missing_required_field_fails(self, tmp_path):
        path = write(tmp_path / "jd.json", {"title": "Software Engineer"})
        result = validate.validate_file(path, "job-description")
        assert not result["valid"]

    def test_errors_are_capped(self, tmp_path):
        # A wholly wrong document should not dump hundreds of errors.
        path = write(tmp_path / "profile.json", {"skills": [{"bad": i} for i in range(60)]})
        result = validate.validate_file(path, "profile")
        assert not result["valid"]
        assert len(result["errors"]) <= 20


class TestSchemasThemselves:
    def test_every_schema_is_well_formed(self):
        import jsonschema
        for name in validate.SCHEMAS:
            jsonschema.Draft7Validator.check_schema(validate.load_schema(name))

    def test_all_three_schemas_are_present(self):
        assert set(validate.SCHEMAS) == {"profile", "application", "job-description"}
        for path in validate.SCHEMAS.values():
            assert path.exists(), path
