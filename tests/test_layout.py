"""Tests for text metrics and density selection.

These are the parts most worth pinning: they are pure functions, and the
calibration constant in particular is an empirical value that could drift
without anything visibly breaking.
"""
import pytest
from generate_resume import (
    BODY_SIZE,
    DENSITIES,
    DENSITY_BY_NAME,
    ESTIMATE_CALIBRATION,
    NAME_SIZE,
    OPT_IN_DENSITIES,
    ROLE_TITLE_SIZE,
    SECTION_HEADING_SIZE,
    STRAGGLER_PAGE_FRACTION,
    choose_density,
    estimate_pages,
)
from layout import LINE_HEIGHT, text_width_pt, wrapped_lines


class TestWrappedLines:
    def test_short_text_is_one_line(self):
        assert wrapped_lines("hello world", 10, 500) == 1

    def test_empty_text_is_one_line(self):
        assert wrapped_lines("", 10, 500) == 1

    def test_long_text_wraps(self):
        assert wrapped_lines("word " * 200, 10, 200) > 1

    def test_narrower_column_wraps_more(self):
        text = "word " * 60
        assert wrapped_lines(text, 10, 200) > wrapped_lines(text, 10, 500)

    def test_larger_font_wraps_more(self):
        text = "word " * 60
        assert wrapped_lines(text, 14, 400) > wrapped_lines(text, 8, 400)

    def test_indent_reduces_available_width(self):
        text = "word " * 60
        assert wrapped_lines(text, 10, 400, indent_pt=100) >= wrapped_lines(text, 10, 400)

    def test_a_single_unbreakable_word_does_not_loop(self):
        # No space to break on: must still terminate and claim at least a line.
        assert wrapped_lines("x" * 500, 10, 50) >= 1


class TestTextWidth:
    def test_width_grows_with_length(self):
        assert text_width_pt("aaaa", 10) > text_width_pt("aa", 10)

    def test_width_grows_with_size(self):
        assert text_width_pt("hello", 20) > text_width_pt("hello", 10)

    def test_empty_string_has_no_width(self):
        assert text_width_pt("", 10) == pytest.approx(0, abs=0.01)


class TestEstimatePages:
    def test_short_resume_fits_one_page(self, short_resume):
        assert estimate_pages(short_resume, DENSITY_BY_NAME["normal"]) < 1.0

    def test_long_resume_needs_several(self, long_resume):
        assert estimate_pages(long_resume, DENSITY_BY_NAME["normal"]) > 2.0

    def test_tighter_density_never_costs_more_space(self, long_resume):
        estimates = [estimate_pages(long_resume, d) for d in DENSITIES]
        assert estimates == sorted(estimates, reverse=True), (
            "each preset should be at least as compact as the one before it"
        )

    def test_more_content_means_more_pages(self, short_resume):
        density = DENSITY_BY_NAME["normal"]
        before = estimate_pages(short_resume, density)
        bulked = dict(short_resume)
        bulked["experience"] = short_resume["experience"] * 8
        assert estimate_pages(bulked, density) > before

    def test_empty_sections_are_skipped(self, short_resume):
        density = DENSITY_BY_NAME["normal"]
        with_empties = dict(short_resume, projects=[], awards=[], publications=[])
        assert estimate_pages(with_empties, density) == pytest.approx(
            estimate_pages(short_resume, density)
        )

    def test_handles_a_nearly_empty_document(self):
        assert estimate_pages({"name": "Jane Doe"}, DENSITY_BY_NAME["normal"]) > 0


