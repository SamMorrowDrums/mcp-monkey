import subprocess
import tempfile
import os

class MCPServer:
    def __init__(self, url, selenium_manager):
        self.url = url
        self.selenium_manager = selenium_manager
        self.connect()
    
    def connect(self):
        """Connect to the MCP server"""
        try:
            self.selenium_manager.navigate_to(self.url)
            # Wait for the main page to load
            self.selenium_manager.wait_for_element("body")
        except Exception as e:
            raise Exception(f"Failed to connect to server: {str(e)}")
    
    def execute_javascript(self, code):
        """Execute JavaScript code in the browser context"""
        try:
            return self.selenium_manager.execute_javascript(code)
        except Exception as e:
            raise Exception(f"Failed to execute JavaScript: {str(e)}")
    
    def execute_python(self, code):
        """Execute Python code in a temporary file"""
        try:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
                temp_file.write(code)
                temp_file_path = temp_file.name
            
            # Execute the Python code
            result = subprocess.run(
                ['python', temp_file_path],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Clean up
            os.unlink(temp_file_path)
            
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise Exception(f"Python execution failed: {e.stderr}")
        except Exception as e:
            raise Exception(f"Failed to execute Python code: {str(e)}")
    
    def __str__(self):
        return f"MCP Server ({self.url})" 