from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Set

from mesa import Agent

from store_layout import StoreItem, manhattan


@dataclass(frozen=True)
class ShopperProfile:
    name: str
    impulse_probability: float
    familiarity: float
    exploration_rate: float
    # Minutes a shopper is willing to spend before abandoning a difficult trip.
    patience: int
    discount_awareness: float
    exposure_radius: int


SHOPPER_PROFILES = {
    "mission_driven": ShopperProfile(
        name="Mission-Driven",
        impulse_probability=0.012,
        familiarity=0.80,
        exploration_rate=0.03,
        patience=90,
        discount_awareness=0.20,
        exposure_radius=2,
    ),
    "bargain_hunter": ShopperProfile(
        name="Bargain Hunter",
        impulse_probability=0.035,
        familiarity=0.65,
        exploration_rate=0.12,
        patience=125,
        discount_awareness=0.85,
        exposure_radius=2,
    ),
    "impulse_buyer": ShopperProfile(
        name="Impulse Buyer",
        impulse_probability=0.090,
        familiarity=0.45,
        exploration_rate=0.20,
        patience=115,
        discount_awareness=0.45,
        exposure_radius=2,
    ),
    "loyal_shopper": ShopperProfile(
        name="Loyal Shopper",
        impulse_probability=0.020,
        familiarity=0.92,
        exploration_rate=0.04,
        patience=105,
        discount_awareness=0.35,
        exposure_radius=2,
    ),
    "browser": ShopperProfile(
        name="Browser",
        impulse_probability=0.055,
        familiarity=0.30,
        exploration_rate=0.34,
        patience=155,
        discount_awareness=0.25,
        exposure_radius=2,
    ),
}


