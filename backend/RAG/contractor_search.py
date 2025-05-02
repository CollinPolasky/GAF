import os
import json
from typing import Dict, List, Optional, Union
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone
from dotenv import load_dotenv
import re

# Load environment variables
load_dotenv()

class ContractorSearch:
    """Class for extracting search filters for contractor queries"""
    
    @staticmethod
    def extract_state(query: str) -> Optional[str]:
        """Extract state code from query"""
        state_pattern = r'\b([A-Z]{2})\b'
        matches = re.findall(state_pattern, query.upper())
        
        # List of valid state codes
        valid_states = ['AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 
                        'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 
                        'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 
                        'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 
                        'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY']
        
        for match in matches:
            if match in valid_states:
                return match
        return None
    
    @staticmethod
    def extract_city(query: str) -> Optional[str]:
        """Extract city name from query"""
        # Common city names in the dataset
        cities = ['New York', 'Brooklyn', 'Staten Island', 'Bronx', 'Queens',
                 'Jersey City', 'Newark', 'Hoboken', 'Yonkers', 'Wayne']
        
        for city in cities:
            if city.lower() in query.lower():
                return city
        return None
    
    @staticmethod
    def extract_rating(query: str) -> Optional[str]:
        """Extract rating requirement from query"""
        rating_pattern = r'(\d+\.?\d*)\s*stars?|rating\s*[>=]\s*(\d+\.?\d*)'
        match = re.search(rating_pattern, query.lower())
        if match:
            rating = match.group(1) or match.group(2)
            return rating
        return None
    
    @staticmethod
    def extract_certification(query: str) -> Optional[str]:
        """Extract certification requirement from query"""
        if 'master elite' in query.lower():
            return 'Master Elite'
        return None
    
    @staticmethod
    def is_value_based_query(query: str) -> bool:
        """Determine if this is a value-based query"""
        value_keywords = [
            'value', 'values', 'culture', 'believe', 'believes',
            'care about', 'cares about', 'focus on', 'focuses on',
            'prioritize', 'prioritizes', 'committed to', 'commitment'
        ]
        
        common_values = [
            'quality', 'service', 'integrity', 'excellence', 'reliability',
            'family', 'customer', 'sustainability', 'eco-friendly', 'environment',
            'innovation', 'technology', 'community', 'safety', 'transparency',
            'trust', 'honesty', 'expertise', 'craftsmanship', 'affordability'
        ]
        
        # Check for value-related keywords
        for keyword in value_keywords:
            if keyword in query.lower():
                return True
        
        # Check for specific values
        for value in common_values:
            # Only match whole words or phrases
            pattern = r'\b' + re.escape(value) + r'\b'
            if re.search(pattern, query.lower()):
                return True
        
        return False

def create_search_filters(query: str) -> Dict[str, Union[str, List[str]]]:
    """Create search filters based on identified query parameters"""
    print("\n[Search Strategy] Analyzing query for specific contractor filters...")
    search = ContractorSearch()
    filters = {}
    
    # Try all possible filters
    state = search.extract_state(query)
    city = search.extract_city(query)
    rating = search.extract_rating(query)
    certification = search.extract_certification(query)
    
    # Build filter dictionary and log
    if state:
        print(f"[Filter Found] State: {state}")
        filters["location"] = {"$text": {"$search": state}}
    
    if city:
        print(f"[Filter Found] City: {city}")
        if "location" in filters:
            # Make sure both city and state match
            filters["location"] = {"$text": {"$search": f"{city}"}}
        else:
            filters["location"] = {"$text": {"$search": city}}
    
    if rating:
        print(f"[Filter Found] Rating: {rating}+")
        filters["review_score"] = {"$gte": rating}
    
    if certification:
        print(f"[Filter Found] Certification: {certification}")
        filters["certifications"] = {"$text": {"$search": certification}}
    
    if not filters:
        print("[Search Strategy] No specific filters found - will use semantic search only")
    else:
        print(f"[Search Strategy] Found {len(filters)} filters to narrow search")
    
    return filters

def query_contractors(query: str, top_k: int = 5) -> Dict:
    """
    Query contractor data with multi-strategy search
    
    Args:
        query: The search query
        top_k: Number of results to return
        
    Returns:
        Dictionary with search results
    """
    try:
        search = ContractorSearch()
        
        # Check if query is value-based
        if search.is_value_based_query(query):
            # Import here to avoid circular imports
            from backend.RAG.vectorize_values import query_values
            print(f"\n[Query Strategy] Detected value-based query: '{query}'")
            print("[Query Strategy] Redirecting to values index search")
            return query_values(query, top_k)
        
        # Initialize Pinecone client and model
        pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
        model = SentenceTransformer('all-MiniLM-L6-v2')
        
        print(f"\n[Query] Processing contractor search: '{query}'")
        
        # Extract search filters
        filters = create_search_filters(query)
        
        # Create vector from query
        print("[Embedding] Creating vector embedding for query...")
        query_vector = model.encode(query).tolist()
        
        # Check if index exists
        if "contractors" not in pc.list_indexes().names():
            print("[Error] Contractors index does not exist in Pinecone")
            return {"matches": [], "error": "Contractors database not found"}
        
        index = pc.Index("contractors")
        
        # If we have filters, try filtered search first
        results = None
        if filters:
            print("[Search Strategy] Attempting filtered vector search...")
            results = index.query(
                vector=query_vector,
                top_k=top_k,
                include_metadata=True,
                filter=filters
            )
            
            if not results['matches']:
                print("[Search Strategy] No results found with filters, falling back to semantic search")
                # Fall back to semantic search without filters
                results = index.query(
                    vector=query_vector,
                    top_k=top_k,
                    include_metadata=True
                )
        else:
            # Pure semantic search
            print("[Search Strategy] Performing pure semantic search...")
            results = index.query(
                vector=query_vector,
                top_k=top_k,
                include_metadata=True
            )
        
        print(f"[Results] Found {len(results['matches'])} matching contractors")
        
        # Process results to a more usable format
        processed_results = {
            "matches": [],
            "query": query,
            "result_count": len(results['matches'])
        }
        
        for match in results['matches']:
            processed_results["matches"].append({
                "id": match['metadata'].get('id', ''),
                "name": match['metadata'].get('name', ''),
                "location": match['metadata'].get('location', ''),
                "website": match['metadata'].get('website', ''),
                "phone": match['metadata'].get('phone', ''),
                "about": match['metadata'].get('about', '')[:200] + '...' if len(match['metadata'].get('about', '')) > 200 else match['metadata'].get('about', ''),
                "certifications": match['metadata'].get('certifications', ''),
                "awards": match['metadata'].get('awards', ''),
                "years_in_business": match['metadata'].get('years_in_business', ''),
                "license": match['metadata'].get('state_license_number', ''),
                "review_score": match['metadata'].get('review_score', ''),
                "review_count": match['metadata'].get('review_count', ''),
                "url": match['metadata'].get('url', ''),
                "similarity_score": round(match['score'], 2)
            })
        
        return processed_results
        
    except Exception as e:
        print(f"[Error] Contractor search failed: {str(e)}")
        return {"matches": [], "error": str(e)} 