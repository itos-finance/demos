from functools import lru_cache
import numpy as np
import pandas as pd
import requests


class GeckoError(Exception):
    pass


@lru_cache
def geckoHistorical(ticker, vs_currency="usd", days="max"):
    """Historical prices from coinGecko

    Args:
        ticker (string): gecko ID, ie "bitcoin"
        vs_currency (str, optional): ie "usd" (default)
        days (str, optional): ie "20", "max" (default)

    Returns:
        DataFrame: Full history: date, price, market cap & volume
    """

    url = f"https://api.coingecko.com/api/v3/coins/{ticker}/market_chart"
    params = {"vs_currency": {vs_currency}, "days": days}
    r = requests.get(url, params).json()
    if "prices" not in r:
        raise GeckoError(f"Invalid currency found in [{ticker}, {vs_currency}]")
    prices = pd.DataFrame(r["prices"])
    market_caps = pd.DataFrame(r["market_caps"])
    total_volumes = pd.DataFrame(r["total_volumes"])
    df = pd.concat([prices, market_caps[1], total_volumes[1]], axis=1)
    df[0] = pd.to_datetime(df[0], unit="ms")
    df.columns = ["date", "price", "market_caps", "total_volumes"]
    df.set_index("date", inplace=True)

    return df


def get_current_price(coin):
    return geckoHistorical(coin)["price"].iloc[-1]


def get_prices(coin, start, end=None):
    "Get a single price series for a coin"
    # Drop last row since it's the current price and constantly changing.
    series = geckoHistorical(coin).loc[start:]["price"].iloc[:-1]
    if end is not None:
        series = series.loc[:end]
    series.name = coin
    return series
