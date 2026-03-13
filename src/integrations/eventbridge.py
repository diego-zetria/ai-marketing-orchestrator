"""EventBridge client for triggering approval portal flow.

Sends events to the custom EventBridge bus when a task moves to
client_approval, which triggers the ApprovalProcessor Lambda.
"""
import json
import logging

import boto3

logger = logging.getLogger(__name__)


def send_task_status_event(
    bus_name: str,
    task_id: str,
    *,
    status: str = "client_approval",
    region: str = "us-east-1",
) -> bool:
    """Send a task_status_changed event to EventBridge.

    Args:
        bus_name: The EventBridge bus name (e.g. "approval-events").
        task_id: The ClickUp task ID.
        status: The new status (default: client_approval).
        region: AWS region.

    Returns:
        True if the event was sent successfully, False otherwise.
    """
    try:
        client = boto3.client("events", region_name=region)
        response = client.put_events(
            Entries=[
                {
                    "Source": "app.clickup",
                    "DetailType": "task_status_changed",
                    "Detail": json.dumps({
                        "task_id": task_id,
                        "status": status,
                    }),
                    "EventBusName": bus_name,
                },
            ],
        )
        failed = response.get("FailedEntryCount", 0)
        if failed > 0:
            logger.error(
                "EventBridge put_events failed for task %s: %s",
                task_id, response.get("Entries", []),
            )
            return False

        logger.info(
            "EventBridge event sent: task %s → %s (bus: %s)",
            task_id, status, bus_name,
        )
        return True
    except Exception:
        logger.exception(
            "Failed to send EventBridge event for task %s", task_id,
        )
        return False
