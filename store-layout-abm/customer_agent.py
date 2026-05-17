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
        exposure_radius=1,
    ),
    "bargain_hunter": ShopperProfile(
        name="Bargain Hunter",
        impulse_probability=0.035,
        familiarity=0.65,
        exploration_rate=0.12,
        patience=125,
        discount_awareness=0.85,
        exposure_radius=1,
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
        exposure_radius=1,
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

    def __init__(self, uid: int, model, shopper_type: str, shopping_list: List[str]) -> None:
        self._init_mesa_agent(uid, model)
        if shopper_type not in SHOPPER_PROFILES:
            raise ValueError(f"Unknown shopper type '{shopper_type}'.")

        self.uid = uid
        self.shopper_type = shopper_type
        self.profile = SHOPPER_PROFILES[shopper_type]
        self.shopping_list = list(shopping_list)
        self.remaining_items = list(shopping_list)
        self.abandoned_items: List[str] = []

        self.bought_item_names: Set[str] = set()
        self.seen_item_names: Set[str] = set()
        self.planned_purchases: List[str] = []
        self.impulse_purchases: List[str] = []
        self.basket_value = 0.0
        self.basket_profit = 0.0

        self.state = "shopping"
        self.time_spent = 0
        self.checkout_wait = 0
        self.completed = False
        self.completion_time: Optional[int] = None
        self.exposure_count = 0
        self.congestion_delay = 0
        self.path_history = []

    def _init_mesa_agent(self, uid: int, model) -> None:
        try:
            super().__init__(model)
        except TypeError:
            super().__init__(uid, model)

    def step(self) -> None:
        if self.completed:
            return

        self.time_spent += 1
        self._interact_with_visible_items()

        if self.state == "checkout":
            self._process_checkout()
            return

        if self.remaining_items and self.time_spent > self.profile.patience:
            if self.model.random.random() < 0.10:
                self.abandoned_items.extend(self.remaining_items)
                self.remaining_items.clear()

        target = self._choose_target()
        if target == self.model.layout.checkout and self.pos == self.model.layout.checkout:
            self._enter_checkout()
            return

        self._move_toward(target)
        self._interact_with_visible_items()

        if not self.remaining_items and self.pos == self.model.layout.checkout:
            self._enter_checkout()

    def _choose_target(self):
        if not self.remaining_items:
            return self.model.layout.checkout

        if self.shopper_type == "bargain_hunter":
            promoted = [
                name
                for name in self.remaining_items
                if self.model.layout.items_by_name.get(name)
                and self.model.layout.items_by_name[name].promotion
            ]
            if promoted:
                item = self.model.layout.nearest_item(promoted, self.pos)
                if item:
                    return item.location

        if self.shopper_type == "browser" and self.model.random.random() < 0.22:
            return self.model.random.choice(list(self.model.layout.hot_zones))

        item = self.model.layout.nearest_item(self.remaining_items, self.pos)
        if item is None:
            return self.model.layout.checkout

        if self.model.random.random() > self.profile.familiarity:
            zone = self.model.layout.zone_centers.get(item.category)
            return zone or item.location
        return item.location

    def _move_toward(self, target) -> None:
        local_crowd = self.model.count_customers_near(self.pos, radius=1, include_self=False)
        delay_probability = min(0.55, local_crowd * 0.075)
        if self.model.random.random() < delay_probability:
            self.congestion_delay += 1
            return

        step = self.model.layout.next_step(
            start=self.pos,
            target=target,
            rng=self.model.random,
            exploration_rate=self.profile.exploration_rate,
            familiarity=self.profile.familiarity,
        )
        if step != self.pos:
            self.model.grid.move_agent(self, step)
        self.path_history.append(self.pos)

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
        self.bought_item_names.add(item.name)
        self.basket_value += item.sale_price
        self.basket_profit += item.profit
        self.model.record_purchase(item, planned=planned)

        if planned:
            self.planned_purchases.append(item.name)
            if item.name in self.remaining_items:
                self.remaining_items.remove(item.name)
        else:
            self.impulse_purchases.append(item.name)

    def _enter_checkout(self) -> None:
        self.state = "checkout"
        self.checkout_wait = self.model.estimate_checkout_wait()
        for item in self.model.layout.checkout_items():
            if item.name not in self.bought_item_names and self._will_buy_impulse(item, 0):
                self._buy_item(item, planned=False)

    def _process_checkout(self) -> None:
        self.checkout_wait -= 1
        if self.checkout_wait <= 0:
            self.completed = True
            self.state = "finished"
            self.completion_time = self.time_spent

    @property
    def planned_completion_rate(self) -> float:
        if not self.shopping_list:
            return 1.0
        return len(self.planned_purchases) / len(self.shopping_list)

    @property
    def satisfaction(self) -> float:
        if self.completion_time is None:
            return 0.0
        overtime = max(0, self.completion_time - self.profile.patience)
        return max(0.0, 1.0 - overtime / max(1, self.profile.patience))
