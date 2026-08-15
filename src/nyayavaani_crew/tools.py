import os
import json
from dotenv import load_dotenv
from langchain_community.utilities import SerpAPIWrapper
from crewai.tools import tool
from src.rag.retriever import get_rag

load_dotenv()

@tool("State Helpline Lookup Tool")
def state_helpline_tool(query: str) -> str:
    """Useful for searching the internet for official state government grievance helplines and portals. 
    Pass a clear search query like 'Karnataka electricity grievance helpline official'."""
    try:
        api_key = os.environ.get("SERPAPI_API_KEY") or os.environ.get("SERPAPI_KEY")
        search = SerpAPIWrapper(serpapi_api_key=api_key)
        
        
        strict_query = f"{query} (contact OR helpline OR toll free OR email OR official portal) site:gov.in OR site:nic.in"
        
        return search.run(strict_query)
    except Exception as e:
        return f"Search failed: {e}. Please advise the citizen to check the official state portal."

@tool("Twitter Handle Lookup Tool")
def twitter_handle_lookup_tool(query: str) -> str:
    """Useful for finding the official INSTITUTIONAL Twitter/X handle of a government department, municipal corporation, or police force.
    STRICTLY DO NOT search for or tag personal individual accounts of politicians (like @MamataOfficial or CM/PM personal handles).
    Pass a specific query like 'Mumbai Police official twitter handle'."""
    try:
        api_key = os.environ.get("SERPAPI_API_KEY") or os.environ.get("SERPAPI_KEY")
        search = SerpAPIWrapper(serpapi_api_key=api_key)
        strict_query = f"{query} department official site:twitter.com OR site:x.com"
        return search.run(strict_query)
    except Exception as e:
        return f"Search failed: {e}. Default to generic institutional tags like @BBMPOFFICIAL or @DelhiPolice."

@tool("Department Lookup Tool")
def department_lookup_tool(category: str) -> str:
    """Useful for finding central government department contact details based on a category.
    Pass the category of the problem."""
    try:

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        json_path = os.path.join(base_dir, "Data", "departments.json")
        if not os.path.exists(json_path):
            json_path = os.path.join(base_dir, "data", "departments.json")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        departments = data.get("departments", {})
        
        cat_lower = category.lower()
        for dept_id, dept_info in departments.items():
            keywords = dept_info.get("keywords", [])
           
            if any(kw.lower() in cat_lower for kw in keywords) or cat_lower in dept_id:
                name = dept_info.get('official_name', 'N/A')
                helpline = dept_info.get('helpline', 'N/A')
                email = dept_info.get('email', 'N/A')
                portal = dept_info.get('portal', 'N/A')
                return f"Department: {name} | Helpline: {helpline} | Email: {email} | Portal: {portal}"
    
        fallback = data.get("universal_portal", {})
        return f"Department: {fallback.get('name')} | Helpline: {fallback.get('helpline')} | Portal: {fallback.get('portal')}"
        
    except Exception as e:
        return f"Error loading department database: {e}"

@tool("Legal RAG Tool")
def legal_rag_tool(query: str) -> str:
    """Useful for finding Indian laws, legal rights, and acts relevant to a citizen's complaint.
    Pass a description of the problem to search the vector database for applicable laws."""
    rag = get_rag()
    try:
        results = rag.retrieve_and_rerank(query)
        chunks = results.get("chunks", [])
        if not chunks:
            return "No specific legal acts found. Advise using the Right to Information (RTI) Act, 2005 for general grievances."
        # Return top 2 chunks trimmed to preserve token quota
        return "\n\n".join([chunk["content"][:450] for chunk in chunks[:2]])
    except Exception as e:
        return f"Error retrieving legal info: {e}. Default to RTI Act."
