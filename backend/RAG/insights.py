import json
import os
from openai import OpenAI
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
import re

# Load environment variables
load_dotenv()

def extract_years_in_business(years_text: str) -> int:
    """Extract the number of years in business from text like 'In business since 2009'"""
    if not years_text:
        return 0
        
    # Try to extract year
    year_pattern = r'since\s+(\d{4})'
    match = re.search(year_pattern, years_text, re.IGNORECASE)
    if match:
        try:
            year = int(match.group(1))
            current_year = 2025  # Hardcoded for demo, could use datetime
            return current_year - year
        except (ValueError, TypeError):
            pass
            
    # If we can't extract the year, try to extract direct years
    years_pattern = r'(\d+)\s+years?'
    match = re.search(years_pattern, years_text, re.IGNORECASE)
    if match:
        try:
            return int(match.group(1))
        except (ValueError, TypeError):
            pass
            
    return 0

def generate_contractor_insight(contractor: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a lead quality insight for a contractor using the ChatGPT API
    
    Args:
        contractor: Dictionary containing contractor information
        
    Returns:
        Dictionary containing score and insight text
    """
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    
    # Extract relevant information
    years_text = contractor.get('years_in_business', '')
    years = extract_years_in_business(years_text)
    
    review_count = 0
    review_score = 0
    
    # Handle different formats for review data
    if isinstance(contractor.get('review_count', ''), str):
        try:
            review_count = int(contractor.get('review_count', '0').replace(',', ''))
        except (ValueError, TypeError):
            review_count = 0
            
    if isinstance(contractor.get('review_score', ''), str):
        try:
            review_score = float(contractor.get('review_score', '0'))
        except (ValueError, TypeError):
            review_score = 0
            
    # Get values
    values = contractor.get('values', [])
    values_text = ', '.join(values) if isinstance(values, list) else values
    
    # Prepare input for the LLM
    prompt = f"""
    You are an expert in B2B sales lead qualification. 
    Analyze this contractor data and provide a score (0-100 with 100 being the best possible lead) and 4-sentence insight about their quality as a potential lead:
    
    Company Name: {contractor.get('name', 'Unknown')}
    Years in Business: {years} years ({years_text})
    Reviews: {review_count} reviews with a score of {review_score}/5
    Values: {values_text}
    
    RESPONSES SHOULD BE NO LONGER THAN THE SCORE AND THEN 4 SENTENCES

    Please structure your response as follows:
        Score: 0-100 based on how good of a lead this contractor is, you do NOT need to limit yourself to multiples of 5 or 10
        Overview of the contractor's establishment and experience
        Assessment of their customer satisfaction based on reviews
        Analysis of their company values and what it indicates
        Brief conclusion about their potential value as a lead
    
    Your insight should be data-driven, professional, and sales-oriented.
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a B2B sales lead qualification expert."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=250
        )
        
        full_response = response.choices[0].message.content.strip()
        
        # Extract score from the response
        score = 0
        insight_text = full_response
        
        # Look for "Score: X" pattern at the beginning
        score_pattern = r'Score:\s*(\d+)'
        score_match = re.search(score_pattern, full_response)
        
        if score_match:
            try:
                score = int(score_match.group(1))
                # Remove the score line from the insight text
                insight_text = re.sub(r'Score:\s*\d+\s*', '', full_response).strip()
            except (ValueError, TypeError):
                pass
        
        return {
            "score": score,
            "insight": insight_text
        }
        
    except Exception as e:
        print(f"Error generating insight with ChatGPT: {e}")
        # Fallback: generate a simple insight
        return f"{contractor.get('name', 'This contractor')} has been in business for {years} years with {review_count} reviews at {review_score}/5 rating. Their values include {values_text[:50]}... These factors suggest they may be a promising lead for roofing services."

