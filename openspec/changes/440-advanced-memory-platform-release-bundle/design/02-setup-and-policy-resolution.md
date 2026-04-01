# 02-setup-and-policy-resolution.md

## Goal
Turn semantic setup from a docs scavenger hunt into one deterministic command.

## Setup report must include
- detected tools
- detected repo markers
- configured provider state
- candidate strategies
- recommended strategy
- unsupported/blocked strategies with reasons
- trust notes
- next steps and generated paths

## Policy rules
- user preference (`no-extra-key` vs `direct-provider`) influences ranking, not truthfulness
- unsupported paths remain visible as unsupported
- trusted/private vs public/untrusted environment affects recommendation
- no recommendation is made unless the return path into OpenDream is actually available
