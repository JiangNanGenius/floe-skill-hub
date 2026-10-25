# Font audit for the theme showcase

The pinned upstream `assets/theme-showcase.pdf` is retained byte-identical. A coordinator inspection corrected the earlier assumption that it contained no embedded fonts. `pdffonts` and the embedded TrueType name tables independently identify six embedded subsets; Helvetica is an unembedded PDF base font. No standalone font software is shipped or installed by this package.

| PDF font | Embedded | Version recorded in the font |
| --- | --- | --- |
| `/Helvetica` | no | base font |
| `/AAAAAA+DejaVuSans-Bold` | yes | Version 2.37 |
| `/AAAAAA+DejaVuSans` | yes | Version 2.37 |
| `/AAAAAA+DejaVuSerif-Bold` | yes | Version 2.37 |
| `/AAAAAA+FreeSerifBold` | yes | Version 0412.4271 |
| `/AAAAAA+FreeSans` | yes | Version 0412.4271 |
| `/AAAAAA+FreeSansBold` | yes | Version 0412.4271 |

The DejaVu subsets retain their Bitstream Vera / DejaVu copyright and permission notices. The GNU FreeFont subsets retain GPLv3-or-later notices and the font-embedding exception in the actual font name tables. `references/licenses/EMBEDDED-FONT-NOTICES.txt` preserves those strings and the applicable copyright notices; `references/licenses/GPL-3.0.txt` supplies the full GPL3 text. These font notices do not relicense the skill text or the Floe project.

The PDF is distributed as a document for display/printing, not as an extracted font package. GNU FreeFont explains this distinction and its embedding exception in its [license](https://www.gnu.org/software/freefont/license.html) and [FAQ](https://www.gnu.org/software/freefont/FAQ.html). The [DejaVu2.37 license](https://github.com/dejavu-fonts/dejavu-fonts/blob/version_2_37/LICENSE) is the reference for the DejaVu notices.

This record concerns the bundled PDF only. The theme presets name fonts rather than installing font software; when a selected font is absent, use an available licensed system font and tell the user.
