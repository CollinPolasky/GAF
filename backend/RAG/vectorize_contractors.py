import json
import os
from typing import Dict, List, Optional, Union
import numpy as np
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv
import re

load_dotenv()

def create_searchable_text(contractor: Dict) -> str:
    """Create rich text representation with multiple search patterns"""
    # Join certifications and awards for better searchability
    certifications = "; ".join(contractor.get('certifications', []))
    awards = "; ".join(contractor.get('awards', []))
    
    # Create a string of review snippets (up to first 3 reviews)
    reviews_text = ""
    for i, review in enumerate(contractor.get('reviews', [])[:3]):
        if i > 0:
            reviews_text += " | "
        reviews_text += f"{review.get('text', '')}"
    
    return f"""
    Contractor: {contractor['name']}
    ID: {contractor.get('id', '')}
    About: {contractor.get('about', '')}
    Location: {extract_location(contractor['url'])}
    Website: {contractor.get('website', '')}
    Phone: {contractor.get('phone', '')}
    Certifications: {certifications}
    Awards: {awards}
    Years in Business: {contractor.get('years_in_business', '')}
    License: {contractor.get('state_license_number', '')}
    Rating: {contractor.get('review_score', '')}
    Reviews Count: {contractor.get('review_count', '')}
    Review Samples: {reviews_text}
    """

def extract_location(url: str) -> str:
    """Extract location information from the URL"""
    pattern = r'/usa/([a-z]{2})/([^/]+)'
    match = re.search(pattern, url)
    if match:
        state = match.group(1).upper()
        city = match.group(2).replace('-', ' ').title()
        return f"{city}, {state}"
    return ""

def create_contractor_metadata(contractor: Dict) -> Dict:
    """Create metadata structure for contractor entries"""
    # Process certifications and awards
    certifications = "; ".join(contractor.get('certifications', []))
    awards = "; ".join(contractor.get('awards', []))
    
    # Get location from URL
    location = extract_location(contractor['url'])
    
    return {
        "id": str(contractor.get('id', '')),
        "name": str(contractor.get('name', '')),
        "website": str(contractor.get('website', '')),
        "phone": str(contractor.get('phone', '')),
        "about": str(contractor.get('about', ''))[:1000] if contractor.get('about') else "",
        "certifications": certifications,
        "awards": awards,
        "years_in_business": str(contractor.get('years_in_business', '')),
        "contractor_id": str(contractor.get('contractor_id', '')),
        "state_license_number": str(contractor.get('state_license_number', '')),
        "review_score": str(contractor.get('review_score', '')),
        "review_count": str(contractor.get('review_count', '')),
        "location": location,
        "url": str(contractor.get('url', '')),
        "reviews_count": str(len(contractor.get('reviews', [])))
    }

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
        filters["location"] = {"$contains": state}
    
    if city:
        print(f"[Filter Found] City: {city}")
        if "location" in filters:
            # Make sure both city and state match
            filters["location"] = {"$contains": f"{city}"}
        else:
            filters["location"] = {"$contains": city}
    
    if rating:
        print(f"[Filter Found] Rating: {rating}+")
        filters["review_score"] = {"$gte": rating}
    
    if certification:
        print(f"[Filter Found] Certification: {certification}")
        filters["certifications"] = {"$contains": certification}
    
    if not filters:
        print("[Search Strategy] No specific filters found - will use semantic search only")
    else:
        print(f"[Search Strategy] Found {len(filters)} filters to narrow search")
    
    return filters

def vectorize_contractors():
    """Vectorize contractor data and upload to Pinecone"""
    # Initialize Pinecone client and model
    pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # Read contractor data from JSON file
    with open('data/contractor_details.json', 'r', encoding='utf-8') as f:
        contractors = json.load(f)
    
    print(f"Loaded {len(contractors)} contractors from JSON file")
    
    # Create index if it doesn't exist
    index_name = "contractors"
    if index_name not in pc.list_indexes().names():
        pc.create_index(
            name=index_name,
            dimension=384,  # MiniLM-L6-v2 dimension
            metric='cosine',
            spec=ServerlessSpec(
                cloud='aws',
                region='us-east-1'
            )
        )
        print(f"Created new '{index_name}' index in Pinecone")
    else:
        print(f"'{index_name}' index already exists in Pinecone")
    
    index = pc.Index(index_name)
    
    # Prepare vectors for upload
    to_upsert = []
    for contractor in contractors:
        # Create searchable text for embedding
        searchable_text = create_searchable_text(contractor)
        
        # Generate embedding
        embedding = model.encode(searchable_text).tolist()
        
        # Create metadata
        metadata = create_contractor_metadata(contractor)
        
        # Add to batch
        to_upsert.append((str(contractor['id']), embedding, metadata))
    
    # Upload in batches
    batch_size = 100
    for i in range(0, len(to_upsert), batch_size):
        batch = to_upsert[i:i+batch_size]
        try:
            index.upsert(vectors=batch)
            print(f"Uploaded batch {i//batch_size + 1} of {(len(to_upsert)-1)//batch_size + 1}")
        except Exception as e:
            print(f"Error uploading batch {i//batch_size + 1}: {str(e)}")
            # Print problematic records for debugging
            for j, (id_, vec, meta) in enumerate(batch):
                try:
                    index.upsert(vectors=[(id_, vec, meta)])
                except Exception as e2:
                    print(f"Problem with record {i+j}: {str(e2)}")
                    print(f"Metadata: {meta}")
    
    print(f"Successfully vectorized and uploaded {len(contractors)} contractors to Pinecone")

def query_contractors(query: str, top_k: int = 5) -> Dict:
    """
    Query contractor data with multi-strategy search
    
    Args:
        query: The search query
        top_k: Number of results to return
        
    Returns:
        Dictionary with search results
    """
    # Initialize Pinecone client and model
    pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    print(f"\n[Query] Processing contractor search: '{query}'")
    
    # Extract search filters
    filters = create_search_filters(query)
    
    # Create vector from query
    print("[Embedding] Creating vector embedding for query...")
    query_vector = model.encode(query).tolist()
    
    index = pc.Index("contractors")
    
    # If we have filters, try filtered search first
    if filters:
        print("[Search Strategy] Attempting filtered vector search...")
        results = index.query(
            vector=query_vector,
            top_k=top_k,
            include_metadata=True,
            filter=filters
        )
        
        if results['matches']:
            print(f"[Results] Found {len(results['matches'])} matches using filters")
            return results
        else:
            print("[Search Strategy] No results found with filters, falling back to semantic search")
    
    # Fall back to semantic search
    print("[Search Strategy] Performing pure semantic search...")
    results = index.query(
        vector=query_vector,
        top_k=top_k,
        include_metadata=True
    )
    print(f"[Results] Found {len(results['matches'])} matches using semantic search")
    return results

if __name__ == "__main__":
    # Run the vectorization process
    vectorize_contractors()
    
    # Test the search functionality
    # Uncomment the following lines to test search
    # print("\n--- Testing Search ---")
    # sample_queries = [
    #     "Roofing contractors in NJ with high ratings",
    #     "Master Elite contractors in New York",
    #     "Contractors with 5-star reviews",
    #     "Roofing companies that specialize in residential projects"
    # ]
    # for query in sample_queries:
    #     results = query_contractors(query)
    #     print(f"\nQuery: {query}")
    #     for i, match in enumerate(results['matches'][:3]):
    #         print(f"{i+1}. {match['metadata']['name']} ({match['metadata']['location']}) - Score: {match['score']:.2f}") 