from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yfinance as yf


ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "data" / "dividends_seed.json"
OUTPUT_PATH = ROOT / "data" / "dividends.json"
REQUEST_DELAY_SECONDS = 0.35
MAX_ATTEMPTS = 2


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def read_fast_price(ticker: yf.Ticker) -> float | None:
    try:
        fast_info = ticker.fast_info
        return clean_number(getattr(fast_info, "last_price", None) or fast_info.get("last_price"))
    except Exception:
        return None


def read_info(ticker: yf.Ticker) -> dict[str, Any]:
    try:
        return dict(ticker.info or {})
    except Exception:
        return {}


def calculate_fields(
    company: dict[str, Any],
    price: float | None,
    live_dividend: float | None,
    fetched_at: str,
    status: str,
    error: str | None = None,
) -> dict[str, Any]:
    avg_yield_10y = clean_number(company.get("avg_yield_10y"))
    live_yield = live_dividend / price if price and live_dividend is not None else None
    live_yield_diff = (
        (live_yield - avg_yield_10y) / avg_yield_10y
        if live_yield is not None and avg_yield_10y
        else None
    )

    output = {
        **company,
        "price": price,
        "live_dividend": live_dividend,
        "live_yield": live_yield,
        "live_yield_diff": live_yield_diff,
        "status": status,
        "fetched_at": fetched_at,
    }
    if error:
        output["error"] = error
    return output


def fetch_company_once(company: dict[str, Any], fetched_at: str) -> dict[str, Any]:
    ticker_symbol = company["ticker"]
    ticker = yf.Ticker(ticker_symbol)
    info = read_info(ticker)

    price = read_fast_price(ticker)
    if price is None:
        price = clean_number(info.get("currentPrice") or info.get("regularMarketPrice"))

    live_dividend = clean_number(info.get("dividendRate"))
    if live_dividend is None:
        live_dividend = clean_number(company.get("dividend_annual"))

    status = "ok" if price and live_dividend is not None else "failed"
    if status == "failed":
        raise ValueError(f"{ticker_symbol}: missing price or dividend")

    return calculate_fields(company, price, live_dividend, fetched_at, status)


def enrich_company(company: dict[str, Any], fetched_at: str) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return fetch_company_once(company, fetched_at)
        except Exception as exc:
            last_error = exc
            if attempt < MAX_ATTEMPTS:
                time.sleep(1.0)

    return calculate_fields(
        company,
        price=None,
        live_dividend=clean_number(company.get("dividend_annual")),
        fetched_at=fetched_at,
        status="failed",
        error=str(last_error) if last_error else "unknown error",
    )


def main() -> None:
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    selected = seed["companies"]
    fetched_at = utc_now_iso()
    companies = []
    for index, company in enumerate(selected, start=1):
        enriched = enrich_company(company, fetched_at)
        companies.append(enriched)
        print(f"[{index}/{len(selected)}] {company['ticker']}: {enriched['status']}")
        if index < len(selected):
            time.sleep(REQUEST_DELAY_SECONDS)

    output = {
        "generated_at": utc_now_iso(),
        "ok_count": sum(1 for company in companies if company["status"] == "ok"),
        "failed_count": sum(1 for company in companies if company["status"] == "failed"),
        "source": seed.get("source"),
        "as_of": seed.get("as_of"),
        "count": len(companies),
        "companies": companies,
    }

    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH} ({output['ok_count']} ok, {output['failed_count']} failed)")


if __name__ == "__main__":
    main()
