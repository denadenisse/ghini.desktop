#
# test.py
#
# Description: test for bauble.utils

import sys
import unittest

from sqlalchemy import *

import bauble
import bauble.db as db
from bauble.error import check, CheckConditionError
import bauble.utils as utils
from bauble.utils.log import debug
from bauble.test import BaubleTestCase
from bauble.utils.pyparsing import *

class UtilsGTKTests(unittest.TestCase):

    def itest_create_message_details_dialog(self):
        """
        Interactive test for bauble.utils.create_message_details_dialog()
        """
        d = utils.create_message_details_dialog('msg', 'details')
        d.run()


    def test_search_tree_model(self):
        """
        Test bauble.utils.search_tree_model
        """
        import gtk
        model = gtk.TreeStore(str)

        # the rows that should be found
        to_find = []

        row = model.append(None, ['1'])
        model.append(row, ['1.1'])
        to_find.append(model.append(row, ['something']))
        model.append(row, ['1.3'])

        row = model.append(None, ['2'])
        to_find.append(model.append(row, ['something']))
        model.append(row, ['2.1'])

        to_find.append(model.append(None, ['something']))

        root = model.get_iter_root()
        results = utils.search_tree_model(model[root], 'something')
        self.assert_(sorted([model.get_path(r) for r in results]),
                     sorted(to_find))



class UtilsTests(unittest.TestCase):

    def test_xml_safe(self):
        """
        Test bauble.utils.xml_safe
        """
        class test(object):
            def __str__(self):
                return repr(self)
            def __unicode__(self):
                return repr(self)

        import re
        assert re.match('&lt;.*?&gt;', utils.xml_safe(str(test())))
        assert re.match('&lt;.*?&gt;', utils.xml_safe(unicode(test())))
        assert utils.xml_safe('test string') == 'test string'
        assert utils.xml_safe(u'test string') == u'test string'
        assert utils.xml_safe(u'test< string') == u'test&lt; string'
        assert utils.xml_safe('test< string') == 'test&lt; string'

    def test_datetime_to_str(self):
        """
        Test bauble.utils.date_to_str
        """
        from datetime import datetime
        dt = datetime(2008, 12, 1)
        s = utils.date_to_str(dt, 'yyyy.m.d')
        assert s == '2008.12.1', s
        s = utils.date_to_str(dt, 'yyyy.mm.d')
        assert s == '2008.12.1', s
        s = utils.date_to_str(dt, 'yyyy.m.dd')
        assert s == '2008.12.01', s
        s = utils.date_to_str(dt, 'yyyy.mm.dd')
        assert s == '2008.12.01', s

        dt = datetime(2008, 12, 12)
        s = utils.date_to_str(dt, 'yyyy.m.d')
        assert s == '2008.12.12', s
        s = utils.date_to_str(dt, 'yyyy.mm.d')
        assert s == '2008.12.12', s
        s = utils.date_to_str(dt, 'yyyy.m.dd')
        assert s == '2008.12.12', s
        s = utils.date_to_str(dt, 'yyyy.mm.dd')
        assert s == '2008.12.12', s

        dt = datetime(2008, 1, 1)
        s = utils.date_to_str(dt, 'yyyy.m.d')
        assert s == '2008.1.1', s
        s = utils.date_to_str(dt, 'yyyy.mm.d')
        assert s == '2008.01.1', s
        s = utils.date_to_str(dt, 'yyyy.m.dd')
        assert s == '2008.1.01', s
        s = utils.date_to_str(dt, 'yyyy.mm.dd')
        assert s == '2008.01.01', s

        dt = datetime(2008, 1, 12)
        s = utils.date_to_str(dt, 'yyyy.m.d')
        assert s == '2008.1.12', s
        s = utils.date_to_str(dt, 'yyyy.mm.d')
        assert s == '2008.01.12', s
        s = utils.date_to_str(dt, 'yyyy.m.dd')
        assert s == '2008.1.12', s
        s = utils.date_to_str(dt, 'yyyy.mm.dd')
        assert s == '2008.01.12', s


    def test_range_builder(self):
        """Test bauble.utils.range_builder
        """
        assert utils.range_builder('1-3') == [1, 2, 3]
        assert utils.range_builder('1-3,5-7') == [1, 2, 3, 5, 6 ,7]
        assert utils.range_builder('1-3,5') == [1, 2, 3, 5]
        assert utils.range_builder('1-3,5,7-9')== [1, 2, 3, 5, 7, 8, 9]
        assert utils.range_builder('1,2,3,4') == [1, 2, 3, 4]

        # bad ranges
        self.assertRaises(ParseException, utils.range_builder, '-1')
        self.assertRaises(CheckConditionError, utils.range_builder, '2-1')
        self.assertRaises(ParseException, utils.range_builder, 'a-b')



