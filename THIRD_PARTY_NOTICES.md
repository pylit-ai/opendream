# Third-Party Notices

This file lists third-party code and assets bundled with OpenDream. Research
inspiration and clean-room benchmark provenance are documented in
[`docs/provenance.md`](./docs/provenance.md).

---

## sigma.js (vendored under opendream/static/vendor/sigma.min.js)

- **Version**: 3.0.2
- **License**: MIT
- **Source**: https://cdnjs.cloudflare.com/ajax/libs/sigma.js/3.0.2/sigma.min.js

Copyright © 2013-2026 Alexis Jacomy, Guillaume Plique, and sigma.js contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## graphology (vendored under opendream/static/vendor/graphology.umd.min.js and opendream/static/vendor/graphology-layout-forceatlas2.min.js)

- **Version**: graphology 0.25.4, graphology-layout-forceatlas2 0.10.1
- **License**: MIT
- **Source**: https://cdnjs.cloudflare.com/ajax/libs/graphology/0.25.4/graphology.umd.min.js and npm:graphology-layout-forceatlas2@0.10.1

Copyright © 2017-2026 Guillaume Plique and graphology contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

## Policy

- **Bundled third-party code/assets**: Include license text or a clear license
  pointer here and keep source/version metadata current.
- **Research references**: Keep conceptual provenance in `docs/provenance.md`; do
  not list papers or external benchmark concepts here unless code, data, or
  assets are bundled.
- **Updates**: If bundled assets change, update this file and rerun
  `python scripts/check_vendor_assets.py`.
