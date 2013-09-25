# -*- coding: utf-8 -*-

import unittest

from time import sleep
from datetime import datetime, timedelta
from flask import Flask
from coaster.sqlalchemy import (BaseMixin, BaseNameMixin, BaseScopedNameMixin,
    BaseIdNameMixin, BaseScopedIdMixin, BaseScopedIdNameMixin, JsonDict,
    MarkdownColumn, MarkdownComposite)
from coaster.gfm import markdown
from coaster.db import db
from sqlalchemy import Column, Integer, Unicode, UniqueConstraint, ForeignKey
from sqlalchemy.orm import relationship, synonym
from sqlalchemy.exc import IntegrityError


app1 = Flask(__name__)
app1.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
app2 = Flask(__name__)
app2.config['SQLALCHEMY_DATABASE_URI'] = 'postgres://:@localhost:5432/coaster_test'
db.init_app(app1)
db.init_app(app2)


# --- Models ------------------------------------------------------------------
class BaseContainer(db.Model):
    __tablename__ = 'base_container'
    id = Column(Integer, primary_key=True)
    name = Column(Unicode(80), nullable=True)


class Container(BaseMixin, db.Model):
    __tablename__ = 'container'
    name = Column(Unicode(80), nullable=True)
    title = Column(Unicode(80), nullable=True)

    content = Column(Unicode(250))


class UnnamedDocument(BaseMixin, db.Model):
    __tablename__ = 'unnamed_document'
    container_id = Column(Integer, ForeignKey('container.id'))
    container = relationship(Container)

    content = Column(Unicode(250))


class NamedDocument(BaseNameMixin, db.Model):
    __tablename__ = 'named_document'
    container_id = Column(Integer, ForeignKey('container.id'))
    container = relationship(Container)

    content = Column(Unicode(250))


class ScopedNamedDocument(BaseScopedNameMixin, db.Model):
    __tablename__ = 'scoped_named_document'
    container_id = Column(Integer, ForeignKey('container.id'))
    container = relationship(Container)
    parent = synonym('container')

    content = Column(Unicode(250))
    __table_args__ = (UniqueConstraint('name', 'container_id'),)


class IdNamedDocument(BaseIdNameMixin, db.Model):
    __tablename__ = 'id_named_document'
    container_id = Column(Integer, ForeignKey('container.id'))
    container = relationship(Container)

    content = Column(Unicode(250))


class ScopedIdDocument(BaseScopedIdMixin, db.Model):
    __tablename__ = 'scoped_id_document'
    container_id = Column(Integer, ForeignKey('container.id'))
    container = relationship(Container)
    parent = synonym('container')

    content = Column(Unicode(250))
    __table_args__ = (UniqueConstraint('url_id', 'container_id'),)


class ScopedIdNamedDocument(BaseScopedIdNameMixin, db.Model):
    __tablename__ = 'scoped_id_named_document'
    container_id = Column(Integer, ForeignKey('container.id'))
    container = relationship(Container)
    parent = synonym('container')

    content = Column(Unicode(250))
    __table_args__ = (UniqueConstraint('url_id', 'container_id'),)


class User(BaseMixin, db.Model):
    __tablename__ = 'user'
    username = Column(Unicode(80), nullable=False)


class MyData(db.Model):
    __tablename__ = 'my_data'
    id = Column(Integer, primary_key=True)
    data = Column(JsonDict)


class MarkdownData(db.Model):
    __tablename__ = 'md_data'
    id = Column(Integer, primary_key=True)
    value = MarkdownColumn('value', nullable=False)

    def __init__(self, **kwargs):
        kwargs['value'] = MarkdownComposite(kwargs.get('value', ''))
        super(MarkdownData, self).__init__(**kwargs)


# -- Tests --------------------------------------------------------------------


