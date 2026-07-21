import json
import logging
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from services.llm.provider import llm_provider

logger = logging.getLogger(__name__)

class ClassifiedEvent(BaseModel):
    event_type: str = Field(description="The category of the macroeconomic event (e.g., Interest Rate Decision, Inflation Report)")
    severity: str = Field(description="High, Medium, or Low")
    affected_asset_classes: List[str] = Field(description="e.g., Equities, Bonds, Crypto, Commodities")
    affected_sectors: List[str] = Field(description="e.g., IT, Banking, Pharma")
    summary: str = Field(description="A concise summary of the event and its immediate implications")

class EventClassifier:
    async def classify_headline(self, headline: str) -> Optional[ClassifiedEvent]:
        system_prompt = """
        You are a financial analyst. Classify the following macroeconomic news headline into a structured JSON format.
        Evaluate the severity of the event on Indian and Global markets.
        """
        
        try:
            # We enforce JSON schema directly if the provider supports it, 
            # but we can also just ask for JSON and parse it
            response = await llm_provider.generate(
                system_prompt=system_prompt,
                messages=[{"role": "user", "content": f"Headline: {headline}"}],
                # passing response_schema might require Pydantic model for Gemini
                response_schema=ClassifiedEvent
            )
            
            # response.content should be a JSON string
            data = json.loads(response.content)
            return ClassifiedEvent(**data)
            
        except Exception as e:
            logger.error(f"Failed to classify headline '{headline}': {e}")
            # Fallback
            return ClassifiedEvent(
                event_type="Unclassified",
                severity="Low",
                affected_asset_classes=[],
                affected_sectors=[],
                summary=headline
            )

event_classifier = EventClassifier()
