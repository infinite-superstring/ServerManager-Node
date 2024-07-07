import os.path

from peewee import Model, UUIDField, CharField, ForeignKeyField, DateTimeField, IntegerField, SqliteDatabase
from uuid import uuid4

database = SqliteDatabase(os.path.join(os.getcwd(), "data", 'database.db'))

class Task(Model):
    name = CharField(null=False)
    uuid = CharField(40, primary_key=True, unique=True)
    count = IntegerField(null=False, default=0)
    max_count = IntegerField(null=True, default=0)

    class Meta:
        database = database

if __name__ == '__main__':
    database.create_tables([Task])

    task1 = Task.create(name='Task 1', uuid=uuid4())
