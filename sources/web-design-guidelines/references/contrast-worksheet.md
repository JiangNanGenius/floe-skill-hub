# Contrast Worksheet (deterministic)

WCAG relative-luminance method, computed by hand or by a staged stdlib script in the task's Linux environment.

## Steps per pair (text color F on background B)
1. Convert each channel c∈{R,G,B} (0–255) to s = c/255.
2. Linearize: if s ≤ 0.04045 → L_c = s/12.92; else L_c = ((s+0.055)/1.055)^2.4.
3. Luminance L = 0.2126·L_R + 0.7152·L_G + 0.0722·L_B.
4. Ratio = (L_lighter + 0.05) / (L_darker + 0.05). Round to one decimal.

## Thresholds
- Normal body text: ≥ 4.5:1. Large text (≥24 px, or ≥18.66 px bold): ≥ 3:1.
- UI component boundaries, icons, focus indicators (non-text contrast): ≥ 3:1.
- Disabled/decorative: exempt — but disabled-with-content still needs a text alternative when its meaning matters.

## Worked examples (verify your arithmetic with these)
- #777777 on #ffffff → L(#777)=0.1845, L(#fff)=1.0 → (1.05)/(0.2345) = 4.5:1 → passes body exactly at the line.
- #767676 on #ffffff → 4.54:1 pass; #787878 → 4.48:1 fail. Edge cases like this are why one decimal matters.

## Reporting a finding
Quote both colors as rendered (computed styles, not source hex if CSS variables differ), the ratio, the threshold used, element/role, and a fix that keeps the palette's meaning (darken ink or lighten surface, don't desaturate the accent below the icon threshold).
