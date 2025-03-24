import requests
import time
import json
import uuid
from typing import List, Dict, Generator

class CrossrefJournalFetcher:
    BASE_URL = "https://api.crossref.org/journals"
    ROWS_PER_PAGE = 1000  # Crossref's maximum items per page
    
    def __init__(self, email: str):
        """Initialize with your email for polite API usage"""
        self.headers = {
            'User-Agent': f'PythonScript/1.0 (mailto:{email})'
        }

    def get_journal_works(self, issn: str) -> Generator[Dict, None, None]:
        """
        Generator that yields all works from a specific journal using its ISSN.
        Handles pagination automatically.
        """
        cursor = '*'  # Starting cursor for pagination
        
        while True:
            params = {
                'rows': self.ROWS_PER_PAGE,
                'cursor': cursor
            }
            
            url = f"{self.BASE_URL}/{issn}/works"
            
            try:
                response = requests.get(url, params=params, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                
                # Get the items from this page
                items = data['message']['items']
                if not items:
                    break  # No more items to fetch
                
                # Yield each item individually
                for item in items:
                    yield item
                
                # Get next cursor for pagination
                next_cursor = data['message'].get('next-cursor')
                if not next_cursor:
                    break  # No more pages
                
                cursor = next_cursor
                
                # Be nice to the API - add a small delay between requests
                time.sleep(0.5)
                
            except requests.exceptions.RequestException as e:
                print(f"Error fetching data: {e}")
                break

    def transform_work(self, work: Dict) -> Dict:
        """Transform the work data into the desired format"""
        return {
            "id": str(uuid.uuid4()),
            "title": work.get('title', [''])[0] if work.get('title') else '',
            "abstract": work.get('abstract', ''),
            "metadata": {
                "doi": work.get('DOI', ''),
                "type": work.get('type', ''),
                "published": work.get('published-print', {}).get('date-parts', [[]])[0],
                "authors": [author.get('given', '') + ' ' + author.get('family', '')
                          for author in work.get('author', [])],
                "url": work.get('URL', ''),
                "publisher": work.get('publisher', ''),
                "container_title": work.get('container-title', [''])[0] if work.get('container-title') else '',
                "volume": work.get('volume', ''),
                "issue": work.get('issue', ''),
                "page": work.get('page', ''),
                "subject": work.get('subject', []),
                "language": work.get('language', ''),
                "issn": work.get('ISSN', []),
                "isbn": work.get('ISBN', []),
                "references_count": work.get('references-count', 0),
                "is_referenced_by_count": work.get('is-referenced-by-count', 0),
                "score": work.get('score', 0)
            }
        }

    def save_to_file(self, issn: str, filename: str):
        """
        Save all works from a journal to a JSON file.
        
        Args:
            issn (str): The ISSN of the journal
            filename (str): The path where to save the JSON file
        """
        transformed_works = []
        total_works = 0
        
        for work in self.get_journal_works(issn):
            transformed_work = self.transform_work(work)
            transformed_works.append(transformed_work)
            total_works += 1
            
            if total_works % 1000 == 0:
                print(f"Processed {total_works} works...")
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(transformed_works, f, indent=2, ensure_ascii=False)
        
        print(f"\nTotal works processed: {total_works}")
        print(f"Data saved to {filename}")

# Example usage
if __name__ == "__main__":
    # Initialize with your email
    fetcher = CrossrefJournalFetcher("your.email@example.com")
    
    # Example ISSN for a journal
    journal_issn = "2053-9517"  # This is the ISSN 
    
    # Save all works to a JSON file
    fetcher.save_to_file(journal_issn, "output.json") 