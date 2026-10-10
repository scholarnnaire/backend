import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import settings
from app.core.database import engine, Base
from app.core.websockets import manager as connection_manager
from app.services.game_engine import global_game
from app.api.v1.api import api_router

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

# Mount static files directory
os.makedirs("static/logos", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    return {"message": "Welcome to Millionaires on Wheels API"}

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await connection_manager.connect(websocket)
    try:
        while True:
            data_str = await websocket.receive_text()
            try:
                data = json.loads(data_str)
                action = data.get("action")
                
                if action == "START_GAME":
                    global_game.start_game()
                    await connection_manager.broadcast_json({
                        "event": "GAME_STARTED",
                        "state": global_game.players
                    })
                    
                elif action == "GET_QUESTION":
                    player_id = data.get("player_id", "player1") 
                    q_data = global_game.get_question(player_id)
                    await connection_manager.send_personal_json({
                        "event": "QUESTION_DATA",
                        "data": q_data
                    }, websocket)
                    
                elif action == "ANSWER_QUESTION":
                    player_id = data.get("player_id")
                    answer_index = data.get("answer_index")
                    result = global_game.answer_question(player_id, answer_index)
                    
                    await connection_manager.send_personal_json({
                        "event": "ANSWER_RESULT",
                        "data": result
                    }, websocket)
                    
                    # Broadcast the new state to all clients (especially the LadderBoard)
                    await connection_manager.broadcast_json({
                        "event": "LADDER_UPDATE",
                        "state": global_game.players
                    })

                elif action == "USE_LIFELINE":
                    player_id = data.get("player_id")
                    lifeline_id = data.get("lifeline_id") # e.g., 'phone_a_scholar'
                    
                    result = global_game.use_lifeline(player_id, lifeline_id)
                    
                    await connection_manager.send_personal_json({
                        "event": "LIFELINE_RESULT",
                        "data": result,
                        "lifeline_id": lifeline_id
                    }, websocket)
                    
                    if result.get("success"):
                        # Broadcast lock status so other team's UI greys it out
                        await connection_manager.broadcast_json({
                            "event": "LIFELINE_LOCKED",
                            "locks": global_game.lifeline_locks
                        })

            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
