# SHL Assessment Recommender

A Conversational Agent built with FastAPI and Google Gemini that recommends SHL Individual Test Solutions based on user requirements.

## Prerequisites
- Python 3.10+
- A Google Gemini API key (Free tier works perfectly)

## Setup Instructions

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Environment Variables**
   Set your Gemini API key in your terminal or create a `.env` file in the root directory:
   ```bash
   # Create a .env file (or export in your terminal)
   GEMINI_API_KEY="your_api_key_here"
   ```

3. **Data Collection (Optional but recommended)**
   The system needs the SHL catalog data to make recommendations. Run the scraper to get the latest data:
   ```bash
   # Install Playwright browsers (only needed once)
   playwright install chromium
   
   # Run the scraper
   python scraper/scrape_catalog.py
   ```
   *(Note: If you skip this step, the application will start but won't be able to find any assessments to recommend).*

4. **Run the API Server**
   Start the FastAPI server using uvicorn:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

## Testing the API

Once the server is running, it will be available at `http://localhost:8000`.

**1. Check Health**
```bash
curl http://localhost:8000/health
```

**2. Send a Chat Request**
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "I am hiring a mid-level Java developer and need an assessment"}
    ]
  }'
```

## Project Structure
- `/app` - The FastAPI service, conversational agent, prompts, and vector search logic
- `/scraper` - Scripts for scraping the SHL catalog (if needed)
- `/data` - Where the scraped `shl_catalog.json` and local FAISS index are stored
- `/tests` - Automated tests
- `/eval` - Evaluation scripts against trace data
