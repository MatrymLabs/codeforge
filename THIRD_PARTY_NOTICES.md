# Third-Party Notices

CodeForge is MIT-licensed (see [LICENSE](LICENSE)); its own reusable parts record their
provenance in the Hardware Store. This file credits the third-party front-end assets the project
ships or loads, and retains their license notices as those licenses require.

## Vendored (checked into this repository)

### htmx (`parts/web/static/htmx.min.js`)
- Version: 2.x
- License: **BSD Zero-Clause License (0BSD)**
- Copyright: (c) the htmx authors
- Project: https://htmx.org/ (license: https://github.com/bigskysoftware/htmx/blob/master/LICENSE)

0BSD is a public-domain-equivalent license and imposes no attribution requirement; this notice is
courtesy, not obligation. The dashboard uses htmx directly (no CDN), so nothing is fetched at
runtime for it.

## Loaded from a CDN (the browser demo terminal, `parts/web/index.html`)

The WebSocket browser demo loads xterm.js from jsDelivr, pinned by version and by Subresource
Integrity (SRI) hash so a tampered CDN asset is rejected by the browser.

### xterm.js (`@xterm/xterm@5.5.0`) and @xterm/addon-fit (`@xterm/addon-fit@0.10.0`)
- License: **MIT**
- Copyright: (c) the xterm.js authors (https://github.com/xtermjs/xterm.js)
- Project: https://xtermjs.org/

MIT requires the copyright and permission notice to be retained; the standard MIT text follows.

```
MIT License

Copyright (c) the xterm.js authors

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
associated documentation files (the "Software"), to deal in the Software without restriction,
including without limitation the rights to use, copy, modify, merge, publish, distribute,
sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES
OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```
