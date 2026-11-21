#!/usr/bin/env bash
#
# generate-sbom.sh — Software Bill of Materials for the autonomylogic:sam platform.
#
# This repository has no package manager for what it ships: build-release.py
# downloads the upstream SAM core and the board manager index points at Arduino's
# toolchain. So the SBOM is assembled from two sources:
#   - cdxgen, for what it can detect (GitHub Actions used to build and release,
#     Python requirements if any are ever added);
#   - security/components.json, the hand-maintained inventory of the core's
#     bundled code and of the toolchain, merged by scripts/merge-components.mjs,
#     which fails when it drifts from tools/ci/upstream.json.
#
# Produces under ./sbom/:
#   - <name>.cdx.json        CycloneDX 1.6
#   - <name>.spdx.json       SPDX 2.3
#   - <name>.components.csv  flattened component list with licences
#
# Usage:  ./scripts/generate-sbom.sh
# CI:     .github/workflows/security-sbom.yml, on every push to main.

set -euo pipefail
cd "$(dirname "$0")/.."

NAME="$(node -p "require('./security/report-config.json').sbomBasename")"
# The platform version is the release tag; between tags git describe names the commit.
VERSION="$(git describe --tags --always 2>/dev/null || echo unversioned)"
VERSION="${VERSION#v}"

OUT="sbom"
mkdir -p "$OUT"
RAW="$OUT/.cdxgen.cdx.json"
trap 'rm -f "$RAW"' EXIT

# Pinned so the SBOM is reproducible. Keep the version in ONE place and never
# paste it through a rendered web page: a previous edit turned the `cdxgen@…`
# reference into Cloudflare's email-obfuscation placeholder
# ("@cyclonedx/[email protected]"), which made this script abort on
# every run — invisibly, because the diagnostic was being sent to /dev/null.
CDXGEN_VERSION="11.11.0"

echo "==> Detecting components with cdxgen ${CDXGEN_VERSION} (-t github -t python) for ${NAME}@${VERSION}"
# stderr is kept: swallowing it means a failure here leaves no trace of WHY.
FETCH_LICENSE=true npx --yes "@cyclonedx/cdxgen@${CDXGEN_VERSION}" \
  -t github -t python \
  --spec-version 1.6 \
  -o "$RAW" \
  --project-name "$NAME" \
  --project-version "$VERSION" \
  .

echo "==> Merging the hand-maintained inventory (security/components.json)"
node scripts/merge-components.mjs "$RAW" security/components.json tools/ci/upstream.json "$VERSION" "$OUT/$NAME.cdx.json"

# CONTENT gate, not just a shape check — see scripts/assert-sbom.mjs. The floor is
# the inventory alone; cdxgen adds the GitHub Actions on top of it.
echo "==> Validating the SBOM has real content"
node scripts/assert-sbom.mjs "$OUT/$NAME.cdx.json" "${MIN_COMPONENTS:-15}"

echo "==> Converting to SPDX 2.3"
node scripts/cdx-to-spdx.mjs "$OUT/$NAME.cdx.json" "$OUT/$NAME.spdx.json"

echo "==> Emitting flattened CSV"
node scripts/cdx-to-csv.mjs "$OUT/$NAME.cdx.json" "$OUT/$NAME.components.csv"

echo "==> Done. Artifacts in ./$OUT/"
ls -la "$OUT"
