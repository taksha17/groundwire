# Design

<!-- impeccable:design-schema 1 -->

Groundwire’s operator surface shares the marketing site’s night control plane: navy void, brass actions, and three spectacle lamps. A run is still a route; approval is still a lever on a held signal — now in the same world as the public page.

## Surfaces

- `dashboard` — Angular signal box at `/` (compose `:4200`). Sticky plate with the three-lamp mark. Left strip lists runs as rounded track rows with a lamp and a status pill. The field is a D3 DAG. Held routes expose Approve / Reject on the approval node. Empty state offers **Set a route**. **Register** is the occurrence book. Sign in lives on the plate.

## Color

| Token | Hex | Use |
|---|---|---|
| Void | `#0B0E14` | Page ground |
| Panel | `#131826` | Cards, field |
| Line | `#232B3D` | Rules, node stroke |
| Text | `#E8ECF6` | Primary type |
| Muted | `#8B95AB` | Secondary type |
| Amber | `#FFB347` | Executing lamp |
| Danger | `#FF5D5D` | Held / awaiting approval |
| Clear | `#42D392` | Completed |
| Brass | `#C9A86A` | Primary levers |
| Ivory | `#F2EAD8` | Highlight type |

## Type

- UI: Space Grotesk (self-hosted), 400/500/700.
- Data, status pills, ledger times: IBM Plex Mono.

## Layout

- Desktop: 320px route strip + diagram field, 64px instrument plate.
- Narrow: strip stacks above the diagram, max 38vh, levers remain on the node.

## Motion

- One authored moment: danger lamps pulse 2.4s ease-in-out while a run is held.

## Controls

- Filters: All routes / Live / Held / Register / Instruments.
- **Set a route** stays on the plate.
- Route rows: left color rail, lamp, name, status pill.
- Approve is the brass primary; Reject is the dark ghost lever.

## Provenance

Direction: marketing-site control plane (`file:///home/taksha/.qwen/artifacts/6381eef4dfc3b951/index.html`). Signal-box task language kept; enamel green world replaced.