class CustomerAgent(Agent):
    """Shopper agent with planned-list and impulse-purchase behavior."""

    PATIENCE_TIME_COST_MULTIPLIER = 0.35
    PATIENCE_TRAFFIC_COST_PER_SHOPPER = 0.10
    MAX_TRAFFIC_PATIENCE_COST = 0.80
    PATIENCE_CONGESTION_DELAY_MULTIPLIER = 0.75
    SAME_TILE_CROWDING_COST_PER_SHOPPER = 0.42
    BLOCKED_TILE_PATIENCE_MULTIPLIER = 0.90
    CHECKOUT_PATIENCE_FRACTION = 0.45
    LOW_PATIENCE_CHECKOUT_THRESHOLD = 0.40
    QUEUE_PATIENCE_COST_MULTIPLIER = 0.55

    def __init__(
        self,
        uid: int,
        model,
        shopper_type: str,
        shopping_list: List[str],
        arrival_time: int = 0,
    ) -> None:
        self._init_mesa_agent(uid, model)
        if shopper_type not in SHOPPER_PROFILES:
            raise ValueError(f"Unknown shopper type '{shopper_type}'.")

        self.uid = uid
        self.shopper_type = shopper_type
        self.profile = SHOPPER_PROFILES[shopper_type]
        self.shopping_list = list(shopping_list)
        self.shopping_list_names = set(shopping_list)
        self.remaining_items = list(shopping_list)
        self.abandoned_items: List[str] = []
        self.max_patience = float(self.profile.patience)
        self.patience_level = self.max_patience
        self.checkout_patience_level = max(8.0, self.max_patience * self.CHECKOUT_PATIENCE_FRACTION)
        self.patience_lost_to_congestion = 0.0
        self.abandoned = False
        self.abandonment_time: Optional[int] = None
        self.abandonment_reason: Optional[str] = None

        self.bought_item_names: Set[str] = set()
        self.seen_item_names: Set[str] = set()
        self.planned_purchases: List[str] = []
        self.impulse_purchases: List[str] = []
        self.unlisted_purchases: List[str] = []
        self.basket_records: List[tuple[StoreItem, bool, bool]] = []
        self.basket_value = 0.0
        self.basket_profit = 0.0
        self.abandoned_value = 0.0
        self.abandoned_profit = 0.0

        self.arrival_time = max(0, arrival_time)
        self.arrived = False
        self.state = "waiting"
        self.time_spent = 0
        self.checkout_wait = 0
        self.checkout_wait_initial = 0
        self.checkout_wait_initial_minutes = 0.0
        self.checkout_time_spent = 0
        self.checkout_position = None
        self.force_checkout = False
        self.loop_entry_released = False
        self.following_loop_entry_route = False
        self.following_recent_purchase_exit = False
        self.recent_purchase_location = None
        self.move_away_steps_remaining = 0
        self.completed = False
        self.completion_time: Optional[int] = None
        self.completion_minutes: Optional[float] = None
        self.exposure_count = 0
        self.congestion_delay = 0
        self.path_history = []

    def _init_mesa_agent(self, uid: int, model) -> None:
        try:
            super().__init__(model)
        except TypeError:
            super().__init__(uid, model)

    def enter_store(self) -> bool:
        if self.arrived:
            return True

        entrance = self.model.choose_entrance_position()
        if not self.model.can_enter_tile(entrance, mover=self):
            return False

        self.arrived = True
        self.state = "shopping"
        self.model.grid.place_agent(self, entrance)
        self.path_history.append(entrance)
        return True

    def step(self) -> None:
        if self.completed or not self.arrived:
            return

        self.time_spent += 1
        if self.model.checkout_cutoff_active and self.state == "shopping":
            self.force_checkout = True
        if self.state == "shopping" and self.patience_ratio < self.LOW_PATIENCE_CHECKOUT_THRESHOLD:
            self.force_checkout = True

        if self.state == "checkout":
            time_cost = 0.0
        elif self._waiting_in_checkout_line() and not self._near_cashier():
            queue_cost = self.model.minutes_per_step * self.QUEUE_PATIENCE_COST_MULTIPLIER
            if self._reduce_checkout_patience(queue_cost):
                return
            time_cost = 0.0
        elif self.force_checkout:
            time_cost = 0.0
        else:
            time_cost = self.model.minutes_per_step * self.PATIENCE_TIME_COST_MULTIPLIER
        if self._reduce_patience(time_cost, "time"):
            return
        if self.state == "shopping" and self.patience_ratio < self.LOW_PATIENCE_CHECKOUT_THRESHOLD:
            self.force_checkout = True

        if self._apply_same_tile_crowding():
            return

        self._interact_with_visible_items()

        if self.state == "checkout":
            self._process_checkout()
            return

        target = self._choose_target()
        if self.model.layout.is_checkout(target) and self.pos == target:
            self._enter_checkout()
            return

        if self._move_toward(target):
            return

        self._interact_with_visible_items()

        if self.should_head_to_checkout and self.model.layout.is_checkout(self.pos):
            self._enter_checkout()

    def _reduce_patience(self, amount: float, reason: str) -> bool:
        if self.completed or amount <= 0:
            return False

        if self.state == "checkout":
            return self._reduce_checkout_patience(amount)

        if self.state != "shopping":
            return False

        self.patience_level = max(0.0, self.patience_level - amount)
        if reason in {"traffic", "congestion"}:
            self.patience_lost_to_congestion += amount

        if self.patience_level <= 0:
            if self.basket_records and reason in {"time", "traffic", "congestion"}:
                self.force_checkout = True
                self.patience_level = 1.0
                return False
            self._abandon_shopping(reason)
            return True
        if self.patience_ratio < self.LOW_PATIENCE_CHECKOUT_THRESHOLD:
            self.force_checkout = True
        return False

    def _reduce_checkout_patience(self, amount: float) -> bool:
        if self.completed or amount <= 0 or self._near_cashier():
            return False

        self.checkout_patience_level = max(0.0, self.checkout_patience_level - amount)
        if self.checkout_patience_level <= 0:
            self._abandon_shopping("checkout")
            return True
        return False

    def _waiting_in_checkout_line(self) -> bool:
        return self.model.layout.checkout_for_queue_cell(self.pos) is not None

    def _near_cashier(self) -> bool:
        if self.model.layout.is_checkout(self.pos):
            return True
        checkout_pos = self.model.layout.checkout_for_queue_cell(self.pos)
        if checkout_pos is None:
            return False
        lane = self.model.layout.checkout_queue_cells.get(checkout_pos, [])
        return bool(lane and self.pos == lane[0])

    def _abandon_shopping(self, reason: str) -> None:
        if self.completed:
            return

        self.abandoned = True
        self.completed = True
        self.state = "abandoned"
        self.abandonment_time = self.time_spent
        self.abandonment_reason = reason
        abandoned_names = list(dict.fromkeys(
            list(self.remaining_items) + [item.name for item, _, _ in self.basket_records]
        ))
        self.abandoned_items.extend(abandoned_names)
        self.abandoned_value = sum(
            self.model.layout.items_by_name[name].sale_price
            for name in self.abandoned_items
            if name in self.model.layout.items_by_name
        )
        self.abandoned_profit = sum(
            self.model.layout.items_by_name[name].profit
            for name in self.abandoned_items
            if name in self.model.layout.items_by_name
        )
        self.model.record_abandonment(self, reason)
        self.remaining_items.clear()

    def _apply_same_tile_crowding(self) -> bool:
        occupants = self.model.count_customers_on_tile(self.pos)
        extra_shoppers = max(0, occupants - self.model.TILE_COMFORT_CAPACITY)
        if extra_shoppers <= 0:
            return False

        crowding_cost = (
            extra_shoppers
            * self.model.minutes_per_step
            * self.SAME_TILE_CROWDING_COST_PER_SHOPPER
        )
        self.model.record_tile_crowding_patience_loss(crowding_cost)
        return self._reduce_patience(crowding_cost, "congestion")

    def _choose_target(self):
        self.following_loop_entry_route = False
        self.following_recent_purchase_exit = False
        if self.should_head_to_checkout:
            return self.model.checkout_target_for(self)

        loop_entry_target = self._loop_entry_route_target()
        if loop_entry_target is not None:
            self.following_loop_entry_route = True
            return loop_entry_target

        move_away_target = self._move_away_from_recent_purchase_target()
        if move_away_target is not None:
            self.following_recent_purchase_exit = True
            return move_away_target

        if self.shopper_type == "browser":
            if self.model.random.random() < 0.65 and self.model.layout.hot_zones:
                return self.model.random.choice(list(self.model.layout.hot_zones))
            browsing_cells = (
                self.model.layout.passable
                - set(self.model.layout.checkout_positions)
                - self.model.layout.all_checkout_queue_cells
            )
            return self.model.random.choice(list(browsing_cells or self.model.layout.passable))

        if self.shopper_type == "bargain_hunter":
            promoted = [
                name
                for name in self.items_left_to_find
                if self.model.layout.items_by_name.get(name)
                and self.model.layout.items_by_name[name].promotion
            ]
            if promoted:
                item = self.model.layout.nearest_item(promoted, self.pos)
                if item:
                    return item.location

        item = self.model.layout.nearest_item(self.items_left_to_find, self.pos)
        if item is None:
            return self.model.checkout_target_for(self)

        if self.model.random.random() > self.profile.familiarity:
            zone = self.model.layout.zone_centers.get(item.category)
            return zone or item.location
        return item.location

    def _move_away_from_recent_purchase_target(self):
        if (
            self.move_away_steps_remaining <= 0
            or self.recent_purchase_location is None
            or self.pos is None
        ):
            return None

        self.move_away_steps_remaining -= 1
        options = [
            cell
            for cell in self.model.layout.neighbors(self.pos)
            if self.model.can_enter_tile(cell, mover=self)
            and manhattan(cell, self.recent_purchase_location) > manhattan(self.pos, self.recent_purchase_location)
        ]
        if not options:
            return None

        return max(
            options,
            key=lambda cell: (
                manhattan(cell, self.recent_purchase_location),
                self.model.random.random(),
            ),
        )

    def _loop_entry_route_target(self):
        layout = self.model.layout
        if (
            layout.layout_name != "loop"
            or self.loop_entry_released
            or not layout.loop_path
        ):
            return None

        release_target = getattr(layout, "loop_entry_release_cell", None)
        if release_target is None:
            self.loop_entry_released = True
            return None

        if self.pos[1] <= release_target[1] or self.pos == release_target:
            self.loop_entry_released = True
            return None

        return release_target

    def _move_toward(self, target) -> bool:
        local_crowd = self.model.count_customers_near(self.pos, radius=1, include_self=False)
        traffic_cost = min(
            self.MAX_TRAFFIC_PATIENCE_COST,
            local_crowd * self.PATIENCE_TRAFFIC_COST_PER_SHOPPER,
        )
        if local_crowd and self._reduce_patience(traffic_cost, "traffic"):
            return True

        delay_probability = min(0.55, local_crowd * 0.075)
        if self.model.random.random() < delay_probability:
            self.congestion_delay += 1
            congestion_cost = (
                self.model.minutes_per_step * self.PATIENCE_CONGESTION_DELAY_MULTIPLIER
            )
            if self._reduce_patience(congestion_cost, "congestion"):
                return True
            return False

        step = self.model.layout.next_step(
            start=self.pos,
            target=target,
            rng=self.model.random,
            exploration_rate=0.0 if self.following_forced_route else self.profile.exploration_rate,
            familiarity=1.0 if self.following_forced_route else self.profile.familiarity,
        )
        step = self.model.preferred_movement_step(self, target, step)
        if step != self.pos:
            if not self.model.can_enter_tile(step, mover=self):
                self.congestion_delay += 1
                self.model.record_tile_capacity_block()
                blocked_cost = (
                    self.model.minutes_per_step
                    * self.BLOCKED_TILE_PATIENCE_MULTIPLIER
                )
                self.model.record_tile_crowding_patience_loss(blocked_cost)
                if self._reduce_patience(blocked_cost, "congestion"):
                    return True
                self.path_history.append(self.pos)
                return False
            self.model.grid.move_agent(self, step)
        self.path_history.append(self.pos)
        return False

    def _interact_with_visible_items(self) -> None:
        for item in self.model.layout.nearby_items(self.pos, self.profile.exposure_radius):
            if item.name in self.bought_item_names:
                continue

            distance = manhattan(self.pos, item.location)
            noticed = item.visibility / (1 + distance)
            if self.model.random.random() > noticed:
                continue

            if item.name not in self.seen_item_names:
                self.exposure_count += 1
                self.seen_item_names.add(item.name)

            if item.name in self.remaining_items:
                self._buy_item(item, planned=True)
            elif self._will_buy_impulse(item, distance):
                self._buy_item(item, planned=False)

    def _will_buy_impulse(self, item: StoreItem, distance: int) -> bool:
        if item.category not in {"snacks", "checkout", "bakery", "frozen"} and not item.promotion:
            base_gate = 0.55 if self.shopper_type in {"impulse_buyer", "browser"} else 0.32
            if self.model.random.random() > base_gate:
                return False

        probability = self.profile.impulse_probability
        probability *= item.visibility
        probability *= 1.0 / (1 + 0.35 * distance)

        if item.promotion:
            probability *= 1.0 + self.profile.discount_awareness
        if item.high_exposure:
            probability *= 1.35
        if self.model.layout.layout_name == "loop":
            probability *= 1.18
        elif self.model.layout.layout_name == "grid":
            probability *= 0.88

        return self.model.random.random() < min(0.38, probability)

    def _buy_item(self, item: StoreItem, planned: bool) -> None:
        if item.name in self.bought_item_names:
            return

        self.bought_item_names.add(item.name)
        self.remaining_items = [
            name for name in self.remaining_items if name not in self.bought_item_names
        ]
        self.recent_purchase_location = item.location
        self.move_away_steps_remaining = 2
        self.basket_value += item.sale_price
        self.basket_profit += item.profit
        on_shopping_list = item.name in self.shopping_list_names
        self.basket_records.append((item, planned, on_shopping_list))

        if planned:
            self.planned_purchases.append(item.name)
        else:
            self.impulse_purchases.append(item.name)

        if not on_shopping_list:
            self.unlisted_purchases.append(item.name)

    def _enter_checkout(self) -> None:
        self.checkout_position = self.pos
        self.checkout_wait = self.model.estimate_checkout_wait(self.checkout_position)
        self.checkout_wait_initial = self.checkout_wait
        self.checkout_wait_initial_minutes = round(
            self.checkout_wait * self.model.minutes_per_step,
            2,
        )
        self.state = "checkout"
        for item in self.model.layout.checkout_items():
            if item.name not in self.bought_item_names and self._will_buy_impulse(item, 0):
                self._buy_item(item, planned=False)

    def _process_checkout(self) -> None:
        self.checkout_time_spent += 1
        self.checkout_wait -= 1
        if self.checkout_wait <= 0:
            for item, planned, on_shopping_list in self.basket_records:
                self.model.record_purchase(
                    item,
                    planned=planned,
                    on_shopping_list=on_shopping_list,
                )
            self.completed = True
            self.state = "finished"
            self.completion_time = self.time_spent
            self.completion_minutes = round(self.time_spent * self.model.minutes_per_step, 2)

    @property
    def should_head_to_checkout(self) -> bool:
        return self.force_checkout or (bool(self.shopping_list) and not self.remaining_items)

    @property
    def following_forced_route(self) -> bool:
        return self.following_loop_entry_route or self.following_recent_purchase_exit

    @property
    def items_left_to_find(self) -> List[str]:
        return [
            name
            for name in self.remaining_items
            if name not in self.bought_item_names
        ]

    @property
    def patience_ratio(self) -> float:
        return self.patience_level / max(1.0, self.max_patience)

    @property
    def planned_completion_rate(self) -> float:
        if not self.shopping_list:
            return 1.0
        return len(self.planned_purchases) / len(self.shopping_list)

    @property
    def satisfaction(self) -> float:
        if self.abandoned:
            return 0.0
        if self.completion_time is None:
            return 0.0
        completion_minutes = self.completion_minutes or (
            self.completion_time * self.model.minutes_per_step
        )
        overtime = max(0.0, completion_minutes - self.max_patience)
        return max(0.0, 1.0 - overtime / max(1.0, self.max_patience))
