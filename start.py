"""
Start Script for SSO Identity Management System
Starts the FastAPI backend server with auto-reload and automatically opens the frontend
"""

import uvicorn
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project root to sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

if __name__ == "__main__":
    # Get port from environment or use default
    port = int(os.getenv("BACKEND_PORT", 8000))
    backend_url = os.getenv("BACKEND_URL", f"http://localhost:{port}")
    
    print("=" * 60)
    print("🔐 SSO Identity Management System")
    print("=" * 60)
    print(f"Starting backend server on {backend_url}")
    print("Frontend will open automatically in your browser...")
    print("=" * 60)
    print("\nPress CTRL+C to stop the server\n")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
