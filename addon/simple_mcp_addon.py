bl_info = {
    "name": "Simple MCP Receiver",
    "author": "Your Name",
    "version": (1, 0, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > MCP",
    "description": "Simple MCP code receiver via TCP socket",
    "category": "Development",
}

import bpy
import socket
import threading
import json
import time

# Global variables
socket_server = None
server_running = False

class SimpleMCPServer:
    def __init__(self, port=8765):
        self.port = port
        self.socket = None
        self.running = False
        
    def start_server(self):
        """Start the TCP server"""
        try:
            # Create socket (like net.createServer() in Node.js)
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind to localhost:8765 (like server.listen(8765) in Node.js)
            self.socket.bind(('localhost', self.port))
            self.socket.listen(1)
            
            self.running = True
            print(f"MCP Server started on port {self.port}")
            
            # Keep accepting connections
            while self.running:
                try:
                    # Accept connection (like server.on('connection') in Node.js)
                    client_socket, address = self.socket.accept()
                    print(f"Client connected from {address}")
                    
                    # Handle this client
                    self.handle_client(client_socket)
                    
                except socket.error as e:
                    if self.running:  # Only print error if we're supposed to be running
                        print(f"Socket error: {e}")
                    break
                    
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            if self.socket:
                self.socket.close()
    
    def handle_client(self, client_socket):
        buffer = ""
        try:
            # Set socket timeout to avoid hanging
            client_socket.settimeout(10.0)
            
            # Read data in chunks until we get complete message
            while True:
                try:
                    data = client_socket.recv(1024)
                    if not data:
                        break
                    
                    chunk = data.decode('utf-8')
                    buffer += chunk
                    print(f"Received chunk: {chunk}")
                    
                    # Try to parse as JSON
                    try:
                        json_data = json.loads(buffer)
                        print(f"Complete JSON received: {json_data}")
                        
                        # Process the message
                        self.process_message(json_data)
                        
                        # Send response
                        response = json.dumps({"status": "received", "message": "Code processed successfully"})
                        client_socket.send(response.encode('utf-8'))
                        print(f"Response sent: {response}")
                        break
                        
                    except json.JSONDecodeError:
                        # Not complete JSON yet, continue reading
                        continue
                        
                except socket.timeout:
                    print("Client socket timeout")
                    break
                except socket.error as e:
                    print(f"Socket receive error: {e}")
                    break

        except Exception as e:
            print(f"Client handling error: {e}")
            try:
                error_response = json.dumps({"status": "error", "error": str(e)})
                client_socket.send(error_response.encode('utf-8'))
            except:
                pass
        finally:
            try:
                client_socket.close()
            except:
                pass
            print("Client disconnected")

    def process_message(self, data):
        """Process the received JSON message"""
        print("=== MCP MESSAGE RECEIVED ===")
        print(f"Full message: {data}")
        
        # Extract message type and code
        msg_type = data.get('type', 'unknown')
        code = data.get('code', '')
        
        print(f"Message type: {msg_type}")
        print(f"Code content: {code}")
        
        # Execute the code if it's a code message
        if msg_type == 'code' and code:
            try:
                print("Executing code...")
                # Execute in Blender's context
                exec(code)
                print("Code executed successfully")
            except Exception as e:
                print(f"Code execution error: {e}")
        
        print("=== END MESSAGE ===")
    
    def stop_server(self):
        """Stop the server"""
        self.running = False
        if self.socket:
            self.socket.close()
        print("MCP Server stopped")

# Blender UI Classes
class MCP_OT_StartServer(bpy.types.Operator):
    """Start MCP Server"""
    bl_idname = "mcp.start_server"
    bl_label = "Start MCP Server"
    bl_description = "Start listening for MCP messages"
    
    def execute(self, context):
        global socket_server, server_running
        
        if server_running:
            self.report({'WARNING'}, "Server already running!")
            return {'CANCELLED'}
        
        # Create and start server
        socket_server = SimpleMCPServer(8765)
        
        # Start in background thread
        server_thread = threading.Thread(target=socket_server.start_server)
        server_thread.daemon = True  # Dies when Blender closes
        server_thread.start()
        
        server_running = True
        self.report({'INFO'}, "MCP Server started on port 8765")
        
        return {'FINISHED'}

class MCP_OT_StopServer(bpy.types.Operator):
    """Stop MCP Server"""
    bl_idname = "mcp.stop_server"
    bl_label = "Stop MCP Server"
    bl_description = "Stop the MCP server"
    
    def execute(self, context):
        global socket_server, server_running
        
        if not server_running:
            self.report({'WARNING'}, "Server not running!")
            return {'CANCELLED'}
        
        if socket_server:
            socket_server.stop_server()
        
        server_running = False
        self.report({'INFO'}, "MCP Server stopped")
        
        return {'FINISHED'}

class MCP_PT_Panel(bpy.types.Panel):
    """MCP Control Panel"""
    bl_label = "Simple MCP"
    bl_idname = "MCP_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MCP"
    
    def draw(self, context):
        layout = self.layout
        
        # Server status
        if server_running:
            layout.label(text="Status: Running on port 8765", icon='PLAY')
            layout.operator("mcp.stop_server", icon='PAUSE')
        else:
            layout.label(text="Status: Stopped", icon='PAUSE')
            layout.operator("mcp.start_server", icon='PLAY')
        
        # Instructions
        box = layout.box()
        box.label(text="Instructions:")
        box.label(text="1. Click 'Start MCP Server'")
        box.label(text="2. Send JSON to localhost:8765")
        box.label(text="3. Check Blender console for logs")
        
        # Example message format
        box = layout.box()
        box.label(text="Expected JSON format:")
        box.label(text='{"type": "code", "code": "..."}')

# Registration
classes = [
    MCP_OT_StartServer,
    MCP_OT_StopServer,
    MCP_PT_Panel,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    print("Simple MCP addon registered")

def unregister():
    global socket_server, server_running
    
    # Stop server if running
    if server_running and socket_server:
        socket_server.stop_server()
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    print("Simple MCP addon unregistered")

if __name__ == "__main__":
    register()