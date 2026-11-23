import pandas as pd
import pytest


def make_ohlcv(closes, start="2024-01-01") -> pd.DataFrame:
    """Cria um OHLCV mínimo e coerente a partir de uma lista de fechamentos."""
    index = pd.bdate_range(start=start, periods=len(closes), name="Date")
    close = pd.Series(closes, index=index, dtype=float)
    return pd.DataFrame(
        {
            "Open": close,
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": 1_000.0,
        },
        index=index,
    )


@pytest.fixture
def ohlcv_factory():
    return make_ohlcv


@pytest.fixture
def valid_ohlcv():
    return make_ohlcv([100, 101, 102, 101, 103, 104])
