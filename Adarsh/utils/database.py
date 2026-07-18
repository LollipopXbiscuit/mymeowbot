#(c) Adarsh-Goel
import datetime
import motor.motor_asyncio


class Database:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.users

    def new_user(self, id):
        return dict(
            id=id,
            join_date=datetime.date.today().isoformat()
        )

    async def add_user(self, id):
        user = self.new_user(id)
        await self.col.insert_one(user)
        
    async def add_user_pass(self, id, ag_pass):
        if not await self.is_user_exist(int(id)):
            await self.add_user(int(id))
        await self.col.update_one({'id': int(id)}, {'$set': {'ag_p': ag_pass}})

    async def delete_user(self, id):
        await self.col.delete_one({'id': int(id)})
    
    async def get_user_pass(self, id):
        user_pass = await self.col.find_one({'id': int(id)})
        return user_pass.get("ag_p", None) if user_pass else None
    
    async def is_user_exist(self, id):
        user = await self.col.find_one({'id': int(id)})
        return True if user else False

    async def total_users_count(self):
        count = await self.col.count_documents({})
        return count

    async def get_all_users(self):
        all_users = self.col.find({})
        return all_users

    async def add_group_user(self, group_id, user_id, username):
        group_col = self.db[f"group_{group_id}"]
        await group_col.update_one(
            {'id': user_id},
            {'$set': {'username': username}},
            upsert=True
        )

    async def get_random_group_user(self, group_id):
        group_col = self.db[f"group_{group_id}"]
        pipeline = [{'$sample': {'size': 1}}]
        async for doc in group_col.aggregate(pipeline):
            return doc
        return None

    async def add_group_message(self, group_id, text):
        """Store a member's message text for the echo-reply feature (capped at 500 per group)."""
        col = self.db[f"msgs_{group_id}"]
        await col.insert_one({'text': text})
        # Keep only the most recent 500 messages
        count = await col.count_documents({})
        if count > 500:
            oldest = await col.find_one(sort=[('_id', 1)])
            if oldest:
                await col.delete_one({'_id': oldest['_id']})

    async def get_random_group_message(self, group_id):
        """Return a random stored message text, or None if none stored."""
        col = self.db[f"msgs_{group_id}"]
        async for doc in col.aggregate([{'$sample': {'size': 1}}]):
            return doc.get('text')
        return None

    async def save_user_memory(self, user_id: int, mem: dict):
        """Persist a user's memory profile (name, likes, dislikes, word_freq)."""
        payload = {k: v for k, v in mem.items() if k != '_id'}
        await self.db.user_memory.update_one(
            {'user_id': int(user_id)},
            {'$set': payload},
            upsert=True,
        )

    async def get_user_memory(self, user_id: int) -> dict | None:
        """Return stored memory for a user, or None if not found."""
        doc = await self.db.user_memory.find_one({'user_id': int(user_id)})
        if doc:
            doc.pop('_id', None)
        return doc

    async def get_all_memory_profiles(self) -> list:
        """Return all stored memory profiles (user_id, name, likes, dislikes)."""
        profiles = []
        async for doc in self.db.user_memory.find({}, {'_id': 0, 'word_freq': 0}):
            profiles.append(doc)
        return profiles

    # ── Allowed groups allowlist ──────────────────────────────────────────────

    async def add_allowed_group(self, group_id: int):
        await self.db.allowed_groups.update_one(
            {'group_id': int(group_id)},
            {'$set': {'group_id': int(group_id)}},
            upsert=True,
        )

    async def remove_allowed_group(self, group_id: int):
        await self.db.allowed_groups.delete_one({'group_id': int(group_id)})

    async def is_group_allowed(self, group_id: int) -> bool:
        doc = await self.db.allowed_groups.find_one({'group_id': int(group_id)})
        return doc is not None

    async def get_allowed_groups(self) -> list:
        return [doc['group_id'] async for doc in self.db.allowed_groups.find({})]

    # ── Files ─────────────────────────────────────────────────────────────────

    async def add_file(self, file_info):
        return await self.db.files.insert_one(file_info)

    async def get_file(self, secure_hash):
        return await self.db.files.find_one({'file_unique_id': secure_hash})
