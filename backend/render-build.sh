#!/usr/bin/env bash
#
# Render native Python runtime - install the Tectonic LaTeX compiler.
#
# The Python runtime has no apt/root, but whatever the build command writes
# into the service's source directory (/opt/render/project/src) is present at
# runtime. So we download the self-contained Tectonic static binary (single
# ~25MB musl executable, no TeX Live) into a vendored directory, verify it,
# and pre-warm its resource bundle so the first runtime compile does not have
# to reach Tectonic's bundle CDN.
#
# The app finds the binary via TECTONIC_BINARY_PATH (set in the Render
# environment to the absolute vendored path printed at the end of this
# script). Compilation reads the bundle cache from TECTONIC_CACHE_DIR.
#
# Usage (Render build command):
#   pip install -U pip && pip install . && ./render-build.sh
#
# Idempotent: re-running skips the download if the pinned binary is present.

set -euo pipefail

TECTONIC_VERSION="${TECTONIC_VERSION:-0.16.9}"
VENDOR_DIR="$(pwd)/.render/tectonic"
CACHE_DIR="$(pwd)/.render/tectonic-cache"
BIN="${VENDOR_DIR}/tectonic"
ASSET="tectonic-${TECTONIC_VERSION}-x86_64-unknown-linux-musl.tar.gz"
URL="https://github.com/tectonic-typesetting/tectonic/releases/download/tectonic%40${TECTONIC_VERSION}/${ASSET}"

mkdir -p "${VENDOR_DIR}" "${CACHE_DIR}"

if [ -x "${BIN}" ] && "${BIN}" --version >/dev/null 2>&1; then
    echo "Tectonic already vendored: $("${BIN}" --version)"
else
    echo "Downloading Tectonic ${TECTONIC_VERSION} ..."
    curl -fsSL "${URL}" -o /tmp/tectonic.tar.gz
    tar -xzf /tmp/tectonic.tar.gz -C "${VENDOR_DIR}" tectonic
    chmod +x "${BIN}"
    rm -f /tmp/tectonic.tar.gz
    echo "Installed: $("${BIN}" --version)"
fi

# Pre-warm the resource bundle into the vendored cache by compiling a document
# whose preamble matches the approved templates (documentclass article +
# geometry - the templates are "minimal package surface by design: geometry
# only"). This caches every package the real resume compiles need, so runtime
# compiles can run offline with TECTONIC_ONLY_CACHED=true.
#
# Best-effort: a transient bundle-CDN hiccup must NOT fail the whole deploy.
# If warming fails here, the binary is still installed and the cache warms
# lazily on the first runtime compile (which then needs CDN access - so keep
# TECTONIC_ONLY_CACHED=false until you confirm a warmed cache, see below).
echo "Pre-warming Tectonic bundle cache ..."
WARM_DIR="$(mktemp -d)"
# The warm document must exercise the SAME font sizes and shapes the approved
# templates use, or XeTeX will request an uncached Latin Modern variant at
# runtime (e.g. lmroman17 for \LARGE) and fail with "TFM file ... not found".
# caviar_classic uses: \LARGE + \bfseries (name), \large + \bfseries (section
# headings), \bfseries (entry/skill labels), \itshape (entry subs), itemize.
# Include one of each so every needed font/size/shape is pulled into the cache.
printf '%s' '\documentclass[10pt]{article}\usepackage[margin=1.6cm]{geometry}\setlength{\parindent}{0pt}\pagenumbering{gobble}\begin{document}{\LARGE Large Normal}\\{\LARGE\bfseries Large Bold}\\{\large Sub Normal}\\{\large\bfseries Sub Bold}\\\rule{\textwidth}{0.4pt}{\bfseries Bold} {\itshape Italic} normal\begin{itemize}\item bullet\end{itemize}\end{document}' > "${WARM_DIR}/warm.tex"
if HOME="${WARM_DIR}" TECTONIC_CACHE_DIR="${CACHE_DIR}" \
       "${BIN}" --outdir "${WARM_DIR}" --chatter minimal "${WARM_DIR}/warm.tex" \
       && [ -f "${WARM_DIR}/warm.pdf" ]; then
    WARMED=1
    echo "Bundle cache warmed at ${CACHE_DIR}"
else
    WARMED=0
    echo "WARNING: bundle pre-warm failed (binary is installed and usable)."
    echo "         The cache will populate on first runtime compile instead."
fi
rm -rf "${WARM_DIR}"

echo ""
echo "==> Set these in your Render service environment:"
echo "    TECTONIC_BINARY_PATH=${BIN}"
echo "    TECTONIC_CACHE_DIR=${CACHE_DIR}"
if [ "${WARMED}" = "1" ]; then
    echo "    TECTONIC_ONLY_CACHED=true    # cache is warmed; safe to run offline"
else
    echo "    TECTONIC_ONLY_CACHED=false   # cache NOT warmed; allow CDN at runtime"
fi
