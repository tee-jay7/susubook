#!/usr/bin/env bash
# Substitute the student's details and rebuild the PDFs.
#
#   ./submission/finalise.sh "Full Name" "Student ID"
#
# Placeholders appear in exactly three places: docs/14-conclusion.md,
# submission/Deployment_and_Source_Links.txt, and the title page defined in
# submission/build_pdfs.py.

set -euo pipefail
NAME="${1:?usage: finalise.sh \"Full Name\" \"Student ID\"}"
ID="${2:?usage: finalise.sh \"Full Name\" \"Student ID\"}"
DATE="$(date '+%d %B %Y')"
cd "$(dirname "$0")/.."

for f in docs/14-conclusion.md submission/Deployment_and_Source_Links.txt submission/build_pdfs.py; do
  sed -i '' "s/\[STUDENT NAME\]/${NAME}/g; s/\[STUDENT ID\]/${ID}/g; s/\[DATE OF SUBMISSION\]/${DATE}/g" "$f"
  echo "  updated $f"
done

echo; echo "Rebuilding PDFs..."
python3 submission/build_pdfs.py

echo; echo "Remaining placeholders (should be none):"
grep -rn "\[STUDENT NAME\]\|\[STUDENT ID\]\|\[DATE OF SUBMISSION\]" docs submission 2>/dev/null || echo "  none"
