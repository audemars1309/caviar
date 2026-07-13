"""Unit tests for deterministic text normalization."""

from __future__ import annotations

from app.services.resume_extraction.normalizer import normalize_text


class TestNormalizeText:
    def test_line_endings_normalized(self) -> None:
        assert normalize_text("a\r\nb\rc") == "a\nb\nc"

    def test_ligatures_folded_by_nfkc(self) -> None:
        assert normalize_text("e\ufb03cient \ufb01nance") == "efficient finance"

    def test_control_characters_removed_tabs_become_spaces(self) -> None:
        assert normalize_text("a\x00b\x0bc\td") == "abc d"

    def test_bullet_glyphs_become_dashes(self) -> None:
        assert normalize_text("\u2022 Built X\n\u25cf Shipped Y\n* Fixed Z") == (
            "- Built X\n- Shipped Y\n- Fixed Z"
        )

    def test_whitespace_runs_collapse(self) -> None:
        assert normalize_text("Python,    FastAPI\t\tPostgreSQL") == "Python, FastAPI PostgreSQL"

    def test_blank_line_runs_collapse(self) -> None:
        assert normalize_text("a\n\n\n\n\nb") == "a\n\nb"

    def test_content_is_never_altered(self) -> None:
        # Factual content with special characters must survive intact.
        text = "C++ and C# developer, 50% faster, $500 saved, R&D, user_name"
        assert normalize_text(text) == text

    def test_deterministic(self) -> None:
        raw = "\u2022 Item\r\nnext   line\n\n\n\nend\x00"
        assert normalize_text(raw) == normalize_text(raw)
        # Idempotent: normalizing normalized text is a no-op.
        assert normalize_text(normalize_text(raw)) == normalize_text(raw)
