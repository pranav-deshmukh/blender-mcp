bl_info = {
    "name": "Simple MCP Receiver",
    "author": "MCP",
    "version": (1, 0, 0),
    "blender": (4, 3, 0),
    "location": "View3D > Sidebar > MCP",
    "description": "Simple MCP code receiver via TCP socket",
    "category": "Development",
}

import bpy
import socket
import threading
import json
import time
import io
import queue
import traceback
import urllib.request
import os
import tempfile
from contextlib import redirect_stdout, redirect_stderr, suppress

socket_server = None
server_running = False

code_execution_queue = queue.Queue()


def getSceneInfo():
    try:
        sceneInfo = {
            "scene_name":bpy.context.scene.name,
            "objects":[],
        }

        for obj in bpy.context.scene.objects:
            obj_info = {
                "name": obj.name,
                "type": obj.type,
                "location": list(obj.location),
                "dimensions": list(obj.dimensions),
            }
            sceneInfo["objects"].append(obj_info)
        return sceneInfo;
    except Exception as e:
        print(f"Error getting scene info: {e}")
        return {"error": str(e)}


def download_file(url, filepath):
    """Download a file from a URL"""
    try:
        print(f"Downloading file from {url} to {filepath}")
        urllib.request.urlretrieve(url, filepath)
        print(f"File downloaded successfully:{filepath}")
        return True
    except Exception as e:
        print(f"Error downloading file {url}: {e}")
        return False

def download_and_import_asset(asset_data):
    """Download blend file and textures, then import into Blender"""
    try:
        asset_name = asset_data.get("asset_name")
        blend_url = asset_data.get("blend_url")
        includes = asset_data.get("includes", {})

        if not blend_url:
           return {"status": "error", "error": "No blend URL provided"}
        
        temp_dir = tempfile.mkdtemp(prefix=f"polyhaven_{asset_name}_")
        print(f"creating temp dir: {temp_dir}")

        blend_filename = f"{asset_name}.blend"
        blend_filepath = os.path.join(temp_dir, blend_filename)

        print(f"Downloading blend file from {blend_url} to {blend_filepath}")
        if not download_file(blend_url, blend_filepath):
            return {"status": "error", "error": "Failed to download blend file"}
        
        textures_dir = os.path.join(temp_dir, "textures")
        os.makedirs(textures_dir, exist_ok=True)

        downloaded_textures = [];
        for texture_path, texture_info in includes.items():
            texture_url = texture_info.get("url")
            if(texture_url):
                texture_filename = os.path.basename(texture_path)
                texture_file_path = os.path.join(textures_dir, texture_filename)
                print(f"Downloading texture {texture_filename} from {texture_url} to {texture_file_path}")
                if download_file(texture_url, texture_file_path):
                    downloaded_textures.append(texture_file_path)
                else:
                    return {"status": "error", "error": "Failed to download texture"}
                
        print(f"Importing blend file {blend_filepath}")
        with bpy.data.libraries.load(blend_filepath) as (data_from, data_to):
            data_to.objects = data_from.objects
            data_to.materials = data_from.materials
            data_to.meshes = data_from.meshes
        
        imported_objects = []
        for obj in data_to.objects:
            if obj:
                bpy.context.collection.objects.link(obj)
                imported_objects.append(obj.name)
                print(f"Imported object: {obj.name}")
        
        
        
        return {
            "status": "success",
            "message": f"Asset '{asset_name}' imported successfully",
            "details": {
                "blend_file": blend_filepath,
                "textures_downloaded": len(downloaded_textures),
                "texture_files": downloaded_textures,
                "imported_objects": imported_objects,
                "temp_directory": temp_dir
            }
        }
        
    except Exception as e:
        error_msg = f"Error importing asset: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        return {"status": "error", "error": error_msg}
        


    
def execute_code_in_main_thread(code):
    """Execute Python code with comprehensive error handling"""
    if not code.strip():
        return {"status": "error", "error": "NO code provided"}
    print("Executing code...")
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    try:
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            try:
                compiled_code = compile(code, "<mcp_code>", "exec")
                exec(compiled_code, {"bpy": bpy})
            except Exception as e:
                print(f"Code execution error: {e}")
                return {
                    "status": "error",
                    "error": str(e),
                    "message": "Code execution error",
                }
        stdout_output = stdout_capture.getvalue()
        stderr_output = stderr_capture.getvalue()
    
        result = {
            "status": "executed",
            "result": stdout_output,
        }
        if stderr_output:
            result["warnings"] = stderr_output
        print("Code executed successfully:", stdout_output)
        return result
    except Exception as e:
        error_msg = str(e)
        traceback.print_exc()
        print(f"Code execution error: {e}")
        return {
            "status": "error",
            "error": error_msg,
            "message": "Code execution error",
            "traceback": traceback.format_exc(),
        }

