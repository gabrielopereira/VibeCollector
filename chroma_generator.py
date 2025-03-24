import json
import os
import chromadb
from chromadb.utils import embedding_functions
from typing import List, Dict

class ChromaGenerator:
    def __init__(self, data_dir: str = "fetcheddata"):
        """Initialize the ChromaDB generator with a data directory"""
        print("\nInitializing ChromaGenerator...")
        self.data_dir = data_dir
        print(f"Using data directory: {self.data_dir}")
        
        print("Setting up ChromaDB client...")
        # Ensure the chroma_db directory exists
        os.makedirs("./chroma_db", exist_ok=True)
        
        # Initialize the client with explicit settings
        self.client = chromadb.PersistentClient(
            path="./chroma_db",
            settings=chromadb.Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        print("Setting up embedding function...")
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
        # Delete existing collection if it exists
        try:
            print("Attempting to delete existing collection...")
            self.client.delete_collection("academic_papers")
            print("Successfully deleted existing collection 'academic_papers'")
        except Exception as e:
            print(f"No existing collection to delete: {str(e)}")
        
        # Create new collection
        print("Creating new collection...")
        self.collection = self.client.create_collection(
            name="academic_papers",
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"}
        )
        print("Successfully created new collection 'academic_papers'")

    def load_json_files(self) -> List[Dict]:
        """Load all JSON files from the data directory"""
        print("\nStarting to load JSON files...")
        all_papers = []
        
        # Ensure the data directory exists
        if not os.path.exists(self.data_dir):
            print(f"Error: Directory {self.data_dir} does not exist.")
            return all_papers
        
        # Load all JSON files in the directory
        json_files = [f for f in os.listdir(self.data_dir) if f.endswith('.json')]
        print(f"Found {len(json_files)} JSON files in {self.data_dir}")
        
        for filename in json_files:
            file_path = os.path.join(self.data_dir, filename)
            try:
                print(f"\nProcessing file: {filename}")
                with open(file_path, 'r', encoding='utf-8') as f:
                    papers = json.load(f)
                    if isinstance(papers, list):
                        print(f"Found {len(papers)} papers in {filename}")
                        all_papers.extend(papers)
                    else:
                        print(f"Found single paper in {filename}")
                        all_papers.append(papers)
            except Exception as e:
                print(f"Error loading {filename}: {str(e)}")
        
        print(f"\nTotal papers loaded: {len(all_papers)}")
        return all_papers

    def create_journal_summary(self, json_files: List[str]):
        """Create a summary of journals and their article counts"""
        print("\nCreating journal summary...")
        journal_summary = {}
        
        for filename in json_files:
            try:
                # Extract ISSN from filename (remove .json extension)
                issn = os.path.splitext(filename)[0]
                file_path = os.path.join(self.data_dir, filename)
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    papers = json.load(f)
                    article_count = len(papers) if isinstance(papers, list) else 1
                    
                    # Get journal title from first paper if available
                    journal_title = "Unknown"
                    if isinstance(papers, list) and papers:
                        journal_title = papers[0].get("metadata", {}).get("container_title", "Unknown")
                    elif isinstance(papers, dict):
                        journal_title = papers.get("metadata", {}).get("container_title", "Unknown")
                    
                    journal_summary[issn] = {
                        "title": journal_title,
                        "article_count": article_count
                    }
                    
            except Exception as e:
                print(f"Error processing {filename} for summary: {str(e)}")
                journal_summary[issn] = {
                    "title": "Error processing file",
                    "article_count": 0
                }
        
        # Save the summary to a JSON file in the chroma_db directory
        summary_file = os.path.join("./chroma_db", "journal_summary.json")
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(journal_summary, f, indent=2, ensure_ascii=False)
        
        print(f"\nJournal summary saved to {summary_file}")
        print(f"Total journals: {len(journal_summary)}")
        for issn, info in journal_summary.items():
            print(f"- {issn}: {info['article_count']} articles")

    def process_papers(self, papers: List[Dict]):
        """Process papers and add them to the ChromaDB collection"""
        print("\nStarting to process papers...")
        processed_count = 0
        
        for i, paper in enumerate(papers, 1):
            try:
                # Create a unique ID
                paper_id = paper.get("id", "")
                if not paper_id:
                    print(f"Warning: Paper {i} has no ID, skipping...")
                    continue
                
                # Extract title and abstract
                title = paper.get("title", "")
                abstract = paper.get("abstract", "")
                
                # Create document text for embedding
                document_text = title
                if abstract:
                    document_text += " " + abstract
                
                # Create metadata with safe defaults for None values
                metadata = {
                    "title": title or "",
                    "abstract": abstract or "",
                    "authors": ", ".join(paper.get("metadata", {}).get("authors", [])),
                    "journal": paper.get("metadata", {}).get("container_title", "") or "",
                    "year": str(paper.get("metadata", {}).get("published", [])[0] if paper.get("metadata", {}).get("published") else ""),
                    "volume": paper.get("metadata", {}).get("volume", "") or "",
                    "issue": paper.get("metadata", {}).get("issue", "") or "",
                    "doi": paper.get("metadata", {}).get("doi", "") or "",
                    "publisher": paper.get("metadata", {}).get("publisher", "") or "",
                    "url": paper.get("metadata", {}).get("url", "") or "",
                    "type": paper.get("metadata", {}).get("type", "") or "",
                    "language": paper.get("metadata", {}).get("language", "") or "",
                    "references_count": str(paper.get("metadata", {}).get("references_count", 0)),
                    "is_referenced_by_count": str(paper.get("metadata", {}).get("is_referenced_by_count", 0))
                }
                
                # Add the document to the collection
                self.collection.add(
                    documents=[document_text],
                    metadatas=[metadata],
                    ids=[paper_id]
                )
                processed_count += 1
                
                if i % 100 == 0:
                    print(f"Processed {i} papers...")
                    
            except Exception as e:
                print(f"Error processing paper {i}: {str(e)}")
                print(f"Paper ID: {paper.get('id', 'unknown')}, Title: {paper.get('title', 'unknown')}")
                continue
        
        print(f"\nSuccessfully processed {processed_count} out of {len(papers)} papers")

    def generate(self):
        """Main method to generate the ChromaDB collection"""
        print("\n=== Starting ChromaDB Generation ===")
        print("Loading papers from JSON files...")
        
        # Get list of JSON files first
        json_files = [f for f in os.listdir(self.data_dir) if f.endswith('.json')]
        
        # Create journal summary
        self.create_journal_summary(json_files)
        
        # Load and process papers
        papers = self.load_json_files()
        
        if not papers:
            print("No papers found to process.")
            return
        
        print(f"\nProcessing {len(papers)} papers...")
        self.process_papers(papers)
        print("\n=== ChromaDB Generation Complete ===")

if __name__ == "__main__":
    generator = ChromaGenerator()
    generator.generate()