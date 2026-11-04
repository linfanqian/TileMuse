"""Where a player can walk, and the doors that lead out. Shared by the generator, the validator,
and the Tiled export."""

from collections import deque
from collections.abc import Collection, Sequence

from app.models import Tile
from app.spec import ObjectKind

Cell = tuple[int, int]  # x, y

BLOCKING_KINDS = {ObjectKind.COVER, ObjectKind.CHEST, ObjectKind.LIGHT}


def neighbors(cell: Cell) -> tuple[Cell, Cell, Cell, Cell]:
    """The cells a player can step to from `cell`: right, left, down, and up."""
    x, y = cell
    return (x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)


def exits(tiles: Sequence[Sequence[Tile]]) -> list[Cell]:
    """Door tiles on the outer wall, row by row. A door tile inside the room leads nowhere, so it
    isn't one."""
    h = len(tiles)
    return [
        (x, y)
        for y, row in enumerate(tiles)
        for x, tile in enumerate(row)
        if tile == Tile.DOOR and (x in (0, len(row) - 1) or y in (0, h - 1))
    ]


def reachable(tiles: Sequence[Sequence[Tile]], blocked: Collection[Cell], start: Cell) -> set[Cell]:
    """Every cell a player at `start` can walk to with BFS, moving up, down, left, and right.
    Empty if no one can stand at `start`."""
    x, y = start
    if start in blocked or tiles[y][x] == Tile.WALL:
        return set()
    seen = {start}
    queue = deque([start])
    while queue:
        for cell in neighbors(queue.popleft()):
            nx, ny = cell
            if not (0 <= ny < len(tiles) and 0 <= nx < len(tiles[ny])):
                continue
            if cell not in seen and cell not in blocked and tiles[ny][nx] != Tile.WALL:
                seen.add(cell)
                queue.append(cell)
    return seen
