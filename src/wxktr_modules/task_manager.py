#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Task Manager Service
--------------------
A centralized service for managing and running background tasks using a
thread pool, ensuring that UI updates are safely handled on the main thread.
"""

import wx
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional, Any

class TaskManager:
    """A singleton service to manage and run background tasks."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TaskManager, cls).__new__(cls)
            cls._instance.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="KtrWorker")
        return cls._instance

    def submit_job(self, target_function: Callable, on_complete: Optional[Callable] = None, on_error: Optional[Callable] = None, *args, **kwargs):
        """
        Submits a job to be run in a background thread.

        Args:
            target_function: The function to execute.
            on_complete: Callback function to be called on the main thread upon success.
                         It receives the result of the target_function as its argument.
            on_error: Callback function to be called on the main thread upon an exception.
                      It receives the exception object as its argument.
            *args: Positional arguments for the target function.
            **kwargs: Keyword arguments for the target function.
        """
        future = self.executor.submit(self._job_wrapper, target_function, on_complete, on_error, *args, **kwargs)
        return future

    def _job_wrapper(self, target_function: Callable, on_complete: Optional[Callable], on_error: Optional[Callable], *args, **kwargs):
        """
        Wrapper that executes the target function and handles callbacks.
        """
        try:
            result = target_function(*args, **kwargs)
            if on_complete:
                wx.CallAfter(on_complete, result)
        except Exception as e:
            if on_error:
                wx.CallAfter(on_error, e)
            else:
                import traceback
                print("Unhandled exception in background task:")
                traceback.print_exc()

    def shutdown(self, wait=True):
        """Shuts down the thread pool."""
        self.executor.shutdown(wait=wait)

_task_manager: Optional[TaskManager] = None

def get_task_manager() -> TaskManager:
    """
    Get the global TaskManager instance.
    """
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager