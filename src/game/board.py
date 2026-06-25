class Board:
    def __init__(self, rows: int, cols: int) -> None:
        self.rows = rows
        self.cols = cols
        self.barriers: set[tuple[int, int]] = set()

    def in_bounds(self, pos: tuple[int, int]) -> bool:
        r, c = pos
        return 0 <= r < self.rows and 0 <= c < self.cols

    def is_blocked(self, pos: tuple[int, int]) -> bool:
        return pos in self.barriers

    def place_barrier(self, pos: tuple[int, int]) -> None:
        if not self.in_bounds(pos):
            raise ValueError(f"Position {pos} is out of bounds")
        if pos in self.barriers:
            raise ValueError(f"Barrier already exists at {pos}")
        self.barriers.add(pos)
