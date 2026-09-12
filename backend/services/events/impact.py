import json
import logging
from typing import List
from pydantic import BaseModel, Field
from services.llm.provider import llm_provider
from services.events.classifier import ClassifiedEvent

logger = logging.getLogger(__name__)

class ImpactChainNode(BaseModel):
    step: str
    description: str

class BeneficiaryRisk(BaseModel):
    ticker: str
    name: str
    market: str
    impact: str = Field(description="'Beneficiary' or 'At-Risk'")
    reasoning: str

class EventImpact(BaseModel):
    chain_reaction: List[ImpactChainNode]
    stocks: List[BeneficiaryRisk]

def _parse_json_lenient(content: str) -> dict:
    """Extract a JSON object from model output that may carry prose around it."""
    import re

    try:
        return json.loads(content)
    except Exception:
        pass
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    return {}


def _normalise_impact(data: dict) -> EventImpact:
    """Build EventImpact from model output that may be partial or loosely shaped.

    Models do not always honour the schema: chain items can arrive as plain
    strings, keys can be missing. Normalise item-by-item so one bad entry
    does not discard the whole analysis.
    """
    chain = []
    raw_chain = data.get("chain_reaction") or []
    if isinstance(raw_chain, str):
        raw_chain = [raw_chain]
    for i, node in enumerate(raw_chain, start=1):
        try:
            if isinstance(node, str):
                chain.append(ImpactChainNode(step=f"Step {i}", description=node))
            elif isinstance(node, dict):
                chain.append(
                    ImpactChainNode(
                        step=str(node.get("step") or f"Step {i}"),
                        description=str(node.get("description") or node.get("text") or ""),
                    )
                )
        except Exception:
            continue

    stocks = []
    raw_stocks = data.get("stocks") or []
    if isinstance(raw_stocks, dict):
        # Some models return {beneficiaries: [...], pressure: [...]} instead
        # of the flat list. Flatten back with the discriminator set.
        grouped = []
        for item in raw_stocks.get("beneficiaries") or []:
            if isinstance(item, dict):
                grouped.append({**item, "impact": "Beneficiary"})
        for item in raw_stocks.get("pressure") or []:
            if isinstance(item, dict):
                grouped.append({**item, "impact": "At-Risk"})
        raw_stocks = grouped
    for s in raw_stocks:
        try:
            if not isinstance(s, dict) or not s.get("ticker"):
                continue
            impact = str(s.get("impact") or "At-Risk")
            if impact.lower() not in ("beneficiary", "at-risk", "at risk"):
                impact = "At-Risk" if "risk" in impact.lower() or "pressure" in impact.lower() else "Beneficiary"
                if impact == "At Risk":
                    impact = "At-Risk"
            stocks.append(
                BeneficiaryRisk(
                    ticker=str(s["ticker"]),
                    name=str(s.get("name") or s["ticker"]),
                    market=str(s.get("market") or "US"),
                    impact=impact,
                    reasoning=str(s.get("reasoning") or s.get("reason") or ""),
                )
            )
        except Exception:
            continue

    return EventImpact(chain_reaction=chain, stocks=stocks)


class ImpactMappingEngine:
    async def map_impact(self, event: ClassifiedEvent, current_prices: dict) -> EventImpact:
        system_prompt = """
        You are an expert macro-strategist. Given the classified macroeconomic event,
        determine its chain reaction impact on Indian and Global markets.
        Return ONLY a raw JSON object, exactly this shape and nothing else:
        {
          "chain_reaction": [{"step": "Step 1", "description": "..."}, {"step": "Step 2", "description": "..."}],
          "stocks": [{"ticker": "AAPL", "name": "Apple Inc", "market": "US", "impact": "Beneficiary", "reasoning": "..."}]
        }
        chain_reaction must have 2-4 steps. stocks must have 2-6 entries.
        market is one of NSE, US, CRYPTO. impact is exactly Beneficiary or At-Risk.
        """

        user_content = f"Event: {event.model_dump_json()}\nCurrent relevant prices context: {current_prices}"

        try:
            response = await llm_provider.generate(
                system_prompt=system_prompt,
                messages=[{"role": "user", "content": user_content}],
                response_schema=EventImpact
            )

            data = _parse_json_lenient(response.content)
            result = _normalise_impact(data)
            if not result.chain_reaction and not result.stocks:
                raise ValueError(f"model returned no usable impact data: {response.content[:200]!r}")
            return result

        except Exception as e:
            logger.error(f"Failed to map impact for event: {e}")
            return EventImpact(chain_reaction=[], stocks=[])

impact_mapping_engine = ImpactMappingEngine()
