import datetime
import os

from tushare_adapter import (
    get_adj_factor,
    get_daily,
    get_daily_basic,
    get_stock_basic,
    get_trade_cal,
)


def print_result(name, result):
    data = result.get("data")
    rows = len(data) if data is not None else 0
    print(
        f"{name}: ok={result.get('ok')} rows={rows} "
        f"source={result.get('source')} api={result.get('api')} "
        f"error={result.get('error')}"
    )


def main():
    if not os.environ.get("TUSHARE_TOKEN"):
        print("TUSHARE_TOKEN 未配置；下面调用应返回 ok=False，不应抛异常。")

    today = datetime.date.today()
    start = (today - datetime.timedelta(days=14)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")
    sample_ts_code = os.environ.get("TUSHARE_TEST_TS_CODE", "000001.SZ")

    calls = [
        ("trade_cal", get_trade_cal(start, end)),
        ("stock_basic", get_stock_basic()),
        ("daily", get_daily(sample_ts_code, start, end)),
        ("daily_basic", get_daily_basic(sample_ts_code, start, end)),
        ("adj_factor", get_adj_factor(sample_ts_code, start, end)),
    ]

    for name, result in calls:
        print_result(name, result)


if __name__ == "__main__":
    main()
