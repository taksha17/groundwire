# Design

<!-- impeccable:design-schema 1 -->

Groundwire’s operator surface is a live railway signal box: enamel plate, glass spectacle lamps, brass rails on the interlocking diagram. Approval is a lever on a red signal, not a modal. Metrics are analog gauges (Instruments), not KPI cards.

## Surfaces

- `dashboard` — Angular signal box at `/` (compose `:4200`). Left strip lists runs with spectacle lamps. The field is a D3 DAG. Held routes expose Approve / Reject on the approval node. Empty state offers **Set a route**. **Register** is the occurrence book (audit query + CSV/JSON). Sign in lives on the instrument plate.

## Color

Restrained, forced by a dim instrument-panel interior.

| Token | Hex | Use |
|---|---|---|
| Panel | `#1C2820` | Page ground |
| Plate | `#151C16` | Header and hold plate |
| Ivory | `#D9D4C6` | Type, rules, node stroke |
| Amber | `#C45C26` | Live / executing lamp, meta |
| Danger | `#8B1E1E` | Awaiting approval |
| Clear | `#3F7A52` | Completed lamp |
| Brass | `#8A6A32` | Levers |

## Type

- UI and diagram labels: Archivo Narrow (self-hosted), 0.08–0.16em tracking, uppercase on plates.
- Longer copy (rationale, params): Archivo.

## Layout

- Desktop: 280px route strip + diagram field, instrument plate across the top.
- Narrow: strip stacks above the diagram, max 40vh, levers remain on the node.

## Motion

- One authored moment: danger lamps pulse 1.6s ease-out while a run is held at approval.

## Controls

- Filters: All routes / Live / Held / Register / Instruments.
- **Set a route** stays on the plate even when the strip is populated.
- Sign in / Sign out on the plate; the actor on a lever pull is the signed-in identity.
- Route rows are full-width strip buttons with a lamp.
- Approve / Reject are brass levers on the DAG node.

## Provenance

Direction: signal box (Impeccable pick, seed `a995afce`). Code-led; no approved raster comps.
