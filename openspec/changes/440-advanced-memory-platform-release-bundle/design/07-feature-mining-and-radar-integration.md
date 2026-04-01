# 07-feature-mining-and-radar-integration.md

## Goal
Make feature mining and radar setup portable across execution surfaces.

## Layers
- Layer A: durable capture
- Layer B: deterministic radar/projection jobs
- Layer C: semantic refresh / reconciliation

## This bundle adds
- adapter-specific Layer C scaffolds
- delegated return paths for feature/fix/bug mining
- setup commands that generate job specs and scheduling instructions
- explicit rule that projections remain non-canonical until promoted

## Why
A release that claims long-horizon coding memory but only works for one narrow local loop is not impressive; it is a weekend project with grandiose docs.
