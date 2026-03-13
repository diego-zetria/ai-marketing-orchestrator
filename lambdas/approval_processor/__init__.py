"""Lambda: Approval Processor.

Triggered by EventBridge when a ClickUp task status change event is received.
Fetches attachments, uploads to S3, creates DB records, and sends email.
"""
