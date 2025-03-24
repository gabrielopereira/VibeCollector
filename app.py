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

app = Flask(__name__)

# Create fetcheddata directory if it doesn't exist
os.makedirs("fetcheddata", exist_ok=True)

class SemanticScholarClient:
    BASE_URL = "https://api.semanticscholar.org/v1/paper"
    
    def __init__(self, api_key: str = None):
        """Initialize with optional API key for higher rate limits"""
        self.headers = {"x-api-key": api_key} if api_key else {}
    
    def get_paper_details(self, doi: str) -> dict:
        """Fetch paper details including abstract from Semantic Scholar"""
        try:
            # Use DOI to fetch paper details
            url = f"{self.BASE_URL}/DOI:{doi}"
            response = requests.get(url, headers=self.headers)
            
            # Rate limiting - be nice to the API
            sleep(1)  # Wait 1 second between requests
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to fetch abstract for DOI {doi}: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error fetching abstract for DOI {doi}: {str(e)}")
            return None

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
                if not isinstance(papers, list):
                    papers = [papers]
                
                stats["total_papers"] += len(papers)
                papers_with_abstracts = sum(1 for p in papers if p.get("abstract"))
                stats["papers_with_abstracts"] += papers_with_abstracts
                
                print(f"Found {len(papers)} papers in file")
                print(f"Papers with existing abstracts: {papers_with_abstracts}")
                
                # Process papers without abstracts
                papers_to_process = [p for p in papers if not p.get("abstract")]
                print(f"Attempting to fetch abstracts for {len(papers_to_process)} papers")
                
                for i, paper in enumerate(papers_to_process, 1):
                    # Check if paper already has an abstract
                    if paper.get("abstract"):
                        print(f"\nPaper {i}/{len(papers_to_process)} already has an abstract, skipping")
                        continue
                        
                    doi = paper.get("metadata", {}).get("doi")
                    if doi:
                        print(f"\nProcessing paper {i}/{len(papers_to_process)}")
                        print(f"DOI: {doi}")
                        
                        try:
                            semantic_paper = semantic_scholar.get_paper_details(doi)
                            
                            if semantic_paper and semantic_paper.get("abstract"):
                                paper["abstract"] = semantic_paper["abstract"]
                                stats["new_abstracts_added"] += 1
                                print("✓ Successfully added abstract")
                                
                                # Save after each successful abstract addition
                                with open(file_path, 'w', encoding='utf-8') as f:
                                    json.dump(papers, f, indent=2, ensure_ascii=False)
                                print("✓ Saved progress to file")
                            else:
                                print("✗ No abstract found")
                                
                            # Rate limiting - wait 1 second between requests
                            sleep(1)
                            
                        except requests.exceptions.RequestException as e:
                            print(f"❌ API Error: {str(e)}")
                            print("Stopping process due to API error")
                            return {"error": f"API Error: {str(e)}"}, stats
                        except Exception as e:
                            print(f"❌ Error processing paper: {str(e)}")
                            stats["errors"] += 1
                    else:
                        print(f"\nPaper {i}/{len(papers_to_process)} has no DOI, skipping")
                    
        except Exception as e:
            print(f"❌ Error processing file {filename}: {str(e)}")
            stats["errors"] += 1
            return {"error": f"Error processing file {filename}: {str(e)}"}, stats
    
    print("\n=== Enrichment Process Complete ===")
    print(f"Total files processed: {stats['total_files']}")
    print(f"Total papers: {stats['total_papers']}")
    print(f"Papers with abstracts: {stats['papers_with_abstracts']}")
    print(f"New abstracts added: {stats['new_abstracts_added']}")
    print(f"Errors encountered: {stats['errors']}")
    
    return {"message": "Data enrichment complete"}, stats

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