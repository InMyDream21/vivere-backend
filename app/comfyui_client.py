from __future__ import annotations

import json
import uuid
import websocket  # type: ignore
import requests
from typing import Optional, Dict, Any
from threading import Thread
from app.config import get_config

_config = get_config()

# Fixed workflow constants
VIDEO_WIDTH = 640
VIDEO_HEIGHT = 400
VIDEO_LENGTH = 81  # frames


class ComfyUIClient:
    """Client for interacting with ComfyUI API"""

    def __init__(self, server_url: Optional[str] = None):
        self.server_url = server_url or _config.COMFYUI_SERVER_URL
        self.client_id = str(uuid.uuid4())
        self.ws = None
        self.ws_thread = None
        self.pending_tasks: Dict[str, Dict[str, Any]] = {}

    def _load_workflow_template(self) -> Dict[str, Any]:
        """Load workflow JSON template"""
        workflow_path = _config.COMFYUI_WORKFLOW_PATH
        if not workflow_path:
            raise ValueError("COMFYUI_WORKFLOW_PATH not configured")

        with open(workflow_path, "r") as f:
            return json.load(f)

    def _modify_workflow(
        self, workflow: Dict[str, Any], image_filename: str, prompt: str
    ) -> Dict[str, Any]:
        """Modify workflow with image and prompt"""
        # Node 97: LoadImage - Set input image
        workflow["97"]["inputs"]["image"] = image_filename

        # Node 116:93: CLIPTextEncode - Set positive prompt
        workflow["116:93"]["inputs"]["text"] = prompt

        # Node 116:98: WanImageToVideo - Fixed video parameters
        workflow["116:98"]["inputs"]["width"] = VIDEO_WIDTH
        workflow["116:98"]["inputs"]["height"] = VIDEO_HEIGHT
        workflow["116:98"]["inputs"]["length"] = VIDEO_LENGTH

        return workflow

    def upload_image(self, image_bytes: bytes, filename: str) -> str:
        """Upload image to ComfyUI input directory"""
        input_dir = _config.COMFYUI_INPUT_DIR
        if not input_dir:
            raise ValueError("COMFYUI_INPUT_DIR not configured")

        import os

        os.makedirs(input_dir, exist_ok=True)

        filepath = os.path.join(input_dir, filename)
        with open(filepath, "wb") as f:
            f.write(image_bytes)

        return filename

    def queue_prompt(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Queue a workflow/prompt for execution"""
        p = {"prompt": workflow, "client_id": self.client_id}
        data = json.dumps(p).encode("utf-8")

        response = requests.post(
            f"{self.server_url}/prompt",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        return response.json()

    def get_image(self, filename: str, subfolder: str, folder_type: str) -> bytes:
        """Retrieve generated image/video"""
        params = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        response = requests.get(f"{self.server_url}/view", params=params)
        response.raise_for_status()
        return response.content

    def get_video_bytes(self, prompt_id: str) -> Optional[bytes]:
        """Get video bytes for a completed prompt"""
        status_info = self.get_status(prompt_id)
        if status_info.get("status") != "completed":
            return None

        video_filename = status_info.get("video_filename")
        video_subfolder = status_info.get("video_subfolder", "")
        video_type = status_info.get("video_type", "output")

        if not video_filename:
            return None

        try:
            return self.get_image(video_filename, video_subfolder, video_type)
        except Exception as e:
            print(f"Error retrieving video: {e}")
            return None

    def _on_message(self, ws, message):
        """Handle WebSocket messages"""
        try:
            data = json.loads(message)
            msg_type = data.get("type")

            if msg_type == "execution_start":
                prompt_id = data.get("data", {}).get("prompt_id")
                if prompt_id:
                    self.pending_tasks[prompt_id] = {"status": "running", "progress": 0}

            elif msg_type == "execution_cached":
                prompt_id = data.get("data", {}).get("prompt_id")
                if prompt_id and prompt_id in self.pending_tasks:
                    self.pending_tasks[prompt_id]["status"] = "cached"

            elif msg_type == "executing":
                node_id = data.get("data", {}).get("node")
                prompt_id = data.get("data", {}).get("prompt_id")
                if prompt_id and prompt_id in self.pending_tasks:
                    if node_id is None:
                        # Execution finished
                        self.pending_tasks[prompt_id]["status"] = "completed"
                    else:
                        self.pending_tasks[prompt_id]["status"] = "running"

            elif msg_type == "progress":
                prompt_id = data.get("data", {}).get("prompt_id")
                value = data.get("data", {}).get("value", 0)
                max_value = data.get("data", {}).get("max", 100)
                if prompt_id and prompt_id in self.pending_tasks:
                    progress = int((value / max_value) * 100) if max_value > 0 else 0
                    self.pending_tasks[prompt_id]["progress"] = progress

            elif msg_type == "executed":
                prompt_id = data.get("data", {}).get("prompt_id")
                if prompt_id and prompt_id in self.pending_tasks:
                    self.pending_tasks[prompt_id]["status"] = "completed"
                    # Extract output info if available
                    output = data.get("data", {}).get("output", {})
                    if output:
                        self.pending_tasks[prompt_id]["output"] = output
                        # Extract video file info from SaveVideo node (node 108)
                        # ComfyUI returns SaveVideo output as dict with 'images' key: {node_id: {"images": [{"filename": "...", ...}]}}
                        if "108" in output:
                            video_info = output["108"]
                            # Check for dict with 'images' key (SaveVideo format)
                            if isinstance(video_info, dict) and "images" in video_info:
                                images = video_info["images"]
                                if isinstance(images, list) and len(images) > 0:
                                    video_data = images[0]
                                    self.pending_tasks[prompt_id]["video_filename"] = (
                                        video_data.get("filename")
                                    )
                                    self.pending_tasks[prompt_id]["video_subfolder"] = (
                                        video_data.get("subfolder", "")
                                    )
                                    self.pending_tasks[prompt_id]["video_type"] = (
                                        video_data.get("type", "output")
                                    )
                            # Fallback: check if it's a list directly (for other node types)
                            elif isinstance(video_info, list) and len(video_info) > 0:
                                video_data = video_info[0]
                                self.pending_tasks[prompt_id]["video_filename"] = (
                                    video_data.get("filename")
                                )
                                self.pending_tasks[prompt_id]["video_subfolder"] = (
                                    video_data.get("subfolder", "")
                                )
                                self.pending_tasks[prompt_id]["video_type"] = (
                                    video_data.get("type", "output")
                                )

            elif msg_type == "execution_error":
                prompt_id = data.get("data", {}).get("prompt_id")
                error_msg = data.get("data", {}).get("error_message", "Unknown error")
                if prompt_id and prompt_id in self.pending_tasks:
                    self.pending_tasks[prompt_id]["status"] = "error"
                    self.pending_tasks[prompt_id]["error"] = error_msg

        except Exception as e:
            print(f"Error processing WebSocket message: {e}")

    def _on_error(self, ws, error):
        """Handle WebSocket errors"""
        print(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        print("WebSocket connection closed")

    def connect_websocket(self):
        """Connect to ComfyUI WebSocket"""
        ws_url = f"ws://{self.server_url.replace('http://', '').replace('https://', '')}/ws?client_id={self.client_id}"

        self.ws = websocket.WebSocketApp(
            ws_url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )

        def run_ws():
            self.ws.run_forever()

        self.ws_thread = Thread(target=run_ws, daemon=True)
        self.ws_thread.start()

    def get_history(self) -> Dict[str, Any]:
        """Get execution history from ComfyUI"""
        try:
            response = requests.get(f"{self.server_url}/history")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching history: {e}")
            return {}

    def get_status(self, prompt_id: str) -> Dict[str, Any]:
        """Get status of a queued prompt"""
        # First check in-memory pending tasks
        if prompt_id in self.pending_tasks:
            return self.pending_tasks[prompt_id]

        # Fallback: check ComfyUI history to see if job completed
        history = self.get_history()
        if prompt_id in history:
            # Job exists in history, check if it has outputs (completed)
            job_data = history[prompt_id]
            outputs = job_data.get("outputs", {})

            # Check if SaveVideo node (108) has output
            if "108" in outputs:
                video_info = outputs["108"]
                # ComfyUI returns SaveVideo output as dict with 'images' key
                if isinstance(video_info, dict) and "images" in video_info:
                    images = video_info["images"]
                    if isinstance(images, list) and len(images) > 0:
                        video_data = images[0]
                        return {
                            "status": "completed",
                            "progress": 100,
                            "video_filename": video_data.get("filename"),
                            "video_subfolder": video_data.get("subfolder", ""),
                            "video_type": video_data.get("type", "output"),
                        }
                # Fallback: check if it's a list directly (for other node types)
                elif isinstance(video_info, list) and len(video_info) > 0:
                    video_data = video_info[0]
                    return {
                        "status": "completed",
                        "progress": 100,
                        "video_filename": video_data.get("filename"),
                        "video_subfolder": video_data.get("subfolder", ""),
                        "video_type": video_data.get("type", "output"),
                    }

            # Job in history but no outputs yet (might be running)
            return {"status": "running", "progress": 0}

        return {"status": "not_found"}

    def generate_video(
        self, image_bytes: bytes, image_filename: str, prompt: str
    ) -> str:
        """Generate video from image and prompt, returns prompt_id"""
        # Upload image
        uploaded_filename = self.upload_image(image_bytes, image_filename)

        # Load and modify workflow
        workflow = self._load_workflow_template()
        modified_workflow = self._modify_workflow(workflow, uploaded_filename, prompt)

        # Queue prompt
        response = self.queue_prompt(modified_workflow)
        prompt_id = response.get("prompt_id")

        if not prompt_id:
            raise ValueError("Failed to get prompt_id from ComfyUI response")

        # Initialize status tracking
        self.pending_tasks[prompt_id] = {"status": "queued", "progress": 0}

        return prompt_id
