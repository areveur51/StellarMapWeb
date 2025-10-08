import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor

import requests
import sentry_sdk

class StellarMapAsyncHelpers:

    def execute_async(self, *args, **kwargs):
        """
        Executes a task asynchronously using a thread pool executor.

        :param args: Arguments to pass to the task function.
        :param kwargs: Keyword arguments to pass to the task function.
        :return: None
        """

        loop = asyncio.get_event_loop()

        future = asyncio.ensure_future(self.add_task_to_threadpool(*args, **kwargs))
        
        loop.run_until_complete(future)

    async def add_task_to_threadpool(self, task_list, custom_function, *args, **kwargs):
        """
        This function runs a list of tasks asynchronously using a custom async function.

        :param self: The object instance of the class method.
        :param task_list: The list of objects to be used as tasks.
        :param custom_function: The async function to execute on each task.
        :param args: The non-keyword arguments for the custom function.
        :param kwargs: The keyword arguments for the custom function.

        Creates async tasks by calling the custom_function for each item in task_list,
        then awaits all tasks concurrently using asyncio.gather. The session parameter
        is passed for compatibility but may not be used by all async functions.
        """

        try:
            with requests.Session() as session:
                # Create async tasks directly - custom_function is an async coroutine
                tasks = [
                    custom_function(session, obj, *args, **kwargs)
                    for obj in task_list
                ]

                # Await all tasks concurrently
                results = await asyncio.gather(*tasks)
                for response in results:
                    print('Success')
        except Exception as e:
            sentry_sdk.capture_exception(e)
            raise ValueError(f'StellarMapAsyncHelpers.add_task_to_threadpool Error: {e}')
