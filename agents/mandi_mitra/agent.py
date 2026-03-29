"""MandiMitra (Market Friend) — ADK agent for mandi price advisory.

Helps farmers find the most profitable mandi (wholesale market) to sell their
crops by combining live AgMarkNet prices with transport cost estimation and
spoilage risk analysis.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from google.adk.agents import Agent
from google.adk.tools import FunctionTool

from .agmarknet_client import fetch_mandi_prices
from .profit_optimizer import rank_mandis

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool functions (exposed to the LLM via FunctionTool)
# ---------------------------------------------------------------------------

def get_mandi_recommendation(
    crop: str,
    lat: float,
    lon: float,
    state: str,
    quantity_quintals: float = 10.0,
) -> dict:
    """Fetch live mandi prices and return a ranked list of mandis by net profit.

    Args:
        crop: Name of the crop, e.g. "Tomato", "Wheat", "Onion".
        lat: Farmer's latitude.
        lon: Farmer's longitude.
        state: Indian state to search mandis in, e.g. "Himachal Pradesh".
        quantity_quintals: Quantity the farmer plans to sell (default 10).

    Returns:
        A dict containing ranked mandis, profit breakdown, and a disclaimer.
    """
    # 1. Fetch prices
    price_response = fetch_mandi_prices(commodity=crop, state=state)

    if not price_response.records:
        return {
            "status": "no_data",
            "message": (
                f"No mandi price data found for {crop} in {state}. "
                "Please try a different crop or state."
            ),
        }

    # 2. Optimise
    result = rank_mandis(
        mandi_prices=price_response.records,
        farmer_lat=lat,
        farmer_lon=lon,
        crop=crop,
        quantity_quintals=quantity_quintals,
        data_source=price_response.source,
    )

    # 3. Build response
    top = result.rankings[0] if result.rankings else None
    summary_lines = []
    for i, r in enumerate(result.rankings, 1):
        summary_lines.append(
            f"{i}. {r.market} ({r.district}) — "
            f"Modal ₹{r.modal_price}/q, "
            f"Net ₹{r.net_profit}/q, "
            f"{r.distance_km} km / {int(r.travel_time_min)} min"
        )

    recommendation = ""
    if top:
        total_profit = round(top.net_profit * quantity_quintals, 2)
        recommendation = (
            f"Best option: {top.market} mandi in {top.district}. "
            f"Expected net profit ≈ ₹{top.net_profit}/quintal "
            f"(₹{total_profit} total for {quantity_quintals} quintals). "
            f"Distance: {top.distance_km} km, travel ≈ {int(top.travel_time_min)} min."
        )

    return {
        "status": "ok",
        "crop": crop,
        "state": state,
        "quantity_quintals": quantity_quintals,
        "data_source": price_response.source,
        "data_fetched_at": price_response.fetched_at,
        "recommendation": recommendation,
        "rankings": [r.model_dump() for r in result.rankings],
        "summary": "\n".join(summary_lines),
        "disclaimer": result.disclaimer,
    }


def get_crop_prices(
    crop: str,
    state: str,
) -> dict:
    """Fetch current mandi prices for a crop in a given state (no ranking).

    Args:
        crop: Crop name, e.g. "Tomato".
        state: Indian state name, e.g. "Himachal Pradesh".

    Returns:
        A dict with a list of mandi price records and metadata.
    """
    price_response = fetch_mandi_prices(commodity=crop, state=state)

    if not price_response.records:
        return {
            "status": "no_data",
            "message": f"No price data found for {crop} in {state}.",
        }

    records = [
        {
            "market": r.market,
            "district": r.district,
            "min_price": r.min_price,
            "max_price": r.max_price,
            "modal_price": r.modal_price,
            "variety": r.variety,
            "arrival_date": r.arrival_date,
        }
        for r in price_response.records
    ]

    return {
        "status": "ok",
        "crop": crop,
        "state": state,
        "source": price_response.source,
        "fetched_at": price_response.fetched_at,
        "prices": records,
        "disclaimer": (
            "Prices are indicative and sourced from AgMarkNet / data.gov.in. "
            "Actual transaction prices may differ. This is not a price guarantee."
        ),
    }


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

mandi_recommendation_tool = FunctionTool(func=get_mandi_recommendation)
crop_prices_tool = FunctionTool(func=get_crop_prices)

mandi_mitra_agent = Agent(
    name="mandi_mitra",
    model="gemini-3.0-flash",
    description=(
        "MandiMitra (Market Friend) helps farmers identify the most profitable "
        "wholesale market (mandi) to sell their crops. It combines live market "
        "prices from AgMarkNet with transport cost and spoilage risk analysis."
    ),
    instruction=(
        "You are MandiMitra, a friendly agricultural market advisor for Indian "
        "farmers. Your job is to help farmers find the best mandi to sell their "
        "crops for maximum profit.\n\n"
        "CAPABILITIES:\n"
        "- Fetch current wholesale (mandi) prices for any crop and state\n"
        "- Rank mandis by estimated net profit after transport, commission, "
        "and spoilage costs\n"
        "- Provide clear, actionable recommendations in simple language\n\n"
        "WORKFLOW:\n"
        "1. Ask the farmer for: crop name, their location (or lat/lon), state, "
        "and quantity they want to sell.\n"
        "2. Use the get_mandi_recommendation tool to fetch prices and rankings.\n"
        "3. Present the results clearly: best mandi first, with profit breakdown.\n"
        "4. If the farmer only wants prices (no ranking), use get_crop_prices.\n\n"
        "GUARDRAILS — you MUST follow these:\n"
        "- NEVER guarantee any price. Always say prices are indicative.\n"
        "- ALWAYS cite the data source (AgMarkNet / data.gov.in) and the date "
        "the data was fetched.\n"
        "- ALWAYS include the disclaimer from the tool response.\n"
        "- If no data is available, clearly state that live data "
        "could not be fetched and advise trying again later.\n"
        "- Use ₹ (rupee symbol) for all monetary amounts.\n"
        "- Be empathetic and supportive — many farmers are making critical "
        "financial decisions based on this advice.\n"
        "- If you do not have enough information, ask follow-up questions "
        "rather than guessing.\n"
    ),
    tools=[mandi_recommendation_tool, crop_prices_tool],
)
