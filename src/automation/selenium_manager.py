from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import subprocess
import stat
import tempfile
import sys
from io import StringIO
from contextlib import redirect_stdout

class SeleniumManager:
    def __init__(self):
        self.driver = None
        self.setup_driver()
    
    def find_chrome_binary(self):
        """Find the Chrome binary location"""
        chrome_paths = [
            "/usr/bin/google-chrome-stable",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser"
        ]
        
        for path in chrome_paths:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
                
        # If no binary found in standard locations, try using 'which'
        try:
            result = subprocess.run(['which', 'google-chrome-stable'], 
                                 capture_output=True, text=True, check=True)
            if result.stdout.strip():
                return result.stdout.strip()
        except subprocess.CalledProcessError:
            pass
            
        raise Exception("Could not find Chrome binary. Please ensure Chrome or Chromium is installed.")
    
    def ensure_driver_permissions(self, driver_path):
        """Ensure the ChromeDriver has correct permissions"""
        try:
            # Get current permissions
            st = os.stat(driver_path)
            # Add executable permissions (equivalent to chmod +x)
            os.chmod(driver_path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            print(f"Set executable permissions for ChromeDriver at: {driver_path}")
        except Exception as e:
            print(f"Warning: Could not set permissions for ChromeDriver: {str(e)}")
    
    def setup_driver(self):
        """Initialize the Chrome WebDriver with headless options"""
        try:
            chrome_binary = self.find_chrome_binary()
            print(f"Using Chrome binary at: {chrome_binary}")
            
            chrome_options = Options()
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.binary_location = chrome_binary
            
            # Set environment variable for ChromeDriver
            os.environ['CHROME_PATH'] = chrome_binary
            
            # Get the ChromeDriver path
            driver_path = ChromeDriverManager().install()
            if os.path.isfile(driver_path):
                driver_dir = os.path.dirname(driver_path)
                actual_driver = os.path.join(driver_dir, 'chromedriver')
                if os.path.isfile(actual_driver):
                    driver_path = actual_driver
            
            # Ensure driver has correct permissions
            self.ensure_driver_permissions(driver_path)
            
            print(f"Using ChromeDriver at: {driver_path}")
            service = Service(executable_path=driver_path)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
        except Exception as e:
            print(f"Error setting up Chrome driver: {str(e)}")
            raise
    
    def navigate_to(self, url):
        """Navigate to a specific URL"""
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        self.driver.get(url)
    
    def execute_javascript(self, script):
        """Execute JavaScript code in the browser"""
        return self.driver.execute_script(script)
    
    def execute_python(self, code, args=None):
        """Execute Python code with access to the WebDriver and capture stdout"""
        # Create a temporary Python file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as temp_file:
            # Add imports and setup
            setup_code = """
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# The WebDriver instance will be injected as 'driver'
"""
            # Write the setup code and user's code
            temp_file.write(setup_code)
            temp_file.write("\n" + code)
            temp_file_path = temp_file.name
        
        try:
            # Create a namespace for execution
            namespace = {
                'driver': self.driver,
                'args': args or {}
            }
            
            # Capture stdout during execution
            stdout = StringIO()
            with redirect_stdout(stdout):
                # Execute the code with the namespace
                with open(temp_file_path, 'r') as f:
                    exec(f.read(), namespace)
            
            # Get the captured output
            output = stdout.getvalue()
            
            # Get the result if one was specified
            result = namespace.get('result', None)
            
            return {
                'output': output,
                'result': result
            }
            
        finally:
            # Clean up
            os.unlink(temp_file_path)
    
    def wait_for_element(self, selector, timeout=10):
        """Wait for an element to be present on the page"""
        wait = WebDriverWait(self.driver, timeout)
        return wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
    
    def get_page_source(self):
        """Get the current page source"""
        return self.driver.page_source
    
    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def __del__(self):
        """Ensure the browser is closed when the object is destroyed"""
        self.close() 