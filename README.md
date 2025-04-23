# VibeCollector 🎯

VibeSearch is a vibe-y search engine for academic articles. It enables you to search using vector search, as well as as 'traditional' and keyword-based search. The idea is that it works only in some journals from the New Media field (list below). It's a prototype.

VibeCollector allows to generate your own database for a local [VibeSearch installation](https://github.com/gabrielopereira/VibeSearch).

## What's This? 🤔

VibeCollector does what the name says: it fetches data on papers from academic journals. This data can then be inputted on VibeSearch.

## Quick Start 🚀

1. Install the requirements:
```bash
pip install -r requirements.txt
```

2. Run the web app:
```bash
python app.py
```

3. Open your browser to `http://localhost:5000` (or whatever your terminal says)

## How It Works 🧠

Here's how to collect those vibes:

1. Enter a journal's ISSN and click "Fetch Data" to collect all its papers. Each journal's data will be saved in its own .txt file. You can add as many journals as you like! 🗂️

2. Got all your journals? Hit "Enrich with Abstracts" to fill in any missing paper abstracts. This makes the search way more powerful! 📝

3. Finally, click "Generate ChromaDB" to create your vector database. The generated folder (/chroma_db) can be copied into VibeSearch: it will power the semantic search in your local installation. ✨


## Tech Stack 💻

- Flask for the simple web interface
- ChromaDB for generating a vector database
- Crossref API for fetching paper metadata from journals
- Semantic Scholar API for enriching papers with missing abstracts

### Note on the Data 📊
  
- Some articles may not have abstracts 
- Abstract availability depends on journal policies and time periods
- Not all journals have year of the pub in CrossRef 

## License 📄

Just do whatever, it's just vibes.