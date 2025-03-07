from .models import SystemLog

def log_system_event(message, type='system', status='info', details=None):
    """
    Utility function to log system events.
    
    Args:
        message (str): The log message
        type (str): The type of log (oauth, sync, system, error, warning, info)
        status (str): The status of the log (success, error, warning, info, in_progress)
        details (dict): Optional JSON-serializable details about the event
    
    Returns:
        SystemLog: The created log entry
    """
    return SystemLog.objects.create(
        message=message,
        type=type,
        status=status,
        details=details
    )
