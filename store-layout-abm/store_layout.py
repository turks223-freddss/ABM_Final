from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import inf
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


Position = Tuple[int, int]

LAYOUT_NAMES = ("grid", "loop", "free_flow")

# Layout coordinates are intentionally verbose so they are easy to edit by hand.
# Coordinates use Mesa/matplotlib grid positions: (x, y), with (0, 0) at bottom-left.
SHELF_COORDINATES: Dict[str, Dict[str, List[Position]]] = {
    "grid": {
        "produce": [
            (2, 13), (3, 13), (2, 14), (3, 14), (2, 15), (3, 15),
            (2, 16), (3, 16), (2, 17), (3, 17), (2, 18), (3, 18),
        ],
        "bakery": [
            (6, 13), (7, 13), (6, 14), (7, 14), (6, 15), (7, 15),
            (6, 16), (7, 16), (6, 17), (7, 17), (6, 18), (7, 18),
        ],
        "pantry": [
            (10, 13), (11, 13), (10, 14), (11, 14), (10, 15), (11, 15),
            (10, 16), (11, 16), (10, 17), (11, 17), (10, 18), (11, 18),
        ],
        "beverages": [
            (14, 13), (15, 13), (14, 14), (15, 14), (14, 15), (15, 15),
            (14, 16), (15, 16), (14, 17), (15, 17), (14, 18), (15, 18),
        ],
        "dairy": [
            (18, 13), (19, 13), (18, 14), (19, 14), (18, 15), (19, 15),
            (18, 16), (19, 16), (18, 17), (19, 17), (18, 18), (19, 18),
        ],
        "meat": [
            (2, 5), (3, 5), (2, 6), (3, 6), (2, 7), (3, 7), (2, 8),
            (3, 8), (2, 9), (3, 9), (2, 10), (3, 10), (2, 11), (3, 11),
        ],
        "snacks": [
            (6, 5), (7, 5), (6, 6), (7, 6), (6, 7), (7, 7), (6, 8),
            (7, 8), (6, 9), (7, 9), (6, 10), (7, 10), (6, 11), (7, 11),
        ],
        "frozen": [
            (10, 5), (11, 5), (10, 6), (11, 6), (10, 7), (11, 7), (10, 8),
            (11, 8), (10, 9), (11, 9), (10, 10), (11, 10), (10, 11), (11, 11),
        ],
        "household": [
            (14, 5), (15, 5), (14, 6), (15, 6), (14, 7), (15, 7), (14, 8),
            (15, 8), (14, 9), (15, 9), (14, 10), (15, 10), (14, 11), (15, 11),
        ],
        "personal_care": [
            (18, 5), (19, 5), (18, 6), (19, 6), (18, 7), (19, 7), (18, 8),
            (19, 8), (18, 9), (19, 9), (18, 10), (19, 10), (18, 11), (19, 11),
        ],
        "checkout": [
            (21, 5), (22, 5), (21, 6), (22, 6), (21, 7), (22, 7), (21, 8),
            (22, 8), (21, 9), (22, 9), (21, 10), (22, 10), (21, 11), (22, 11),
            (21, 12), (22, 12), (21, 13), (22, 13), (21, 14), (22, 14),
            (21, 15), (22, 15), (21, 16), (22, 16), (21, 17), (22, 17),
            (21, 18), (22, 18),
        ],
    },
    "loop": {
        "produce": [
            (2, 14), (3, 14), (2, 15), (3, 15), (2, 16), (3, 16),
            (2, 17), (3, 17), (4, 18), (5, 18), (6, 18), (7, 18),
        ],
        "bakery": [
            (2, 4), (3, 4), (4, 4), (5, 4), (2, 5), (3, 5),
            (2, 6), (3, 6), (2, 7), (3, 7), (2, 8), (3, 8),
        ],
        "pantry": [
            (10, 10), (11, 10), (12, 10), (13, 10), (10, 11), (11, 11),
            (12, 11), (13, 11), (10, 12), (11, 12), (12, 12), (13, 12),
        ],
        "beverages": [
            (16, 9), (17, 9), (18, 9), (19, 9), (16, 10), (17, 10),
            (18, 10), (19, 10), (16, 11), (17, 11), (18, 11), (19, 11),
        ],
        "dairy": [
            (14, 3), (15, 3), (16, 3), (17, 3), (18, 3), (19, 3),
            (14, 4), (15, 4), (16, 4), (17, 4), (18, 4), (19, 4),
        ],
        "meat": [
            (10, 5), (11, 5), (12, 5), (13, 5), (10, 6), (11, 6),
            (12, 6), (13, 6), (10, 7), (11, 7), (12, 7), (13, 7),
        ],
        "snacks": [
            (20, 12), (21, 12), (20, 13), (21, 13), (20, 14), (21, 14),
            (20, 15), (21, 15), (20, 16), (21, 16), (20, 17), (21, 17),
        ],
        "frozen": [
            (20, 5), (21, 5), (20, 6), (21, 6), (20, 7), (21, 7),
            (20, 8), (21, 8), (20, 9), (21, 9), (20, 10), (21, 10),
        ],
        "household": [
            (6, 8), (7, 8), (6, 9), (7, 9), (6, 10), (7, 10),
            (6, 11), (7, 11), (6, 12), (7, 12), (6, 13), (7, 13),
        ],
        "personal_care": [
            (8, 18), (9, 18), (10, 18), (11, 18), (12, 18), (13, 18),
            (8, 17), (9, 17), (10, 17), (11, 17), (12, 17), (13, 17),
        ],
        "checkout": [
            (14, 18), (15, 18), (16, 18), (17, 18), (18, 18), (19, 18),
            (20, 18), (21, 18),
        ],
    },
    "free_flow": {
        "produce": [
            (2, 13), (3, 13), (2, 14), (3, 14), (2, 15), (3, 15),
            (5, 16), (6, 16), (7, 16), (5, 17), (6, 17), (7, 17),
        ],
        "bakery": [
            (3, 4), (4, 4), (5, 4), (6, 4), (3, 5), (4, 5),
            (5, 5), (6, 5), (8, 7), (9, 7), (8, 8), (9, 8),
        ],
        "pantry": [
            (10, 8), (11, 8), (12, 8), (13, 8), (10, 9), (11, 9),
            (12, 9), (13, 9), (11, 13), (12, 13), (13, 13), (14, 13),
        ],
        "beverages": [
            (16, 7), (17, 7), (18, 7), (19, 7), (16, 8), (17, 8),
            (18, 8), (19, 8), (17, 11), (18, 11), (19, 11), (20, 11),
        ],
        "dairy": [
            (15, 3), (16, 3), (17, 3), (18, 3), (19, 3), (20, 3),
            (15, 4), (16, 4), (17, 4), (18, 4), (19, 4), (20, 4),
        ],
        "meat": [
            (11, 4), (12, 4), (13, 4), (14, 4), (11, 5), (12, 5),
            (13, 5), (14, 5), (12, 6), (13, 6), (14, 6), (15, 6),
        ],
        "snacks": [
            (20, 13), (21, 13), (20, 14), (21, 14), (20, 15), (21, 15),
            (20, 16), (21, 16), (18, 17), (19, 17), (20, 17), (21, 17),
        ],
        "frozen": [
            (19, 5), (20, 5), (21, 5), (19, 6), (20, 6), (21, 6),
            (19, 7), (20, 7), (21, 7), (19, 8), (20, 8), (21, 8),
        ],
        "household": [
            (7, 11), (8, 11), (7, 12), (8, 12), (7, 13), (8, 13),
            (9, 14), (10, 14), (9, 15), (10, 15), (9, 16), (10, 16),
        ],
        "personal_care": [
            (4, 10), (5, 10), (4, 11), (5, 11), (4, 12), (5, 12),
            (14, 15), (15, 15), (14, 16), (15, 16), (14, 17), (15, 17),
        ],
        "checkout": [
            (8, 18), (9, 18), (10, 18), (11, 18), (12, 18), (13, 18),
            (14, 18), (15, 18),
        ],
    },
}


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

    CHECKOUT_QUEUE_DEPTH = 3

    def __init__(
        self,
        layout_name: str,
        width: int,
        height: int,
        promotion_level: float,
        rng,
        num_cashiers: int = 3,
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
        self.num_cashiers = max(1, min(int(num_cashiers), width - 4))

        self.front_service_y = height - 2
        self.queue_direction = -1
        self.entrance_positions: List[Position] = []
        self.checkout_positions: List[Position] = []
        self.checkout_display_cells: List[Position] = []
        self.checkout_separator_cells: set[Position] = set()
        self.front_service_area_cells: set[Position] = set()
        self.checkout_queue_area_cells: set[Position] = set()
        self.checkout_queue_cells: Dict[Position, List[Position]] = {}
        self.all_checkout_queue_cells: set[Position] = set()
        self.entrance: Position = (1, self.front_service_y)
        self.checkout: Position = (2, self.front_service_y)
        self.passable: set[Position] = set()
        self.shelf_cells: set[Position] = set()
        self.accessible_shelf_cells: set[Position] = set()
        self.shelf_categories: Dict[Position, str] = {}
        self.hot_zones: set[Position] = set()
        self.loop_path: List[Position] = []
        self.zone_centers: Dict[str, Position] = {}
        self.items: List[StoreItem] = []
        self.items_by_location: Dict[Position, List[StoreItem]] = {}
        self.items_by_name: Dict[str, StoreItem] = {}

        self._configure_front_service_area()
        self._build_geometry()
        self._build_shelf_map()
        self._place_items()

    def _configure_front_service_area(self) -> None:
        service_width = self.num_cashiers * 2 + 1
        start_x = max(1, (self.width - service_width) // 2)
        end_x = start_x + service_width - 1
        if end_x > self.width - 2:
            end_x = self.width - 2
            start_x = end_x - service_width + 1

        self.entrance_positions = [
            (start_x, self.front_service_y),
            (end_x, self.front_service_y),
        ]
        self.checkout_positions = [
            (start_x + 1 + cashier_index * 2, self.front_service_y)
            for cashier_index in range(self.num_cashiers)
        ]
        self.checkout_separator_cells = {
            (left_cashier[0] + 1, self.front_service_y)
            for left_cashier in self.checkout_positions[:-1]
        }
        self.checkout_display_cells = list(
            SHELF_COORDINATES.get(self.layout_name, {}).get("checkout", [])
        )
        band_width = min(self.width - 2, max(self.num_cashiers + 8, 14))
        band_start_x = max(1, (self.width - band_width) // 2)
        band_end_x = min(self.width - 2, band_start_x + band_width - 1)
        self.front_service_area_cells = {
            (x, self.front_service_y)
            for x in range(band_start_x, band_end_x + 1)
        }
        self.checkout_queue_cells = {
            checkout: [
                (checkout[0], checkout[1] + self.queue_direction * step)
                for step in range(1, self.CHECKOUT_QUEUE_DEPTH + 1)
                if 1 <= checkout[1] + self.queue_direction * step <= self.height - 2
            ]
            for checkout in self.checkout_positions
        }
        self.checkout_queue_area_cells = {
            (x, self.front_service_y + self.queue_direction * step)
            for x in range(band_start_x, band_end_x + 1)
            for step in range(1, self.CHECKOUT_QUEUE_DEPTH + 1)
            if 1 <= self.front_service_y + self.queue_direction * step <= self.height - 2
        }
        self.all_checkout_queue_cells = {
            cell
            for lane in self.checkout_queue_cells.values()
            for cell in lane
        }
        self.entrance = self.entrance_positions[0]
        self.checkout = self.checkout_positions[0]

    def _build_geometry(self) -> None:
        if self.layout_name == "grid":
            self._build_grid_layout()
        elif self.layout_name == "loop":
            self._build_loop_layout()
        else:
            self._build_free_flow_layout()

        front_x_values = [
            x
            for x, _ in self.entrance_positions + self.checkout_positions
        ]
        if front_x_values:
            start_x = max(1, min(front_x_values) - 1)
            end_x = min(self.width - 1, max(front_x_values) + 2)
            for x in range(start_x, end_x):
                self.passable.add((x, self.front_service_y))
                if self.front_service_y + 1 < self.height - 1:
                    self.passable.add((x, self.front_service_y + 1))

        self.passable.update(self.entrance_positions)
        self.passable.update(self.checkout_positions)
        self.passable.update(self.front_service_area_cells)
        self.passable.update(self.checkout_queue_area_cells)
        self.passable.update(self.all_checkout_queue_cells)
        self.passable.difference_update(self.checkout_separator_cells)

    def _build_grid_layout(self) -> None:
        self._build_open_floor_around_manual_shelves()

        self.hot_zones = {
            (self.entrance[0], self.front_service_y - 1),
            (self.checkout_positions[-1][0], self.front_service_y - 1),
            (20, 18),
            (21, 18),
        }
        self.zone_centers = {
            "produce": (2, 16),
            "bakery": (6, 16),
            "pantry": (10, 16),
            "beverages": (14, 16),
            "dairy": (18, 16),
            "meat": (2, 8),
            "snacks": (6, 8),
            "frozen": (10, 8),
            "household": (14, 8),
            "personal_care": (18, 8),
            "checkout": self.checkout,
        }

    def _build_open_floor_around_manual_shelves(self) -> None:
        self._fill_open_floor()
        self.passable.difference_update(self._manual_shelf_cells())

    def _manual_shelf_cells(self) -> set[Position]:
        category_cells = SHELF_COORDINATES.get(self.layout_name, {})
        return {
            cell
            for cells in category_cells.values()
            for cell in cells
            if 0 <= cell[0] < self.width and 0 <= cell[1] < self.height
        }

    def _build_loop_layout(self) -> None:
        self._build_open_floor_around_manual_shelves()
        bottom = 1
        top = self.height - 2

        manual_shelves = self._manual_shelf_cells()
        self.loop_path = [
            cell
            for cell in self._build_reference_loop_path()
            if cell not in manual_shelves
        ]
        self.passable.update(self.loop_path)

        mid_y = self.height // 2
        self.hot_zones = {
            (self.width - 4, mid_y),
            (self.width - 4, mid_y + 1),
            (self.width - 5, bottom + 2),
            (self.width // 2, bottom + 2),
            (self.entrance[0], self.front_service_y - 1),
            (self.checkout_positions[-1][0], self.front_service_y - 1),
        }
        self.zone_centers = {
            "produce": (3, 11),
            "bakery": (5, 3),
            "pantry": (11, 7),
            "beverages": (16, 7),
            "dairy": (16, 3),
            "meat": (11, 4),
            "snacks": (21, 10),
            "frozen": (21, 5),
            "household": (3, 6),
            "personal_care": (6, top - 1),
            "checkout": self.checkout,
        }

    def _build_free_flow_layout(self) -> None:
        self._build_open_floor_around_manual_shelves()

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

    def _fill_open_floor(self) -> None:
        for x in range(1, self.width - 1):
            for y in range(1, self.height - 1):
                self.passable.add((x, y))

    def _build_reference_loop_path(self) -> List[Position]:
        start = self.entrance
        top_y = max(2, self.height - 4)
        bottom_y = 3
        left_x = 4
        right_x = self.width - 4
        target_x = self.checkout_positions[-1][0]

        waypoints = [
            start,
            (start[0], top_y),
            (left_x, top_y),
            (left_x, bottom_y),
            (right_x, bottom_y),
            (right_x, top_y),
            (target_x, top_y),
            (target_x, self.front_service_y - self.CHECKOUT_QUEUE_DEPTH),
        ]
        path: List[Position] = []
        for current, target in zip(waypoints, waypoints[1:]):
            segment = self._straight_segment(current, target)
            if path and segment and segment[0] == path[-1]:
                path.extend(segment[1:])
            else:
                path.extend(segment)
        return [cell for cell in path if 1 <= cell[0] < self.width - 1 and 1 <= cell[1] < self.height - 1]

    def _straight_segment(self, start: Position, target: Position) -> List[Position]:
        x, y = start
        target_x, target_y = target
        segment = [(x, y)]
        while x != target_x:
            x += 1 if target_x > x else -1
            segment.append((x, y))
        while y != target_y:
            y += 1 if target_y > y else -1
            segment.append((x, y))
        return segment

    def _build_shelf_map(self) -> None:
        manual_category_cells = SHELF_COORDINATES.get(self.layout_name, {})
        manual_categories = {
            cell: category
            for category, cells in manual_category_cells.items()
            for cell in cells
            if 0 <= cell[0] < self.width and 0 <= cell[1] < self.height
        }
        for cell in self.checkout_separator_cells:
            manual_categories[cell] = "checkout"
        self.shelf_cells = set(manual_categories)

        self.accessible_shelf_cells = {
            cell
            for cell in self.shelf_cells
            if any(neighbor in self.passable for neighbor in self._raw_neighbors(cell))
        }

        self.shelf_categories.update(manual_categories)

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

        templates_by_category: Dict[str, List[Tuple[str, str, float, float, bool, float]]] = {}
        for spec in item_specs:
            templates_by_category.setdefault(spec[1], []).append(spec)

        category_order = list(SHELF_COORDINATES.get(self.layout_name, {}))
        category_order.extend(
            sorted(set(self.shelf_categories.values()) - set(category_order))
        )
        name_counts: Dict[str, int] = {}

        for category in category_order:
            shelf_locations = sorted(
                cell
                for cell, shelf_category in self.shelf_categories.items()
                if shelf_category == category
            )
            templates = templates_by_category.get(category)
            if not shelf_locations or not templates:
                continue

            for index, location in enumerate(shelf_locations):
                base_name, _, price, margin, essential, list_probability = (
                    templates[index % len(templates)]
                )
                occurrence = name_counts.get(base_name, 0) + 1
                name_counts[base_name] = occurrence
                name = base_name if occurrence == 1 else f"{base_name} {occurrence}"

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

    def _next_item_location(
        self,
        category: str,
        slot_indexes: Dict[str, int],
    ) -> Position:
        slots = [
            cell
            for cell in SHELF_COORDINATES.get(self.layout_name, {}).get(category, [])
            if cell in self.accessible_shelf_cells
        ]
        if not slots:
            return self._nearest_shelf_cell(self.zone_centers[category], set(), category)

        index = slot_indexes.get(category, 0)
        slot_indexes[category] = index + 1
        return slots[index % len(slots)]

    def _nearest_shelf_cell(
        self,
        start: Position,
        used_positions: set[Position],
        category: Optional[str] = None,
    ) -> Position:
        def is_available(cell: Position) -> bool:
            if cell not in self.accessible_shelf_cells or cell in used_positions:
                return False
            if category is None:
                return True
            return self.shelf_categories.get(cell) == category

        queue = deque([start])
        seen = {start}
        while queue:
            current = queue.popleft()
            if is_available(current):
                return current
            for neighbor in self._raw_neighbors(current):
                if neighbor in seen:
                    continue
                seen.add(neighbor)
                queue.append(neighbor)

        if category is not None:
            return self._nearest_shelf_cell(start, used_positions, None)
        raise RuntimeError("No available shelf cell for item placement.")

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

    def is_checkout(self, pos: Position) -> bool:
        return pos in self.checkout_positions

    def is_entrance(self, pos: Position) -> bool:
        return pos in self.entrance_positions

    def checkout_for_queue_cell(self, pos: Position) -> Optional[Position]:
        for checkout, lane in self.checkout_queue_cells.items():
            if pos in lane:
                return checkout
        return None


def manhattan(a: Position, b: Position) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])
