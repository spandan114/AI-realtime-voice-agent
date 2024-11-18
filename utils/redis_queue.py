from rq import Queue
from redis import Redis

class RedisQueue:
    def __init__(self, queue_name, redis_host='localhost', redis_port=6379, redis_db=0):
        """
        Initializes the RedisQueue instance using RQ and Redis.

        :param queue_name: Name of the Redis queue.
        :param redis_host: Hostname of the Redis server.
        :param redis_port: Port of the Redis server.
        :param redis_db: Redis database index.
        """
        self.queue_name = queue_name
        self.redis_conn = Redis(host=redis_host, port=redis_port, db=redis_db)
        self.queue = Queue(queue_name, connection=self.redis_conn)

    def enqueue(self, func, *args, **kwargs):
        """
        Adds a task to the queue.

        :param func: The function to be executed.
        :param args: Positional arguments for the function.
        :param kwargs: Keyword arguments for the function.
        """
        return self.queue.enqueue(func, *args, **kwargs)

    def size(self):
        """
        Gets the current size of the queue.

        :return: The size of the queue.
        """
        return len(self.queue)

    def empty(self):
        """
        Clears all jobs in the queue.
        """
        for job in self.queue.jobs:
            job.delete()

    def list_jobs(self):
        """
        Lists all jobs in the queue.

        :return: A list of job IDs.
        """
        return [job.id for job in self.queue.jobs]