def process_queue_timer():
    """Timer function to process queued code execution tasks"""
    try:
        while not code_execution_queue.empty():
            task = code_execution_queue.get_nowait()
            if task["type"] == "code":
                result = execute_code_in_main_thread(task["code"])
                task["result"] = result
                task["completed"] = True
            elif task["type"] == "download_asset":
                result = download_and_import_asset(task["asset_data"])
                task["result"] = result
                task["completed"] = True
    except queue.Empty:
        pass
    except Exception as e:
        print(f"Error processing code execution queue: {e}")
    return 0.1

class SimpleMCPServer:
    def __init__(self, port=8765):
        self.port = port
        self.socket = None
        self.running = False
        
    def start_server(self):
        """Start the TCP server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            self.socket.bind(('localhost', self.port))
            self.socket.listen(1)
            
            self.running = True
            print(f"MCP Server started on port {self.port}")
            
            while self.running:
                try:
                    client_socket, address = self.socket.accept()
                    print(f"Client connected from {address}")
                    
                    self.handle_client(client_socket)
                    
                except socket.error as e:
                    if self.running:  
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
            client_socket.settimeout(10.0)
            
            while True:
                
                    data = client_socket.recv(1024)
                    if not data:
                        break
                    
                    chunk = data.decode('utf-8')
                    buffer += chunk
                    print(f"Received chunk: {chunk}")
                    
                    try:
                        json_data = json.loads(buffer)
                        print(f"Complete JSON received: {json_data}")
                        
                        response = self.process_message(json_data)
                        client_socket.send((json.dumps(response) + "\n").encode('utf-8'))
                        print("Response sent to client")
                        break
                        
                    except json.JSONDecodeError:
                        continue
                        
                

        except Exception as e:
            error_response = {"status": "error", "error": str(e)}
            try:
                client_socket.send((json.dumps(error_response) + "\n").encode('utf-8'))
            except:
                pass
        finally:
            client_socket.close()
            print("Client disconnected")
    


    def process_message(self, data):
        """Process the received JSON message"""
        print("=== MCP MESSAGE RECEIVED ===")
        print(f"Full message: {data}")
        
        try:
            msg_type = data.get('type', 'unknown')
            if(msg_type == 'code'):
                return self.execute_code_via_queue(data.get('code', ''))
            elif(msg_type == 'fetch-scene'):
                return getSceneInfo()
            elif(msg_type == 'asset-data'):
                return self.handle_asset_data(data)
            else:
                return {"status": "error", "error": "Unknown message type"}
        except Exception as e:
            print(f"Error processing message: {e}")
            return {"status": "error", "error": str(e)}
        
    def handle_asset_data(self, data):
        """Handle asset data received from Blender"""
        try:
            print(f"Received asset data: {data}")
            task = {
                'type': 'download_asset',
                'asset_data': data,
                'completed': False,
                'result': None
            }
            code_execution_queue.put(task)
        
            timeout = 60.0
            start_time = time.time()
            while not task["completed"] and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            if task["completed"]:
                return task["result"]
            else:
                return {"status": "error", "error": "Asset download / import timed out"}
        except Exception as e:
            print(f"Error processing asset data: {e}")
            return {"status": "error", "error": str(e)}

    def execute_code_via_queue(self, code):
        """Execute Python code with comprehensive error handling"""
        if not code.strip():
            return {"status": "error", "error": "NO code provided"}
        
        task = {
            'type': 'code',
            'code': code,
            'completed': False,
            'result': None
        }

        code_execution_queue.put(task)

        timeout = 10.0
        start_time = time.time()
        while not task["completed"] and (time.time() - start_time) < timeout:
            time.sleep(0.1)
        if task["completed"]:
            return task["result"]
        else:
            return {"status": "error", "error": "Code execution timed out"}
        

    def stop_server(self):
        """Stop the server"""
        self.running = False
        if self.socket:
            self.socket.close()
        print("MCP Server stopped")

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
        
        socket_server = SimpleMCPServer(8765)
        
        server_thread = threading.Thread(target=socket_server.start_server)
        server_thread.daemon = True  
        server_thread.start()

        if not bpy.app.timers.is_registered(process_queue_timer):
            bpy.app.timers.register(process_queue_timer)
        
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

        if bpy.app.timers.is_registered(process_queue_timer):
            bpy.app.timers.unregister(process_queue_timer)
        
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
        
        if server_running:
            layout.label(text="Status: Running on port 8765", icon='PLAY')
            layout.operator("mcp.stop_server", icon='PAUSE')
        else:
            layout.label(text="Status: Stopped", icon='PAUSE')
            layout.operator("mcp.start_server", icon='PLAY')
        
        box = layout.box()
        box.label(text="Instructions:")
        box.label(text="1. Click 'Start MCP Server'")
        box.label(text="2. Send JSON to localhost:8765")
        box.label(text="3. Check Blender console for logs")
        
        box = layout.box()
        box.label(text="Expected JSON format:")
        box.label(text='{"type": "code", "code": "..."}')

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
    
    if server_running and socket_server:
        socket_server.stop_server()

    if bpy.app.timers.is_registered(process_queue_timer):
        bpy.app.timers.unregister(process_queue_timer)
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    print("Simple MCP addon unregistered")

if __name__ == "__main__":
    register()