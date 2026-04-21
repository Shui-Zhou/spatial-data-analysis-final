#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "$0")" && pwd)"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
HTML_URI="$(python3 -c 'import pathlib, sys; print(pathlib.Path(sys.argv[1]).resolve().as_uri())' "$SCRIPT_DIR/CW2_Final_Report.html")"

cd "$SCRIPT_DIR"

pandoc CW2_Draft.md \
  --from gfm \
  --resource-path=. \
  -o CW2_Final_Report.docx

pandoc CW2_Draft.md \
  --from gfm \
  --resource-path=. \
  --standalone \
  -V pagetitle="Spatial Variation in Airbnb Listing Counts across London" \
  -c export_styles.css \
  -o CW2_Final_Report.html

"$CHROME" \
  --headless=new \
  --disable-gpu \
  --allow-file-access-from-files \
  --no-pdf-header-footer \
  --print-to-pdf="$SCRIPT_DIR/CW2_Final_Report.pdf" \
  "$HTML_URI"

APPENDIX_HTML_URI="$(python3 -c 'import pathlib, sys; print(pathlib.Path(sys.argv[1]).resolve().as_uri())' "$SCRIPT_DIR/CW2_Appendix.html")"

pandoc CW2_Appendix.md \
  --from gfm \
  --resource-path=. \
  -o CW2_Appendix.docx

pandoc CW2_Appendix.md \
  --from gfm \
  --resource-path=. \
  --standalone \
  -V pagetitle="Appendix for CW2 Report" \
  -c export_styles.css \
  -o CW2_Appendix.html

"$CHROME" \
  --headless=new \
  --disable-gpu \
  --allow-file-access-from-files \
  --no-pdf-header-footer \
  --print-to-pdf="$SCRIPT_DIR/CW2_Appendix.pdf" \
  "$APPENDIX_HTML_URI"

cp "$SCRIPT_DIR/CW2_Final_Report.pdf" "$SCRIPT_DIR/K25120780_7CUSMSDA_Coursework.pdf"
cp "$SCRIPT_DIR/CW2_Appendix.pdf" "$SCRIPT_DIR/K25120780_7CUSMSDA_Appendix.pdf"

/usr/bin/python3 - "$SCRIPT_DIR" <<'PY'
import sys
from pypdf import PdfWriter, PdfReader
d = sys.argv[1]
w = PdfWriter()
for f in ("CW2_Final_Report.pdf", "CW2_Appendix.pdf"):
    for p in PdfReader(f"{d}/{f}").pages:
        w.add_page(p)
with open(f"{d}/CW2_Final_Report_with_Appendix.pdf", "wb") as out:
    w.write(out)
PY
