# Copyright (c) 2023 Itos Inc (Itos.Fi)

import pandas as pd
import math
import datetime as dt

from Utils.Prices import get_prices
from Utils.Pos import Maker, TakerCall, TakerPut, calcX, calcY


def make_il_takercall(maker, hedge_percent, width):
    "Create a TakerCall that hedges the Maker's IL"
    mean_sqrt = math.sqrt(maker.low_sqrt * maker.high_sqrt)
    x = calcX(maker.liq, mean_sqrt, maker.high_sqrt)

    num = calcY(maker.liq, maker.low_sqrt, maker.high_sqrt) - (
        1 - hedge_percent
    ) * calcY(maker.liq, maker.low_sqrt, mean_sqrt)
    denom = calcX(maker.liq, mean_sqrt, maker.high_sqrt)
    taker_mean_sqrt = math.sqrt(num / denom)

    w = math.sqrt(width) - 1 / math.sqrt(width)
    return TakerCall(
        x * taker_mean_sqrt / w,
        taker_mean_sqrt**2 / width,
        taker_mean_sqrt**2 * width,
    )


def make_il_takerput(maker, hedge_percent, width):
    "Create a TakerPut that hedges the Maker's IL"
    mean_sqrt = math.sqrt(maker.low_sqrt * maker.high_sqrt)
    x = calcX(maker.liq, maker.low_sqrt, mean_sqrt)

    num = (1 - hedge_percent) * calcY(maker.liq, maker.low_sqrt, mean_sqrt)
    denom = calcX(maker.liq, maker.low_sqrt, mean_sqrt)
    taker_mean_sqrt = math.sqrt(num / denom)

    w = math.sqrt(width) - 1 / math.sqrt(width)
    return TakerPut(
        x * taker_mean_sqrt / w,
        taker_mean_sqrt**2 / width,
        taker_mean_sqrt**2 * width,
    )


# We always start the maker at a value of 1 per period so we can get the change in value each period.
def maker_from_value(value, low, high, price):
    "Construct a Maker given the intended initial starting value"
    liq = value / (2 * math.sqrt(price) - price / math.sqrt(high) - math.sqrt(low))
    return Maker(liq, low, high)


def calc_performances(
    prices, maker_width, hedge_percent, hedge_width, rebalance_frequency, apr_est
):
    "Calculate the cumulative performance of an unhedged liquidity provision, an IL hedge LP, and hodling"

    # First divide our prices into the periods according to our rebalancing frequency
    pdf = pd.DataFrame({"price": prices})
    temp = (
        pd.DataFrame(prices[::rebalance_frequency])
        .reset_index()
        .reset_index(names="period")
        .set_index("date")
    )
    pdf = pdf.merge(
        temp[["period"]], how="outer", left_index=True, right_index=True
    ).ffill()

    period_dates = pdf.reset_index().groupby("period").first()["date"]

    # Construct our makers and takers for each of the rebalanced periods
    period_df = pdf.groupby("period").first()
    period_df["next"] = period_df["price"].shift(-1)
    period_df["maker"] = period_df["price"].apply(
        lambda p: maker_from_value(1, p / maker_width, p * maker_width, p)
    )
    period_df["tCall"] = period_df["maker"].apply(
        lambda m: make_il_takercall(m, hedge_percent, hedge_width)
    )
    period_df["tPut"] = period_df["maker"].apply(
        lambda m: make_il_takerput(m, hedge_percent, hedge_width)
    )

    # Compute the returns from each of the rebalanced periods
    period_df["postValueMakerMult"] = period_df.apply(
        lambda row: row["maker"].value(row["next"]), axis=1
    )
    period_df["postValueBundleMult"] = period_df.apply(
        lambda row: sum(
            map(lambda x: x.value(row["next"]), row[["maker", "tCall", "tPut"]])
        ),
        axis=1,
    )
    period_df["callFeeScale"] = period_df.apply(
        lambda row: row["tCall"].liq / row["maker"].liq, axis=1
    )
    period_df["putFeeScale"] = period_df.apply(
        lambda row: row["tPut"].liq / row["maker"].liq, axis=1
    )

    temp = pdf.copy()
    temp["listify"] = pdf["price"].apply(lambda x: [x])
    period_price_dict = (
        temp[["period", "listify"]].groupby("period").sum()["listify"].to_dict()
    )

    # Handle fee earns
    period_df["maker_inrange"] = period_df.apply(
        lambda row: sum(map(row["maker"].in_range, period_price_dict[row.name])), axis=1
    )
    period_df["call_inrange"] = period_df.apply(
        lambda row: sum(map(row["tCall"].in_range, period_price_dict[row.name])), axis=1
    )
    period_df["put_inrange"] = period_df.apply(
        lambda row: sum(map(row["tPut"].in_range, period_price_dict[row.name])), axis=1
    )
    daily_fee_rate = apr_est / 365
    period_df["maker_fees"] = period_df["maker_inrange"] * daily_fee_rate
    period_df["net_fees"] = (
        period_df["maker_fees"]
        - (period_df["call_inrange"] + period_df["put_inrange"]) * daily_fee_rate
    )
    # And now net earnings
    period_df["net_maker_change"] = (
        period_df["postValueMakerMult"] + period_df["maker_fees"]
    )
    period_df["net_change"] = period_df["postValueBundleMult"] + period_df["net_fees"]

    # A hodl would have 50% of the original investment in the token and 50% in the numeraire.
    hodl = period_df.price / period_df.price[0] / 2 + 0.5
    hodl.name = "hodl"

    # Convert the results into cumulative results
    rolling_changes = period_df[["net_maker_change", "net_change"]].dropna().cumprod()
    rolling_changes = rolling_changes.merge(
        hodl, how="inner", left_index=True, right_index=True
    )
    # Index by the dates
    return rolling_changes.merge(
        pd.DataFrame(period_dates), left_index=True, right_index=True, how="inner"
    ).set_index("date")
