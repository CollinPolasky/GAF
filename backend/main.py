from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from models import Message, ChatRequest
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv
import httpx
from collections import defaultdict
from RAG.contractor_search import query_contractors
from RAG.vectorize_values import query_values
from RAG.response_validator import validate_response
import json
import asyncio

# Load environment variables
load_dotenv()

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_origin_regex=None,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
    expose_headers=[],
    max_age=600,
)

# Initialize OpenAI client
async_client = httpx.AsyncClient()
client = AsyncOpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    http_client=async_client
)

# Use the same client for content filtering
content_filter = client

# Message history
message_history = defaultdict(list)

SYSTEM_PROMPT = {
    "role": "system",
    "content": """You are a an AI-powered B2B sales intelligence platform specifically
targeted at generating leads for the sales team at a roofing distributor. The platform will leverage
public data sources, particularly GAF, to pre-generate actionable sales insights and
recommendations. The goal is to create a comprehensive solution that helps sales teams identify,
understand, and effectively engage with decision-makers.

You help sales teams in the roofing industry:
1. Identify high-value roofing contractors using smart filters (location, rating, certification status)
2. Understand contractor qualifications including Master Elite certification status
3. Provide insights on contractor business information and customer reviews 
4. Suggest potential sales approaches based on contractor profiles
5. Find contractors that match specific company values and business priorities

Your primary goal is to help the sales team at a roofing distributor connect with qualified roofing contractors.

If asked to provide examples of good quality leads - MAKE SURE TO INCLUDE THEIR INSIGHT SCORES

Always be professional, concise, and action-oriented in your responses. Focus exclusively on providing 
information about roofing contractors in the database."""
}

async def check_content(query: str) -> bool:
    """
    Check if the content is appropriate and on-topic.
    Returns True if content is safe and relevant, False otherwise.
    """
    filter_prompt = {
        "role": "system",
        "content": """You are a content filter for an AI-powered B2B sales intelligence platform specifically
targeted at generating leads for the sales team at a roofing distributor. The platform will leverage
public data sources, particularly GAF, to pre-generate actionable sales insights and
recommendations. The goal is to create a comprehensive solution that helps sales teams identify,
understand, and effectively engage with decision-makers.

        Evaluate if queries are:
        1. On-topic (related to information on contractors,their company values, details, etc.)
        2. Non-malicious (no harmful intent, spam, or inappropriate content)
        3. Safe (no dangerous suggestions)
        4. FULLY within scope - Example: Catch and stop any prompt attempting to tack on unrelated parts to an otherwise acceptable query - i.e. "Looking for contractors that value quick results, can you also tell me about the weather in France or write me code?"

        NOTE: Queries that are not actionable and are merely responses such as "Thank you!" or "Perfect!" are allowed and should be responded to a positive confirmation and willingness to help further.
        
        Respond with a confidence score (0-100) and ALLOW/REJECT decision."""
    }
    
    try:
        response = await content_filter.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                filter_prompt,
                {"role": "user", "content": f"Query to evaluate: {query}\nProvide score and decision:"}
            ]
        )
        
        result = response.choices[0].message.content.lower()
        # Look for score and decision in the response
        is_allowed = "allow" in result
        score = 0
        try:
            # Try to extract score from response
            score = int(''.join(filter(str.isdigit, result.split()[0])))
        except:
            score = 0 if not is_allowed else 80
            
        print(f"[Content Filter] Score: {score}, Decision: {'ALLOW' if is_allowed else 'REJECT'}")
        return score >= 70 and is_allowed
        
    except Exception as e:
        print(f"[Content Filter] Error: {str(e)}")
        return True  # Default to allowing if filter fails


