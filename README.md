# Caution

_This is an experiment at vibe coding with Cursor initially, just to see how it fares. It is not recommended to try, or to collaborate on or use now and quite possibly ever._


# MCP Monkey

A Python GUI application for dynamically creating and managing MCP servers using Selenium and headless Chrome. This tool allows users to create servers and add custom Python/JavaScript tools for automation.

## Features
- Dynamic MCP server creation
- Headless Chrome automation
- Custom Python code execution
- JavaScript injection capabilities
- Modern PyQt6-based GUI

## Setup
1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Linux/Mac
# or
.\venv\Scripts\activate  # On Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python src/main.py
```

## Project Structure
- `src/` - Main application code
  - `main.py` - Application entry point
  - `gui/` - GUI components
  - `server/` - Server management code
  - `automation/` - Selenium and automation utilities
  - `tools/` - Custom tools and scripts

## License
See LICENSE file for details.