class UtilsDBTests(BaubleTestCase):

    def test_find_dependent_tables(self):
        """
        Test bauble.utils.find_dependent_tables
        """
        metadata = MetaData()
        metadata.bind = db.engine

        # table1 does't depend on any tables
        table1 = Table('table1', metadata,
                       Column('id', Integer, primary_key=True))

        # table2 depends on table1
        table2 = Table('table2', metadata,
                       Column('id', Integer, primary_key=True),
                       Column('table1', Integer, ForeignKey('table1.id')))

        # table3 depends on table2
        table3 = Table('table3', metadata,
                       Column('id', Integer, primary_key=True),
                       Column('table2', Integer, ForeignKey('table2.id')),
                       Column('table4', Integer, ForeignKey('table4.id'))
                       )

        # table4 depends on table2
        table4 = Table('table4', metadata,
                       Column('id', Integer, primary_key=True),
                       Column('table2', Integer, ForeignKey('table2.id')))

        # tables that depend on table 1 are 3, 4, 2
        depends = list(utils.find_dependent_tables(table1, metadata))
        print 'table1: %s' % [table.name for table in depends]
        self.assert_(list(depends) == [table2, table4, table3])

        # tables that depend on table 2 are 3, 4
        depends = list(utils.find_dependent_tables(table2, metadata))
        print 'table2: %s' % [table.name for table in depends]
        self.assert_(depends == [table4, table3])

        # no tables depend on table 3
        depends = list(utils.find_dependent_tables(table3, metadata))
        print 'table3: %s' % [table.name for table in depends]
        self.assert_(depends == [])

        # table that depend on table 4 are 3
        depends = list(utils.find_dependent_tables(table4, metadata))
        print 'table4: %s' % [table.name for table in depends]
        self.assert_(depends == [table3])



class ResetSequenceTests(BaubleTestCase):

    def setUp(self):
        super(ResetSequenceTests, self).setUp()
        self.metadata = MetaData()
        self.metadata.bind  = db.engine
        self.currval_stmt = None

        # self.currval_stmt should return 2
        if db.engine.name == 'postgres':
            self.currval_stmt = "SELECT currval(%s)"
        elif db.engine.name == 'sqlite':
            # assume sqlite just works
            self.currval_stmt = 'select 2'
        self.conn = db.engine.contextual_connect()


    def tearDown(self):
        super(ResetSequenceTests, self).tearDown()
        self.metadata.drop_all()
        self.conn.close()


    def test_no_col_sequence(self):
        """
        test utils.reset_sequence on a column without a Sequence()
        """
        # test that a column without a sequence works
        self.table = Table('test_reset_sequence', self.metadata,
                           Column('id', Integer, primary_key=True))
        self.metadata.create_all()
        self.insert = self.table.insert().compile()
        self.conn.execute(self.insert, values=[{'id': 1}])
        utils.reset_sequence(self.table.c.id)
        currval = self.conn.execute(self.currval_stmt).fetchone()[0]
        self.assert_(currval > 1)


    def test_with_col_sequence(self):
        """
        test utils.reset_sequence on a column that has an Sequence()
        """
        self.table = Table('test_reset_sequence', self.metadata,
                           Column('id', Integer,
                                  Sequence('test_reset_sequence_id'),
                                  primary_key=True))
        self.metadata.create_all()
        self.insert = self.table.insert().compile()
        self.conn.execute(self.insert, values=[{'id': 1}])
        utils.reset_sequence(self.table.c.id)
        currval = self.conn.execute(self.currval_stmt).fetchone()[0]
        self.assert_(currval > 1)


