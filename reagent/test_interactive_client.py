"""Test client for interactive WebSocket workflow.

Run this to test the interactive orchestration system.
"""

import asyncio
import websockets
import json
import sys


async def interactive_workflow():
    """Run an interactive workflow via WebSocket."""
    
    workflow_id = "workflow_test_" + str(int(asyncio.get_event_loop().time()))
    uri = f"ws://localhost:8001/ws/{workflow_id}"
    
    print(f"🔌 Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to Reagent")
            
            # Start workflow
            await websocket.send(json.dumps({
                "type": "start_workflow",
                "workflow_id": workflow_id,
                "requirements": "Build an ERC-20 token for a DeFi project",
                "mode": "orchestrate"
            }))
            
            print("🚀 Workflow started\n")
            
            # Listen for messages
            async for message in websocket:
                data = json.loads(message)
                
                msg_type = data.get("type", "")
                
                # Handle different message types
                if msg_type == "connected":
                    print("✅ WebSocket connected")
                
                elif msg_type == "workflow_started":
                    print("🚀 Workflow started")
                
                elif msg_type == "stage.started":
                    print(f"\n📍 Stage: {data.get('stage')}")
                    print(f"   {data.get('message')}")
                
                elif msg_type == "stage.progress":
                    progress = data.get("data", {}).get("progress", 0)
                    print(f"   ⏳ Progress: {progress}%")
                
                elif msg_type == "stage.complete":
                    print(f"   ✅ Completed: {data.get('stage')}")
                
                elif msg_type == "stage.error":
                    print(f"   ❌ Error: {data.get('message')}")
                
                elif msg_type == "question.asked":
                    # Handle question
                    question_data = data.get("data", {})
                    question = question_data.get("question")
                    question_id = question_data.get("question_id")
                    options = question_data.get("options", [])
                    
                    print(f"\n❓ Question: {question}")
                    
                    if options:
                        for i, option in enumerate(options, 1):
                            print(f"   {i}. {option}")
                        
                        # Get user input
                        while True:
                            try:
                                choice = input("\nYour choice (number or text): ").strip()
                                
                                # Try to parse as number
                                try:
                                    choice_num = int(choice)
                                    if 1 <= choice_num <= len(options):
                                        answer = options[choice_num - 1]
                                        break
                                except ValueError:
                                    pass
                                
                                # Use as text
                                if choice in options or choice.lower() in [o.lower() for o in options]:
                                    answer = choice
                                    break
                                
                                print("Invalid choice. Try again.")
                            except KeyboardInterrupt:
                                print("\n\n⚠️  Aborting workflow...")
                                await websocket.send(json.dumps({
                                    "type": "abort",
                                    "workflow_id": workflow_id,
                                    "reason": "User interrupted"
                                }))
                                return
                    else:
                        # Free text answer
                        try:
                            answer = input("Your answer: ").strip()
                        except KeyboardInterrupt:
                            print("\n\n⚠️  Aborting workflow...")
                            await websocket.send(json.dumps({
                                "type": "abort",
                                "workflow_id": workflow_id,
                                "reason": "User interrupted"
                            }))
                            return
                    
                    # Send answer
                    await websocket.send(json.dumps({
                        "type": "answer",
                        "workflow_id": workflow_id,
                        "question_id": question_id,
                        "answer": answer
                    }))
                    
                    print(f"✅ Answered: {answer}\n")
                
                elif msg_type == "answer.received":
                    print("   ✅ Answer received")
                
                elif msg_type == "feedback.loop":
                    from_stage = data.get("data", {}).get("from")
                    to_stage = data.get("data", {}).get("to")
                    reason = data.get("data", {}).get("reason")
                    print(f"\n🔄 Feedback loop: {from_stage} → {to_stage}")
                    print(f"   Reason: {reason}")
                
                elif msg_type == "workflow.complete":
                    print("\n🎉 Workflow completed successfully!")
                    print(f"   Status: {data.get('data', {}).get('status')}")
                    break
                
                elif msg_type == "workflow.failed":
                    print(f"\n❌ Workflow failed: {data.get('message')}")
                    break
                
                elif msg_type == "error":
                    print(f"❌ Error: {data.get('message')}")
                
                else:
                    # Print other messages
                    print(f"📨 {msg_type}: {data.get('message', '')}")
    
    except websockets.exceptions.ConnectionClosed:
        print("\n🔌 Connection closed")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main entry point."""
    print("=" * 60)
    print("🧪 Reagent Interactive Workflow Test Client")
    print("=" * 60)
    print()
    
    try:
        asyncio.run(interactive_workflow())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    main()

# Made with Bob
