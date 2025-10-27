#!/bin/bash

# Script to render ECOSTRESS STARS Data Products User Guide to PDF
# Requires pandoc and XeLaTeX

pandoc "ECOv003_L2_STARS_User_Guide.md" \
    --pdf-engine=xelatex \
    --variable mainfont="Arial Unicode MS" \
    --variable geometry="margin=1in" \
    --variable fontsize="11pt" \
    --variable linestretch="1.2" \
    --table-of-contents \
    --toc-depth=2 \
    --number-sections \
    --metadata title="ECOSTRESS STARS NDVI & Albedo User Guide" \
    -o "ECOv003_L2_STARS_User_Guide.pdf"

echo "PDF generated: ECOv003_L2_STARS_User_Guide.pdf"