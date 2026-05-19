"""
In-Memory Bounded Buffer for Activity Logs.
Utilizes the custom FIFO Queue implementation to store the last 50 transactions,
drastically reducing database read operations.
"""
from my_logic.queue import Queue
from app.storage.database import SessionLocal
from app.storage.models import ActivityLog
from sqlalchemy import desc
from app.utils.logging import logger

# Global In-Memory Queue for Activities
activity_queue = Queue()

def init_activity_queue():
    """Fetches the last 50 activities from the DB and seeds the in-memory queue."""
    db = SessionLocal()
    try:
        # Fetch last 50 descending to get newest, but we enqueue them oldest first
        logs = db.query(ActivityLog).order_by(desc(ActivityLog.id)).limit(50).all()
        
        # Reset count in case it's called multiple times
        activity_queue.head = None
        activity_queue.tail = None
        activity_queue.count = 0
        
        # Reverse to get chronological order (oldest to newest)
        for log in reversed(logs):
            activity_queue.enqueue({
                "id": log.id,
                "activity_type": log.activity_type,
                "description": log.description,
                "amount": log.amount,
                "created_at": log.created_at.isoformat() if log.created_at else None
            })
        logger.info(f"Initialized Bounded Activity Queue with {activity_queue.count} items.")
    finally:
        db.close()

def push_to_activity_queue(log_entry):
    """Pushes a new log entry to the queue and maintains the bounded buffer of 50."""
    activity_queue.enqueue({
        "id": log_entry.id,
        "activity_type": log_entry.activity_type,
        "description": log_entry.description,
        "amount": log_entry.amount,
        "created_at": log_entry.created_at.isoformat() if hasattr(log_entry, 'created_at') and log_entry.created_at else None
    })
    
    # Maintain max 50 items
    while activity_queue.count > 50:
        try:
            activity_queue.dequeue()
        except IndexError:
            break

def get_activity_queue_list():
    """Traverses the Linked List queue to return a standard Python list of items, reversed (newest first)."""
    items = []
    current = activity_queue.head
    while current is not None:
        items.append(current.value)
        current = current.next_node
    # Return newest items first
    return list(reversed(items))
