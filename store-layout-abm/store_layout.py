from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import inf
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


Position = Tuple[int, int]

LAYOUT_NAMES = ("grid", "loop", "free_flow")


@dataclass(frozen=True)
class StoreItem:
    name: str
    category: str
    price: float
    margin: float
    location: Position
    visibility: float
    promotion: bool
    is_essential: bool
    list_probability: float
    high_exposure: bool = False

    @property
    def sale_price(self) -> float:
        discount = 0.85 if self.promotion else 1.0
        return round(self.price * discount, 2)

    @property
    def profit(self) -> float:
        promotion_margin_penalty = 0.75 if self.promotion else 1.0
        return round(self.sale_price * self.margin * promotion_margin_penalty, 2)

    @property
    def list_probability_percent(self) -> float:
        return round(self.list_probability * 100, 1)


class StoreLayout:
    """Static store geometry and products used by shopper agents."""

    def __init__(
        self,
        layout_name: str,
        width: int,
        height: int,
        promotion_level: float,
        rng,
    ) -> None:
        if layout_name not in LAYOUT_NAMES:
            raise ValueError(f"Unknown layout '{layout_name}'. Choose from {LAYOUT_NAMES}.")
        if width < 12 or height < 10:
            raise ValueError("Store grid must be at least 12x10.")

        self.layout_name = layout_name
        self.width = width
        self.height = height
        self.promotion_level = max(0.0, min(1.0, promotion_level))
        self.rng = rng

        self.entrance: Position = (1, height // 2)
        self.checkout: Position = (width - 2, height // 2)
        self.passable: set[Position] = set()
        self.hot_zones: set[Position] = set()
        self.loop_path: List[Position] = []
        self.zone_centers: Dict[str, Position] = {}
        self.items: List[StoreItem] = []
        self.items_by_location: Dict[Position, List[StoreItem]] = {}
        self.items_by_name: Dict[str, StoreItem] = {}

        self._build_geometry()
        self._place_items()

    def _build_geometry(self) -> None:
        if self.layout_name == "grid":
            self._build_grid_layout()
        elif self.layout_name == "loop":
            self._build_loop_layout()
        else:
            self._build_free_flow_layout()

        self.passable.add(self.entrance)
        self.passable.add(self.checkout)

    def _build_grid_layout(self) -> None:
        aisle_x = {2, 5, 8, 11, 14, 17, 20, self.width - 2}
        cross_y = {1, self.height // 2, self.height - 2}
        for x in range(1, self.width - 1):
            for y in range(1, self.height - 1):
                if x in aisle_x or y in cross_y:
                    self.passable.add((x, y))

        self.hot_zones = {
            (3, self.height // 2),
            (self.width - 4, self.height // 2),
            (self.width - 3, self.height // 2 - 1),
            (self.width - 3, self.height // 2 + 1),
        }
        self.zone_centers = {
            "produce": (2, self.height // 2 - 2),
            "bakery": (5, self.height // 2 + 2),
            "pantry": (14, self.height // 2),
            "beverages": (17, self.height // 2),
            "dairy": (20, 2),
            "meat": (17, self.height - 2),
            "snacks": (11, self.height // 2),
            "frozen": (20, self.height // 2),
            "household": (8, self.height - 2),
            "personal_care": (8, 1),
            "checkout": self.checkout,
        }

    def _build_loop_layout(self) -> None:
        left, right = 2, self.width - 3
        bottom, top = 1, self.height - 2
        path: List[Position] = []

        for x in range(left, right + 1):
            path.append((x, bottom))
        for y in range(bottom + 1, top + 1):
            path.append((right, y))
        for x in range(right - 1, left - 1, -1):
            path.append((x, top))
        for y in range(top - 1, bottom, -1):
            path.append((left, y))

        self.loop_path = path
        self.passable.update(path)

        mid_y = self.height // 2
        for x in range(left, right + 1):
            if x % 3 != 0:
                self.passable.add((x, mid_y))
        for y in range(bottom, top + 1):
            if y % 4 != 0:
                self.passable.add((self.width // 2, y))

        self.hot_zones = {
            (right, mid_y),
            (right, mid_y - 1),
            (right, mid_y + 1),
            (self.width // 2, bottom),
            (self.width // 2, top),
            (self.width - 4, self.height // 2),
        }
        self.zone_centers = {
            "produce": (left, bottom + 1),
            "bakery": (left + 5, bottom),
            "pantry": (self.width // 2, mid_y),
            "beverages": (right - 2, mid_y),
            "dairy": (right, bottom + 2),
            "meat": (right, top - 2),
            "snacks": (self.width // 2, top),
            "frozen": (right - 4, top),
            "household": (left, top - 2),
            "personal_care": (left + 2, top),
            "checkout": self.checkout,
        }

    def _build_free_flow_layout(self) -> None:
        for x in range(1, self.width - 1):
            for y in range(1, self.height - 1):
                self.passable.add((x, y))

        display_islands = {
            (self.width // 2, self.height // 2),
            (self.width // 2 + 1, self.height // 2),
            (self.width // 2, self.height // 2 + 1),
            (6, 4),
            (7, 4),
            (self.width - 7, self.height - 5),
            (self.width - 8, self.height - 5),
        }
        self.passable.difference_update(display_islands)

        self.hot_zones = {
            (4, self.height // 2),
            (self.width // 2 - 1, self.height // 2),
            (self.width - 4, self.height // 2),
            (self.width - 4, self.height // 2 - 1),
            (self.width - 4, self.height // 2 + 1),
        }
        self.zone_centers = {
            "produce": (3, self.height // 2 - 2),
            "bakery": (5, self.height // 2 + 2),
            "pantry": (self.width // 2 + 2, self.height // 2),
            "beverages": (self.width // 2 + 5, self.height // 2 - 1),
            "dairy": (self.width - 4, 3),
            "meat": (self.width - 5, self.height - 3),
            "snacks": (self.width // 2 - 2, self.height // 2),
            "frozen": (self.width - 6, self.height // 2 + 3),
            "household": (self.width // 2, self.height - 3),
            "personal_care": (self.width // 2 - 3, self.height - 3),
            "checkout": self.checkout,
        }

    def _place_items(self) -> None:
        item_specs = [
            ("Apples", "produce", 3.50, 0.34, True, 0.46),
            ("Bananas", "produce", 2.40, 0.30, True, 0.54),
            ("Oranges", "produce", 4.10, 0.33, True, 0.34),
            ("Tomatoes", "produce", 4.80, 0.36, True, 0.30),
            ("Potatoes", "produce", 4.20, 0.32, True, 0.36),
            ("Onions", "produce", 3.20, 0.31, True, 0.24),
            ("Carrots", "produce", 3.60, 0.32, True, 0.28),
            ("Salad Pack", "produce", 5.20, 0.38, False, 0.40),
            ("Bread", "bakery", 3.10, 0.32, True, 0.62),
            ("Burger Buns", "bakery", 4.20, 0.34, False, 0.24),
            ("Wraps", "bakery", 4.80, 0.35, False, 0.26),
            ("Croissants", "bakery", 6.20, 0.48, False, 0.16),
            ("Muffins", "bakery", 5.90, 0.46, False, 0.18),
            ("Milk", "dairy", 4.10, 0.27, True, 0.70),
            ("Eggs", "dairy", 5.80, 0.28, True, 0.66),
            ("Butter", "dairy", 5.40, 0.34, True, 0.36),
            ("Cheese", "dairy", 6.50, 0.39, True, 0.50),
            ("Yoghurt", "dairy", 4.80, 0.35, False, 0.38),
            ("Cream", "dairy", 3.90, 0.36, False, 0.18),
            ("Orange Juice", "dairy", 5.20, 0.32, False, 0.26),
            ("Chicken", "meat", 10.50, 0.31, True, 0.48),
            ("Ground Beef", "meat", 11.20, 0.30, True, 0.36),
            ("Pork Chops", "meat", 12.40, 0.30, False, 0.22),
            ("Sausages", "meat", 8.40, 0.34, False, 0.24),
            ("Bacon", "meat", 7.80, 0.36, False, 0.26),
            ("Rice", "pantry", 4.90, 0.34, True, 0.42),
            ("Pasta", "pantry", 3.40, 0.36, True, 0.45),
            ("Pasta Sauce", "pantry", 4.60, 0.37, True, 0.34),
            ("Cooking Oil", "pantry", 6.70, 0.32, True, 0.26),
            ("Flour", "pantry", 3.70, 0.30, True, 0.22),
            ("Sugar", "pantry", 3.30, 0.29, True, 0.22),
            ("Cereal", "pantry", 5.60, 0.40, False, 0.34),
            ("Canned Tuna", "pantry", 3.20, 0.33, False, 0.30),
            ("Baked Beans", "pantry", 2.40, 0.34, False, 0.24),
            ("Soup", "pantry", 3.10, 0.35, False, 0.22),
            ("Coffee", "pantry", 8.50, 0.42, False, 0.28),
            ("Tea Bags", "pantry", 5.20, 0.39, False, 0.22),
            ("Chocolate", "snacks", 3.80, 0.52, False, 0.22),
            ("Chips", "snacks", 4.70, 0.50, False, 0.34),
            ("Soft Drink", "snacks", 5.40, 0.45, False, 0.30),
            ("Cookies", "snacks", 4.40, 0.48, False, 0.28),
            ("Crackers", "snacks", 3.90, 0.45, False, 0.24),
            ("Granola Bars", "snacks", 5.10, 0.43, False, 0.22),
            ("Nuts", "snacks", 6.80, 0.44, False, 0.20),
            ("Water", "beverages", 4.20, 0.35, True, 0.30),
            ("Cola", "beverages", 5.60, 0.44, False, 0.30),
            ("Sparkling Water", "beverages", 5.20, 0.38, False, 0.20),
            ("Sports Drink", "beverages", 4.80, 0.42, False, 0.18),
            ("Energy Drink", "beverages", 4.10, 0.48, False, 0.16),
            ("Ice Cream", "frozen", 7.20, 0.41, False, 0.20),
            ("Frozen Pizza", "frozen", 8.90, 0.36, False, 0.28),
            ("Frozen Vegetables", "frozen", 4.60, 0.32, True, 0.28),
            ("Frozen Berries", "frozen", 6.40, 0.36, False, 0.18),
            ("Frozen Chips", "frozen", 5.20, 0.35, False, 0.22),
            ("Laundry Powder", "household", 13.50, 0.28, True, 0.18),
            ("Dish Soap", "household", 4.80, 0.34, True, 0.22),
            ("Trash Bags", "household", 6.80, 0.35, False, 0.18),
            ("Paper Towels", "household", 6.90, 0.30, False, 0.16),
            ("Toilet Paper", "household", 9.90, 0.28, True, 0.34),
            ("All-Purpose Cleaner", "household", 5.40, 0.36, False, 0.16),
            ("Shampoo", "personal_care", 7.20, 0.42, False, 0.18),
            ("Toothpaste", "personal_care", 4.20, 0.40, True, 0.26),
            ("Soap", "personal_care", 3.50, 0.39, True, 0.22),
            ("Deodorant", "personal_care", 5.80, 0.43, False, 0.16),
            ("Checkout Gum", "checkout", 2.20, 0.58, False, 0.00),
            ("Checkout Mints", "checkout", 2.60, 0.57, False, 0.00),
            ("Chocolate Bar", "checkout", 2.80, 0.55, False, 0.00),
            ("Magazine", "checkout", 6.50, 0.38, False, 0.00),
            ("Batteries", "checkout", 6.00, 0.49, False, 0.00),
        ]

        used_positions: set[Position] = set()
        for spec in item_specs:
            name, category, price, margin, essential, list_probability = spec
            location = self._nearest_open_cell(self.zone_centers[category], used_positions)
            used_positions.add(location)

            high_exposure = location in self.hot_zones or category == "checkout"
            base_visibility = {
                "grid": 0.42,
                "loop": 0.58,
                "free_flow": 0.50,
            }[self.layout_name]
            if high_exposure:
                base_visibility += 0.25
            if category in {"snacks", "checkout"}:
                base_visibility += 0.12

            promotion = self.rng.random() < self.promotion_level
            item = StoreItem(
                name=name,
                category=category,
                price=price,
                margin=margin,
                location=location,
                visibility=min(0.95, base_visibility),
                promotion=promotion,
                is_essential=essential,
                list_probability=list_probability,
                high_exposure=high_exposure,
            )
            self.items.append(item)
            self.items_by_name[item.name] = item
            self.items_by_location.setdefault(location, []).append(item)

    def _nearest_open_cell(self, start: Position, used_positions: set[Position]) -> Position:
        if start in self.passable and start not in used_positions:
            return start

        queue = deque([start])
        seen = {start}
        while queue:
            current = queue.popleft()
            for neighbor in self._raw_neighbors(current):
                if neighbor in seen:
                    continue
                seen.add(neighbor)
                if neighbor in self.passable and neighbor not in used_positions:
                    return neighbor
                queue.append(neighbor)
        raise RuntimeError("No available passable cell for item placement.")

    def _raw_neighbors(self, pos: Position) -> Iterable[Position]:
        x, y = pos
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            neighbor = (x + dx, y + dy)
            if 0 <= neighbor[0] < self.width and 0 <= neighbor[1] < self.height:
                yield neighbor

    def neighbors(self, pos: Position, include_diagonal: bool = False) -> List[Position]:
        x, y = pos
        directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        if include_diagonal:
            directions.extend([(1, 1), (1, -1), (-1, 1), (-1, -1)])

        cells: List[Position] = []
        for dx, dy in directions:
            candidate = (x + dx, y + dy)
            if candidate in self.passable:
                cells.append(candidate)
        return cells

    def items_at(self, pos: Position) -> List[StoreItem]:
        return self.items_by_location.get(pos, [])

    def nearby_items(self, pos: Position, radius: int = 1) -> List[StoreItem]:
        px, py = pos
        found: List[StoreItem] = []
        for item in self.items:
            ix, iy = item.location
            if abs(px - ix) + abs(py - iy) <= radius:
                found.append(item)
        return found

    def nearest_item(self, item_names: Sequence[str], pos: Position) -> Optional[StoreItem]:
        candidates = [self.items_by_name[name] for name in item_names if name in self.items_by_name]
        if not candidates:
            return None
        return min(candidates, key=lambda item: manhattan(pos, item.location))

    def next_step(
        self,
        start: Position,
        target: Position,
        rng,
        exploration_rate: float,
        familiarity: float,
    ) -> Position:
        if start == target:
            return start

        if rng.random() < exploration_rate:
            return self.random_neighbor(start, rng)

        if self.layout_name == "loop" and rng.random() < max(0.45, familiarity):
            loop_step = self._next_loop_step(start, target)
            if loop_step is not None:
                return loop_step

        if rng.random() <= familiarity:
            return self._bfs_step(start, target) or self.greedy_step(start, target, rng)

        return self.greedy_step(start, target, rng)

    def random_neighbor(self, pos: Position, rng) -> Position:
        options = self.neighbors(pos)
        return rng.choice(options) if options else pos

    def greedy_step(self, start: Position, target: Position, rng) -> Position:
        options = self.neighbors(start)
        if not options:
            return start

        best_distance = min(manhattan(option, target) for option in options)
        best_options = [option for option in options if manhattan(option, target) == best_distance]
        if rng.random() < 0.18:
            return rng.choice(options)
        return rng.choice(best_options)

    def _bfs_step(self, start: Position, target: Position) -> Optional[Position]:
        if target not in self.passable:
            target = self._nearest_open_cell(target, set())

        queue = deque([start])
        came_from: Dict[Position, Optional[Position]] = {start: None}
        while queue:
            current = queue.popleft()
            if current == target:
                break
            for neighbor in self.neighbors(current):
                if neighbor not in came_from:
                    came_from[neighbor] = current
                    queue.append(neighbor)

        if target not in came_from:
            return None

        current = target
        previous = came_from[current]
        while previous is not None and previous != start:
            current = previous
            previous = came_from[current]
        return current

    def _next_loop_step(self, start: Position, target: Position) -> Optional[Position]:
        if not self.loop_path:
            return None

        start_idx = self._nearest_loop_index(start)
        target_idx = self._nearest_loop_index(target)
        if start_idx is None or target_idx is None:
            return None

        if start not in self.loop_path:
            return self._bfs_step(start, self.loop_path[start_idx])

        path_len = len(self.loop_path)
        clockwise = (target_idx - start_idx) % path_len
        counter = (start_idx - target_idx) % path_len
        next_idx = (start_idx + 1) % path_len if clockwise <= counter else (start_idx - 1) % path_len
        return self.loop_path[next_idx]

    def _nearest_loop_index(self, pos: Position) -> Optional[int]:
        if not self.loop_path:
            return None
        best_distance = inf
        best_index: Optional[int] = None
        for index, cell in enumerate(self.loop_path):
            distance = manhattan(pos, cell)
            if distance < best_distance:
                best_distance = distance
                best_index = index
        return best_index

    def essential_item_names(self) -> List[str]:
        return [item.name for item in self.items if item.is_essential]

    def listable_items(self) -> List[StoreItem]:
        return [
            item
            for item in self.items
            if item.category != "checkout" and item.list_probability > 0
        ]

    def promotional_item_names(self) -> List[str]:
        return [item.name for item in self.items if item.promotion]

    def checkout_items(self) -> List[StoreItem]:
        return [item for item in self.items if item.category == "checkout"]


def manhattan(a: Position, b: Position) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])
