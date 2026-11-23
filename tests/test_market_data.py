import numpy as np
import pandas as pd
import pytest

from tradelab.data import DataValidationError, generate_synthetic_ohlcv, load_csv, validate_ohlcv


def test_valid_data_passes(valid_ohlcv):
    out = validate_ohlcv(valid_ohlcv)
    assert list(out.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert out.index.name == "Date"


def test_lowercase_columns_are_normalized(valid_ohlcv):
    df = valid_ohlcv.rename(columns=str.lower)
    out = validate_ohlcv(df)
    assert "Close" in out.columns


def test_date_column_becomes_index(valid_ohlcv):
    df = valid_ohlcv.reset_index()
    out = validate_ohlcv(df)
    assert isinstance(out.index, pd.DatetimeIndex)


def test_validation_does_not_mutate_input(valid_ohlcv):
    original = valid_ohlcv.copy()
    validate_ohlcv(valid_ohlcv.rename(columns=str.lower))
    pd.testing.assert_frame_equal(valid_ohlcv, original)


def test_empty_dataframe_fails():
    with pytest.raises(DataValidationError, match="vazio"):
        validate_ohlcv(pd.DataFrame())


def test_missing_column_fails(valid_ohlcv):
    with pytest.raises(DataValidationError, match="ausentes"):
        validate_ohlcv(valid_ohlcv.drop(columns=["Volume"]))


def test_non_datetime_index_fails(valid_ohlcv):
    with pytest.raises(DataValidationError, match="DatetimeIndex"):
        validate_ohlcv(valid_ohlcv.reset_index(drop=True))


def test_invalid_date_string_fails(valid_ohlcv):
    df = valid_ohlcv.reset_index()
    df["Date"] = df["Date"].astype(str)
    df.loc[2, "Date"] = "não-é-data"
    with pytest.raises(DataValidationError, match="datas inválidas"):
        validate_ohlcv(df)


def test_duplicate_dates_fail(valid_ohlcv):
    df = pd.concat([valid_ohlcv, valid_ohlcv.iloc[[-1]]])
    with pytest.raises(DataValidationError, match="duplicadas"):
        validate_ohlcv(df)


def test_unsorted_dates_fail(valid_ohlcv):
    with pytest.raises(DataValidationError, match="crescente"):
        validate_ohlcv(valid_ohlcv.iloc[::-1])


def test_non_numeric_value_fails(valid_ohlcv):
    df = valid_ohlcv.astype(object)
    df.iloc[1, df.columns.get_loc("Close")] = "abc"
    with pytest.raises(DataValidationError, match="não numéricos"):
        validate_ohlcv(df)


def test_nan_fails(valid_ohlcv):
    df = valid_ohlcv.copy()
    df.iloc[2, df.columns.get_loc("Volume")] = np.nan
    with pytest.raises(DataValidationError, match="ausentes"):
        validate_ohlcv(df)


def test_non_positive_price_fails(valid_ohlcv):
    df = valid_ohlcv.copy()
    df.iloc[0, df.columns.get_loc("Low")] = 0
    with pytest.raises(DataValidationError, match="positivos"):
        validate_ohlcv(df)


def test_negative_volume_fails(valid_ohlcv):
    df = valid_ohlcv.copy()
    df.iloc[0, df.columns.get_loc("Volume")] = -1
    with pytest.raises(DataValidationError, match="volume"):
        validate_ohlcv(df)


def test_high_below_close_fails(valid_ohlcv):
    df = valid_ohlcv.copy()
    df.iloc[3, df.columns.get_loc("High")] = df["Close"].iloc[3] - 1
    with pytest.raises(DataValidationError, match="High"):
        validate_ohlcv(df)


def test_low_above_open_fails(valid_ohlcv):
    df = valid_ohlcv.copy()
    df.iloc[3, df.columns.get_loc("Low")] = df["Open"].iloc[3] + 0.5
    with pytest.raises(DataValidationError):
        validate_ohlcv(df)


def test_load_csv_roundtrip(tmp_path, valid_ohlcv):
    path = tmp_path / "ativo.csv"
    valid_ohlcv.to_csv(path)
    loaded = load_csv(path)
    pd.testing.assert_frame_equal(loaded, validate_ohlcv(valid_ohlcv), check_freq=False)


def test_load_csv_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_csv(tmp_path / "nao_existe.csv")


@pytest.mark.parametrize("scenario", ["bull", "bear", "sideways"])
def test_synthetic_data_is_valid(scenario):
    df = generate_synthetic_ohlcv(scenario=scenario, n_periods=300, seed=1)
    assert len(df) == 300
    validate_ohlcv(df)


def test_synthetic_same_seed_is_reproducible():
    a = generate_synthetic_ohlcv("bull", seed=42)
    b = generate_synthetic_ohlcv("bull", seed=42)
    pd.testing.assert_frame_equal(a, b)


def test_synthetic_different_seed_differs():
    a = generate_synthetic_ohlcv("bull", seed=1)
    b = generate_synthetic_ohlcv("bull", seed=2)
    assert not a["Close"].equals(b["Close"])


def test_synthetic_drift_direction_on_average():
    """Na média de muitas seeds, bull > sideways > bear (verifica o drift, não uma trajetória)."""
    def mean_log_return(scenario):
        finals = [
            np.log(generate_synthetic_ohlcv(scenario, n_periods=252, seed=s)["Close"].iloc[-1] / 100)
            for s in range(60)
        ]
        return float(np.mean(finals))

    assert mean_log_return("bull") > mean_log_return("sideways") > mean_log_return("bear")


def test_synthetic_invalid_scenario():
    with pytest.raises(ValueError, match="Cenário inválido"):
        generate_synthetic_ohlcv("crash")
