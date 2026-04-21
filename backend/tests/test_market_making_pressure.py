"""Unit tests for MarketState pressure model — pure functions, no DB needed."""
import pytest
from decimal import Decimal
from app.services.market_making_service import MarketState, PressureSettings


DEFAULT_SETTINGS = PressureSettings(
    tick_size=Decimal("0.10"),
    avg_spread=Decimal("0.20"),
    pressure_momentum=Decimal("0.70"),
    pressure_sigma=Decimal("0.25"),
    reversion_alpha=Decimal("0.20"),
    band_amplitude_ticks=3,
)
SCRAPED = Decimal("12.09")


def test_pressure_stays_in_band():
    """mid_price must stay within ±3 ticks of scraped on every tick for 100 ticks."""
    state = MarketState(mid_price=SCRAPED, pressure=0.0)
    band = DEFAULT_SETTINGS.tick_size * DEFAULT_SETTINGS.band_amplitude_ticks
    for _ in range(100):
        state.tick(scraped_price=SCRAPED, settings=DEFAULT_SETTINGS)
        assert abs(state.mid_price - SCRAPED) <= band, (
            f"mid_price {state.mid_price} exceeded band ±{band} from scraped {SCRAPED}"
        )


def test_pressure_mean_reverts():
    """A price far from scraped must drift back within 20 ticks."""
    state = MarketState(mid_price=Decimal("12.50"), pressure=1.0)
    for _ in range(20):
        state.tick(scraped_price=SCRAPED, settings=DEFAULT_SETTINGS)
    assert state.mid_price < Decimal("12.30")


def test_bid_ask_prices_computed():
    """buy_price and sell_price are symmetric around mid_price."""
    state = MarketState(mid_price=SCRAPED, pressure=0.0)
    state.tick(scraped_price=SCRAPED, settings=DEFAULT_SETTINGS)
    half = DEFAULT_SETTINGS.avg_spread / 2
    assert state.buy_price == state.mid_price - half
    assert state.sell_price == state.mid_price + half


def test_pressure_clipped():
    """Pressure is always in [-1.0, +1.0] regardless of noise."""
    state = MarketState(mid_price=SCRAPED, pressure=0.99)
    for _ in range(50):
        state.tick(scraped_price=SCRAPED, settings=DEFAULT_SETTINGS)
    assert -1.0 <= state.pressure <= 1.0
