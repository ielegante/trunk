import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class RedisConfig:
    """Configuration management for Redis connection"""

    def __init__(self):
        self.host = os.getenv("REDIS_HOST", "localhost")
        self.port = int(os.getenv("REDIS_PORT", 6379))
        self.password = os.getenv("REDIS_PASSWORD", "redispassword")
        self.db = int(os.getenv("REDIS_DB", 0))
        self.max_connections = int(os.getenv("REDIS_MAX_CONNECTIONS", 20))
        self.socket_timeout = int(os.getenv("REDIS_SOCKET_TIMEOUT", 5))
        self.retry_on_timeout = True
        self.health_check_interval = 30


class RedisConnection:
    """Redis connection management with health monitoring"""

    def __init__(self, config: RedisConfig):
        self.config = config
        self._pool: Optional[redis.ConnectionPool] = None
        self._client: Optional[redis.Redis] = None

    async def connect(self) -> redis.Redis:
        """Establish connection to Redis"""
        if self._client is None:
            try:
                # Create connection pool
                self._pool = redis.ConnectionPool(
                    host=self.config.host,
                    port=self.config.port,
                    password=self.config.password,
                    db=self.config.db,
                    max_connections=self.config.max_connections,
                    socket_timeout=self.config.socket_timeout,
                    retry_on_timeout=self.config.retry_on_timeout,
                    health_check_interval=self.config.health_check_interval,
                )

                # Create Redis client
                self._client = redis.Redis(connection_pool=self._pool)

                # Test connection
                await self._client.ping()
                logger.info(
                    f"Connected to Redis at {self.config.host}:{self.config.port}"
                )

            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise ConnectionError(f"Redis connection failed: {e}")

        return self._client

    async def close(self):
        """Close Redis connections"""
        if self._client:
            await self._client.aclose()
            self._client = None
        if self._pool:
            await self._pool.aclose()
            self._pool = None
        logger.info("Redis connections closed")

    async def health_check(self) -> bool:
        """Check Redis connection health"""
        try:
            if self._client:
                await self._client.ping()
                return True
            return False
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False

    @asynccontextmanager
    async def get_client(self):
        """Context manager for Redis client"""
        client = await self.connect()
        try:
            yield client
        except Exception as e:
            logger.error(f"Redis operation failed: {e}")
            raise
        finally:
            # Connection is managed by the pool, no need to close here
            pass


# Global Redis connection instance
_redis_config = RedisConfig()
_redis_connection = RedisConnection(_redis_config)


async def get_redis_client() -> redis.Redis:
    """Dependency to get Redis client"""
    return await _redis_connection.connect()


async def init_redis():
    """Initialize Redis connection"""
    try:
        await _redis_connection.connect()
        logger.info("Redis initialization completed")
    except Exception as e:
        logger.error(f"Redis initialization failed: {e}")
        raise


async def close_redis():
    """Close Redis connections"""
    await _redis_connection.close()