def generate_insights_for_all(json_file: str = 'data/contractor_details.json', 
                             output_file: str = 'data/contractor_insights.json',
                             max_contractors: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Generate insights for all contractors in the JSON file
    
    Args:
        json_file: Path to the JSON file with contractor details
        output_file: Path to save the output JSON file with insights
        max_contractors: Maximum number of contractors to process (for testing)
        
    Returns:
        List of contractors with added insights
    """
    try:
        # Load contractor data
        with open(json_file, 'r', encoding='utf-8') as f:
            contractors = json.load(f)
        
        print(f"Loaded {len(contractors)} contractors from {json_file}")
        
        # Limit the number of contractors for testing
        if max_contractors is not None:
            contractors = contractors[:max_contractors]
            print(f"Processing {len(contractors)} contractors (limited by max_contractors)")
        
        # Generate insights for each contractor
        simplified_results = []
        
        for i, contractor in enumerate(contractors):
            print(f"Generating insight for contractor {i+1}/{len(contractors)}: {contractor.get('name', 'Unknown')}")
            result = generate_contractor_insight(contractor)
            
            # Create simplified entry with id, name, score, and insight text
            simplified_entry = {
                "id": contractor.get('id', ''),
                "name": contractor.get('name', ''),
                "score": result["score"],
                "insight": result["insight"]
            }
            simplified_results.append(simplified_entry)
        
        # Save simplified data
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(simplified_results, f, indent=4)
            
        print(f"Successfully generated insights for {len(simplified_results)} contractors and saved to {output_file}")
        
        return simplified_results
        
    except Exception as e:
        print(f"Error processing contractor insights: {e}")
        return []

def generate_sample_insight(contractor_id: Optional[str] = None):
    """
    Generate a sample insight for a specific contractor or the first one in the file
    
    Args:
        contractor_id: Optional ID of the contractor to analyze
    """
    try:
        # Load contractor data
        with open('data/contractor_details.json', 'r', encoding='utf-8') as f:
            contractors = json.load(f)
        
        target_contractor = None
        
        # Find specific contractor if ID provided
        if contractor_id:
            for contractor in contractors:
                if str(contractor.get('id', '')) == contractor_id:
                    target_contractor = contractor
                    break
        else:
            # Use the first contractor
            target_contractor = contractors[0]
        
        if target_contractor:
            print(f"\nGenerating sample insight for: {target_contractor.get('name', 'Unknown')}")
            print("-" * 50)
            
            # Display basic info
            years_text = target_contractor.get('years_in_business', 'Unknown')
            years = extract_years_in_business(years_text)
            review_count = target_contractor.get('review_count', 'Unknown')
            review_score = target_contractor.get('review_score', 'Unknown')
            values = target_contractor.get('values', [])
            values_text = ', '.join(values) if isinstance(values, list) else values
            
            print(f"Name: {target_contractor.get('name', 'Unknown')}")
            print(f"Years in Business: {years} years ({years_text})")
            print(f"Reviews: {review_count} reviews with a score of {review_score}/5")
            print(f"Values: {values_text}")
            print("-" * 50)
            
            # Generate and display insight
            result = generate_contractor_insight(target_contractor)
            print("\nLead Quality Score:", result["score"])
            print("\nLead Quality Insight:")
            print(result["insight"])
            
        else:
            print(f"No contractor found with ID: {contractor_id}")
    
    except Exception as e:
        print(f"Error generating sample insight: {e}")

if __name__ == "__main__":
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Generate insights for contractors')
    parser.add_argument('--sample', action='store_true', help='Generate a sample insight for a single contractor')
    parser.add_argument('--id', type=str, help='Contractor ID for sample insight')
    parser.add_argument('--max', type=int, help='Maximum number of contractors to process')
    parser.add_argument('--input', type=str, default='data/contractor_details.json', help='Input JSON file')
    parser.add_argument('--output', type=str, default='data/contractor_insights.json', help='Output JSON file')
    args = parser.parse_args()
    
    if args.sample:
        generate_sample_insight(args.id)
    else:
        print("=" * 80)
        print("GENERATING LEAD QUALITY INSIGHTS FOR ALL CONTRACTORS")
        print("=" * 80)
        print(f"Input file: {args.input}")
        print(f"Output file: {args.output}")
        if args.max:
            print(f"Processing up to {args.max} contractors")
        else:
            print("Processing all contractors")
        print("-" * 80)
        
        # Generate insights for all contractors
        results = generate_insights_for_all(args.input, args.output, args.max)
        
        print("\n" + "=" * 80)
        print(f"COMPLETED: Generated insights for {len(results)} contractors")
        print(f"Insights saved to: {args.output}")
        print("=" * 80)
        
        # Create a copy for the public folder if needed
        try:
            import os
            import shutil
            public_file = 'public/data/contractor_insights.json'
            os.makedirs(os.path.dirname(public_file), exist_ok=True)
            shutil.copy2(args.output, public_file)
            print(f"A copy of the insights has been saved to: {public_file}")
            print(f"This file can be accessed by the web application.")
        except Exception as e:
            print(f"Note: Could not create public copy: {e}")
            print(f"You may need to manually copy {args.output} to public/data/ for web access.")
