#!/usr/bin/python
# Author: Erlon R. Cruz <erlon@canonical.com>

import datetime

from sqlalchemy import Column, Integer, String, create_engine, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DB_FILE = "automaas.db"

engine = create_engine("sqlite:///{}".format(DB_FILE))


Session = sessionmaker(bind=engine)
Base = declarative_base()


class AutoMaasServer(Base):
    __tablename__ = t = 'AutoMaasServer'
    session = Session()

    id = Column(Integer, primary_key=True)
    name = Column('name', String(32))
    macaddr = Column('macaddr', String(32))
    group = Column('group', String(32))
    created = Column('created', Date())

    @staticmethod
    def all():
        return AutoMaasServer.session.query(AutoMaasServer).all()

    @staticmethod
    def factory(name, group):
        obj = AutoMaasServer(name, group)
        obj.save()
        return obj

    def __init__(self, name, group):
        self.name = name
        self.group = group
        self.created = datetime.datetime.now(datetime.timezone.utc)

    def save(self):
        self.session.add(self)
        self.session.commit()

    def delete(self):
        self.session.query(AutoMaasServer).filter(
                AutoMaasServer.id == self.id).delete()
        self.session.commit()


Base.metadata.create_all(engine)

