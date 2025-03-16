from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QListWidget, QTextEdit, QLabel,
    QInputDialog, QMessageBox, QDialog, QLineEdit,
    QComboBox, QScrollArea, QFrame, QSpinBox,
    QDialogButtonBox, QTabWidget, QPlainTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QTextCursor
from automation.selenium_manager import SeleniumManager
from mcp.server.fastmcp import FastMCP
from mcp.types import Tool
import json
import os
import asyncio
import threading
import types
from functools import partial

class OutputDialog(QDialog):
    """Dialog to display code execution output"""
    def __init__(self, title, output, result=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(self)
        
        # Output section
        if output:
            output_group = QWidget()
            output_layout = QVBoxLayout(output_group)
            output_layout.addWidget(QLabel("Output:"))
            output_text = QPlainTextEdit()
            output_text.setPlainText(output)
            output_text.setReadOnly(True)
            output_layout.addWidget(output_text)
            layout.addWidget(output_group)
        
        # Result section
        if result is not None:
            result_group = QWidget()
            result_layout = QVBoxLayout(result_group)
            result_layout.addWidget(QLabel("Return Value:"))
            result_text = QPlainTextEdit()
            result_text.setPlainText(str(result))
            result_text.setReadOnly(True)
            result_layout.addWidget(result_text)
            layout.addWidget(result_group)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

class PythonREPL(QPlainTextEdit):
    """Interactive Python REPL widget"""
    def __init__(self, selenium_manager=None, parent=None):
        super().__init__(parent)
        self.selenium_manager = selenium_manager
        self.history = []
        self.history_index = 0
        self.current_line = ""
        self.prompt = ">>> "
        
        # Set read-only until prompt
        self.setReadOnly(True)
        
        # Initialize REPL
        self.clear()
        self.write_prompt()
        self.setReadOnly(False)
    
    def clear(self):
        """Clear the REPL"""
        super().clear()
        self.moveCursor(QTextCursor.MoveOperation.End)
    
    def write_prompt(self):
        """Write the prompt at the current position"""
        self.insertPlainText(self.prompt)
        self.moveCursor(QTextCursor.MoveOperation.End)
    
    def write_output(self, text):
        """Write output text"""
        self.insertPlainText(str(text) + "\n")
        self.moveCursor(QTextCursor.MoveOperation.End)
    
    def get_current_line(self):
        """Get the current input line"""
        doc = self.document()
        current_block = doc.findBlockByLineNumber(doc.lineCount() - 1)
        return current_block.text()[len(self.prompt):]
    
    def keyPressEvent(self, event):
        """Handle key press events"""
        cursor = self.textCursor()
        
        # Only allow editing on the current line after the prompt
        if cursor.block().text()[:len(self.prompt)] == self.prompt:
            cursor_in_prompt = cursor.positionInBlock() < len(self.prompt)
            
            if event.key() == Qt.Key.Key_Return:
                # Execute the current line
                line = self.get_current_line()
                if line.strip():
                    self.history.append(line)
                    self.history_index = len(self.history)
                    self.execute_line(line)
                self.insertPlainText("\n")
                self.write_prompt()
                return
                
            elif event.key() == Qt.Key.Key_Up:
                # Previous history item
                if self.history and self.history_index > 0:
                    self.history_index -= 1
                    self.replace_current_line(self.history[self.history_index])
                return
                
            elif event.key() == Qt.Key.Key_Down:
                # Next history item
                if self.history_index < len(self.history) - 1:
                    self.history_index += 1
                    self.replace_current_line(self.history[self.history_index])
                elif self.history_index == len(self.history) - 1:
                    self.history_index = len(self.history)
                    self.replace_current_line("")
                return
                
            elif cursor_in_prompt:
                # Prevent editing the prompt
                if event.key() not in (Qt.Key.Key_Right, Qt.Key.Key_End):
                    return
            
            super().keyPressEvent(event)
        
    def replace_current_line(self, new_text):
        """Replace the current line with new text"""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.movePosition(
            QTextCursor.MoveOperation.StartOfLine,
            QTextCursor.MoveMode.KeepAnchor
        )
        cursor.insertText(self.prompt + new_text)
        self.moveCursor(QTextCursor.MoveOperation.End)
    
    def execute_line(self, code):
        """Execute a line of Python code"""
        try:
            result = self.selenium_manager.execute_python(code)
            if result['output'] or result['result'] is not None:
                self.insertPlainText("\n")  # Add newline before any output
            if result['output']:
                self.write_output(result['output'].strip())
            if result['result'] is not None:
                self.write_output(repr(result['result']))
        except Exception as e:
            self.insertPlainText("\n")  # Add newline before error message
            self.write_output(f"Error: {str(e)}")

class ToolCell(QFrame):
    """A cell that represents a single operation in a tool"""
    def __init__(self, parent=None, selenium_manager=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.selenium_manager = selenium_manager
        self.repl = None
        
        layout = QVBoxLayout(self)
        
        # Cell type selection
        type_layout = QHBoxLayout()
        self.cell_type = QComboBox()
        self.cell_type.addItems(["Load Page", "Execute Python", "Execute JavaScript", "Return Data", "Python REPL"])
        self.cell_type.currentTextChanged.connect(self.on_type_changed)
        type_layout.addWidget(QLabel("Cell Type:"))
        type_layout.addWidget(self.cell_type)
        
        # Order control
        order_layout = QHBoxLayout()
        self.order = QSpinBox()
        order_layout.addWidget(QLabel("Order:"))
        order_layout.addWidget(self.order)
        
        # Code editor
        self.code_editor = QPlainTextEdit()
        self.code_editor.setPlaceholderText("Enter code here...")
        
        # Add all components
        layout.addLayout(type_layout)
        layout.addLayout(order_layout)
        layout.addWidget(self.code_editor)
        
        # Control buttons
        button_layout = QHBoxLayout()
        self.run_btn = QPushButton("Run Cell")
        self.delete_btn = QPushButton("Delete Cell")
        self.run_btn.clicked.connect(self.run_cell)
        button_layout.addWidget(self.run_btn)
        button_layout.addWidget(self.delete_btn)
        layout.addLayout(button_layout)
        
        # Store layout for later reference
        self.layout = layout
        
        # Set initial placeholder
        self.on_type_changed(self.cell_type.currentText())
    
    def on_type_changed(self, cell_type):
        """Update the placeholder text based on cell type"""
        # Remove existing editor widget
        if self.repl:
            self.layout.removeWidget(self.repl)
            self.repl.deleteLater()
            self.repl = None
            self.code_editor.show()
        
        if cell_type == "Python REPL":
            # Create and add REPL widget
            self.code_editor.hide()
            self.repl = PythonREPL(selenium_manager=self.selenium_manager)
            self.layout.insertWidget(2, self.repl)  # Insert at the same position as code_editor
            self.run_btn.setEnabled(False)  # Disable run button for REPL
        else:
            self.run_btn.setEnabled(True)
            if cell_type == "Load Page":
                self.code_editor.setPlaceholderText("Enter URL to load")
            elif cell_type == "Execute Python":
                self.code_editor.setPlaceholderText("Enter Python code\nAvailable variables:\n- driver: Selenium WebDriver instance\n- args: Dictionary of tool arguments")
            elif cell_type == "Execute JavaScript":
                self.code_editor.setPlaceholderText("Enter JavaScript code to execute in the browser")
            else:  # Return Data
                self.code_editor.setPlaceholderText("Enter Python code to return data\nMust include a 'return' statement")
    
    def run_cell(self):
        """Execute the cell's code"""
        if not self.selenium_manager:
            QMessageBox.warning(self, "Error", "Selenium manager not initialized")
            return
            
        try:
            cell_type = self.cell_type.currentText()
            code = self.code_editor.toPlainText().strip()
            
            if not code:
                QMessageBox.warning(self, "Error", "Please enter code/URL first")
                return
            
            if cell_type == "Load Page":
                self.selenium_manager.navigate_to(code)
                dialog = OutputDialog("Page Loaded", f"Successfully loaded: {code}")
                dialog.exec()
                
            elif cell_type == "Execute JavaScript":
                result = self.selenium_manager.execute_javascript(code)
                dialog = OutputDialog("JavaScript Result", "", result)
                dialog.exec()
                
            elif cell_type in ["Execute Python", "Return Data"]:
                result = self.selenium_manager.execute_python(code)
                dialog = OutputDialog(
                    "Python Execution Result",
                    result['output'],
                    result['result']
                )
                dialog.exec()
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to execute cell: {str(e)}")

class ToolDialog(QDialog):
    """Dialog for creating/editing a tool"""
    def __init__(self, parent=None, tool_data=None, selenium_manager=None):
        super().__init__(parent)
        self.setWindowTitle("Tool Configuration")
        self.setMinimumWidth(600)
        self.selenium_manager = selenium_manager
        
        layout = QVBoxLayout(self)
        
        # Tool name
        name_layout = QHBoxLayout()
        self.tool_name = QLineEdit()
        name_layout.addWidget(QLabel("Tool Name:"))
        name_layout.addWidget(self.tool_name)
        layout.addLayout(name_layout)
        
        # Arguments
        args_layout = QHBoxLayout()
        self.args_edit = QLineEdit()
        self.args_edit.setPlaceholderText("arg1,arg2,arg3")
        args_layout.addWidget(QLabel("Required Arguments:"))
        args_layout.addWidget(self.args_edit)
        layout.addLayout(args_layout)
        
        # Cells
        cells_label = QLabel("Execution Cells:")
        layout.addWidget(cells_label)
        
        # Scrollable area for cells
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.cells_widget = QWidget()
        self.cells_layout = QVBoxLayout(self.cells_widget)
        scroll.setWidget(self.cells_widget)
        layout.addWidget(scroll)
        
        # Add cell button
        add_cell_btn = QPushButton("Add Cell")
        add_cell_btn.clicked.connect(self.add_cell)
        layout.addWidget(add_cell_btn)
        
        # Dialog buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        
        # Load existing data if provided
        if tool_data:
            self.load_tool_data(tool_data)
    
    def add_cell(self):
        cell = ToolCell(selenium_manager=self.selenium_manager)
        cell.order.setValue(self.cells_layout.count())
        cell.delete_btn.clicked.connect(lambda: self.delete_cell(cell))
        self.cells_layout.addWidget(cell)
    
    def delete_cell(self, cell):
        cell.deleteLater()
        self.reorder_cells()
    
    def reorder_cells(self):
        """Update the order numbers of all cells"""
        for i in range(self.cells_layout.count()):
            cell = self.cells_layout.itemAt(i).widget()
            if isinstance(cell, ToolCell):
                cell.order.setValue(i)
    
    def load_tool_data(self, data):
        """Load existing tool data into the dialog"""
        self.tool_name.setText(data.get('name', ''))
        self.args_edit.setText(','.join(data.get('args', [])))
        
        for cell_data in data.get('cells', []):
            cell = ToolCell(selenium_manager=self.selenium_manager)
            cell.cell_type.setCurrentText(cell_data.get('type', ''))
            cell.order.setValue(cell_data.get('order', 0))
            cell.code_editor.setPlainText(cell_data.get('code', ''))
            cell.delete_btn.clicked.connect(lambda: self.delete_cell(cell))
            self.cells_layout.addWidget(cell)
    
    def validate_and_accept(self):
        """Validate the tool configuration before accepting"""
        # Check for REPL cells
        for i in range(self.cells_layout.count()):
            cell = self.cells_layout.itemAt(i).widget()
            if isinstance(cell, ToolCell) and cell.cell_type.currentText() == "Python REPL":
                QMessageBox.warning(
                    self,
                    "Invalid Configuration",
                    "Tools containing Python REPL cells cannot be saved. Please remove or change the REPL cells before saving."
                )
                return
        
        self.accept()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MCP Monkey")
        self.setMinimumSize(1200, 800)
        
        # Initialize managers
        self.selenium_manager = SeleniumManager()
        self.current_server = None
        self.mcp_server = None
        self.server_thread = None
        self.is_server_running = False
        
        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)
        
        # Left panel - Server List
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        server_label = QLabel("MCP Servers")
        self.server_list = QListWidget()
        self.server_list.itemSelectionChanged.connect(self.load_server)
        
        server_buttons = QHBoxLayout()
        new_server_btn = QPushButton("New Server")
        open_server_btn = QPushButton("Open Server")
        self.server_control_btn = QPushButton("Start Server")
        new_server_btn.clicked.connect(self.create_server)
        open_server_btn.clicked.connect(self.open_server)
        self.server_control_btn.clicked.connect(self.toggle_server)
        
        server_buttons.addWidget(new_server_btn)
        server_buttons.addWidget(open_server_btn)
        server_buttons.addWidget(self.server_control_btn)
        
        left_layout.addWidget(server_label)
        left_layout.addWidget(self.server_list)
        left_layout.addLayout(server_buttons)
        
        # Right panel - Tool Management
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Tool list and controls
        tool_header = QHBoxLayout()
        tool_header.addWidget(QLabel("Server Tools"))
        
        tool_buttons = QHBoxLayout()
        add_tool_btn = QPushButton("Add Tool")
        delete_tool_btn = QPushButton("Delete Tool")
        add_tool_btn.clicked.connect(self.add_tool)
        delete_tool_btn.clicked.connect(self.delete_tool)
        tool_buttons.addWidget(add_tool_btn)
        tool_buttons.addWidget(delete_tool_btn)
        tool_header.addLayout(tool_buttons)
        
        self.tool_list = QListWidget()
        self.tool_list.itemDoubleClicked.connect(self.edit_tool)
        
        right_layout.addLayout(tool_header)
        right_layout.addWidget(self.tool_list)
        
        # Add panels to main layout
        layout.addWidget(left_panel, 1)
        layout.addWidget(right_panel, 2)
        
        # Load existing servers
        self.load_servers()
    
    def create_server(self):
        """Create a new server configuration"""
        name, ok = QInputDialog.getText(
            self, "Create Server", "Enter server name:"
        )
        if ok and name:
            server_dir = os.path.join("servers", name)
            os.makedirs(server_dir, exist_ok=True)
            
            # Create empty server config
            config = {
                "name": name,
                "tools": []
            }
            
            with open(os.path.join(server_dir, "config.json"), "w") as f:
                json.dump(config, f, indent=2)
            
            self.load_servers()
            
            # Select the new server
            for i in range(self.server_list.count()):
                if self.server_list.item(i).text() == name:
                    self.server_list.setCurrentRow(i)
                    break
    
    def open_server(self):
        """Open an existing server configuration"""
        # TODO: Implement file dialog to open server config
        pass
    
    def load_servers(self):
        """Load all available servers"""
        self.server_list.clear()
        if os.path.exists("servers"):
            for server in os.listdir("servers"):
                if os.path.isdir(os.path.join("servers", server)):
                    self.server_list.addItem(server)
    
    def load_server(self):
        """Load the selected server's tools"""
        self.tool_list.clear()
        current_item = self.server_list.currentItem()
        if current_item:
            server_name = current_item.text()
            config_path = os.path.join("servers", server_name, "config.json")
            
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    config = json.load(f)
                    self.current_server = config
                    
                    for tool in config.get("tools", []):
                        self.tool_list.addItem(tool["name"])
    
    def add_tool(self):
        """Add a new tool to the current server"""
        if not self.current_server:
            QMessageBox.warning(self, "Warning", "Please select a server first")
            return
        
        dialog = ToolDialog(self, selenium_manager=self.selenium_manager)
        if dialog.exec():
            # Get tool configuration from dialog
            tool_data = self.get_tool_data_from_dialog(dialog)
            
            # Add to server config
            self.current_server["tools"].append(tool_data)
            self.save_current_server()
            
            # Update tool list
            self.tool_list.addItem(tool_data["name"])
    
    def edit_tool(self, item):
        """Edit an existing tool"""
        if not self.current_server:
            return
        
        # Find tool data
        tool_data = next(
            (tool for tool in self.current_server["tools"] if tool["name"] == item.text()),
            None
        )
        
        if tool_data:
            dialog = ToolDialog(self, tool_data, selenium_manager=self.selenium_manager)
            if dialog.exec():
                # Update tool configuration
                new_tool_data = self.get_tool_data_from_dialog(dialog)
                
                # Replace old tool data
                self.current_server["tools"] = [
                    new_tool_data if tool["name"] == item.text() else tool
                    for tool in self.current_server["tools"]
                ]
                
                self.save_current_server()
                self.load_server()  # Reload tools
    
    def get_tool_data_from_dialog(self, dialog):
        """Extract tool data from dialog"""
        cells = []
        for i in range(dialog.cells_layout.count()):
            cell = dialog.cells_layout.itemAt(i).widget()
            if isinstance(cell, ToolCell):
                cells.append({
                    "type": cell.cell_type.currentText(),
                    "order": cell.order.value(),
                    "code": cell.code_editor.toPlainText()
                })
        
        return {
            "name": dialog.tool_name.text(),
            "args": [arg.strip() for arg in dialog.args_edit.text().split(",") if arg.strip()],
            "cells": sorted(cells, key=lambda x: x["order"])
        }
    
    def save_current_server(self):
        """Save the current server configuration"""
        if self.current_server:
            server_dir = os.path.join("servers", self.current_server["name"])
            os.makedirs(server_dir, exist_ok=True)
            
            with open(os.path.join(server_dir, "config.json"), "w") as f:
                json.dump(self.current_server, f, indent=2)
    
    def delete_tool(self):
        """Delete the selected tool"""
        if not self.current_server:
            QMessageBox.warning(self, "Warning", "Please select a server first")
            return
        
        current_item = self.tool_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Warning", "Please select a tool to delete")
            return
        
        tool_name = current_item.text()
        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete the tool '{tool_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            # Remove from server config
            self.current_server["tools"] = [
                tool for tool in self.current_server["tools"]
                if tool["name"] != tool_name
            ]
            
            # Save changes
            self.save_current_server()
            
            # Update tool list
            self.load_server()  # Reload tools
    
    def toggle_server(self):
        """Start or stop the MCP server"""
        if not self.current_server:
            QMessageBox.warning(self, "Warning", "Please select a server first")
            return
        
        if not self.is_server_running:
            self.start_server()
        else:
            self.stop_server()
    
    def start_server(self):
        """Start the MCP server and register tools"""
        try:
            # Check if there are any tools to register
            if not self.current_server["tools"]:
                QMessageBox.warning(self, "Warning", "No tools available to register. Please create at least one tool before starting the server.")
                return
            
            # Create MCP server
            self.mcp_server = FastMCP(self.current_server["name"])
            
            # Register tools
            for tool in self.current_server["tools"]:
                mcp_tool = self.create_mcp_tool(tool)
                self.mcp_server.add_tool(mcp_tool)
            
            # Start server in a separate thread
            self.server_thread = threading.Thread(target=self._run_server)
            self.server_thread.daemon = True
            self.server_thread.start()
            
            self.is_server_running = True
            self.server_control_btn.setText("Stop Server")
            QMessageBox.information(self, "Success", "Server started successfully")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start server: {str(e)}")
    
    def stop_server(self):
        """Stop the MCP server"""
        try:
            if self.mcp_server:
                # Stop the server
                asyncio.run(self.mcp_server.stop())
                self.mcp_server = None
            
            if self.server_thread:
                self.server_thread.join(timeout=5)
                self.server_thread = None
            
            self.is_server_running = False
            self.server_control_btn.setText("Start Server")
            QMessageBox.information(self, "Success", "Server stopped successfully")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to stop server: {str(e)}")
    
    def _run_server(self):
        """Run the MCP server in a separate thread"""
        try:
            asyncio.run(self.mcp_server.run())
        except Exception as e:
            print(f"Server error: {str(e)}")
    
    def create_mcp_tool(self, tool_data):
        """Create an MCP tool from tool data"""
        # Create a named function for this specific tool
        async def named_tool_function(tool_name, cells, selenium_manager, **kwargs):
            try:
                # Execute cells in order
                for cell in cells:
                    if cell["type"] == "Load Page":
                        selenium_manager.navigate_to(cell["code"])
                    elif cell["type"] == "Execute JavaScript":
                        selenium_manager.execute_javascript(cell["code"])
                    elif cell["type"] in ["Execute Python", "Return Data"]:
                        result = selenium_manager.execute_python(
                            cell["code"],
                            args=kwargs
                        )
                        if cell["type"] == "Return Data":
                            return result.get("result")
                return None
            except Exception as e:
                raise Exception(f"Tool execution failed: {str(e)}")
        
        # Create a partial function with the tool's specific data
        tool_function = partial(
            named_tool_function,
            tool_data["name"],
            tool_data["cells"],
            self.selenium_manager
        )
        tool_function.__name__ = tool_data["name"]
        
        # Create input schema for the tool
        properties = {}
        required = []
        for arg in tool_data["args"]:
            properties[arg] = {
                "type": "string",
                "description": f"Parameter {arg}"
            }
            required.append(arg)
        
        input_schema = {
            "type": "object",
            "properties": properties,
            "required": required
        }
        
        # Create MCP tool
        return Tool(
            name=tool_data["name"],
            description=f"Automated tool for {tool_data['name']}",
            function=tool_function,
            inputSchema=input_schema
        )
    
    def closeEvent(self, event):
        """Handle application shutdown"""
        try:
            # Stop the server if running
            if self.is_server_running:
                self.stop_server()
            
            # Close Selenium
            if self.selenium_manager:
                self.selenium_manager.close()
            
            event.accept()
        except Exception as e:
            print(f"Shutdown error: {str(e)}")
            event.accept() 