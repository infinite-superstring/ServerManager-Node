from peewee import Model, UUIDField ,CharField, IntegerField, SqliteDatabase

database = SqliteDatabase('database.db')

class Task(Model):
    uuid = UUIDField(primary_key=True, unique=True)
    count = IntegerField(null=False, default=0)

    class Meta:
        database = database

if __name__ == '__main__':
    database.create_tables([Task])
