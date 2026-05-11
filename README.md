# Flight & Temperature Chat Application

A Streamlit frontend application for querying flight information and weather data with an AI chatbot interface, backed by a FastAPI server.

## Prerequisites

- Python 3.10 or higher
- pip (Python package manager)

## Installation

### 1. Create a Virtual Environment

```bash
python -m venv .venv
```

Activate the virtual environment:

**On Windows (Command Prompt):**
```bash
.venv\Scripts\activate
```

**On Windows (PowerShell):**
```bash
.venv\Scripts\Activate.ps1
```

**On macOS/Linux:**
```bash
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

## Running the Application

The application consists of two components that need to run simultaneously:

### Backend Server (FastAPI)

In a terminal/command prompt, run:

```bash
python main.py
```

The backend API will start on `http://127.0.0.1:8000`

### Frontend Application (Streamlit)

In a separate terminal/command prompt, run:

**Option 1 - Using the provided batch script (Windows only):**
```bash
run_streamlit.cmd
```

**Option 2 - Direct command:**
```bash
streamlit run streamlit_app.py
```

The Streamlit frontend will open in your browser at `http://localhost:8501`

## Complete Setup for Client Demo

### Step-by-step execution:

1. **Terminal 1 - Start Backend:**
   ```bash
   python main.py
   ```
   Wait for the message confirming the server is running on port 8000

2. **Terminal 2 - Start Frontend:**
   ```bash
   streamlit run streamlit_app.py
   ```
   The application will automatically open in your default browser

3. **Access the Application:**
   - Frontend UI: `http://localhost:8501`
   - Backend API: `http://127.0.0.1:8000` (for API requests)

## Features

- **Flight Information**: Query flight status and details
- **Weather Data**: Get current temperature and weather information
- **AI Chatbot**: Natural language interface for flight and weather queries
- **Chat History**: Persistent conversation tracking
- **Theme Support**: Light and Dark mode themes

## Troubleshooting

**Port 8000 already in use:**
```bash
# Find process using port 8000 and terminate it, or modify FastAPI startup port in main.py
```

**Streamlit connection error:**
- Ensure the backend server is running first
- Verify backend is accessible at `http://127.0.0.1:8000`

**Import errors:**
- Confirm virtual environment is activated
- Run `pip install -r requirements.txt` again

## Project Structure

```
Flight/
├── main.py                 # FastAPI backend entry point
├── streamlit_app.py        # Streamlit frontend entry point
├── requirements.txt        # Python dependencies
├── run_streamlit.cmd       # Windows batch script to run Streamlit
├── app/
│   ├── main.py            # FastAPI application setup
│   ├── core/              # Core utilities (config, logging, exceptions)
│   ├── mcp/               # Model Context Protocol implementation
│   ├── models/            # Data models (Flight, Weather, Chat)
│   ├── routes/            # API routes (chat, flight, weather)
│   └── services/          # Business logic services
```

## Development Notes

- Backend runs on FastAPI with Uvicorn
- Frontend is built with Streamlit for rapid UI development
- Communication between frontend and backend uses HTTP requests
- Backend URL is configured in `streamlit_app.py` as `BACKEND_URL = "http://127.0.0.1:8000"`

## Demo Tips

- The application features a chat interface for querying flight and weather information
- Use natural language queries like "What's the weather in London?" or "Show me flights to NYC"
- The chatbot will process requests and return relevant information
- Theme can be toggled between Light and Dark modes using the interface