class TestChooseDensity:
    def test_explicit_request_is_honoured(self, short_resume):
        for name in DENSITY_BY_NAME:
            density, note = choose_density(short_resume, requested=name)
            assert density.name == name
            assert "explicit" in note

    def test_unknown_density_raises(self, short_resume):
        with pytest.raises(ValueError, match="unknown density"):
            choose_density(short_resume, requested="enormous")

    def test_no_goal_prefers_the_roomiest(self, short_resume):
        density, _ = choose_density(short_resume)
        assert density.name == "normal"

    def test_a_page_goal_picks_the_loosest_that_fits(self, long_resume):
        # The fixture needs ~2.6-2.8 pages, so 3 is reachable and 2 is not.
        density, note = choose_density(long_resume, target_pages=3)
        assert estimate_pages(long_resume, density) <= 3
        assert density.name == "normal", "should not tighten past what the goal needs"
        assert "loosest" in note

    def test_impossible_goal_falls_back_to_tightest_and_says_so(self, long_resume):
        density, note = choose_density(long_resume, target_pages=2)
        assert density.name == DENSITIES[-1].name
        assert "trim content" in note

    def test_generous_goal_keeps_the_roomiest(self, short_resume):
        density, _ = choose_density(short_resume, target_pages=5)
        assert density.name == "normal"


class TestOptInDensities:
    """`ultra` buys space with type size, which the formatting rules only allow
    when the candidate asks for it. The guarantee under test is that no code
    path reaches it on its own."""

    def test_ultra_is_registered_but_off_the_automatic_ladder(self):
        assert "ultra" in DENSITY_BY_NAME
        assert DENSITY_BY_NAME["ultra"] not in DENSITIES

    def test_automatic_selection_never_reaches_an_opt_in_preset(self, long_resume):
        # Three routes through choose_density: no goal, a goal the ladder can
        # meet, and a goal it cannot. The last is the dangerous one -- it falls
        # back to the tightest preset available, which is where a preset off
        # the ladder would leak in.
        for kwargs in ({}, {"target_pages": 3}, {"target_pages": 1}):
            density, _ = choose_density(long_resume, **kwargs)
            assert density not in OPT_IN_DENSITIES, kwargs
            assert density.font_scale == 1.0, kwargs

    def test_ultra_is_reachable_by_name(self, short_resume):
        density, note = choose_density(short_resume, requested="ultra")
        assert density.name == "ultra"
        assert "explicit" in note

    def test_ladder_presets_never_shrink_type(self):
        for d in DENSITIES:
            assert d.font_scale == 1.0, d.name

    def test_opt_in_presets_are_the_ones_that_shrink_type(self):
        for d in OPT_IN_DENSITIES:
            assert d.font_scale < 1.0, d.name

    def test_ultra_is_more_compact_than_the_tightest_ladder_preset(self, long_resume):
        assert estimate_pages(long_resume, DENSITY_BY_NAME["ultra"]) < estimate_pages(
            long_resume, DENSITIES[-1]
        )


class TestFontScaling:
    """Scaling has to preserve the size hierarchy, not just the sizes."""

    BASES = (NAME_SIZE, SECTION_HEADING_SIZE, ROLE_TITLE_SIZE, BODY_SIZE)

    def test_scaled_sizes_land_on_the_half_point_word_stores(self):
        ultra = DENSITY_BY_NAME["ultra"]
        for base in self.BASES:
            halves = ultra.pt(base).pt * 2
            assert halves == pytest.approx(round(halves)), base.pt

    def test_hierarchy_survives_scaling(self):
        # 11pt and 10.5pt scale to 10.45 and 9.975; rounding each on its own is
        # what keeps headings above role titles instead of merging them.
        name, heading, role, body = (DENSITY_BY_NAME["ultra"].pt(s).pt for s in self.BASES)
        assert name > heading > role > body, (name, heading, role, body)

    def test_unscaled_presets_leave_sizes_untouched(self):
        for d in DENSITIES:
            for base in self.BASES:
                assert d.pt(base).pt == pytest.approx(base.pt), (d.name, base.pt)

    def test_generated_document_carries_the_scaled_body_size(
        self, monkeypatch, tmp_path, short_resume
    ):
        import docx
        import generate_resume
        import layout
        monkeypatch.setattr(layout, "_render_pdf", lambda p: None)

        ultra = DENSITY_BY_NAME["ultra"]
        out = tmp_path / "ultra.docx"
        generate_resume.generate_resume(short_resume, out, density=ultra)

        rendered = docx.Document(str(out))
        assert rendered.styles["Normal"].font.size.pt == pytest.approx(ultra.pt(BODY_SIZE).pt)
        assert rendered.styles["Normal"].font.size.pt < BODY_SIZE.pt


