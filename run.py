"""
Application entry point.
Automatically detects and runs the appropriate application based on pattern configuration.
Supports FastAPI (Sync), FastMCP (Sync), and Azure Functions (Async/Hybrid).
"""

import os
import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))
os.environ['PYTHONPATH'] = str(src_path)

# Detect which framework to run based on available modules
def detect_framework():
    """
    Detect which framework module is available in src/
   
    Returns:
        str: 'fastapi', 'fastmcp', or 'azure_functions'
    """
    src = Path(__file__).parent / "src"
   
    # Check for available application directories
    if (src / "servicenowautomation_api").exists():
        return "fastapi"
    elif (src / "servicenowautomation_mcp").exists():
        return "fastmcp"
    elif (src / "servicenowautomation_fa").exists():
        return "azure_functions"
    else:
        return None


if __name__ == "__main__":
    framework = detect_framework()

    if framework == "fastapi":
        # Run FastAPI application
        import uvicorn
        from servicenowautomation_api.main import app

        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            reload=False,  # Disable reload to avoid path issues
            log_level="info"
        )
    elif framework == "fastmcp":
        # Run FastMCP application
        from servicenowautomation_mcp.config import settings
        from servicenowautomation_mcp.main import mcp

        mcp.run(
            transport=settings.mcp_transport,
            host=settings.mcp_host,
            port=settings.mcp_port,
        )
    elif framework == "azure_functions":
        # Run Azure Functions
        print("Azure Functions runtime detected.")
        print("Run with: func start")
        sys.exit(1)
    else:
        print("ERROR: Could not detect application framework.")
        print("Expected application directories not found in src/")
        sys.exit(1)