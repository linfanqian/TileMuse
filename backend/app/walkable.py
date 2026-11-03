"""Where a player can walk. Shared by the generator and the validator."""

from collections import deque
from collections.abc import Collection, Sequence

from app.models import Tile
from app.spec import ObjectKind

Cell = tuple[int, int]  # x, y

BLOCKING_KINDS = {ObjectKind.COVER, ObjectKind.CHEST, ObjectKind.LIGHT}


def reachable(tiles: Sequence[Sequence[Tile]], blocked: Collection[Cell], start: Cell) -> set[Cell]:
    """Every cell a player at `start` can walk to with BFS, moving up, down, left, and right.
    Empty if no one can stand at `start`."""
    x, y = start
    if start in blocked or tiles[y][x] == Tile.WALL:
        return set()
    seen = {start}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for cell in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            nx, ny = cell
            if not (0 <= ny < len(tiles) and 0 <= nx < len(tiles[ny])):
                continue
            if cell not in seen and cell not in blocked and tiles[ny][nx] != Tile.WALL:
                seen.add(cell)
                queue.append(cell)
    return seen