class TestConstants:
    def test_calibration_compensates_upward(self):
        # Text-metric summing lands under what Word and LibreOffice produce, so
        # the factor must inflate. A value <= 1 would silently reintroduce the
        # straggler bug the render check exists to catch.
        assert ESTIMATE_CALIBRATION > 1.0

    def test_every_density_stays_within_the_documented_margins(self):
        # resume-formatting.md permits 0.5-0.75in. Tightening to win a page must
        # never produce a non-compliant document.
        for d in DENSITIES:
            assert 0.5 <= d.margin_in <= 0.75, d.name

    def test_densities_are_ordered_loosest_first(self):
        margins = [d.margin_in for d in DENSITIES]
        assert margins == sorted(margins, reverse=True)

    def test_straggler_fraction_is_a_small_proportion(self):
        assert 0 < STRAGGLER_PAGE_FRACTION < 0.5

    def test_line_height_is_plausible(self):
        assert 1.0 < LINE_HEIGHT < 1.5


class TestVerificationFallback:
    """Page verification is optional -- CI has no LibreOffice installed."""

    def test_verify_layout_reports_unknown_without_a_renderer(self, monkeypatch, tmp_path):
        import layout
        monkeypatch.setattr(layout, "_render_pdf", lambda p: None)
        assert layout.verify_layout(tmp_path / "anything.docx") == (None, None)

    def test_verify_page_count_reports_unknown_without_a_renderer(self, monkeypatch, tmp_path):
        import layout
        monkeypatch.setattr(layout, "_render_pdf", lambda p: None)
        assert layout.verify_page_count(tmp_path / "anything.docx") is None

    def test_generation_still_succeeds_without_a_renderer(self, monkeypatch, tmp_path, short_resume):
        import generate_resume
        import layout
        monkeypatch.setattr(layout, "_render_pdf", lambda p: None)
        out = tmp_path / "resume.docx"
        density, note, dropped = generate_resume.generate_resume(short_resume, out)
        assert out.exists() and out.stat().st_size > 0
        assert density.name in generate_resume.DENSITY_BY_NAME
        assert dropped == []


class TestEstimatorAccuracy:
    """Guard the calibration constant against drift.

    ESTIMATE_CALIBRATION was measured empirically against LibreOffice renders.
    It cannot be verified without a renderer, so these skip rather than fail on
    machines that lack one -- which includes CI.
    """

    def test_metrics_source_is_reported(self):
        import layout
        source = layout.metrics_source()
        assert source == "heuristic" or source.endswith(".ttf")

    def test_heuristic_fallback_still_measures_something(self, monkeypatch):
        import layout
        monkeypatch.setattr(layout, "_LOAD_FONT", None)
        assert layout.text_width_pt("hello", 10) > 0
        assert layout.wrapped_lines("word " * 100, 10, 200) > 1
        assert layout.metrics_source() == "heuristic"

    @pytest.mark.parametrize("fixture_name", ["short_resume", "long_resume"])
    def test_estimate_lands_near_the_real_render(self, request, tmp_path, fixture_name):
        import generate_resume
        import layout

        if layout._render_pdf(__file__) is None and not _renderer_available():
            pytest.skip("no LibreOffice available to verify against")

        data = request.getfixturevalue(fixture_name)
        density = DENSITY_BY_NAME["normal"]
        out = tmp_path / "check.docx"
        generate_resume.generate_resume(data, out, density=density)

        pages, _ = layout.verify_layout(out)
        if pages is None:
            pytest.skip("renderer unavailable")

        estimate = estimate_pages(data, density)
        # The estimate must land within one page of reality. Wider than that and
        # density selection starts making visibly wrong choices.
        assert abs(estimate - pages) < 1.0, (
            f"estimate {estimate:.2f} vs rendered {pages} -- "
            f"ESTIMATE_CALIBRATION ({ESTIMATE_CALIBRATION}) may need remeasuring"
        )


def _renderer_available():
    import shutil
    from pathlib import Path
    if shutil.which("soffice") or shutil.which("libreoffice"):
        return True
    return any(Path(c).exists() for c in (
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ))
