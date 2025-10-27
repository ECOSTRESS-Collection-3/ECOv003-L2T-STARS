#!/bin/bash

# Script to render the ECOv003 L2T STARS ATBD markdown to PDF
# Usage: ./ECOv003_L2_STARS_ATBD.sh

echo "Rendering ECOv003 L2T STARS ATBD to PDF..."

pandoc "ECOv003_L2_STARS_ATBD.md" \
    -o "ECOv003_L2_STARS_ATBD.pdf" \
    --pdf-engine=xelatex \
    -V "mainfont:Arial Unicode MS" \
    -V geometry:margin=1in \
    -V colorlinks=true \
    -V linkcolor=blue \
    -V fontsize=11pt \
    -V linestretch=1.15

if [ $? -eq 0 ]; then
    echo "✅ PDF successfully generated: ECOv003_L2_STARS_ATBD.pdf"
else
    echo "❌ Error generating PDF"
    exit 1
fi