from typing import List, Dict, Any
from datetime import datetime
import json

class ContextAssembler:
    """
    Assembles explicitly retrieved data into a structured context block for the RAG pipeline.
    """
    def retrieve_and_rank(self, raw_events: List[Dict], prices: Dict[str, Any]) -> Dict[str, Any]:
        """
        Rank/Filter: discard stale or low-relevance retrieved data
        """
        # Simple recency + severity scoring filter
        # Assuming events have 'timestamp' and 'severity'
        filtered_events = []
        for event in raw_events:
            # Add logic here to filter events older than 24h unless historical context
            # For simplicity, we just pass high/medium severity events.
            # None-safe: unclassified events (severity None) are skipped, not crashed on.
            if (event.get('severity') or '').lower() in ['high', 'medium']:
                filtered_events.append(event)
                
        return {
            "events": filtered_events,
            "prices": prices
        }

    def augment(self, context_data: Dict[str, Any]) -> str:
        """
        Format the retrieved, filtered context into a structured block using clear delimiters.
        """
        events_str = json.dumps(context_data.get("events", []), indent=2)
        prices_str = json.dumps(context_data.get("prices", {}), indent=2)
        
        augmented_prompt = f"""
<live_data>
{prices_str}
</live_data>

<macro_events>
{events_str}
</macro_events>
"""
        return augmented_prompt

context_assembler = ContextAssembler()
