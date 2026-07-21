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

class ImpactMappingEngine:
    async def map_impact(self, event: ClassifiedEvent, current_prices: dict) -> EventImpact:
        system_prompt = """
        You are an expert macro-strategist. Given the classified macroeconomic event, 
        determine its chain reaction impact on Indian and Global markets.
        Provide a step-by-step chain reaction.
        Then, list specific beneficiary and at-risk stocks with their tickers, names, market (NSE, US, CRYPTO), and reasoning.
        Output must be strict JSON matching the schema.
        """
        
        user_content = f"Event: {event.model_dump_json()}\nCurrent relevant prices context: {current_prices}"
        
        try:
            response = await llm_provider.generate(
                system_prompt=system_prompt,
                messages=[{"role": "user", "content": user_content}],
                response_schema=EventImpact
            )
            
            data = json.loads(response.content)
            return EventImpact(**data)
            
        except Exception as e:
            logger.error(f"Failed to map impact for event: {e}")
            return EventImpact(chain_reaction=[], stocks=[])

impact_mapping_engine = ImpactMappingEngine()
