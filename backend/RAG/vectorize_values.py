import json
import os
from typing import Dict, List, Optional, Union
import numpy as np
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv
import re

# Load environment variables
load_dotenv()

def create_searchable_text(contractor: Dict) -> str:
    """Create rich text representation focused on values"""
    # Get the company values
    values_text = contractor.get('values_text', '')
    
    # Create a string of review snippets (up to first 3 reviews)
    reviews_text = ""
    for i, review in enumerate(contractor.get('reviews', [])[:3]):
        if i > 0:
            reviews_text += " | "
        if isinstance(review, dict):
            reviews_text += f"{review.get('text', '')}"
        else:
            reviews_text += str(review)
    
    return f"""
    Contractor: {contractor['name']}
    ID: {contractor.get('id', '')}
    Website: {contractor.get('website', '')}
    Values: {values_text}
    About: {contractor.get('about', '')}
    Review Samples: {reviews_text}
    """

def create_contractor_metadata(contractor: Dict) -> Dict:
    """Create metadata structure focusing on values"""
    # Prepare individual values
    values = contractor.get('values', [])
    values_dict = {}
    for i, value in enumerate(values):
        values_dict[f"value_{i+1}"] = value
    
    # Create the metadata object
    metadata = {
        "id": str(contractor.get('id', '')),
        "name": str(contractor.get('name', '')),
        "website": str(contractor.get('website', '')),
        "about": str(contractor.get('about', ''))[:1000] if contractor.get('about') else "",
        "values_text": str(contractor.get('values_text', '')),
        **values_dict  # Include individual values
    }
    
    return metadata

class ValueSearch:
    """Class for extracting value-related search terms"""
    
    @staticmethod
    def extract_value_terms(query: str) -> List[str]:
        """Extract potential value terms from query"""
        # Common value terms in roofing industry
        value_terms = [
            'quality', 'reliability', 'integrity', 'professionalism', 
            'service', 'safety', 'excellence', 'customer', 'innovation',
            'sustainability', 'eco-friendly', 'communication', 'transparency',
            'affordability', 'speed', 'efficiency', 'craftsmanship', 'expertise',
            'warranty', 'guarantee', 'family', 'trust', 'responsive', 'punctual'
        ]
        
        found_terms = []
        for term in value_terms:
            if term.lower() in query.lower():
                found_terms.append(term)
        
        return found_terms

def create_search_filters(query: str) -> Dict[str, Union[str, List[str]]]:
    """Create search filters based on identified value terms"""
    print("\n[Search Strategy] Analyzing query for specific value filters...")
    search = ValueSearch()
    filters = {}
    
    # Extract value terms
    value_terms = search.extract_value_terms(query)
    
    # Build filter dictionary for values
    if value_terms:
        print(f"[Filter Found] Value terms: {', '.join(value_terms)}")
        # Create an OR filter across all value fields
        or_filters = []
        for term in value_terms:
            field_filters = []
            for i in range(1, 11):  # Assuming up to 10 values per contractor
                # Using $eq instead of $contains, which is more widely supported
                field_filters.append({f"value_{i}": {"$eq": term}})
            or_filters.extend(field_filters)
            
        if len(or_filters) == 1:
            filters = or_filters[0]
        else:
            filters = {"$or": or_filters}
    else:
        print("[Search Strategy] No specific value terms found - will use semantic search only")
    
    return filters

def vectorize_values():
    """Vectorize contractor values data and upload to Pinecone"""
    # Initialize Pinecone client and model
    pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # Read contractor values data from JSON file
    with open('data/contractor_values.json', 'r', encoding='utf-8') as f:
        contractors = json.load(f)
    
    print(f"Loaded {len(contractors)} contractors from JSON file")
    
    # Create index if it doesn't exist
    index_name = "values"
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
    
    print(f"Successfully vectorized and uploaded {len(contractors)} contractor values to Pinecone")

def query_values(query: str, top_k: int = 5) -> Dict:
    """
    Query contractor values with multi-strategy search
    
    Args:
        query: The search query
        top_k: Number of results to return
        
    Returns:
        Dictionary with search results
    """
    # Initialize Pinecone client and model
    pc = Pinecone(api_key=os.environ.get("PINECONE_API_KEY"))
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    print(f"\n[Query] Processing value-based search: '{query}'")
    
    # Extract search filters
    filters = create_search_filters(query)
    
    # Create vector from query
    print("[Embedding] Creating vector embedding for query...")
    query_vector = model.encode(query).tolist()
    
    index = pc.Index("values")
    
    # If we have filters, try filtered search first
    if filters and not isinstance(filters, list):
        print("[Search Strategy] Attempting filtered vector search...")
        results = index.query(
            vector=query_vector,
            top_k=top_k,
            include_metadata=True,
            filter=filters
        )
        
        if results['matches']:
            print(f"[Results] Found {len(results['matches'])} matches using filters")
        else:
            print("[Search Strategy] No results found with filters, falling back to semantic search")
            # Fall back to semantic search
            print("[Search Strategy] Performing pure semantic search...")
            results = index.query(
                vector=query_vector,
                top_k=top_k,
                include_metadata=True
            )
    else:
        # Fall back to semantic search
        print("[Search Strategy] Performing pure semantic search...")
        results = index.query(
            vector=query_vector,
            top_k=top_k,
            include_metadata=True
        )
    
    print(f"[Results] Found {len(results['matches'])} matches using semantic search")
    
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
            "website": match['metadata'].get('website', ''),
            "values_text": match['metadata'].get('values_text', ''),
            "about": match['metadata'].get('about', '')[:200] + '...' if len(match['metadata'].get('about', '')) > 200 else match['metadata'].get('about', ''),
            "similarity_score": round(match['score'], 2)
        })
    
    return processed_results

if __name__ == "__main__":
    # First, run value.py to generate contractor_values.json if it doesn't exist
    if not os.path.exists('data/contractor_values.json'):
        print("contractor_values.json not found. Please run value.py first.")
    else:
        # Run the vectorization process
        vectorize_values()