class TestCoasterModels(unittest.TestCase):
    app = app1

    def setUp(self):
        self.ctx = self.app.test_request_context()
        self.ctx.push()
        db.create_all()
        self.session = db.session

    def tearDown(self):
        self.session.rollback()
        db.drop_all()
        self.ctx.pop()

    def make_container(self):
        c = Container()
        self.session.add(c)
        return c

    def test_container(self):
        c = self.make_container()
        self.assertEqual(c.id, None)
        self.session.commit()
        self.assertEqual(c.id, 1)

    def test_timestamp(self):
        now1 = datetime.utcnow()
        # The db may not store microsecond precision, so sleep at least 1 second
        # to ensure adequate gap between operations
        sleep(1)
        c = self.make_container()
        self.session.commit()
        u = c.updated_at
        sleep(1)
        now2 = datetime.utcnow()
        self.assertTrue(now1 < c.created_at)
        self.assertTrue(now2 > c.created_at)
        c.content = u"updated"
        sleep(1)
        self.session.commit()
        self.assertTrue(c.updated_at > now2)
        self.assertTrue(c.updated_at > c.created_at)
        self.assertTrue(c.updated_at > u)

    def test_unnamed(self):
        c = self.make_container()
        d = UnnamedDocument(content=u"hello", container=c)
        self.session.add(d)
        self.session.commit()
        self.assertEqual(c.id, 1)
        self.assertEqual(d.id, 1)

    def test_named(self):
        """Named documents have globally unique names."""
        c1 = self.make_container()
        d1 = NamedDocument(title=u"Hello", content=u"World", container=c1)
        self.session.add(d1)
        self.session.commit()
        self.assertEqual(d1.name, u'hello')

        c2 = self.make_container()
        d2 = NamedDocument(title=u"Hello", content=u"Again", container=c2)
        self.session.add(d2)
        self.session.commit()
        self.assertEqual(d2.name, u'hello1')
        # check make_name() modified `name` parameter or not, since `name` value already exists.
        name = d2.name
        d2.make_name()
        self.assertEqual(d2.name, name)

    def test_scoped_named(self):
        """Scoped named documents have names unique to their containers."""
        c1 = self.make_container()
        d1 = ScopedNamedDocument(title=u"Hello", content=u"World", container=c1)
        u = User(username="foo")
        self.session.add(d1)
        self.session.commit()
        self.assertEqual(d1.name, u'hello')
        self.assertEqual(d1.make_name(), None)
        self.assertEqual(d1.permissions(user=u), set([]))
        self.assertEqual(d1.permissions(user=u, inherited=set(['view'])), set(['view']))

        d2 = ScopedNamedDocument(title=u"Hello", content=u"Again", container=c1)
        self.session.add(d2)
        self.session.commit()
        self.assertEqual(d2.name, u'hello1')

        c2 = self.make_container()
        d3 = ScopedNamedDocument(title=u"Hello", content=u"Once More", container=c2)
        self.session.add(d3)
        self.session.commit()
        self.assertEqual(d3.name, u'hello')

        c3 = BaseContainer()
        self.session.add(c3)
        d4 = ScopedNamedDocument(title=u"Hello", container=c3)
        self.session.commit()
        self.assertEqual(d4.permissions(user=u), set([]))

    def test_scoped_named_short_title(self):
        """Test the short_title method of BaseScopedNameMixin."""
        c1 = self.make_container()
        d1 = ScopedNamedDocument(title=u"Hello", content=u"World", container=c1)
        self.assertEqual(d1.short_title(), u"Hello")

        c1.title = u"Container"
        d1.title = u"Container Contained"
        self.assertEqual(d1.short_title(), u"Contained")

    def test_id_named(self):
        """Documents with a global id in the URL"""
        c1 = self.make_container()
        d1 = IdNamedDocument(title=u"Hello", content=u"World", container=c1)
        self.session.add(d1)
        self.session.commit()
        self.assertEqual(d1.url_name, u'1-hello')

        d2 = IdNamedDocument(title=u"Hello", content=u"Again", container=c1)
        self.session.add(d2)
        self.session.commit()
        self.assertEqual(d2.url_name, u'2-hello')

        c2 = self.make_container()
        d3 = IdNamedDocument(title=u"Hello", content=u"Once More", container=c2)
        self.session.add(d3)
        self.session.commit()
        self.assertEqual(d3.url_name, u'3-hello')

    def test_scoped_id(self):
        """Documents with a container-specific id in the URL"""
        c1 = self.make_container()
        d1 = ScopedIdDocument(content=u"Hello", container=c1)
        u = User(username="foo")
        self.session.add(d1)
        self.assertEqual(d1.permissions(user=u, inherited=set(['view'])), set(['view']))
        self.assertEqual(d1.permissions(user=u), set([]))

        d2 = ScopedIdDocument(content=u"New document", container=c1)
        self.session.add(d2)
        self.session.commit()
        self.assertEqual(d1.url_id, 1)
        self.assertEqual(d2.url_id, 2)

        c2 = self.make_container()
        d3 = ScopedIdDocument(content=u"Once More", container=c2)
        self.session.add(d3)
        self.session.commit()
        self.assertEqual(d3.url_id, 1)

        d4 = ScopedIdDocument(content=u"Third", container=c1)
        self.session.add(d4)
        self.session.commit()
        self.assertEqual(d4.url_id, 3)

    def test_scoped_id_named(self):
        """Documents with a container-specific id and name in the URL"""
        c1 = self.make_container()
        d1 = ScopedIdNamedDocument(title=u"Hello", content=u"World", container=c1)
        self.session.add(d1)
        self.session.commit()
        self.assertEqual(d1.url_name, u'1-hello')

        d2 = ScopedIdNamedDocument(title=u"Hello again", content=u"New name", container=c1)
        self.session.add(d2)
        self.session.commit()
        self.assertEqual(d2.url_name, u'2-hello-again')

        c2 = self.make_container()
        d3 = ScopedIdNamedDocument(title=u"Hello", content=u"Once More", container=c2)
        self.session.add(d3)
        self.session.commit()
        self.assertEqual(d3.url_name, u'1-hello')

        d4 = ScopedIdNamedDocument(title=u"Hello", content=u"Third", container=c1)
        self.session.add(d4)
        self.session.commit()
        self.assertEqual(d4.url_name, u'3-hello')

    def test_scoped_id_without_parent(self):
        d1 = ScopedIdDocument(content=u"Hello")
        self.session.add(d1)
        self.assertRaises(IntegrityError, self.session.commit)
        self.session.rollback()
        d2 = ScopedIdDocument(content=u"Hello again")
        self.session.add(d2)
        self.assertRaises(IntegrityError, self.session.commit)

    def test_scoped_named_without_parent(self):
        d1 = ScopedNamedDocument(title=u"Hello", content=u"World")
        self.session.add(d1)
        self.assertRaises(IntegrityError, self.session.commit)
        self.session.rollback()
        d2 = ScopedIdNamedDocument(title=u"Hello", content=u"World")
        self.session.add(d2)
        self.assertRaises(IntegrityError, self.session.commit)

    def test_delayed_name(self):
        c = self.make_container()
        d1 = NamedDocument(container=c)
        d1.title = u'Document 1'
        d1.make_name()
        self.session.add(d1)
        d2 = ScopedNamedDocument(container=c)
        d2.title = u'Document 2'
        d2.make_name()
        self.session.add(d2)
        d3 = IdNamedDocument(container=c)
        d3.title = u'Document 3'
        d3.make_name()
        self.session.add(d3)
        d4 = ScopedIdNamedDocument(container=c)
        d4.title = u'Document 4'
        d4.make_name()
        self.session.add(d4)
        self.session.commit()

    def test_has_timestamps(self):
        # Confirm that a model with multiple base classes between it and
        # TimestampMixin still has created_at and updated_at
        c = self.make_container()
        d = ScopedIdNamedDocument(title=u"Hello", content=u"World", container=c)
        self.session.add(d)
        self.session.commit()
        self.assertTrue(d.created_at is not None)
        self.assertTrue(d.updated_at is not None)
        updated_at = d.updated_at
        self.assertTrue(d.updated_at - d.created_at < timedelta(seconds=1))
        self.assertTrue(isinstance(d.created_at, datetime))
        self.assertTrue(isinstance(d.updated_at, datetime))
        d.title = u"Updated hello"
        self.session.commit()
        self.assertTrue(d.updated_at > updated_at)

    def test_url_for(self):
        d = UnnamedDocument(content=u"hello")
        self.assertEqual(d.url_for(), None)

    def test_jsondict(self):
        m1 = MyData(data={'value': 'foo'})
        self.session.add(m1)
        self.session.commit()
        #Test for __setitem__
        m1.data['value'] = 'bar'
        self.assertEqual(m1.data['value'], 'bar')
        del m1.data['value']
        self.assertEqual(m1.data, {})
        self.assertRaises(ValueError, MyData, data='NonDict')

    def test_markdown_column(self):
        text = u"""# this is going to be h1.\n- Now a list. \n- 1\n- 2\n- 3"""
        data = MarkdownData(value=text)
        self.session.add(data)
        self.session.commit()
        self.assertEqual(data.value.html, markdown(text))
        self.assertEqual(data.value.text, text)
        self.assertEqual(data.value.__str__(), text)
        self.assertEqual(data.value.__html__(), markdown(text))


class TestCoasterModels2(TestCoasterModels):
    app = app2


if __name__ == '__main__':
    unittest.main()
