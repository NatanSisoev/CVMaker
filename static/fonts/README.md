# Self-hosted fonts

Latin-subset variable WOFF2 files from the [Fontsource](https://fontsource.org) packages
(`@fontsource-variable/inter`, `fraunces`, `jetbrains-mono`), all under the SIL Open Font
License 1.1. To refresh after bumping the npm packages:

    npm install
    cp node_modules/@fontsource-variable/inter/files/inter-latin-wght-normal.woff2 static/fonts/Inter-Variable.woff2
    cp node_modules/@fontsource-variable/fraunces/files/fraunces-latin-wght-normal.woff2 static/fonts/Fraunces-Variable.woff2
    cp node_modules/@fontsource-variable/jetbrains-mono/files/jetbrains-mono-latin-wght-normal.woff2 static/fonts/JetBrainsMono-Variable.woff2

Only the Latin range is shipped; other scripts fall back to system fonts.
