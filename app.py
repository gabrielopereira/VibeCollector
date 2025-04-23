from flask import Flask, render_template, request, send_file, jsonify
from crossref_fetcher import CrossrefJournalFetcher
from chroma_generator import ChromaGenerator
import os
import chromadb
import shutil
import json
import requests
from time import sleep
from datetime import datetime
import socket
import time

app = Flask(__name__)

# Create fetcheddata directory if it doesn't exist
os.makedirs("fetcheddata", exist_ok=True)

class SemanticScholarClient:
    BASE_URL = "https://api.semanticscholar.org/v1/paper"
    
    def __init__(self, api_key: str = None):
        """Initialize with optional API key for higher rate limits"""
        self.headers = {"x-api-key": api_key} if api_key else {}
        # Rate limit: 100 requests per 5 minutes (300 seconds)
        self.rate_limit = 100
        self.time_window = 300  # 5 minutes in seconds
        self.requests = []
    
    def _wait_if_needed(self):
        """Implement token bucket algorithm for rate limiting"""
        current_time = time.time()
        
        # Remove requests older than the time window
        self.requests = [req_time for req_time in self.requests 
                        if current_time - req_time < self.time_window]
        
        # If we've hit the rate limit, wait until the oldest request expires
        if len(self.requests) >= self.rate_limit:
            sleep_time = self.requests[0] + self.time_window - current_time
            if sleep_time > 0:
                print(f"Rate limit reached. Waiting {sleep_time:.1f} seconds...")
                sleep(sleep_time)
        
        # Add current request
        self.requests.append(current_time)
    
    def get_paper_details(self, doi: str) -> dict:
        """Fetch paper details including abstract from Semantic Scholar"""
        try:
            # Use DOI to fetch paper details
            url = f"{self.BASE_URL}/DOI:{doi}"
            
            # Wait if needed to respect rate limit
            self._wait_if_needed()
            
            response = requests.get(url, headers=self.headers)
            
            # Check for rate limit errors
            if response.status_code == 429:  # Too Many Requests
                raise Exception("Rate limit exceeded. Please wait before making more requests.")
            elif response.status_code == 403:  # Forbidden
                raise Exception("Access forbidden. Possible rate limit or API key issue.")
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to fetch abstract for DOI {doi}: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Error fetching abstract for DOI {doi}: {str(e)}")
            raise  # Re-raise the exception to handle it in the calling code

