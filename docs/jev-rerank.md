# Optional Jev retrieval ordering

The ordinary `retrieve` command remains local and deterministic. An experimental,
per-invocation option can reorder up to eight records **within the already selected
baseline shortlist**. It cannot find additional memories, promote records, modify
trust, or bypass status/conflict rules. `prepare-context`, activation hooks and
background jobs do not enable this option.

First inspect the ordinary local retrieval output. Approve only memory titles and
summaries appropriate to share with TypeSafe, then explicitly approve each ID:

```sh
opendream retrieve --workspace . --query 'package dependency installation'
# Supply TYPESAFE_API_KEY through your approved secret mechanism before this call.
opendream retrieve --workspace . --query 'package dependency installation' \
  --jev-rerank --jev-allow-memory mem-example-a --jev-allow-memory mem-example-b
```

The flag authorizes sharing the query (first 1,000 characters). The repeatable ID
flag authorizes sharing that record's title (160 characters) and summary (400
characters). Memory IDs are replaced with temporary aliases. Bodies, provenance,
source events, file paths and credentials are not included in model state. Content
is untrusted evidence, not instructions. Explicit approval is required because
truncation is not redaction and a title/summary can contain private information.

Only active, conflict-free records with local confidence at least 0.4 qualify.
Records marked sensitive, or backed by stored source events with non-normal
sensitivity, remain local. Unknown/missing source sensitivity is not a privacy
classification: the operator's explicit ID approval remains necessary. Unapproved
records keep their original positions. With fewer than two approved candidates,
there is no request. Default runs never inspect credentials or contact Jev.

The adapter uses standard-library HTTPS to the fixed TypeSafe endpoint, model
`jev-1.13.0`, one request, no retries, a three-second socket timeout, and a 64 KiB
response limit. The timeout bounds stalled socket operations, not total wall time
against a server sending a continuous slow stream. This is an experimental,
operator-invoked route; it is not enabled for automatic context preparation.
Provider errors, missing credentials, unexpected models or IDs, malformed or
non-finite scores, inconsistent probability distributions, changed rubric legends,
and confidence below 0.5 all preserve the baseline. These thresholds are
conservative fallback rules, not measured accuracy or calibrated probabilities.

Opted-in results and retrieval audits add `rerank.jev` version 1, documented by
`jev-rerank.schema.json` and the `jev_rerank` contract-export version entry. It
contains `applied`, a fixed reason code, pinned model, baseline memory IDs and
approved candidate IDs, attempted request count, elapsed milliseconds, returned
model and validated provider token usage when available (never an invented cost).
Existing explanation scores still describe the local
baseline; Jev changes ordering only. The baseline can always be inspected there
or reproduced by omitting the flags. No content or provider exception is added
to logs, and no monetary or performance benefit is asserted.

Verification uses synthetic responses and temporary memory stores. Live provider
compatibility, quality, latency and cost have not been measured. Keep any later
evaluation data private and use a separately authorized budget.
