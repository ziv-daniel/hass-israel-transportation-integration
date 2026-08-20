"""Tests for SilentBusCoordinator._process_rail_routes.

Regression coverage for a live bug report: "Next Train" showed 0m when a
real train was actually several minutes away. The Israel Rail searchTrain
API sometimes returns a train that has already departed alongside the
upcoming ones — observed live up to 26 minutes in the past — rather than
strictly filtering to future departures. The old code clamped that
negative time delta to 0 with max(0, ...), which made the departed train
sort as "next" ahead of the real next train.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.israel_transportation.const import DEFAULT_MAX_ARRIVALS
from custom_components.israel_transportation.coordinator import SilentBusCoordinator


class FakeTrainPart:
    """Duck-typed stand-in for israelrailapi.api.TrainRoutePart."""

    def __init__(self, departure, arrival, platform=1, train_number="123"):
        self.departure = departure
        self.arrival = arrival
        self.platform = platform
        self.data = {"trainNumber": train_number}


class FakeTrainRoute:
    """Duck-typed stand-in for israelrailapi.api.TrainRoute."""

    def __init__(self, trains):
        self.trains = trains


def _iso(now, offset_minutes):
    """Format an offset from `now` like the Rail API does: naive ISO, no timezone."""
    return (now + timedelta(minutes=offset_minutes)).replace(tzinfo=None).isoformat()


def _route(now, departure_offset_minutes, arrival_offset_minutes, train_number="123"):
    return FakeTrainRoute(
        [
            FakeTrainPart(
                _iso(now, departure_offset_minutes),
                _iso(now, arrival_offset_minutes),
                train_number=train_number,
            )
        ]
    )


def _make_rail_coordinator(
    hass: HomeAssistant, config_entry, max_arrivals: int = DEFAULT_MAX_ARRIVALS
) -> SilentBusCoordinator:
    """Create a SilentBusCoordinator configured for the train/rail path."""
    return SilentBusCoordinator(
        hass=hass,
        update_interval=timedelta(seconds=30),
        config_entry=config_entry,
        transport_type="train",
        from_station="3600",
        to_station="7300",
        from_station_name="Tel Aviv-Savidor Center",
        to_station_name="Sderot",
        max_arrivals=max_arrivals,
    )


def _process(coordinator, routes, now):
    # Patch dt_util.now so the code under test sees the exact same instant
    # the fixture departure/arrival strings were built relative to — this is
    # what makes the minutes_until assertions deterministic rather than
    # dependent on wall-clock proximity between fixture setup and execution.
    with patch(
        "custom_components.israel_transportation.coordinator.dt_util.now",
        return_value=now,
    ):
        return coordinator._process_rail_routes(routes)


class TestProcessRailRoutes:
    """Test _process_rail_routes against realistic Rail API shapes."""

    async def test_already_departed_train_is_skipped_not_zeroed(
        self, hass: HomeAssistant, simple_mock_config_entry
    ):
        """A departed train must not appear as the next arrival at 0m.

        Reproduces the exact live failure: Tel Aviv-Savidor Center -> Sderot
        returned a train that left 9 minutes ago as the first result, ahead
        of real upcoming trains at +17 and +20 minutes.
        """
        now = dt_util.now()
        routes = [
            _route(now, -9, 85),
            _route(now, 17, 112),
            _route(now, 20, 118),
        ]

        coordinator = _make_rail_coordinator(hass, simple_mock_config_entry)
        result = _process(coordinator, routes, now)

        arrivals = result["train_route"]
        assert [a["minutes_until"] for a in arrivals] == [17, 20]
        assert arrivals[0]["minutes_until"] != 0

    async def test_reverse_direction_also_skips_departed_train(
        self, hass: HomeAssistant, simple_mock_config_entry
    ):
        """Same bug, reverse route (Sderot -> Savidor) — the other half of the report."""
        now = dt_util.now()
        routes = [
            _route(now, -26, 60),
            _route(now, 4, 95),
        ]

        coordinator = _make_rail_coordinator(hass, simple_mock_config_entry)
        result = _process(coordinator, routes, now)

        arrivals = result["train_route"]
        assert [a["minutes_until"] for a in arrivals] == [4]

    async def test_filtering_does_not_underfill_max_arrivals(
        self, hass: HomeAssistant, simple_mock_config_entry
    ):
        """A past train occupying an early slot must not crowd out real future ones.

        max_arrivals=3 with one departed train ahead of 4 future trains must
        still return 3 future arrivals, not 2 — the old code sliced routes to
        max_arrivals *before* filtering, so a departed train in that slice
        silently reduced the real result count.
        """
        now = dt_util.now()
        routes = [
            _route(now, -5, 80),
            _route(now, 10, 90),
            _route(now, 20, 100),
            _route(now, 30, 110),
            _route(now, 40, 120),
        ]

        coordinator = _make_rail_coordinator(
            hass, simple_mock_config_entry, max_arrivals=3
        )
        result = _process(coordinator, routes, now)

        arrivals = result["train_route"]
        assert [a["minutes_until"] for a in arrivals] == [10, 20, 30]

    async def test_all_departed_yields_no_arrivals(
        self, hass: HomeAssistant, simple_mock_config_entry
    ):
        """If every returned route is already in the past, report nothing rather than 0m."""
        now = dt_util.now()
        routes = [_route(now, -15, 70)]

        coordinator = _make_rail_coordinator(hass, simple_mock_config_entry)
        result = _process(coordinator, routes, now)

        assert result.get("train_route", []) == []

    async def test_normal_future_only_routes_unaffected(
        self, hass: HomeAssistant, simple_mock_config_entry
    ):
        """Baseline: with no departed trains in the response, behavior is unchanged."""
        now = dt_util.now()
        routes = [_route(now, 5, 60), _route(now, 35, 95)]

        coordinator = _make_rail_coordinator(hass, simple_mock_config_entry)
        result = _process(coordinator, routes, now)

        arrivals = result["train_route"]
        assert [a["minutes_until"] for a in arrivals] == [5, 35]
