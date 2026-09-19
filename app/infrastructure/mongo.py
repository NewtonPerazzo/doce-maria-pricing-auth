from datetime import timedelta

from pymongo import AsyncMongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError


class MongoIdentityRepository:
    def __init__(self, client: AsyncMongoClient, database: str):
        self.database = client[database]

    async def initialize(self):
        await self.database.users.create_index("email", unique=True)
        await self.database.users.create_index("id", unique=True)
        await self.database.users.create_index("reset_digest", sparse=True)
        await self.database.sessions.create_index("id", unique=True)
        await self.database.sessions.create_index("expires_at", expireAfterSeconds=0)
        await self.database.rate_limits.create_index("expires_at", expireAfterSeconds=0)

    async def create_user(self, user: dict) -> bool:
        try:
            await self.database.users.insert_one(dict(user))
            return True
        except DuplicateKeyError:
            return False

    async def find_user(self, email: str) -> dict | None:
        return await self.database.users.find_one({"email": email})

    async def get_user(self, user_id: str) -> dict | None:
        return await self.database.users.find_one({"id": user_id})

    async def create_session(self, session: dict) -> None:
        await self.database.sessions.insert_one(dict(session))

    async def get_session(self, session_id: str) -> dict | None:
        return await self.database.sessions.find_one({"id": session_id})

    async def rotate_session(self, session_id: str, old_digest: str, new_digest: str, now) -> bool:
        result = await self.database.sessions.update_one(
            {
                "id": session_id,
                "refresh_digest": old_digest,
                "revoked": False,
                "expires_at": {"$gt": now},
            },
            {
                "$set": {"refresh_digest": new_digest, "last_used_at": now},
                "$push": {"used_refresh_digests": {"$each": [old_digest], "$slice": -100}},
            },
        )
        return result.modified_count == 1

    async def revoke_session(self, session_id: str) -> None:
        await self.database.sessions.update_one({"id": session_id}, {"$set": {"revoked": True}})

    async def set_reset(self, user_id: str, digest: str, expires_at) -> None:
        await self.database.users.update_one(
            {"id": user_id},
            {
                "$set": {
                    "reset_digest": digest,
                    "reset_expires_at": expires_at,
                }
            },
        )

    async def reset_password(self, digest: str, password_hash: str, now) -> bool:
        result = await self.database.users.update_one(
            {"reset_digest": digest, "reset_expires_at": {"$gt": now}, "is_active": True},
            {
                "$set": {"password_hash": password_hash, "password_changed_at": now},
                "$inc": {"auth_version": 1},
                "$unset": {"reset_digest": "", "reset_expires_at": ""},
            },
        )
        return result.modified_count == 1

    async def allow_request(self, key: str, now, limit: int) -> bool:
        bucket = int(now.timestamp()) // 60
        identifier = f"{key}:{bucket}"
        try:
            result = await self.database.rate_limits.find_one_and_update(
                {"_id": identifier},
                {"$inc": {"count": 1}, "$setOnInsert": {"expires_at": now + timedelta(minutes=2)}},
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError:
            return False
        return result["count"] <= limit
