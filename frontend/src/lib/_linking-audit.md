# Linking audit (stage 10)

Internal working doc. Lists every entity reference rendered by the SPA, whether it
was clickable before this stage, and the click target wired up after.

Legend
  D = dead text before stage 10
  L = already a link/button
  →  click target after stage 10

## /overview (Overview.tsx)

| Site                                             | Before | After                                                |
| ------------------------------------------------ | ------ | ---------------------------------------------------- |
| Stat: Durable count                              | D      | → /memories?status=active                            |
| Stat: Contested count                            | D      | → /memories?status=contested                         |
| Stat: Learned active                             | D      | → /memories?status=learned                           |
| Stat: Recently pruned                            | D      | → /memories?status=pruned                            |
| Stat: Retrievals                                 | D      | → /retrievals                                        |
| Posture chip                                     | D      | → /settings                                          |
| Recent activity row (kind=run)                   | D      | → /runs?id=<run_id>                                  |
| Recent activity row (kind=retrieval)             | D      | → /retrievals?id=<id>                                |
| Recent activity row (kind=session)               | D      | → /sessions?id=<id>                                  |
| Recent activity row · agent text                 | D      | → /runs?agent=<name> (separate click)                |
| Recent activity row · status chip                | D      | → /runs?status=<status>                              |
| Memory highlight row (memory_id)                 | D      | → /memories?id=<id> (IdLink)                         |
| Memory highlight row · type chip                 | D      | → /memories?type=<type>                              |

## /memories surface (Memories.tsx)

| Site                            | Before | After                                  |
| ------------------------------- | ------ | -------------------------------------- |
| Memory ID column                | L      | unchanged (IdLink → inspector)         |
| Status chip                     | D      | → /memories?status=<status>            |
| Type column                     | D      | → /memories?type=<type>                |
| Agent column                    | D      | → /runs?agent=<id>                     |
| Stat strip durable/contested/…  | D      | clickable → status filters             |
| Deep link `?id=<id>`            | —      | auto-open inspector                    |

## /runs (Runs.tsx)

| Site                            | Before | After                              |
| ------------------------------- | ------ | ---------------------------------- |
| Run ID column                   | L      | also pushes `?id=<id>` to URL      |
| Agent column                    | D      | → /runs?agent=<id>                 |
| Kind column                     | D      | → /runs?kind=<kind>                |
| Status chip                     | D      | → /runs?status=<status>            |
| Memory op IDs in inspector      | L      | unchanged                          |
| Filter URL sync (agent, search) | —      | URL ↔ filters bidirectional        |
| Deep link `?id=<id>`            | —      | auto-open inspector                |

## /retrievals (Retrievals.tsx)

| Site                            | Before | After                              |
| ------------------------------- | ------ | ---------------------------------- |
| Retrieval ID column             | L      | also pushes `?id=<id>` to URL      |
| Agent column                    | D      | → /retrievals?agent=<id>           |
| Memory IDs in scoring breakdown | L      | unchanged                          |
| Filter URL sync (agent, search) | —      | URL ↔ filters bidirectional        |
| Deep link `?id=<id>`            | —      | auto-open inspector                |

## /sessions (Sessions.tsx)

| Site                            | Before | After                              |
| ------------------------------- | ------ | ---------------------------------- |
| Session ID column               | L      | pushes `?id=<id>` to URL           |
| Agent column                    | D      | → /sessions?agent=<id>             |
| Timeline event object_id        | L      | unchanged                          |
| Deep link `?id=<id>`            | —      | auto-open timeline                 |

## /reviews (Reviews.tsx)

| Site                            | Before | After                              |
| ------------------------------- | ------ | ---------------------------------- |
| Item ID column                  | L      | also pushes `?id=<id>` to URL      |
| Type chip in row                | D      | → /reviews?type=<queue_item_type>  |
| Filter URL sync (type)          | —      | URL ↔ filter bidirectional         |
| Deep link `?id=<id>`            | —      | auto-open review item              |

## /workspaces (Workspaces.tsx)

| Site                            | Before | After                                 |
| ------------------------------- | ------ | ------------------------------------- |
| Path column                     | D      | clickable → opens detail SlideOver    |
| Deep link `?path=<>`            | —      | auto-open SlideOver                   |

## /graph

| Site                            | Before | After                                 |
| ------------------------------- | ------ | ------------------------------------- |
| Node click (memory)             | L      | unchanged → MemoryInspector           |
| Node click (run)                | D      | → /runs?id=<id>                       |
| Node click (retrieval)          | D      | → /retrievals?id=<id>                 |
| Node click (review)             | D      | → /reviews?id=<id>                    |

## Counts (3 retrievals etc.)

The current API responses don't expose per-memory drill-down counts in the
inspector. We render counts as `count` not `count of related X` — there is no
linkable count site to wire.

## Tally

  Linkable sites discovered                           34
  Already clickable before stage 10                    9
  Wired in stage 10                                   25