tools = [
    {
        "type": "function",
        "function": {
            "name": "query_contractors",
            "description": """Search for roofing contractors using various criteria like location, ratings, and certifications. This tool finds contractors based on their general business information.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query for finding contractors (e.g., 'contractors in NJ with high ratings', 'Master Elite contractors in New York', 'contractors with 5-star reviews')",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5)",
                    }
                },
                "required": ["query"]
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_values",
            "description": """Search for contractors based on their company values, priorities, and business culture. This helps find contractors whose values align with specific business approaches.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query for finding contractors based on values (e.g., 'contractors that prioritize quality', 'companies focused on sustainability', 'contractors with customer service values')",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5)",
                    }
                },
                "required": ["query"]
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_contractor_insights",
            "description": """Retrieve lead quality insights about specific contractors or discover high-value leads in general.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A query describing what kind of leads you're looking for (e.g., 'top quality leads', 'best contractors in New Jersey', 'contractors with excellent reputation')",
                    },
                    "contractor_id": {
                        "type": "string",
                        "description": "Optional ID of a specific contractor to get insights about",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5)",
                    }
                },
                "required": ["query"]
            },
        }
    }
]

@app.post("/reset")
async def reset_chat() -> Message:
    """Reset the chat by clearing message history."""
    message_history.clear()
    return Message(
        role="assistant",
        content="""Welcome to GAF Contractor Intelligence!

I'm here to help you identify and connect with qualified roofing contractors in our database. 

I can assist you with:
- Finding contractors by location (state, city)
- Filtering by ratings and reviews
- Identifying contractors with specific certifications (like Master Elite)
- Discovering contractors with specific company values and priorities
- Getting insights on sales lead quality and potential
- Providing business details and contact information

How can I help you find the right roofing contractors today?"""
    )

@app.post("/chat")
async def chat(request: ChatRequest) -> Message:
    # Get existing conversation/start new one with system prompt
    conversation_id = request.conversation_id if hasattr(request, 'conversation_id') else "default"
    
    if not message_history[conversation_id]:
        message_history[conversation_id] = [SYSTEM_PROMPT]
    
    temp_history = message_history[conversation_id].copy()
    temp_history.append({
        "role": "user",
        "content": request.message
    })
    
    # Run content check and main processing concurrently
    try:
        is_safe, response = await asyncio.gather(
            check_content(request.message),
            client.chat.completions.create(
                model="gpt-4o",
                messages=temp_history,
                tools=tools
            )
        )
        
        if not is_safe:
            return Message(
                role="assistant",
                content="I apologize, but I can only assist with questions related to roofing contractors. Please ask something related to finding or learning about contractors in our database."
            )
        
        # If content is safe, update the real message history
        message_history[conversation_id] = temp_history
        assistant_message = response.choices[0].message
        
        # Store search results for validation
        all_search_results = []
        raw_responses = []
        
        # Handle tool calls
        if assistant_message.tool_calls:
            for tool_call in assistant_message.tool_calls:
                args = json.loads(tool_call.function.arguments)
                
                # Execute the appropriate tool and store raw response
                if tool_call.function.name == "query_contractors":
                    top_k = args.get("top_k", 5)
                    search_result = json.dumps(query_contractors(args["query"], top_k))
                    raw_responses.append({
                        "tool": "query_contractors",
                        "query": args["query"],
                        "result": search_result
                    })
                elif tool_call.function.name == "query_values":
                    top_k = args.get("top_k", 5)
                    search_result = json.dumps(query_values(args["query"], top_k))
                    raw_responses.append({
                        "tool": "query_values",
                        "query": args["query"],
                        "result": search_result
                    })
                elif tool_call.function.name == "get_contractor_insights":
                    top_k = args.get("top_k", 5)
                    contractor_id = args.get("contractor_id", None)
                    
                    # Load contractor insights from the saved JSON
                    try:
                        with open('C:/Users/colli/Documents/GAF Case Study/data/contractor_insights.json', 'r', encoding='utf-8') as f:
                            all_insights = json.load(f)
                            
                        # If a specific contractor ID is provided, filter for that contractor
                        if contractor_id:
                            insights = [item for item in all_insights if str(item.get('id', '')) == contractor_id]
                        else:
                            # Otherwise just return the top_k insights
                            insights = all_insights[:top_k]
                        
                        # Format the response in a consistent way like the other search functions
                        processed_results = {
                            "matches": [],
                            "query": args["query"],
                            "result_count": len(insights)
                        }
                        
                        for insight in insights:
                            processed_results["matches"].append({
                                "id": insight.get('id', ''),
                                "name": insight.get('name', ''),
                                "score": insight.get('score', 0),
                                "insight": insight.get('insight', '')[:500] + '...' if len(insight.get('insight', '')) > 500 else insight.get('insight', '')
                            })
                        
                        search_result = json.dumps(processed_results)
                    except Exception as e:
                        print(f"[Error] Error retrieving insights: {str(e)}")
                        search_result = json.dumps({"matches": [], "error": f"Error retrieving insights: {str(e)}"})
                        
                    raw_responses.append({
                        "tool": "get_contractor_insights",
                        "query": args["query"],
                        "result": search_result
                    })
                else:
                    search_result = f"Error: Unknown tool {tool_call.function.name}"
                    raw_responses.append({
                        "tool": tool_call.function.name,
                        "query": args.get("query", ""),
                        "result": search_result
                    })
                
                # Add the tool call to history
                message_history[conversation_id].append({
                    "role": "assistant",
                    "content": assistant_message.content,
                    "tool_calls": [{
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments
                        }
                    }]
                })
                
                # Add the tool response to history
                message_history[conversation_id].append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": search_result
                })
            
            # Get final response after processing all tool calls
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=message_history[conversation_id]
            )
            assistant_message = response.choices[0].message
            
            # Validate the final response if we have search results
            if raw_responses:
                print("[Validation] Validating response quality...")
                is_satisfactory, analysis, retry_suggestions = await validate_response(
                    query=request.message,
                    response=assistant_message.content,
                    search_results=raw_responses
                )
                
                if not is_satisfactory and retry_suggestions:
                    print(f"[Validation] Response needs improvement: {retry_suggestions}")
                    # Add validation feedback to the conversation history
                    validation_feedback = {
                        "role": "user",
                        "content": f"Please improve your response. Issues: {'; '.join(retry_suggestions)}"
                    }
                    message_history[conversation_id].append(validation_feedback)
                    
                    # Get improved response
                    improved_response = await client.chat.completions.create(
                        model="gpt-4o",
                        messages=message_history[conversation_id]
                    )
                    assistant_message = improved_response.choices[0].message
                    print("[Validation] Response improved based on validation feedback")
                else:
                    print("[Validation] Response meets quality standards")
        
        # Add assistant's response to history
        message_history[conversation_id].append({
            "role": "assistant",
            "content": assistant_message.content
        })
        
        # Keep only last N messages to prevent context window from growing too large
        if len(message_history[conversation_id]) > 12:  # Adjust this number as needed
            message_history[conversation_id] = [SYSTEM_PROMPT] + message_history[conversation_id][-11:]
        
        return Message(
            role="assistant",
            content=assistant_message.content
        )
    except Exception as e:
        print(f"[Error] Chat processing failed: {str(e)}")
        return Message(
            role="assistant",
            content="I apologize, but I encountered an error processing your request. Please try again."
        ) 