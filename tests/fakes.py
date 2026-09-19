from copy import deepcopy


class MemoryIdentityRepository:
    def __init__(self):
        self.users = {}
        self.sessions = {}
        self.requests = {}

    async def create_user(self, user):
        if any(item["email"] == user["email"] for item in self.users.values()):
            return False
        self.users[user["id"]] = deepcopy(user)
        return True

    async def find_user(self, email):
        return deepcopy(
            next((item for item in self.users.values() if item["email"] == email), None)
        )

    async def get_user(self, user_id):
        return deepcopy(self.users.get(user_id))

    async def create_session(self, session):
        self.sessions[session["id"]] = deepcopy(session)

    async def get_session(self, session_id):
        return deepcopy(self.sessions.get(session_id))

    async def rotate_session(self, session_id, old_digest, new_digest, now):
        session = self.sessions[session_id]
        if (
            session["refresh_digest"] != old_digest
            or session["revoked"]
            or session["expires_at"] <= now
        ):
            return False
        session["used_refresh_digests"].append(old_digest)
        session["refresh_digest"] = new_digest
        return True

    async def revoke_session(self, session_id):
        self.sessions[session_id]["revoked"] = True

    async def set_reset(self, user_id, digest, expires_at):
        self.users[user_id].update(reset_digest=digest, reset_expires_at=expires_at)

    async def reset_password(self, digest, password_hash, now):
        for user in self.users.values():
            if (
                user.get("reset_digest") == digest
                and user["reset_expires_at"] > now
                and user["is_active"]
            ):
                user["password_hash"] = password_hash
                user["auth_version"] += 1
                del user["reset_digest"]
                return True
        return False

    async def allow_request(self, key, now, limit):
        key = (key, int(now.timestamp()) // 60)
        self.requests[key] = self.requests.get(key, 0) + 1
        return self.requests[key] <= limit


class CapturingMailer:
    def __init__(self):
        self.messages = []

    async def password_reset(self, email, token):
        self.messages.append((email, token))
