# Tileset

The tiles TileMuse draws maps with. Load them through `load_tileset()` in `backend/app/tileset.py`, which checks the data.

| File | What it is |
|---|---|
| `tilesheet.png` | All tiles on one sheet |
| `catalog.yaml` | What each tile is |
| `kits.yaml` | Which tiles each theme uses |

## Sheet

16 x 16px tiles, 12 columns x 44 rows, 528 tiles, no gaps. An `id` is the cell number, counted left to right and top to bottom from 0. With one tileset, Tiled's `gid = id + 1`.

| Pack | Ids |
|---|---|
| Tiny Dungeon | 0-131 |
| Tiny Town | 132-263 |
| Tiny Farm | 264-395 |
| Tiny Factory | 396-527 |

## Catalog

- `name` is the unique key. `id` is not unique, because openings share tiles.
- A multi-tile entry lists its tiles in `parts`, left to right and top to bottom. `footprint` is `[width, height]`.
- Tiles used by a kit were checked by eye in a sample room. All other entries are draft labels, even with `confidence: high`.
- `tags` include `set:<name>` for floors, walls, and doors that fit together, and `on:<side>` for the walls a door fits in.
- The catalog leaves out UI markers, building exteriors, and conveyor and pipe pieces with unknown joins.

## Kits

Each kit names a floor, 8 wall pieces, a door for each side, and a tile for each object kind. A kit may use tiles from any pack. Every tile it uses must have `confidence: high`.

Each slot takes one tile `kind`. Floors, walls, and doors take their own kind. `player_spawn` and `guard` take `character`, `key` takes `item`, and `chest`, `cover`, and `light` take `object`.

To change a kit:

1. Edit `kits.yaml`.
2. Check the new tile in a sample room.
3. Set its `confidence` to `high` in `catalog.yaml`.
4. Run `uv run pytest tests/test_tileset.py`.

## Drawing notes

- Draw the floor under the whole map first. Fence walls are see-through.
- `dungeon` and `factory` have a top wall two rows tall. Their top doors go on the lower row.
- Openings are three cells wide: a wall end, the floor, and a wall end.
- Doors double as exits, so kits have no `exit` tile.
- No pack has a lamp or torch, so `light` uses `alarm_beacon`.
- Tiled flips and rotation are not used.

## Credits

Art by [Kenney](https://kenney.nl/assets/) (Tiny Dungeon, Tiny Town, Tiny Farm, Tiny Factory), under [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
