import json
import os
from openai import OpenAI
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def extract_values_from_text(text: str) -> List[str]:
    """
    Use ChatGPT to extract values from contractor text
    
    Args:
        text: Consolidated text about the contractor
        
    Returns:
        List of up 10 1-3 word value phrases
    """
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    
    system_prompt = """You are an expert in analyzing company descriptions and customer reviews to identify 
    core company values. Based on the text provided, identify exactly 10 values that seem to be important to 
    the company. Each value should be 1-3 words long.
    
    Format your response as a simple comma-separated list with no numbering, bullet points, or additional explanation.
    Example format: "Quality Service, Fast Service, Customer Focus, Reliability, Innovation, Sustainability, Excellence, 
    Communication, Transparency, Safety"
    
    Important:
    - Return EXACTLY 10 values, no more, no less
    - Values SHOULD be RANKED in order of importance/what seems most important for the company
    - Each value should be 1-3 words
    - Values should reflect the company's actual priorities and practices
    - Be specific - avoid generic values unless they're clearly relevant
    - No explanation or commentary, just the comma-separated list
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract 10 company values from this text:\n\n{text}"}
            ],
            temperature=0.7,
            max_tokens=150
        )
        
        # Extract and clean values
        values_text = response.choices[0].message.content.strip()
        values = [value.strip() for value in values_text.split(',')]
        
        # Ensure we have exactly 10 values
        if len(values) > 10:
            values = values[:10]
        elif len(values) < 10:
            # Add N/A values to fill any gaps
            generic_values = ["N/A", "N/A", "N/A", 
                             "N/A", "N/A", "N/A", 
                             "N/A", "N/A", "N/A", "N/A"]
            values.extend(generic_values[:(10-len(values))])
            
        return values
    
    except Exception as e:
        print(f"Error extracting values with ChatGPT: {e}")
        # Fallback to generic roofing contractor values
        return ["N/A", "N/A", "N/A", 
                "N/A", "N/A", "N/A", 
                "N/A", "N/A", "N/A", "N/A"]

def prepare_contractor_text(contractor: Dict[str, Any]) -> str:
    """
    Consolidate contractor information into a single text for analysis
    
    Args:
        contractor: Dictionary containing contractor information
        
    Returns:
        Consolidated text about the contractor
    """
    text_parts = []
    
    # Add company name
    text_parts.append(f"Company Name: {contractor.get('name', 'Unknown')}")
    
    # Add years in business
    if contractor.get('years_in_business'):
        text_parts.append(f"Business History: {contractor.get('years_in_business')}")
    
    # Add about section
    if contractor.get('about'):
        text_parts.append(f"Company Description: {contractor.get('about')}")
    
    # Add certifications
    if contractor.get('certifications'):
        if isinstance(contractor['certifications'], list):
            certs = '; '.join(contractor['certifications'])
        else:
            certs = contractor['certifications']
        text_parts.append(f"Certifications and Qualifications: {certs}")
    
    # Add awards
    if contractor.get('awards'):
        if isinstance(contractor['awards'], list):
            awards = '; '.join(contractor['awards'])
        else:
            awards = contractor['awards']
        text_parts.append(f"Awards and Recognition: {awards}")
    
    # Add reviews
    if contractor.get('reviews') and isinstance(contractor['reviews'], list):
        review_texts = []
        for review in contractor['reviews'][:5]:  # Limit to 5 reviews to keep text length manageable
            if isinstance(review, dict) and review.get('text'):
                review_texts.append(review['text'])
        
        if review_texts:
            text_parts.append("Customer Reviews:")
            text_parts.extend(review_texts)
    
    # Combine all parts
    return "\n\n".join(text_parts)

def get_contractor_values(contractor_id: str = None) -> Dict[str, Any]:
    """
    Extract values for a specific contractor or all contractors
    
    Args:
        contractor_id: Optional ID of specific contractor to analyze
        
    Returns:
        Dictionary with contractor ID(s) and their values
    """
    try:
        # Load contractor data
        with open('data/contractor_details.json', 'r', encoding='utf-8') as f:
            contractors = json.load(f)
        
        results = {}
        
        # Process single contractor if ID provided
        if contractor_id:
            for contractor in contractors:
                if str(contractor.get('id', '')) == contractor_id or str(contractor.get('contractor_id', '')) == contractor_id:
                    contractor_text = prepare_contractor_text(contractor)
                    values = extract_values_from_text(contractor_text)
                    
                    results[str(contractor.get('id', ''))] = {
                        "name": contractor.get('name', ''),
                        "values": values,
                        "values_text": ", ".join(values)
                    }
                    break
        # Process all contractors if no ID provided
        else:
            for contractor in contractors:
                contractor_text = prepare_contractor_text(contractor)
                values = extract_values_from_text(contractor_text)
                
                results[str(contractor.get('id', ''))] = {
                    "name": contractor.get('name', ''),
                    "values": values,
                    "values_text": ", ".join(values)
                }
        
        return results
    
    except Exception as e:
        print(f"Error processing contractor values: {e}")
        return {"error": str(e)}

def add_values_to_json() -> None:
    """
    Process all contractors and add values to the JSON file,
    storing only name, values, website, reviews, and description
    """
    try:
        # Load contractor data
        with open('data/contractor_details.json', 'r', encoding='utf-8') as f:
            contractors = json.load(f)
        
        # Process each contractor and create simplified records
        simplified_contractors = []
        
        for contractor in contractors:
            contractor_text = prepare_contractor_text(contractor)
            values = extract_values_from_text(contractor_text)
            
            # Create simplified contractor record with only required fields
            simplified_contractor = {
                "id": contractor.get('id', ''),
                "name": contractor.get('name', ''),
                "website": contractor.get('website', ''),
                "about": contractor.get('about', ''),
                "reviews": contractor.get('reviews', []),
                "values": values,
                "values_text": ", ".join(values)
            }
            
            simplified_contractors.append(simplified_contractor)
        
        # Save simplified data
        with open('data/contractor_values.json', 'w', encoding='utf-8') as f:
            json.dump(simplified_contractors, f, indent=4)
            
        print(f"Successfully processed {len(contractors)} contractors and saved to contractor_values.json")
    
    except Exception as e:
        print(f"Error adding values to JSON: {e}")

if __name__ == "__main__":
    # When run directly, process all contractors and add values to JSON
    add_values_to_json()