def enrich_with_abstracts():
    """Enrich JSON files with abstracts from Semantic Scholar"""
    data_dir = "fetcheddata"
    semantic_scholar = SemanticScholarClient()
    stats = {
        "total_files": 0,
        "total_papers": 0,
        "papers_with_abstracts": 0,
        "new_abstracts_added": 0,
        "errors": 0
    }
    
    # Ensure the data directory exists
    if not os.path.exists(data_dir):
        return {"error": f"Directory {data_dir} does not exist."}, stats
    
    # Process each JSON file
    json_files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
    stats["total_files"] = len(json_files)
    print(f"\nFound {len(json_files)} JSON files to process")
    
    for filename in json_files:
        file_path = os.path.join(data_dir, filename)
        print(f"\nProcessing file: {filename}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                papers = json.load(f)
                
            stats["total_papers"] += len(papers)
            
            # First, mark papers that already have abstracts
            abstract_stats = {"yes": 0, "no": 0, "not available": 0}
            
            for paper in papers:
                if paper.get("abstract"):
                    paper["metadata"]["abstract_available"] = "yes"
                    stats["papers_with_abstracts"] += 1
                    abstract_stats["yes"] += 1
                elif paper.get("metadata", {}).get("abstract_available") == "not available":
                    abstract_stats["not available"] += 1
                else:
                    abstract_stats["no"] += 1
            
            print("\nInitial abstract availability status:")
            print(f"✓ Papers with abstracts: {abstract_stats['yes']}")
            print(f"✗ Papers without abstracts: {abstract_stats['no']}")
            print(f"⚠ Papers marked as not available: {abstract_stats['not available']}")
            
            # Then process papers without abstracts that haven't been marked as not available
            papers_to_process = [p for p in papers if not p.get("abstract") and 
                               p.get("metadata", {}).get("abstract_available") != "not available"]
            
            if not papers_to_process:
                print("No papers need abstract enrichment")
                # Save the updated metadata for papers that already had abstracts
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(papers, f, indent=2, ensure_ascii=False)
                continue
                
            print(f"Found {len(papers_to_process)} papers to check for abstracts")
            
            for i, paper in enumerate(papers_to_process, 1):
                doi = paper.get("metadata", {}).get("doi")
                if doi:
                    print(f"\nProcessing paper {i}/{len(papers_to_process)}")
                    print(f"DOI: {doi}")
                    
                    try:
                        semantic_paper = semantic_scholar.get_paper_details(doi)
                        
                        if semantic_paper and semantic_paper.get("abstract"):
                            paper["abstract"] = semantic_paper["abstract"]
                            paper["metadata"]["abstract_available"] = "yes"
                            stats["new_abstracts_added"] += 1
                            print("✓ Successfully added abstract")
                        else:
                            paper["metadata"]["abstract_available"] = "not available"
                            print("✗ No abstract found")
                        
                        # Save after each paper is processed
                        with open(file_path, 'w', encoding='utf-8') as f:
                            json.dump(papers, f, indent=2, ensure_ascii=False)
                        print("✓ Saved progress to file")
                        
                    except requests.exceptions.RequestException as e:
                        print(f"❌ API Error: {str(e)}")
                        print("Stopping process due to API error")
                        return {"error": f"API Error: {str(e)}"}, stats
                        
        except Exception as e:
            print(f"Error processing file {filename}: {str(e)}")
            stats["errors"] += 1
            continue
            
    return {"message": "Abstract enrichment completed"}, stats

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/fetch', methods=['POST'])
def fetch_journal():
    issn = request.form.get('issn')
    if not issn:
        return jsonify({'error': 'Please provide an ISSN'}), 400
    
    try:
        # Initialize fetcher with a default email
        fetcher = CrossrefJournalFetcher("webapp@example.com")
        
        # Save the data to fetcheddata directory
        filename = os.path.join("fetcheddata", f"{issn}.json")
        fetcher.save_to_file(issn, filename)
        
        # Check if file exists
        if os.path.exists(filename):
            return jsonify({
                'success': True,
                'message': f'Data saved to {filename}',
                'filename': filename
            })
        else:
            return jsonify({'error': 'Failed to create file'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/generate-chroma', methods=['POST'])
def generate_chroma():
    try:
        generator = ChromaGenerator()
        generator.generate()
        return jsonify({
            'success': True,
            'message': 'ChromaDB collection generated successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/purge_chroma', methods=['POST'])
def purge_chroma():
    """Endpoint to purge the ChromaDB collection"""
    try:
        # First try to delete the collection through the API
        try:
            client = chromadb.PersistentClient(path="./chroma_db")
            client.delete_collection("academic_papers")
            print("Successfully deleted collection 'academic_papers'")
        except Exception as e:
            print(f"No collection to delete: {str(e)}")
        
        # Then remove the entire chroma_db directory
        if os.path.exists("./chroma_db"):
            shutil.rmtree("./chroma_db")
            print("Successfully removed chroma_db directory")
            return jsonify({"message": "ChromaDB collection and files purged successfully"})
        else:
            return jsonify({"message": "No ChromaDB files found to purge"})
            
    except Exception as e:
        print(f"Error purging ChromaDB: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    try:
        return send_file(os.path.join("fetcheddata", filename), as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/enrich_abstracts', methods=['POST'])
def enrich_abstracts():
    """Endpoint to enrich JSON files with abstracts from Semantic Scholar"""
    message, stats = enrich_with_abstracts()
    return jsonify({
        "message": message.get("message", "Data enrichment complete"),
        "stats": stats
    })

def find_available_port(start_port=5000, max_port=5010):
    """Find an available port starting from start_port up to max_port"""
    for port in range(start_port, max_port + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"No available ports found between {start_port} and {max_port}")

if __name__ == '__main__':
    try:
        port = find_available_port()
        print(f"Starting server on port {port}")
        app.run(debug=True, port=port)
    except RuntimeError as e:
        print(f"Error: {e}")
        print("Please try a different port range or check if any other services are using the ports.") 