"""Map + kit -> the sheet tiles that draw it. Shared, so the exporter and the editor draw alike.

The drawing has three layers: floor, walls (doors included), and objects. A kit whose top wall
is two tiles tall draws one extra row at the top. So the drawing is one row taller than the map,
and map row y is drawn at row y + shift, where shift is 1 for those kits and 0 for the rest.

Rules, from the tileset README:
- The floor fills the whole drawing first, since some walls are see-through.
- Openings are three cells wide: a wall end, the floor, and a wall end. The middle stays empty
  on the walls layer, so the floor shows through.
- A top door goes on the lowest row of the top wall.
- A wall painted inside the room uses the kit's bottom wall piece. A door tile inside the room
  leads nowhere, so it is drawn as floor.
"""

from dataclasses import dataclass

from app.models import GameMap, Tile
from app.spec import ObjectKind
from app.tileset import Side, ThemeKit, TileEntry, WallPiece, load_tileset

Cell = tuple[int, int]  # x, y
Layer = list[list[int | None]]  # [y][x] sheet ids; None draws nothing


@dataclass(frozen=True)
class DrawnObject:
    kind: str
    x: int  # cell in the drawing
    y: int
    tile: int | None  # sheet id, or None for a kind the kit has no tile for


@dataclass(frozen=True)
class Drawing:
    width: int
    height: int
    shift: int  # map row y is drawn at row y + shift
    floor: Layer
    walls: Layer
    objects: list[DrawnObject]


def draw(game_map: GameMap, kit_name: str) -> Drawing:
    tileset = load_tileset()
    kit = tileset.kits[kit_name]
    entries = {e.name: e for e in tileset.catalog.entries}
    w, h = game_map.width, game_map.height
    shift = entries[kit.walls["top"]].footprint[1] - 1
    height = h + shift
    tiles = game_map.tiles

    floor: Layer = [[entries[kit.floor].id] * w for _ in range(height)]
    if kit.floor_shadow_top and h > 2:
        for x in range(1, w - 1):
            floor[1 + shift][x] = entries[kit.floor_shadow_top].id

    walls: Layer = [[None] * w for _ in range(height)]
    for y in range(h):
        for x in range(w):
            # A top door sits on the top wall's lowest row, so the rows above it are still wall.
            if tiles[y][x] == Tile.WALL or (y == 0 and tiles[y][x] == Tile.DOOR):
                _wall(walls, kit, entries, x, y, w, h, shift)
    if shift:
        _face_ends(walls, kit, entries, tiles, w)
    for y in range(h):
        for x in range(w):
            if tiles[y][x] == Tile.DOOR:
                _door(walls, kit, entries, tiles, x, y, w, h, shift)

    objects = [
        DrawnObject(obj.kind, obj.x, obj.y + shift, _object_tile(kit, entries, obj.kind))
        for obj in game_map.objects
    ]
    return Drawing(w, height, shift, floor, walls, objects)


def _place(walls: Layer, x: int, y: int, entry: TileEntry) -> None:
    """Places an entry with its top-left tile at drawing cell (x, y), clipped to the drawing."""
    width = entry.footprint[0]
    for i, part in enumerate(entry.parts or [entry.id]):
        px, py = x + i % width, y + i // width
        if 0 <= py < len(walls) and 0 <= px < len(walls[py]):
            walls[py][px] = part


def _wall(
    walls: Layer,
    kit: ThemeKit,
    entries: dict[str, TileEntry],
    x: int,
    y: int,
    w: int,
    h: int,
    shift: int,
) -> None:
    piece = _wall_piece(x, y, w, h)
    if y == 0:
        _place(walls, x, 0, entries[kit.walls[piece or "top"]])  # Fills every top-wall row.
        return
    entry = entries[kit.walls[piece or "bottom"]]
    width, tall = entry.footprint
    # Below the top wall there is room for one row, so a tall piece gives only its lowest tile.
    tile = (entry.parts or [entry.id])[(tall - 1) * width]
    walls[y + shift][x] = tile


def _wall_piece(x: int, y: int, w: int, h: int) -> WallPiece | None:
    """The kit wall piece for an outer-ring cell, or None for a cell inside the room."""
    left, right, top, bottom = x == 0, x == w - 1, y == 0, y == h - 1
    if top:
        return "corner_tl" if left else "corner_tr" if right else "top"
    if bottom:
        return "corner_bl" if left else "corner_br" if right else "bottom"
    if left:
        return "left"
    if right:
        return "right"
    return None


def _face_ends(
    walls: Layer, kit: ThemeKit, entries: dict[str, TileEntry], tiles: list[list[Tile]], w: int
) -> None:
    """The ends of the lower row of a two-row top wall, next to the corners."""
    for name, x in ((kit.face_end_left, 1), (kit.face_end_right, w - 2)):
        if name and 0 < x < w - 1 and tiles[0][x] == Tile.WALL:
            walls[1][x] = entries[name].id


def _door(
    walls: Layer,
    kit: ThemeKit,
    entries: dict[str, TileEntry],
    tiles: list[list[Tile]],
    x: int,
    y: int,
    w: int,
    h: int,
    shift: int,
) -> None:
    """Draws the door centered on map cell (x, y). Its ends replace wall cells only."""
    side = _door_side(x, y, w, h)
    if side is None:
        return  # A door inside the room leads nowhere, so the floor shows.
    entry = entries[kit.doors[side]]
    width, tall = entry.footprint
    if side in ("top", "bottom"):
        cells = [(x - width // 2 + i, y) for i in range(width)]
    else:
        cells = [(x, y - tall // 2 + i) for i in range(tall)]
    floor_tile = entries[kit.floor].id
    for (mx, my), part in zip(cells, entry.parts or [entry.id], strict=True):
        if not (0 <= mx < w and 0 <= my < h):
            continue
        if (mx, my) == (x, y):
            walls[my + shift][mx] = None if part == floor_tile else part
        elif tiles[my][mx] == Tile.WALL:
            walls[my + shift][mx] = part


def _door_side(x: int, y: int, w: int, h: int) -> Side | None:
    if y == 0:
        return "top"
    if y == h - 1:
        return "bottom"
    if x == 0:
        return "left"
    if x == w - 1:
        return "right"
    return None


def _object_tile(kit: ThemeKit, entries: dict[str, TileEntry], kind: str) -> int | None:
    try:
        return entries[kit.objects[ObjectKind(kind)]].id
    except ValueError:
        return None  # Not a kind the spec knows, so the kit has no tile for it.
