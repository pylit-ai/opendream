# 435-opendream-automations

## Why
OpenDream needs a recurring automation layer for maintained projections such as feature candidates, bug radar, and fix queues, but those outputs should not be treated as canonical durable memory.

## Goal
Reuse the existing runtime machinery to run managed automation jobs that produce typed, reviewable projection records with explicit provenance and health.

## What Changes
- add canonical automation job specs and a dedicated automation output store
- add `opendream automation ...` commands for registration, execution, scheduling, and review
- surface automation health from top-level status and selected context assembly
- keep automation records separate from durable memory and product code mutation

## Success criteria
- recurring automation jobs are schedulable without inventing a new daemon model
- automation outputs remain auditable and clearly distinct from durable memory
- status and context can surface active automation records without obscuring core memory state
