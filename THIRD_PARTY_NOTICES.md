# Third-Party Notices

This file documents third-party works referenced, adapted, or reused in OpenDream's semantic sleep-time mode and benchmark suite.

## Sleep-time Compute

- **Source**: Google DeepMind — Sleep-time Compute (2025)
- **License**: MIT
- **What we use**: Concepts and selective code patterns for offline semantic anticipation, query-family planning, and learned-context synthesis.
- **How we use it**: Direct reuse with attribution where applicable. MIT license terms are satisfied by this notice and in-code comments referencing the origin.

## MemoryAgentBench

- **Source**: MemoryAgentBench benchmark suite
- **License**: No clear open-source license at time of integration (2026-03)
- **What we use**: Competency definitions (Accurate Retrieval, Test-Time Learning, Long-Range Understanding, Conflict Resolution) as evaluation dimensions.
- **How we use it**: **Clean-room adapters only.** No code, fixtures, datasets, or prompts are vendored from the original repository. Our adapters (`opendream/benchmark_adapters.py`) implement the competency measurements independently using OpenDream's own retrieval and storage APIs. If an explicit permissive license is published, this policy may be revised.

## Meta-Harness

- **Source**: Meta-Harness environment bootstrap and optimization framework
- **License**: No clear open-source license at time of integration (2026-03)
- **What we use**: The concept of environment bootstrap capture and harness parameter optimization for coding-agent contexts.
- **How we use it**: **Clean-room adapters only.** No code is vendored. Our implementation (`opendream/harness_optimizer.py`) captures environment context and runs optimization independently. If an explicit permissive license is published, this policy may be revised.

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

- **MIT-licensed sources**: Selective reuse with attribution is permitted. Attribution appears in this file and in relevant source comments.
- **Unlicensed or ambiguously-licensed sources**: Clean-room adapter policy applies. We implement the same competency measurements or concepts but write all code independently, using only publicly documented APIs and definitions. No vendored code, fixtures, or prompts.
- **Updates**: If license status changes for any listed project, update this file and re-evaluate the adapter policy.
