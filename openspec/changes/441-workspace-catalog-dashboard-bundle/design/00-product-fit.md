# 00-product-fit.md

## Why this aligns with the product

The North Star says OpenDream should be the default local-first memory substrate across multiple repos and runtimes. Without a central index of workspaces, the product forces operators to remember filesystem paths or manually search for `.opendream/` directories.

A workspace dashboard is therefore not a cosmetic extra. It is the natural operator-control surface for a multi-repo local memory substrate.

## Why this aligns with the Constitution

This feature is compatible with the Constitution if it obeys four rules:
1. machine-local only
2. derived, not canonical
3. explicit root scans, not hidden crawling
4. visible failures, not silent fallback

Done that way, it increases operator control and observability instead of weakening them.
