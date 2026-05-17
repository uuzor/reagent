"""WebSocket connection manager for interactive workflows.

Manages WebSocket connections and routes messages between clients and orchestrator.
"""

from fastapi import WebSocket
from typing import Dict, Set, Optional, Any
import json
import asyncio
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for workflows."""
    
    def __init__(self):
        """Initialize connection manager."""
        # workflow_id -> set of WebSocket connections
        self._connections: Dict[str, Set[WebSocket]] = {}
        
        # WebSocket -> workflow_id mapping
        self._workflow_to_ws: Dict[WebSocket, str] = {}
        
        # Connection metadata: WebSocket -> dict
        self._metadata: Dict[WebSocket, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, workflow_id: str, metadata: Optional[Dict[str, Any]] = None):
        """Accept WebSocket connection and associate with workflow.
        
        Args:
            websocket: WebSocket connection
            workflow_id: Workflow ID to associate with
            metadata: Optional connection metadata (user_id, etc.)
        """
        await websocket.accept()
        
        if workflow_id not in self._connections:
            self._connections[workflow_id] = set()
        
        self._connections[workflow_id].add(websocket)
        self._workflow_to_ws[websocket] = workflow_id
        
        if metadata:
            self._metadata[websocket] = metadata
        
        logger.info(f"WebSocket connected: workflow={workflow_id}, total_connections={len(self._connections[workflow_id])}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection.
        
        Args:
            websocket: WebSocket connection to remove
        """
        workflow_id = self._workflow_to_ws.pop(websocket, None)
        
        if workflow_id and workflow_id in self._connections:
            self._connections[workflow_id].discard(websocket)
            
            # Clean up empty workflow connection sets
            if not self._connections[workflow_id]:
                del self._connections[workflow_id]
        
        # Clean up metadata
        self._metadata.pop(websocket, None)
        
        logger.info(f"WebSocket disconnected: workflow={workflow_id}")
    
    async def send_to_workflow(self, workflow_id: str, message: dict):
        """Send message to all connections for a workflow.
        
        Args:
            workflow_id: Workflow ID
            message: Message dictionary to send
        """
        if workflow_id not in self._connections:
            return
        
        message_json = json.dumps(message)
        dead_connections = set()
        
        for websocket in self._connections[workflow_id]:
            try:
                await websocket.send_text(message_json)
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {e}")
                dead_connections.add(websocket)
        
        # Clean up dead connections
        for ws in dead_connections:
            self.disconnect(ws)
    
    async def send_to_connection(self, websocket: WebSocket, message: dict):
        """Send message to a specific connection.
        
        Args:
            websocket: WebSocket connection
            message: Message dictionary to send
        """
        try:
            message_json = json.dumps(message)
            await websocket.send_text(message_json)
        except Exception as e:
            logger.error(f"Error sending to WebSocket: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connections.
        
        Args:
            message: Message dictionary to send
        """
        message_json = json.dumps(message)
        
        for connections in self._connections.values():
            for websocket in connections:
                try:
                    await websocket.send_text(message_json)
                except Exception as e:
                    logger.error(f"Error broadcasting to WebSocket: {e}")
    
    def get_workflow_connections(self, workflow_id: str) -> Set[WebSocket]:
        """Get all connections for a workflow.
        
        Args:
            workflow_id: Workflow ID
            
        Returns:
            Set of WebSocket connections
        """
        return self._connections.get(workflow_id, set()).copy()
    
    def get_workflow_id(self, websocket: WebSocket) -> Optional[str]:
        """Get workflow ID for a connection.
        
        Args:
            websocket: WebSocket connection
            
        Returns:
            Workflow ID or None
        """
        return self._workflow_to_ws.get(websocket)
    
    def get_metadata(self, websocket: WebSocket) -> Optional[Dict[str, Any]]:
        """Get metadata for a connection.
        
        Args:
            websocket: WebSocket connection
            
        Returns:
            Metadata dictionary or None
        """
        return self._metadata.get(websocket)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection manager statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            "total_workflows": len(self._connections),
            "total_connections": sum(len(conns) for conns in self._connections.values()),
            "workflows": {
                wf_id: len(conns)
                for wf_id, conns in self._connections.items()
            }
        }


# Global singleton
_connection_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """Get global connection manager singleton.
    
    Returns:
        ConnectionManager instance
    """
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return _connection_manager


def reset_connection_manager() -> None:
    """Reset global connection manager (for testing)."""
    global _connection_manager
    _connection_manager = None

# Made with Bob
