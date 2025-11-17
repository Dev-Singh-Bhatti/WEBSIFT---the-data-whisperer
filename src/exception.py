import os
import sys
import traceback

def error_message_detail(error, error_detail):
    """
    Extract error details from exception traceback.
    
    Args:
        error: Error message or exception object
        error_detail: sys module or traceback object
        
    Returns:
        Formatted error message string
    """
    # First, try to get traceback from the error object if it's an exception
    exc_tb = None
    if isinstance(error, BaseException) and hasattr(error, '__traceback__'):
        exc_tb = error.__traceback__
    
    # If error_detail has exc_info() method (sys module), use it
    if exc_tb is None and hasattr(error_detail, 'exc_info'):
        exc_type, exc_value, exc_tb = error_detail.exc_info()
    elif exc_tb is None:
        # If it's already a traceback tuple
        if isinstance(error_detail, tuple) and len(error_detail) == 3:
            exc_type, exc_value, exc_tb = error_detail
    
    # If we have a traceback, use it
    if exc_tb is not None:
        file_name = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        error_message = "Error occurred python script name [{0}] line number [{1}] error message [{2}]".format(
            file_name, exc_tb.tb_lineno, str(error)
        )
    else:
        # No active exception context - extract from current call stack
        # Skip the last frame (this function) and get the caller
        stack = traceback.extract_stack()
        if len(stack) >= 2:
            # Get the frame that called CustomException (skip error_message_detail and __init__)
            frame = stack[-3] if len(stack) >= 3 else stack[-2]
            file_name = os.path.split(frame.filename)[1]
            error_message = "Error occurred python script name [{0}] line number [{1}] error message [{2}]".format(
                file_name, frame.lineno, str(error)
            )
        else:
            # Fallback if we can't extract stack info
            error_message = f"Error occurred: {str(error)}"
    
    return error_message




class CustomException(Exception):
    def __init__(self, error_message, error_detail):
        """
        :param error_message: error message in string format
        """
        super().__init__(error_message)
        self.error_message = error_message_detail(
            error_message, error_detail=error_detail
        )


    def __str__(self):
        return self.error_message