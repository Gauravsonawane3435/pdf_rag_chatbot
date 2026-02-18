import redis
import json
import os
from hashlib import md5

class CacheService:
    def __init__(self):
        self.redis_client = None
        try:
            self.redis_client = redis.Redis(
                host=os.getenv('REDIS_HOST', 'localhost'),
                port=int(os.getenv('REDIS_PORT', 6379)),
                password=os.getenv('REDIS_PASSWORD', None),
                decode_responses=True
            )
            # Test connection
            self.redis_client.ping()
        except Exception as e:
            print(f"Redis not available: {e}. Falling back to in-memory cache.")
            self.memory_cache = {}

    def get_cache_key(self, session_id, query):
        query_hash = md5(query.encode()).hexdigest()
        return f"rag_cache:{session_id}:{query_hash}"

    def get(self, session_id, query):
        key = self.get_cache_key(session_id, query)
        if self.redis_client:
            try:
                data = self.redis_client.get(key)
                return json.loads(data) if data else None
            except:
                return None
        return self.memory_cache.get(key)

    def set(self, session_id, query, response, ttl=3600):
        key = self.get_cache_key(session_id, query)
        data = json.dumps(response)
        if self.redis_client:
            try:
                self.redis_client.setex(key, ttl, data)
                return
            except:
                pass
        self.memory_cache[key] = response

    def clear_session(self, session_id):
        """Remove all cached items for a specific session."""
        if self.redis_client:
            try:
                # Find all keys for this session
                pattern = f"rag_cache:{session_id}:*"
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
            except Exception as e:
                print(f"Error clearing Redis cache: {e}")
        
        # Clear from memory cache
        prefix = f"rag_cache:{session_id}:"
        to_delete = [k for k in self.memory_cache.keys() if k.startswith(prefix)]
        for k in to_delete:
            del self.memory_cache[k]
