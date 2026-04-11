import sys
import os

# Add the current directory (backend) to sys.path
sys.path.append(os.getcwd())

try:
    from app.core.state import TASKS
    print("SUCCESS: app.core.state imported")
except ImportError as e:
    print(f"FAILED: app.core.state import failed - {e}")

import uuid, time, asyncio

async def test_task():
    task_id = str(uuid.uuid4())
    TASKS[task_id] = {
        "id": task_id, "module": "domain", "target": "google.com", "status": "pending",
        "created_at": time.time(), "result": None, "error": None
    }
    print(f"STARTING: Task {task_id}")
    try:
        from app.api.endpoints.investigations import _execute_task
        await _execute_task(task_id)
        print(f"FINISHED: Task status: {TASKS[task_id]['status']}")
        if TASKS[task_id]['status'] == 'completed':
            print("SUCCESS: Result found")
        else:
            print(f"FAILED: Error: {TASKS[task_id].get('error')}")
    except Exception as e:
        print(f"FATAL: {e}")

asyncio.run(test_task())
