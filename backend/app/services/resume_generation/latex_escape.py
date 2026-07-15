"""The deterministic LaTeX escaping and normalization boundary (Phase 7).

THE ESCAPING BOUNDARY, EXACTLY: ``prepare_for_latex`` is called in exactly
one place - the renderer's context builder - on every string leaf of the
structured resume content, at the moment the Jinja rendering context is
assembled. Upstream of the boundary (DB, services, API) content is plain
data and is never escaped; downstream (Jinja context, templates, compiler
input) every string is already LaTeX-safe and is NEVER escaped again.
Templates must never apply additional escaping filters. One boundary, one
pass: double escaping is prevented by construction, not by heuristics
that try to detect already-escaped text.

Escaping is a deterministic single-pass character mapping (never
sequential ``str.replace`` calls, whose earlier substitutions can be
re-matched by later ones). All ten LaTeX-special characters are handled:

    \\   -> \\textbackslash{}      &  -> \\&      %  -> \\%
    $   -> \\$                    #  -> \\#      _  -> \\_
    {   -> \\{                    }  -> \\}
    ~   -> \\textasciitilde{}     ^  -> \\textasciicircum{}

Unicode is preserved, not transliterated: the compiler is Tectonic's
XeTeX engine, which is natively Unicode-capable, so accented names,
non-Latin scripts, and symbols pass through intact. Glyphs the template's
font stack cannot render surface later as structured
``UNSUPPORTED_GLYPHS`` warnings parsed from the engine log - a rendering
concern, deliberately not an escaping concern.

Normalization (before escaping): Unicode NFC (canonical composition -
XeTeX works best with composed forms), removal of control/format
characters (Cc/Cf) that are invalid in typeset text, with tabs and
newlines converted to single spaces (all v1 template fields are inline;
line structure comes from the template, never from embedded newlines).

User- and AI-generated content is untrusted. After this boundary no
content character can begin a LaTeX command, open or close a group,
switch modes, or terminate an argument - command injection through
resume content is structurally impossible, which is the point.
"""

from __future__ import annotations

import re
import unicodedata

_LATEX_SPECIAL_MAP: dict[str, str] = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}

_LATEX_SPECIAL_PATTERN = re.compile(r"[\\&%$#_{}~^]")


def normalize_for_latex(text: str) -> str:
    """Unicode NFC + control-character policy. Pure and deterministic."""
    normalized = unicodedata.normalize("NFC", text)
    characters: list[str] = []
    for ch in normalized:
        if ch in ("\n", "\r", "\t"):
            characters.append(" ")
        elif unicodedata.category(ch) in ("Cc", "Cf"):
            continue  # invalid in typeset text; removed explicitly
        else:
            characters.append(ch)
    return re.sub(r" {2,}", " ", "".join(characters)).strip()


def escape_latex(text: str) -> str:
    """Single-pass escaping of all LaTeX special characters."""
    return _LATEX_SPECIAL_PATTERN.sub(lambda m: _LATEX_SPECIAL_MAP[m.group(0)], text)


def prepare_for_latex(text: str) -> str:
    """normalize -> escape. The one function the escaping boundary calls."""
    return escape_latex(normalize_for_latex(text))
