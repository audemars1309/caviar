"""Unit tests for the deterministic LaTeX escaping/normalization boundary,
covering every content case mandated by the master spec plus injection
payloads."""

from __future__ import annotations

import pytest

from app.services.resume_generation.latex_escape import (
    escape_latex,
    normalize_for_latex,
    prepare_for_latex,
)


class TestEscapeLatex:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("C++", "C++"),  # + is not LaTeX-special; must pass through
            ("C#", r"C\#"),
            ("Node.js", "Node.js"),
            ("50% improvement", r"50\% improvement"),
            ("R&D", r"R\&D"),
            ("$500", r"\$500"),
            ("user_name", r"user\_name"),
            ("AI/ML", "AI/ML"),
            ("{braces}", r"\{braces\}"),
            ("100~200", r"100\textasciitilde{}200"),
            ("x^2", r"x\textasciicircum{}2"),
            (
                "https://example.com/a_b?x=1&y=2#top",
                r"https://example.com/a\_b?x=1\&y=2\#top",
            ),
        ],
    )
    def test_spec_mandated_cases(self, raw: str, expected: str) -> None:
        assert escape_latex(raw) == expected

    def test_backslash_single_pass_no_double_escaping(self) -> None:
        # Sequential-replace implementations turn "\" into
        # "\textbackslash\{\}" by re-matching inserted braces. The
        # single-pass mapping must not.
        assert escape_latex("\\") == r"\textbackslash{}"
        assert escape_latex(r"\&") == r"\textbackslash{}\&"

    def test_all_ten_special_characters_neutralized(self) -> None:
        escaped = escape_latex("\\ & % $ # _ { } ~ ^")
        assert escaped == (
            r"\textbackslash{} \& \% \$ \# \_ \{ \} "
            r"\textasciitilde{} \textasciicircum{}"
        )

    def test_command_injection_payloads_inert(self) -> None:
        for payload in (
            r"\input{/etc/passwd}",
            r"\write18{rm -rf /}",
            r"\immediate\openout\f=owned.txt",
            r"}{\Huge HIRED}\begin{comment}",
        ):
            escaped = escape_latex(payload)
            # No raw backslash-command or unescaped group delimiter survives.
            assert "\\input" not in escaped
            assert "\\write" not in escaped
            assert not any(
                ch in escaped.replace(r"\{", "").replace(r"\}", "").replace("{}", "")
                for ch in "{}"
            )

    def test_unicode_preserved(self) -> None:
        assert escape_latex("Zoë Müller — 東京 – naïve") == "Zoë Müller — 東京 – naïve"


class TestNormalizeForLatex:
    def test_control_characters_removed(self) -> None:
        assert normalize_for_latex("a\x00b\x0bc\x1bd") == "abcd"

    def test_tabs_and_newlines_become_single_spaces(self) -> None:
        assert normalize_for_latex("one\ttwo\nthree\r\nfour") == "one two three four"

    def test_nfc_composition(self) -> None:
        decomposed = "Zoe\u0308"  # e + combining diaeresis
        assert normalize_for_latex(decomposed) == "Zoë"

    def test_zero_width_format_characters_removed(self) -> None:
        assert normalize_for_latex("na\u200bme\u200d") == "name"


class TestPrepareForLatex:
    def test_normalize_then_escape(self) -> None:
        assert prepare_for_latex("R&D\tteam\x00 100%") == r"R\&D team 100\%"

    def test_deterministic(self) -> None:
        raw = "C# & $500 ~ x^2 \\ {ok}\u200b"
        assert prepare_for_latex(raw) == prepare_for_latex(raw)
