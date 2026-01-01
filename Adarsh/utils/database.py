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
        await self.add_user(int(id))
        await self.col.update_one({'id': int(id)}, {'$set': {'ag_p': ag_pass}})
    
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

    async def add_file(self, file_info):
        return await self.db.files.insert_one(file_info)

    async def get_file(self, secure_hash):
        return await self.db.files.find_one({'file_unique_id': secure_hash})
