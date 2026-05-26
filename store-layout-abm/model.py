from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from statistics import mean
from typing import Dict, List, Optional, Set, Tuple

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

DEFAULT_DAILY_SHOPPERS = 400

DEFAULT_TRAFFIC_SHAPE = (
    (0.0, 1 / 12, 0.05, "Opening"),
    (1 / 12, 2 / 12, 0.35, "Morning peak"),
    (2 / 12, 6 / 12, 0.15, "Midday"),
    (6 / 12, 8 / 12, 0.35, "Afternoon peak"),
    (8 / 12, 1.0, 0.10, "Evening"),
)


@dataclass(frozen=True)
class TrafficPeriod:
    start_hour: float
    end_hour: float
    share: float
    label: str


class StoreModel(Model):
    """Mesa model for grocery layout, shopper movement, and store profit."""

    def __init__(
        self,
        layout_name: str = "grid",
        width: int = 24,
        height: int = 16,
        num_shoppers: int | str = DEFAULT_DAILY_SHOPPERS,
        max_steps: int = 720,
        promotion_level: float = 0.25,
        shopper_mix: Optional[Dict[str, float]] = None,
        opening_hour: float = 9.0,
        closing_hour: float = 21.0,
        traffic_profile: Optional[List[TrafficPeriod]] = None,
        seed: Optional[int] = None,
    ) -> None:
        self._init_mesa_model(seed)

        if layout_name not in LAYOUT_NAMES:
            raise ValueError(f"layout_name must be one of {LAYOUT_NAMES}.")
        num_shoppers = self._coerce_positive_int(num_shoppers, "num_shoppers")
        if max_steps <= 0:
            raise ValueError("max_steps must be positive.")
        if closing_hour <= opening_hour:
            raise ValueError("closing_hour must be after opening_hour.")

        self.layout_name = layout_name
        self.width = width
        self.height = height
        self.num_shoppers = num_shoppers
        self.max_steps = max_steps
        self.promotion_level = promotion_level
        self.opening_hour = float(opening_hour)
        self.closing_hour = float(closing_hour)
        self.minutes_per_step = self._minutes_per_step()
        self.step_count = 0
        self.running = True

        self.grid = MultiGrid(width, height, torus=False)
        self.layout = StoreLayout(layout_name, width, height, promotion_level, self.random)
        self.customers: List[CustomerAgent] = []
        self.arrival_window_steps = self._default_arrival_window()
        self.traffic_profile = self._normalize_traffic_profile(
            traffic_profile or self._default_traffic_profile()
        )

        self.total_revenue = 0.0
        self.total_profit = 0.0
        self.planned_purchase_count = 0
        self.impulse_purchase_count = 0
        self.unlisted_purchase_count = 0
        self.revenue_from_planned = 0.0
        self.revenue_from_impulse = 0.0
        self.revenue_from_unlisted = 0.0
        self.profit_from_unlisted = 0.0
        self.lost_revenue_from_abandonment = 0.0
        self.lost_profit_from_abandonment = 0.0
        self.abandonment_reason_counts: Dict[str, int] = {
            "time": 0,
            "traffic": 0,
            "congestion": 0,
            "checkout": 0,
        }
        self.checkout_entry_count = 0
        self.total_checkout_wait = 0
        self.max_checkout_wait = 0
        self.longest_checkout_queue = 0
        self.item_metrics = {
            item.name: self._empty_sales_bucket(item.category)
            for item in self.layout.items
        }
        self.category_metrics: Dict[str, Dict[str, float]] = {}

        self.shopper_mix = self._normalize_mix(shopper_mix or DEFAULT_SHOPPER_MIX)
        self._create_customers()
        self._activate_arrivals()

        self.datacollector = DataCollector(
            model_reporters={
                "step": lambda m: m.step_count,
                "store_hour": lambda m: round(m.current_store_hour, 2),
                "store_time": lambda m: m.current_time_label,
                "traffic_period": lambda m: m.current_traffic_period,
                "traffic_share": lambda m: round(m.current_traffic_share, 3),
                "target_active_shoppers": lambda m: m.target_active_shopper_count,
                "active_shopper_share": lambda m: round(m.active_shopper_share, 3),
                "active_shoppers": lambda m: m.active_shopper_count,
                "arrived_shoppers": lambda m: m.arrived_shopper_count,
                "waiting_shoppers": lambda m: m.waiting_shopper_count,
                "finished_shoppers": lambda m: m.finished_shopper_count,
                "abandoned_shoppers": lambda m: m.abandoned_shopper_count,
                "checkout_queue": lambda m: m.checkout_queue_length,
                "revenue": lambda m: round(m.total_revenue, 2),
                "profit": lambda m: round(m.total_profit, 2),
                "impulse_purchases": lambda m: m.impulse_purchase_count,
                "planned_purchases": lambda m: m.planned_purchase_count,
                "unlisted_purchases": lambda m: m.unlisted_purchase_count,
                "revenue_from_unlisted": lambda m: round(m.revenue_from_unlisted, 2),
                "profit_from_unlisted": lambda m: round(m.profit_from_unlisted, 2),
                "lost_revenue_from_abandonment": lambda m: round(
                    m.lost_revenue_from_abandonment,
                    2,
                ),
                "lost_profit_from_abandonment": lambda m: round(
                    m.lost_profit_from_abandonment,
                    2,
                ),
                "avg_completion_time": lambda m: round(m.avg_completion_time, 2),
                "avg_completion_minutes": lambda m: round(m.avg_completion_minutes, 2),
                "avg_planned_completion": lambda m: round(m.avg_planned_completion, 3),
                "avg_satisfaction": lambda m: round(m.avg_satisfaction, 3),
                "avg_congestion_delay": lambda m: round(m.avg_congestion_delay, 2),
                "avg_checkout_wait": lambda m: round(m.avg_checkout_wait, 2),
                "longest_checkout_queue": lambda m: m.longest_checkout_queue,
                "avg_basket_value": lambda m: round(m.avg_basket_value, 2),
                "avg_basket_profit": lambda m: round(m.avg_basket_profit, 2),
                "avg_items_per_shopper": lambda m: round(m.avg_items_per_shopper, 2),
                "avg_patience_remaining": lambda m: round(m.avg_patience_remaining, 2),
                "avg_patience_lost_to_congestion": lambda m: round(
                    m.avg_patience_lost_to_congestion,
                    2,
                ),
                "layout_score": lambda m: round(m.layout_score, 2),
            },
            agent_reporters={
                "shopper_type": lambda a: getattr(a, "shopper_type", None),
                "arrival_time": lambda a: getattr(a, "arrival_time", 0),
                "arrival_clock_time": lambda a: a.model.step_to_time_label(
                    getattr(a, "arrival_time", 0)
                ),
                "arrived": lambda a: getattr(a, "arrived", False),
                "shopping_list": lambda a: ", ".join(getattr(a, "shopping_list", [])),
                "shopping_list_size": lambda a: len(getattr(a, "shopping_list", [])),
                "time_spent": lambda a: getattr(a, "time_spent", 0),
                "patience_level": lambda a: round(getattr(a, "patience_level", 0.0), 2),
                "abandoned": lambda a: getattr(a, "abandoned", False),
                "abandonment_reason": lambda a: getattr(a, "abandonment_reason", None),
                "planned_completion": lambda a: getattr(a, "planned_completion_rate", 0),
                "impulse_purchases": lambda a: len(getattr(a, "impulse_purchases", [])),
                "unlisted_purchases": lambda a: len(getattr(a, "unlisted_purchases", [])),
                "abandoned_items": lambda a: len(getattr(a, "abandoned_items", [])),
                "basket_value": lambda a: round(getattr(a, "basket_value", 0.0), 2),
                "basket_profit": lambda a: round(getattr(a, "basket_profit", 0.0), 2),
                "checkout_wait": lambda a: getattr(a, "checkout_wait_initial", 0),
                "checkout_wait_minutes": lambda a: getattr(
                    a,
                    "checkout_wait_initial_minutes",
                    0.0,
                ),
                "checkout_time_spent": lambda a: getattr(a, "checkout_time_spent", 0),
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

    def _coerce_positive_int(self, value: int | str, name: str) -> int:
        try:
            parsed = int(str(value).replace(",", "").strip())
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be a positive whole number.") from exc
        if parsed <= 0:
            raise ValueError(f"{name} must be positive.")
        return parsed

    def _minutes_per_step(self) -> float:
        return (self.closing_hour - self.opening_hour) * 60 / self.max_steps

    def _default_arrival_window(self) -> int:
        return self.max_steps

    def _default_traffic_profile(self) -> List[TrafficPeriod]:
        open_duration = self.closing_hour - self.opening_hour
        return [
            TrafficPeriod(
                start_hour=self.opening_hour + start_fraction * open_duration,
                end_hour=self.opening_hour + end_fraction * open_duration,
                share=share,
                label=label,
            )
            for start_fraction, end_fraction, share, label in DEFAULT_TRAFFIC_SHAPE
        ]

    def _normalize_traffic_profile(
        self,
        traffic_profile: List[TrafficPeriod],
    ) -> List[TrafficPeriod]:
        if not traffic_profile:
            raise ValueError("traffic_profile must contain at least one period.")

        normalized_periods: List[TrafficPeriod] = []
        total_share = 0.0
        for period in traffic_profile:
            if period.end_hour <= period.start_hour:
                raise ValueError("Each traffic period must end after it starts.")
            if period.start_hour < self.opening_hour or period.end_hour > self.closing_hour:
                raise ValueError("Traffic periods must fit inside opening and closing hours.")
            if period.share < 0:
                raise ValueError("Traffic period shares cannot be negative.")
            total_share += period.share

        if total_share <= 0:
            raise ValueError("traffic_profile must contain at least one positive share.")

        for period in sorted(traffic_profile, key=lambda item: item.start_hour):
            normalized_periods.append(
                TrafficPeriod(
                    start_hour=period.start_hour,
                    end_hour=period.end_hour,
                    share=period.share / total_share,
                    label=period.label,
                )
            )
        return normalized_periods

    def _traffic_segment_counts(self) -> List[int]:
        raw_counts = [period.share * self.num_shoppers for period in self.traffic_profile]
        counts = [int(count) for count in raw_counts]
        remaining = self.num_shoppers - sum(counts)
        remainders = sorted(
            range(len(raw_counts)),
            key=lambda index: raw_counts[index] - counts[index],
            reverse=True,
        )
        for index in remainders[:remaining]:
            counts[index] += 1
        return counts

    def _arrival_times_from_traffic_profile(self) -> List[int]:
        arrival_times: List[int] = []
        for period, count in zip(self.traffic_profile, self._traffic_segment_counts()):
            if count <= 0:
                continue

            start_step = self._hour_to_step(period.start_hour)
            arrival_times.extend([start_step] * count)

        return sorted(arrival_times)

    def _hour_to_step(self, hour: float) -> int:
        open_duration = self.closing_hour - self.opening_hour
        progress = (hour - self.opening_hour) / open_duration
        progress = max(0.0, min(1.0, progress))
        return round(progress * self.max_steps)

    def step_to_store_hour(self, step: int) -> float:
        progress = max(0.0, min(1.0, step / max(1, self.max_steps)))
        return self.opening_hour + progress * (self.closing_hour - self.opening_hour)

    def step_to_time_label(self, step: int) -> str:
        return self._format_hour(self.step_to_store_hour(step))

    def _format_hour(self, hour: float) -> str:
        total_minutes = int(round(hour * 60))
        hour24 = (total_minutes // 60) % 24
        minute = total_minutes % 60
        suffix = "AM" if hour24 < 12 else "PM"
        display_hour = hour24 % 12 or 12
        return f"{display_hour}:{minute:02d} {suffix}"

    def _empty_sales_bucket(self, category: str) -> Dict[str, float]:
        return {
            "category": category,
            "units": 0,
            "planned_units": 0,
            "impulse_units": 0,
            "unlisted_units": 0,
            "revenue": 0.0,
            "profit": 0.0,
            "unlisted_revenue": 0.0,
            "unlisted_profit": 0.0,
            "lost_units": 0,
            "lost_revenue": 0.0,
            "lost_profit": 0.0,
        }

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
        used_shopping_lists: Set[Tuple[str, ...]] = set()
        arrival_times = self._arrival_times_from_traffic_profile()
        for index in range(self.num_shoppers):
            shopper_type = self._weighted_choice(shopper_types, weights)
            shopping_list = self._generate_unique_shopping_list(shopper_type, used_shopping_lists)
            customer = CustomerAgent(
                index + 1,
                self,
                shopper_type,
                shopping_list,
                arrival_time=arrival_times[index],
            )
            self.customers.append(customer)

    def _activate_arrivals(self) -> None:
        available_slots = self.target_active_shopper_count - self.active_shopper_count
        if available_slots <= 0:
            return

        eligible_customers = [
            customer
            for customer in self.customers
            if not customer.arrived and customer.arrival_time <= self.step_count
        ]
        self.random.shuffle(eligible_customers)
        for customer in eligible_customers[:available_slots]:
            customer.enter_store()

    def _weighted_choice(self, options: List[str], weights: List[float]) -> str:
        threshold = self.random.random() * sum(weights)
        running = 0.0
        for option, weight in zip(options, weights):
            running += weight
            if threshold <= running:
                return option
        return options[-1]

    def _generate_unique_shopping_list(
        self,
        shopper_type: str,
        used_shopping_lists: Set[Tuple[str, ...]],
    ) -> List[str]:
        for _ in range(200):
            shopping_list = self._generate_shopping_list(shopper_type)
            key = self._shopping_list_key(shopping_list)
            if key not in used_shopping_lists:
                used_shopping_lists.add(key)
                return shopping_list

        shopping_list = self._fallback_unique_shopping_list(shopper_type, used_shopping_lists)
        used_shopping_lists.add(self._shopping_list_key(shopping_list))
        return shopping_list

    def _generate_shopping_list(self, shopper_type: str) -> List[str]:
        listable_items = self.layout.listable_items()
        if not listable_items:
            return []

        min_size, max_size = self._shopping_list_size_bounds(shopper_type)
        min_size = min(min_size, len(listable_items))
        max_size = min(max_size, len(listable_items))
        probabilities = {
            item.name: self._adjusted_list_probability(item, shopper_type)
            for item in listable_items
        }

        selected = [
            item.name
            for item in listable_items
            if self.random.random() < probabilities[item.name]
        ]

        if len(selected) < min_size:
            selected_names = set(selected)
            remaining = [
                item
                for item in listable_items
                if item.name not in selected_names
            ]
            selected.extend(
                self._weighted_sample_without_replacement(
                    [item.name for item in remaining],
                    [probabilities[item.name] for item in remaining],
                    min_size - len(selected),
                )
            )
        elif len(selected) > max_size:
            selected = self._weighted_sample_without_replacement(
                selected,
                [probabilities[name] for name in selected],
                max_size,
            )

        self.random.shuffle(selected)
        return selected

    def _shopping_list_size_bounds(self, shopper_type: str) -> Tuple[int, int]:
        if shopper_type in {"mission_driven", "loyal_shopper"}:
            return (5, 8)
        if shopper_type == "browser":
            return (2, 5)
        if shopper_type == "impulse_buyer":
            return (3, 6)
        return (4, 7)

    def _adjusted_list_probability(self, item: StoreItem, shopper_type: str) -> float:
        probability = item.list_probability

        if shopper_type == "mission_driven":
            probability *= 1.20 if item.is_essential else 0.40
        elif shopper_type == "loyal_shopper":
            probability *= 1.25 if item.is_essential else 0.50
        elif shopper_type == "bargain_hunter":
            probability *= 1.35 if item.promotion else 0.90
        elif shopper_type == "impulse_buyer":
            probability *= 0.80
        elif shopper_type == "browser":
            probability *= 0.55

        return min(0.95, max(0.01, probability))

    def _weighted_sample_without_replacement(
        self,
        options: List[str],
        weights: List[float],
        count: int,
    ) -> List[str]:
        pool = [
            (option, max(0.0, weight))
            for option, weight in zip(options, weights)
        ]
        selected: List[str] = []
        for _ in range(min(count, len(pool))):
            total = sum(weight for _, weight in pool)
            if total <= 0:
                index = self.random.randrange(len(pool))
            else:
                threshold = self.random.random() * total
                running = 0.0
                index = len(pool) - 1
                for candidate_index, (_, weight) in enumerate(pool):
                    running += weight
                    if threshold <= running:
                        index = candidate_index
                        break
            option, _ = pool.pop(index)
            selected.append(option)
        return selected

    def _shopping_list_key(self, shopping_list: List[str] | Tuple[str, ...]) -> Tuple[str, ...]:
        return tuple(sorted(shopping_list))

    def _fallback_unique_shopping_list(
        self,
        shopper_type: str,
        used_shopping_lists: Set[Tuple[str, ...]],
    ) -> List[str]:
        item_names = [item.name for item in self.layout.listable_items()]
        min_size, max_size = self._shopping_list_size_bounds(shopper_type)
        max_size = min(max_size, len(item_names))
        sizes = list(range(min(min_size, max_size), max_size + 1))
        self.random.shuffle(sizes)

        for size in sizes:
            candidates = list(item_names)
            self.random.shuffle(candidates)
            for combination in combinations(candidates, size):
                key = self._shopping_list_key(combination)
                if key not in used_shopping_lists:
                    shopping_list = list(combination)
                    self.random.shuffle(shopping_list)
                    return shopping_list

        raise RuntimeError(
            "Unable to create a unique shopping list for every shopper. "
            "Reduce num_shoppers or add more listable products."
        )

    def step(self) -> None:
        if not self.running:
            return

        self.step_count += 1
        self._activate_arrivals()
        active = [
            customer
            for customer in self.customers
            if customer.arrived and not customer.completed
        ]
        self.random.shuffle(active)
        for customer in active:
            customer.step()

        self.datacollector.collect(self)
        if self.step_count >= self.max_steps or self.incomplete_shopper_count == 0:
            self.running = False

    def run_model(self, max_steps: Optional[int] = None) -> None:
        target_steps = max_steps or self.max_steps
        while self.running and self.step_count < target_steps:
            self.step()

    def _category_bucket(self, category: str) -> Dict[str, float]:
        if category not in self.category_metrics:
            self.category_metrics[category] = self._empty_sales_bucket(category)
        return self.category_metrics[category]

    def _record_item_metric(
        self,
        item: StoreItem,
        field: str,
        amount: float = 1.0,
    ) -> None:
        self.item_metrics[item.name][field] += amount
        self._category_bucket(item.category)[field] += amount

    def record_purchase(self, item: StoreItem, planned: bool, on_shopping_list: bool) -> None:
        self.total_revenue += item.sale_price
        self.total_profit += item.profit
        self._record_item_metric(item, "units")
        self._record_item_metric(item, "revenue", item.sale_price)
        self._record_item_metric(item, "profit", item.profit)
        if planned:
            self.planned_purchase_count += 1
            self.revenue_from_planned += item.sale_price
            self._record_item_metric(item, "planned_units")
        else:
            self.impulse_purchase_count += 1
            self.revenue_from_impulse += item.sale_price
            self._record_item_metric(item, "impulse_units")
        if not on_shopping_list:
            self.unlisted_purchase_count += 1
            self.revenue_from_unlisted += item.sale_price
            self.profit_from_unlisted += item.profit
            self._record_item_metric(item, "unlisted_units")
            self._record_item_metric(item, "unlisted_revenue", item.sale_price)
            self._record_item_metric(item, "unlisted_profit", item.profit)

    def record_abandonment(self, customer: CustomerAgent, reason: str) -> None:
        self.abandonment_reason_counts[reason] = (
            self.abandonment_reason_counts.get(reason, 0) + 1
        )
        self.lost_revenue_from_abandonment += customer.abandoned_value
        self.lost_profit_from_abandonment += customer.abandoned_profit
        for name in customer.abandoned_items:
            item = self.layout.items_by_name.get(name)
            if item is None:
                continue
            self._record_item_metric(item, "lost_units")
            self._record_item_metric(item, "lost_revenue", item.sale_price)
            self._record_item_metric(item, "lost_profit", item.profit)

    def estimate_checkout_wait(self) -> int:
        queue_pressure = sum(
            1
            for customer in self.customers
            if not customer.completed
            and customer.state == "checkout"
            and customer.pos == self.layout.checkout
        )
        queue_length = queue_pressure + 1
        wait_minutes = 3.0 + queue_pressure * 1.2 + self.random.random() * 3.0
        wait = max(1, round(wait_minutes / self.minutes_per_step))
        self.checkout_entry_count += 1
        self.total_checkout_wait += wait_minutes
        self.max_checkout_wait = max(self.max_checkout_wait, wait_minutes)
        self.longest_checkout_queue = max(self.longest_checkout_queue, queue_length)
        return wait

    def count_customers_near(self, pos, radius: int = 1, include_self: bool = True) -> int:
        nearby_agents = self.grid.get_neighbors(
            pos,
            moore=False,
            include_center=include_self,
            radius=radius,
        )
        return sum(
            1
            for agent in nearby_agents
            if isinstance(agent, CustomerAgent) and not agent.completed
        )

    @property
    def active_shopper_count(self) -> int:
        return sum(
            1
            for customer in self.customers
            if customer.arrived and not customer.completed
        )

    @property
    def active_shopper_share(self) -> float:
        return self.active_shopper_count / self.num_shoppers

    @property
    def current_store_hour(self) -> float:
        return self.step_to_store_hour(self.step_count)

    @property
    def current_time_label(self) -> str:
        return self._format_hour(self.current_store_hour)

    @property
    def current_traffic_segment(self) -> TrafficPeriod:
        current_hour = self.current_store_hour
        for period in self.traffic_profile:
            if period.start_hour <= current_hour < period.end_hour:
                return period
        return self.traffic_profile[-1]

    @property
    def current_traffic_period(self) -> str:
        return self.current_traffic_segment.label

    @property
    def current_traffic_share(self) -> float:
        return self.current_traffic_segment.share

    @property
    def target_active_shopper_count(self) -> int:
        return round(self.num_shoppers * self.current_traffic_share)

    @property
    def traffic_profile_summary(self) -> str:
        return "; ".join(
            f"{self._format_hour(period.start_hour)}-{self._format_hour(period.end_hour)} "
            f"{period.share:.0%} {period.label}"
            for period in self.traffic_profile
        )

    @property
    def arrived_shopper_count(self) -> int:
        return sum(1 for customer in self.customers if customer.arrived)

    @property
    def waiting_shopper_count(self) -> int:
        return sum(1 for customer in self.customers if not customer.arrived)

    @property
    def incomplete_shopper_count(self) -> int:
        return sum(1 for customer in self.customers if not customer.completed)

    @property
    def finished_shopper_count(self) -> int:
        return sum(1 for customer in self.customers if customer.state == "finished")

    @property
    def abandoned_shopper_count(self) -> int:
        return sum(1 for customer in self.customers if customer.abandoned)

    @property
    def abandoned_list_item_count(self) -> int:
        return sum(len(customer.abandoned_items) for customer in self.customers)

    @property
    def avg_completion_time(self) -> float:
        completed_times = [
            customer.completion_time
            for customer in self.customers
            if customer.completion_time is not None
        ]
        return mean(completed_times) if completed_times else 0.0

    @property
    def avg_completion_minutes(self) -> float:
        completed_minutes = [
            customer.completion_minutes
            for customer in self.customers
            if customer.completion_minutes is not None
        ]
        return mean(completed_minutes) if completed_minutes else 0.0

    @property
    def avg_planned_completion(self) -> float:
        return mean(customer.planned_completion_rate for customer in self.customers)

    @property
    def avg_satisfaction(self) -> float:
        inactive = [customer for customer in self.customers if customer.completed]
        return mean(customer.satisfaction for customer in inactive) if inactive else 0.0

    @property
    def avg_congestion_delay(self) -> float:
        return mean(customer.congestion_delay for customer in self.customers)

    @property
    def checkout_queue_length(self) -> int:
        return sum(
            1
            for customer in self.customers
            if customer.arrived
            and not customer.completed
            and customer.state == "checkout"
            and customer.pos == self.layout.checkout
        )

    @property
    def avg_checkout_wait(self) -> float:
        if self.checkout_entry_count == 0:
            return 0.0
        return self.total_checkout_wait / self.checkout_entry_count

    @property
    def avg_basket_value(self) -> float:
        return mean(customer.basket_value for customer in self.customers)

    @property
    def avg_basket_profit(self) -> float:
        return mean(customer.basket_profit for customer in self.customers)

    @property
    def avg_items_per_shopper(self) -> float:
        return mean(len(customer.bought_item_names) for customer in self.customers)

    @property
    def avg_profit_per_customer(self) -> float:
        return self.total_profit / self.num_shoppers

    @property
    def avg_patience_remaining(self) -> float:
        return mean(customer.patience_level for customer in self.customers)

    @property
    def avg_patience_lost_to_congestion(self) -> float:
        return mean(customer.patience_lost_to_congestion for customer in self.customers)

    @property
    def unique_shopping_list_count(self) -> int:
        return len({
            self._shopping_list_key(customer.shopping_list)
            for customer in self.customers
        })

    @property
    def layout_score(self) -> float:
        completion_component = self.finished_shopper_count / self.num_shoppers
        abandonment_component = 1.0 - self.abandoned_shopper_count / self.num_shoppers
        profit_component = min(1.0, self.avg_profit_per_customer / 10.0)
        congestion_component = max(0.0, 1.0 - self.avg_congestion_delay / max(1, self.max_steps))
        score = (
            completion_component * 0.30
            + self.avg_planned_completion * 0.15
            + self.avg_satisfaction * 0.20
            + profit_component * 0.20
            + abandonment_component * 0.10
            + congestion_component * 0.05
        )
        return max(0.0, min(100.0, score * 100))

    def traffic_heatmap(self) -> np.ndarray:
        heatmap = np.zeros((self.height, self.width), dtype=int)
        for customer in self.customers:
            for x, y in customer.path_history:
                heatmap[y, x] += 1
        return heatmap

    def summary(self) -> Dict[str, float]:
        completion_rate = self.finished_shopper_count / self.num_shoppers
        abandonment_rate = self.abandoned_shopper_count / self.num_shoppers
        avg_impulse_per_customer = self.impulse_purchase_count / self.num_shoppers
        avg_unlisted_per_customer = self.unlisted_purchase_count / self.num_shoppers
        avg_revenue_per_customer = self.total_revenue / self.num_shoppers
        return {
            "layout": self.layout_name,
            "shoppers": self.num_shoppers,
            "opening_time": self._format_hour(self.opening_hour),
            "closing_time": self._format_hour(self.closing_hour),
            "current_store_time": self.current_time_label,
            "traffic_period": self.current_traffic_period,
            "traffic_share": round(self.current_traffic_share, 3),
            "target_active_shoppers": self.target_active_shopper_count,
            "active_shopper_share": round(self.active_shopper_share, 3),
            "traffic_profile": self.traffic_profile_summary,
            "arrival_window_steps": self.arrival_window_steps,
            "unique_shopping_lists": self.unique_shopping_list_count,
            "steps_run": self.step_count,
            "arrived_shoppers": self.arrived_shopper_count,
            "waiting_shoppers": self.waiting_shopper_count,
            "finished_shoppers": self.finished_shopper_count,
            "abandoned_shoppers": self.abandoned_shopper_count,
            "completion_rate": round(completion_rate, 3),
            "abandonment_rate": round(abandonment_rate, 3),
            "abandoned_due_to_time": self.abandonment_reason_counts.get("time", 0),
            "abandoned_due_to_traffic": self.abandonment_reason_counts.get("traffic", 0),
            "abandoned_due_to_congestion": self.abandonment_reason_counts.get("congestion", 0),
            "abandoned_due_to_checkout": self.abandonment_reason_counts.get("checkout", 0),
            "avg_completion_time": round(self.avg_completion_time, 2),
            "avg_completion_minutes": round(self.avg_completion_minutes, 2),
            "avg_planned_completion": round(self.avg_planned_completion, 3),
            "avg_satisfaction": round(self.avg_satisfaction, 3),
            "avg_checkout_wait": round(self.avg_checkout_wait, 2),
            "max_checkout_wait": round(self.max_checkout_wait, 2),
            "longest_checkout_queue": self.longest_checkout_queue,
            "planned_purchases": self.planned_purchase_count,
            "impulse_purchases": self.impulse_purchase_count,
            "unlisted_purchases": self.unlisted_purchase_count,
            "abandoned_list_items": self.abandoned_list_item_count,
            "lost_revenue_from_abandonment": round(self.lost_revenue_from_abandonment, 2),
            "lost_profit_from_abandonment": round(self.lost_profit_from_abandonment, 2),
            "avg_impulse_per_customer": round(avg_impulse_per_customer, 3),
            "avg_unlisted_per_customer": round(avg_unlisted_per_customer, 3),
            "avg_basket_value": round(self.avg_basket_value, 2),
            "avg_basket_profit": round(self.avg_basket_profit, 2),
            "avg_items_per_shopper": round(self.avg_items_per_shopper, 2),
            "revenue": round(self.total_revenue, 2),
            "profit": round(self.total_profit, 2),
            "revenue_from_planned": round(self.revenue_from_planned, 2),
            "revenue_from_impulse": round(self.revenue_from_impulse, 2),
            "revenue_from_unlisted": round(self.revenue_from_unlisted, 2),
            "profit_from_unlisted": round(self.profit_from_unlisted, 2),
            "avg_revenue_per_customer": round(avg_revenue_per_customer, 2),
            "avg_profit_per_customer": round(self.avg_profit_per_customer, 2),
            "avg_congestion_delay": round(self.avg_congestion_delay, 2),
            "avg_patience_remaining": round(self.avg_patience_remaining, 2),
            "avg_patience_lost_to_congestion": round(
                self.avg_patience_lost_to_congestion,
                2,
            ),
            "layout_score": round(self.layout_score, 2),
        }

    def shopping_list_item_summary(self) -> List[Dict[str, float]]:
        rows: List[Dict[str, float]] = []
        for item in self.layout.items:
            metrics = self.item_metrics[item.name]
            listed_shoppers = sum(
                1
                for customer in self.customers
                if item.name in customer.shopping_list_names
            )
            rows.append(
                {
                    "item": item.name,
                    "category": item.category,
                    "configured_list_probability": round(item.list_probability, 3),
                    "configured_list_percentage": item.list_probability_percent,
                    "listed_shoppers": listed_shoppers,
                    "observed_list_percentage": round(
                        listed_shoppers / self.num_shoppers * 100,
                        1,
                    ),
                    "units_sold": int(metrics["units"]),
                    "planned_units": int(metrics["planned_units"]),
                    "impulse_units": int(metrics["impulse_units"]),
                    "unlisted_units": int(metrics["unlisted_units"]),
                    "revenue": round(metrics["revenue"], 2),
                    "profit": round(metrics["profit"], 2),
                    "unlisted_revenue": round(metrics["unlisted_revenue"], 2),
                    "unlisted_profit": round(metrics["unlisted_profit"], 2),
                    "lost_units_from_abandonment": int(metrics["lost_units"]),
                    "lost_revenue_from_abandonment": round(metrics["lost_revenue"], 2),
                    "lost_profit_from_abandonment": round(metrics["lost_profit"], 2),
                }
            )
        return rows

    def category_summary(self) -> List[Dict[str, float]]:
        categories = sorted({item.category for item in self.layout.items})
        rows: List[Dict[str, float]] = []
        for category in categories:
            metrics = self.category_metrics.get(category, self._empty_sales_bucket(category))
            rows.append(
                {
                    "category": category,
                    "units_sold": int(metrics["units"]),
                    "planned_units": int(metrics["planned_units"]),
                    "impulse_units": int(metrics["impulse_units"]),
                    "unlisted_units": int(metrics["unlisted_units"]),
                    "revenue": round(metrics["revenue"], 2),
                    "profit": round(metrics["profit"], 2),
                    "profit_margin_observed": round(
                        metrics["profit"] / metrics["revenue"],
                        3,
                    )
                    if metrics["revenue"]
                    else 0.0,
                    "revenue_share": round(
                        metrics["revenue"] / self.total_revenue,
                        3,
                    )
                    if self.total_revenue
                    else 0.0,
                    "profit_share": round(
                        metrics["profit"] / self.total_profit,
                        3,
                    )
                    if self.total_profit
                    else 0.0,
                    "unlisted_revenue": round(metrics["unlisted_revenue"], 2),
                    "unlisted_profit": round(metrics["unlisted_profit"], 2),
                    "lost_units_from_abandonment": int(metrics["lost_units"]),
                    "lost_revenue_from_abandonment": round(metrics["lost_revenue"], 2),
                    "lost_profit_from_abandonment": round(metrics["lost_profit"], 2),
                }
            )
        return rows

    def shopper_type_summary(self) -> List[Dict[str, float]]:
        rows: List[Dict[str, float]] = []
        for shopper_type, profile in SHOPPER_PROFILES.items():
            shoppers = [
                customer
                for customer in self.customers
                if customer.shopper_type == shopper_type
            ]
            if not shoppers:
                continue

            finished = [customer for customer in shoppers if customer.state == "finished"]
            abandoned = [customer for customer in shoppers if customer.abandoned]
            rows.append(
                {
                    "shopper_type": shopper_type,
                    "profile_name": profile.name,
                    "shopper_type_shoppers": len(shoppers),
                    "finished_shoppers": len(finished),
                    "abandoned_shoppers": len(abandoned),
                    "abandonment_rate": round(len(abandoned) / len(shoppers), 3),
                    "avg_completion_time": round(
                        mean(customer.completion_time for customer in finished),
                        2,
                    )
                    if finished
                    else 0.0,
                    "avg_planned_completion": round(
                        mean(customer.planned_completion_rate for customer in shoppers),
                        3,
                    ),
                    "avg_satisfaction": round(
                        mean(customer.satisfaction for customer in shoppers),
                        3,
                    ),
                    "avg_basket_value": round(
                        mean(customer.basket_value for customer in shoppers),
                        2,
                    ),
                    "avg_basket_profit": round(
                        mean(customer.basket_profit for customer in shoppers),
                        2,
                    ),
                    "avg_items": round(
                        mean(len(customer.bought_item_names) for customer in shoppers),
                        2,
                    ),
                    "avg_unlisted_purchases": round(
                        mean(len(customer.unlisted_purchases) for customer in shoppers),
                        2,
                    ),
                    "lost_revenue_from_abandonment": round(
                        sum(customer.abandoned_value for customer in shoppers),
                        2,
                    ),
                    "lost_profit_from_abandonment": round(
                        sum(customer.abandoned_profit for customer in shoppers),
                        2,
                    ),
                }
            )
        return rows

    def shopper_list_summary(self) -> List[Dict[str, float]]:
        return [
            {
                "shopper_id": customer.uid,
                "shopper_type": customer.shopper_type,
                "arrival_time": customer.arrival_time,
                "arrival_clock_time": self.step_to_time_label(customer.arrival_time),
                "arrived": customer.arrived,
                "state": customer.state,
                "shopping_list": ", ".join(customer.shopping_list),
                "shopping_list_size": len(customer.shopping_list),
                "planned_purchases": len(customer.planned_purchases),
                "impulse_purchases": len(customer.impulse_purchases),
                "unlisted_purchases": len(customer.unlisted_purchases),
                "unlisted_items": ", ".join(customer.unlisted_purchases),
                "basket_value": round(customer.basket_value, 2),
                "basket_profit": round(customer.basket_profit, 2),
                "checkout_wait": customer.checkout_wait_initial,
                "checkout_wait_minutes": customer.checkout_wait_initial_minutes,
                "checkout_time_spent": customer.checkout_time_spent,
                "abandoned": customer.abandoned,
                "abandoned_item_count": len(customer.abandoned_items),
                "abandoned_items": ", ".join(customer.abandoned_items),
                "abandoned_value": round(customer.abandoned_value, 2),
                "abandoned_profit": round(customer.abandoned_profit, 2),
                "patience_remaining": round(customer.patience_level, 2),
                "patience_lost_to_congestion": round(
                    customer.patience_lost_to_congestion,
                    2,
                ),
                "abandonment_reason": customer.abandonment_reason or "",
            }
            for customer in self.customers
        ]
