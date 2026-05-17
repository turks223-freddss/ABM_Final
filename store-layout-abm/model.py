from __future__ import annotations

from statistics import mean
from typing import Dict, List, Optional

import numpy as np
from mesa import Model
from mesa.datacollection import DataCollector
from mesa.space import MultiGrid

from customer_agent import CustomerAgent, SHOPPER_PROFILES
from store_layout import LAYOUT_NAMES, StoreItem, StoreLayout


DEFAULT_SHOPPER_MIX = {
    "mission_driven": 0.28,
    "bargain_hunter": 0.22,
    "impulse_buyer": 0.18,
    "loyal_shopper": 0.20,
    "browser": 0.12,
}


class StoreModel(Model):
    """Mesa model for grocery layout, shopper movement, and store profit."""

    def __init__(
        self,
        layout_name: str = "grid",
        width: int = 24,
        height: int = 16,
        num_shoppers: int = 40,
        max_steps: int = 250,
        promotion_level: float = 0.25,
        shopper_mix: Optional[Dict[str, float]] = None,
        seed: Optional[int] = None,
    ) -> None:
        self._init_mesa_model(seed)

        if layout_name not in LAYOUT_NAMES:
            raise ValueError(f"layout_name must be one of {LAYOUT_NAMES}.")
        if num_shoppers <= 0:
            raise ValueError("num_shoppers must be positive.")

        self.layout_name = layout_name
        self.width = width
        self.height = height
        self.num_shoppers = num_shoppers
        self.max_steps = max_steps
        self.promotion_level = promotion_level
        self.step_count = 0
        self.running = True

        self.grid = MultiGrid(width, height, torus=False)
        self.layout = StoreLayout(layout_name, width, height, promotion_level, self.random)
        self.customers: List[CustomerAgent] = []

        self.total_revenue = 0.0
        self.total_profit = 0.0
        self.planned_purchase_count = 0
        self.impulse_purchase_count = 0
        self.revenue_from_planned = 0.0
        self.revenue_from_impulse = 0.0

        self.shopper_mix = self._normalize_mix(shopper_mix or DEFAULT_SHOPPER_MIX)
        self._create_customers()

        self.datacollector = DataCollector(
            model_reporters={
                "step": lambda m: m.step_count,
                "active_shoppers": lambda m: m.active_shopper_count,
                "finished_shoppers": lambda m: m.finished_shopper_count,
                "revenue": lambda m: round(m.total_revenue, 2),
                "profit": lambda m: round(m.total_profit, 2),
                "impulse_purchases": lambda m: m.impulse_purchase_count,
                "planned_purchases": lambda m: m.planned_purchase_count,
                "avg_completion_time": lambda m: round(m.avg_completion_time, 2),
                "avg_planned_completion": lambda m: round(m.avg_planned_completion, 3),
                "avg_satisfaction": lambda m: round(m.avg_satisfaction, 3),
                "avg_congestion_delay": lambda m: round(m.avg_congestion_delay, 2),
            },
            agent_reporters={
                "shopper_type": lambda a: getattr(a, "shopper_type", None),
                "time_spent": lambda a: getattr(a, "time_spent", 0),
                "planned_completion": lambda a: getattr(a, "planned_completion_rate", 0),
                "impulse_purchases": lambda a: len(getattr(a, "impulse_purchases", [])),
                "completed": lambda a: getattr(a, "completed", False),
            },
        )
        self.datacollector.collect(self)

    def _init_mesa_model(self, seed: Optional[int]) -> None:
        try:
            super().__init__(rng=seed)
        except TypeError:
            try:
                super().__init__(seed=seed)
            except TypeError:
                super().__init__()
                if seed is not None:
                    self.random.seed(seed)

    def _normalize_mix(self, mix: Dict[str, float]) -> Dict[str, float]:
        unknown = set(mix) - set(SHOPPER_PROFILES)
        if unknown:
            raise ValueError(f"Unknown shopper type(s): {sorted(unknown)}")

        total = sum(max(0.0, weight) for weight in mix.values())
        if total <= 0:
            raise ValueError("shopper_mix must contain at least one positive weight.")
        return {key: max(0.0, value) / total for key, value in mix.items()}

    def _create_customers(self) -> None:
        shopper_types = list(self.shopper_mix)
        weights = [self.shopper_mix[name] for name in shopper_types]
        for index in range(self.num_shoppers):
            shopper_type = self._weighted_choice(shopper_types, weights)
            shopping_list = self._generate_shopping_list(shopper_type)
            customer = CustomerAgent(index + 1, self, shopper_type, shopping_list)
            self.grid.place_agent(customer, self.layout.entrance)
            customer.path_history.append(self.layout.entrance)
            self.customers.append(customer)

    def _weighted_choice(self, options: List[str], weights: List[float]) -> str:
        threshold = self.random.random() * sum(weights)
        running = 0.0
        for option, weight in zip(options, weights):
            running += weight
            if threshold <= running:
                return option
        return options[-1]

    def _generate_shopping_list(self, shopper_type: str) -> List[str]:
        essentials = self.layout.essential_item_names()
        non_checkout = [item.name for item in self.layout.items if item.category != "checkout"]

        if shopper_type in {"mission_driven", "loyal_shopper"}:
            size = self.random.randint(4, 6)
            pool = essentials
        elif shopper_type == "browser":
            size = self.random.randint(2, 4)
            pool = non_checkout
        else:
            size = self.random.randint(3, 5)
            pool = essentials + non_checkout

        size = min(size, len(set(pool)))
        return self.random.sample(list(dict.fromkeys(pool)), size)

    def step(self) -> None:
        if not self.running:
            return

        self.step_count += 1
        active = [customer for customer in self.customers if not customer.completed]
        self.random.shuffle(active)
        for customer in active:
            customer.step()

        self.datacollector.collect(self)
        if self.step_count >= self.max_steps or self.finished_shopper_count == self.num_shoppers:
            self.running = False

    def run_model(self, max_steps: Optional[int] = None) -> None:
        target_steps = max_steps or self.max_steps
        while self.running and self.step_count < target_steps:
            self.step()

    def record_purchase(self, item: StoreItem, planned: bool) -> None:
        self.total_revenue += item.sale_price
        self.total_profit += item.profit
        if planned:
            self.planned_purchase_count += 1
            self.revenue_from_planned += item.sale_price
        else:
            self.impulse_purchase_count += 1
            self.revenue_from_impulse += item.sale_price

    def estimate_checkout_wait(self) -> int:
        queue_pressure = sum(
            1
            for customer in self.customers
            if not customer.completed
            and customer.state == "checkout"
            and customer.pos == self.layout.checkout
        )
        return 3 + queue_pressure + self.random.randint(0, 3)

    def count_customers_near(self, pos, radius: int = 1, include_self: bool = True) -> int:
        count = 0
        px, py = pos
        for customer in self.customers:
            if customer.completed or customer.pos is None:
                continue
            if not include_self and customer.pos == pos:
                continue
            cx, cy = customer.pos
            if abs(px - cx) + abs(py - cy) <= radius:
                count += 1
        return count

    @property
    def active_shopper_count(self) -> int:
        return sum(1 for customer in self.customers if not customer.completed)

    @property
    def finished_shopper_count(self) -> int:
        return sum(1 for customer in self.customers if customer.completed)

    @property
    def avg_completion_time(self) -> float:
        completed_times = [
            customer.completion_time
            for customer in self.customers
            if customer.completion_time is not None
        ]
        return mean(completed_times) if completed_times else 0.0

    @property
    def avg_planned_completion(self) -> float:
        return mean(customer.planned_completion_rate for customer in self.customers)

    @property
    def avg_satisfaction(self) -> float:
        finished = [customer for customer in self.customers if customer.completed]
        return mean(customer.satisfaction for customer in finished) if finished else 0.0

    @property
    def avg_congestion_delay(self) -> float:
        return mean(customer.congestion_delay for customer in self.customers)

    def traffic_heatmap(self) -> np.ndarray:
        heatmap = np.zeros((self.height, self.width), dtype=int)
        for customer in self.customers:
            for x, y in customer.path_history:
                heatmap[y, x] += 1
        return heatmap

    def summary(self) -> Dict[str, float]:
        completion_rate = self.finished_shopper_count / self.num_shoppers
        avg_impulse_per_customer = self.impulse_purchase_count / self.num_shoppers
        avg_revenue_per_customer = self.total_revenue / self.num_shoppers
        return {
            "layout": self.layout_name,
            "shoppers": self.num_shoppers,
            "steps_run": self.step_count,
            "finished_shoppers": self.finished_shopper_count,
            "completion_rate": round(completion_rate, 3),
            "avg_completion_time": round(self.avg_completion_time, 2),
            "avg_planned_completion": round(self.avg_planned_completion, 3),
            "avg_satisfaction": round(self.avg_satisfaction, 3),
            "planned_purchases": self.planned_purchase_count,
            "impulse_purchases": self.impulse_purchase_count,
            "avg_impulse_per_customer": round(avg_impulse_per_customer, 3),
            "revenue": round(self.total_revenue, 2),
            "profit": round(self.total_profit, 2),
            "revenue_from_planned": round(self.revenue_from_planned, 2),
            "revenue_from_impulse": round(self.revenue_from_impulse, 2),
            "avg_revenue_per_customer": round(avg_revenue_per_customer, 2),
            "avg_congestion_delay": round(self.avg_congestion_delay, 2),
        }
