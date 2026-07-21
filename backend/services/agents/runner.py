import logging
from typing import List, Dict, Any, Callable
from services.llm.provider import llm_provider

logger = logging.getLogger(__name__)

class AgentRunner:
    def __init__(self, system_prompt: str, tools: List[Callable]):
        self.system_prompt = system_prompt
        self.tools = tools
        self.max_iterations = 6

    async def run(self, initial_message: str, context_augmentation: str = "") -> str:
        messages = []
        
        full_system_prompt = self.system_prompt
        if context_augmentation:
            full_system_prompt += f"\n\nContext provided by RAG Pipeline:\n{context_augmentation}"
            
        messages.append({"role": "user", "content": initial_message})
        
        for iteration in range(self.max_iterations):
            try:
                response = await llm_provider.generate(
                    system_prompt=full_system_prompt,
                    messages=messages,
                    tools=self.tools
                )
                
                if not response.tool_calls:
                    # Final answer reached
                    return response.content
                
                # We have tool calls
                messages.append({"role": "assistant", "content": response.content}) # Or add tool calls to message history appropriately depending on provider logic
                
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["arguments"]
                    
                    logger.info(f"Agent iterating, calling tool: {tool_name} with args {tool_args}")
                    
                    # Find tool callable
                    tool_callable = next((t for t in self.tools if t.__name__ == tool_name), None)
                    if tool_callable:
                        # Execute tool
                        # In a real async environment, we should check if tool is async and await it
                        try:
                            # Simplified for now assuming sync or simple async handling
                            import inspect
                            if inspect.iscoroutinefunction(tool_callable):
                                result = await tool_callable(**tool_args)
                            else:
                                result = tool_callable(**tool_args)
                                
                            messages.append({
                                "role": "user", 
                                "content": f"Tool '{tool_name}' returned: {result}"
                            })
                        except Exception as e:
                            logger.error(f"Error executing tool {tool_name}: {e}")
                            messages.append({
                                "role": "user", 
                                "content": f"Tool '{tool_name}' failed with error: {e}"
                            })
                    else:
                        messages.append({
                            "role": "user", 
                            "content": f"Tool '{tool_name}' not found."
                        })
                        
            except Exception as e:
                logger.error(f"Agent iteration failed: {e}")
                return "Agent failed to generate response."
                
        logger.warning(f"Agent hit max iterations ({self.max_iterations})")
        return "Agent stopped after reaching maximum iterations without a final answer."
