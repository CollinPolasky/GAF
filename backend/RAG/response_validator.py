from typing import Dict, List, Optional, Tuple
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv
import json
import httpx
import re

load_dotenv()

# Initialize client for validation
async_client = httpx.AsyncClient()
client = AsyncOpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    http_client=async_client
)

VALIDATION_PROMPT = """Validate this customer service response. Focus on:
1. ACCURACY (A): Facts match search results
2. COMPLETENESS (C): All questions answered
3. RELEVANCE (R): Response uses relevant info
4. CLARITY (CL): Clear and organized

Query: {query}
Search Results: {search_results}
Response: {response}

Return ONLY JSON:
{{
    "is_satisfactory": true if all scores ≥7, else false,
    "analysis": {{
        "accuracy": {{"score": 1-10, "issues": null or ["issue1",...], "suggestions": null or ["fix1",...]}}
        "completeness": {{"score": 1-10, "issues": null or ["issue1",...], "suggestions": null or ["fix1",...]}}
        "relevance": {{"score": 1-10, "issues": null or ["issue1",...], "suggestions": null or ["fix1",...]}}
        "clarity": {{"score": 1-10, "issues": null or ["issue1",...], "suggestions": null or ["fix1",...]}}
    }},
    "retry_needed": true if any score <7,
    "retry_suggestions": null or ["suggestion1",...]
}}"""

def extract_json_from_text(text: str) -> str:
    """Extract JSON object from text, handling cases where there might be extra content."""
    json_match = re.search(r'({[\s\S]*})', text)
    return json_match.group(1) if json_match else text

def validate_analysis_structure(analysis: Dict) -> bool:
    """Quick validation of analysis structure."""
    try:
        if not all(key in analysis for key in ['is_satisfactory', 'analysis', 'retry_needed']):
            return False
        
        if not isinstance(analysis['is_satisfactory'], bool) or not isinstance(analysis['retry_needed'], bool):
            return False
        
        analysis_data = analysis['analysis']
        for aspect in ['accuracy', 'completeness', 'relevance', 'clarity']:
            if aspect not in analysis_data:
                return False
            
            aspect_data = analysis_data[aspect]
            if not all(key in aspect_data for key in ['score', 'issues', 'suggestions']):
                return False
            
            if not isinstance(aspect_data['score'], (int, float)) or not (1 <= aspect_data['score'] <= 10):
                return False
            
            for field in ['issues', 'suggestions']:
                if aspect_data[field] is not None:
                    if not isinstance(aspect_data[field], list):
                        return False
                    if not all(isinstance(item, str) for item in aspect_data[field]):
                        return False
        
        return True
    except Exception:
        return False

def format_search_results(search_results: List[Dict]) -> str:
    """Format search results concisely."""
    formatted = []
    for result in search_results:
        # Extract key information and truncate if too long
        content = result['result']
        if len(content) > 500:  # Truncate long results
            content = content[:497] + "..."
        
        formatted.append(
            f"{result['tool']}: {content}"
        )
    return "\n".join(formatted) if formatted else "No results"

async def validate_response(
    query: str,
    response: str,
    search_results: List[Dict],
    min_acceptable_score: int = 7
) -> Tuple[bool, Optional[Dict], Optional[List[str]]]:
    """Validate response quality."""
    try:
        # Format inputs concisely
        search_results_text = format_search_results(search_results)
        
        # Get validation analysis with minimal prompt
        validation_response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a validator. Return ONLY valid JSON matching the specified format."
                },
                {
                    "role": "user",
                    "content": VALIDATION_PROMPT.format(
                        query=query,
                        search_results=search_results_text,
                        response=response
                    )
                }
            ],
            temperature=0.1,
            max_tokens=500  # Limit response length
        )
        
        validation_text = validation_response.choices[0].message.content.strip()
        json_text = extract_json_from_text(validation_text)
        
        try:
            analysis = json.loads(json_text)
            
            if not validate_analysis_structure(analysis):
                return True, None, None
            
            scores = [analysis['analysis'][aspect]['score'] for aspect in ['accuracy', 'completeness', 'relevance', 'clarity']]
            is_satisfactory = all(score >= min_acceptable_score for score in scores)
            
            if not is_satisfactory and not analysis.get('retry_needed'):
                analysis['retry_needed'] = True
                if not analysis.get('retry_suggestions'):
                    analysis['retry_suggestions'] = ["Improve response quality"]
            
            return (
                is_satisfactory,
                analysis.get('analysis'),
                analysis.get('retry_suggestions') if analysis.get('retry_needed') else None
            )
            
        except json.JSONDecodeError:
            return True, None, None
            
    except Exception as e:
        print(f"[Validation Error] {str(e)}")
        return True, None, None 