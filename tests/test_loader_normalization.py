from regime_engine.ingestor import Bar
from regime_engine.loader import load_bars


def test_loader_returns_bar_objects():
    bars = load_bars("SPY")  # uses your current loader implementation
    assert isinstance(bars, list)
    assert len(bars) > 0
    assert isinstance(bars[0], Bar)
