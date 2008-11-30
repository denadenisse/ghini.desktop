#
# view.py
#
# Description: the default view
#
import sys
import re
import traceback
import itertools

import gtk
import gobject
import pango
from sqlalchemy import *
from sqlalchemy.orm import *
import sqlalchemy.sql
import sqlalchemy.exc as saexc
from sqlalchemy.orm.mapper import Mapper
from sqlalchemy.orm.properties import ColumnProperty, PropertyLoader

import bauble
import bauble.db as db
from bauble.error import check, CheckConditionError, BaubleError
from bauble.i18n import *
import bauble.pluginmgr as pluginmgr
import bauble.utils as utils
from bauble.prefs import prefs
from bauble.utils.log import debug, error
from bauble.utils.pyparsing import *

# TODO: should we provide a way to change the results view from list to icon
# and provide an icon type to each type that can be returned and then you could
# double click on an icon to open the children of that type

# use different formatting template for the result view depending on the
# platform
_mainstr_tmpl = '<b>%s</b>'
if sys.platform == 'win32':
    _substr_tmpl = '%s'
else:
    _substr_tmpl = '<small>%s</small>'

#import gc
#gc.enable()
#gc.set_debug(gc.DEBUG_UNCOLLECTABLE|gc.DEBUG_INSTANCES|gc.DEBUG_OBJECTS)
#gc.set_debug(gc.DEBUG_LEAK)

# TODO: reset expander data on expand, the problem is that we don't keep the
# row around that was used to update the infoexpander, if we don't do this
# then we can't update unless the search view updates us, this means that
# the search view would have to register on_expanded on each info expander
# in the infobox

class InfoExpander(gtk.Expander):
    """
    an abstract class that is really just a generic expander with a vbox
    to extend this you just have to implement the update() method
    """

    def __init__(self, label, widgets=None):
        """
        :param label: the name of this info expander, this is displayed on the
        expander's expander
        :param glade_xml: a gtk.glade.XML instace where can find the expanders
        widgets
        """
        super(InfoExpander, self).__init__(label)
        self.vbox = gtk.VBox(False)
        self.vbox.set_border_width(5)
        self.add(self.vbox)
        self.set_expanded(True)
        self.widgets = widgets


    def set_widget_value(self, widget_name, value, markup=True, default=None):
        '''
        a shorthand for L{bauble.utils.set_widget_value()}
        '''
        utils.set_widget_value(self.widgets.glade_xml, widget_name, value,
                               markup, default)


    def update(self, value):
        '''
        This method should be implemented by classes that extend InfoExpander
        '''
        raise NotImplementedError("InfoExpander.update(): not implemented")


class PropertiesExpander(InfoExpander):

    def __init__(self):
        super(PropertiesExpander, self).__init__(_('Properties'))
        table = gtk.Table(rows=4, columns=2)
        table.set_col_spacings(15)
        table.set_row_spacings(8)

        # database id
        id_label = gtk.Label(_("<b>ID:</b>"))
        id_label.set_use_markup(True)
        id_label.set_alignment(1, .5)
        self.id_data = gtk.Label('--')
        self.id_data.set_alignment(0, .5)
        table.attach(id_label, 0, 1, 0, 1)
        table.attach(self.id_data, 1, 2, 0, 1)

        # object type
        type_label = gtk.Label(_("<b>Type:</b>"))
        type_label.set_use_markup(True)
        type_label.set_alignment(1, .5)
        self.type_data = gtk.Label('--')
        self.type_data.set_alignment(0, .5)
        table.attach(type_label, 0, 1, 1, 2)
        table.attach(self.type_data, 1, 2, 1, 2)

        # date created
        created_label = gtk.Label(_("<b>Date created:</b>"))
        created_label.set_use_markup(True)
        created_label.set_alignment(1, .5)
        self.created_data = gtk.Label('--')
        self.created_data.set_alignment(0, .5)
        table.attach(created_label, 0, 1, 2, 3)
        table.attach(self.created_data, 1, 2, 2, 3)

        # date last updated
        updated_label = gtk.Label(_("<b>Last updated:</b>"))
        updated_label.set_use_markup(True)
        updated_label.set_alignment(1, .5)
        self.updated_data = gtk.Label('--')
        self.updated_data.set_alignment(0, .5)
        table.attach(updated_label, 0, 1, 3, 4)
        table.attach(self.updated_data, 1, 2, 3, 4)

        box = gtk.HBox()
        box.pack_start(table, expand=False, fill=False)
        self.vbox.pack_start(box, expand=False, fill=False)


    def update(self, row):
        """"
        Update the widget in the expander.
        """
        self.id_data.set_text(str(row.id))
        self.type_data.set_text(str(type(row).__name__))
        self.created_data.set_text(str(row._created))
        self.updated_data.set_text(str(row._last_updated))




class InfoBoxPage(gtk.ScrolledWindow):
    """
    a VBox with a bunch of InfoExpanders
    """

    def __init__(self):
        super(InfoBoxPage, self).__init__()
        self.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        self.vbox = gtk.VBox()
        self.vbox.set_spacing(10)
        viewport = gtk.Viewport()
        viewport.add(self.vbox)
        self.add(viewport)
        self.expanders = {}
        self.label = None


    def add_expander(self, expander):
        '''
        Add an expander to the list of exanders in this infobox

        :param expander: the bauble.view.InfoExpander to add to this infobox
        '''
        self.vbox.pack_start(expander, expand=False, fill=True, padding=5)
        self.expanders[expander.get_property("label")] = expander

        sep = gtk.HSeparator()
        self.vbox.pack_start(sep, False, False)


    def get_expander(self, label):
        """
        returns an expander by the expander's label name

        :param label: the name of the expander to return
        """
        if label in self.expanders:
            return self.expanders[label]
        else: return None


    def remove_expander(self, label):
        """
        remove expander from the infobox by the expander's label bel

        :param label: the name of th expander to remove
        @return: return the expander that was removed from the infobox
        """
        if label in self.expanders:
            return self.vbox.remove(self.expanders[label])


    def update(self, row):
        """
        updates the infobox with values from row

        :param row: the mapper instance to use to update this infobox,
        this is passed to each of the infoexpanders in turn
        """
        for expander in self.expanders.values():
            expanders.update(row)
        ## TODO: should we just iter over the expanders and update them all
        #raise NotImplementedError


class InfoBox(gtk.Notebook):
    """
    Holds list of expanders with an optional tabbed layout.

    The default is to not use tabs. To create the InfoBox with tabs
    use InfoBox(tabbed=True).  When using tabs then you can either add
    expanders directly to the InfoBoxPage or using
    InfoBox.add_expander with the page_num argument.
    """

    def __init__(self, tabbed=False):
        super(InfoBox, self).__init__()
        self.set_property('show-border', False)
        if not tabbed:
            page = InfoBoxPage()
            self.insert_page(page, position=0)
            self.set_property('show-tabs', False)


    def on_switch_page(self, dummy_page, page_num, *args):
        page = self.get_nth_page(page_num)
        page.update(self.row)


    def add_expander(self, expander, page_num=0):
        page = self.get_nth_page(page_num)
        page.add_expander(expander)


    def update(self, row):
        self.row = row
        page_num = self.get_current_page()
        self.get_nth_page(page_num).update(row)



# TODO: should be able to just to a add_link(uri, description) to
# add buttons
## class LinkExpander(InfoExpander):

##     def __init__(self):
##         super(LinkExpander, self).__init__()

##     def add_button(button):
##         self.vbox.pack_start(button)


class SearchParser(object):
    """
    The parser for bauble.view.MapperSearch
    """

    value_chars = Word(alphanums + '%.-_*')
    # value can contain any string once its quoted
    value = value_chars | quotedString.setParseAction(removeQuotes)
    value_list = (value ^ delimitedList(value) ^ OneOrMore(value))
    binop = oneOf('= == != <> < <= > >= not like contains has ilike '\
                  'icontains ihas')('binop')
    domain = Word(alphas, alphanums)('domain')
    domain_values = Group(value_list.copy())
    domain_expression = (domain + Literal('=') + Literal('*') + StringEnd()) \
                        | (domain + binop + domain_values + StringEnd())

    and_token = CaselessKeyword('and')
    or_token = CaselessKeyword('or')
    log_op = and_token | or_token

    identifier = Group(delimitedList(Word(alphas, alphanums+'_'), '.'))
    ident_expression = Group(identifier + binop + value)
    query_expression = ident_expression \
                       + ZeroOrMore(log_op + ident_expression)
    query = domain + CaselessKeyword('where').suppress() \
            + Group(query_expression) + StringEnd()

    statement = query | domain_expression | value_list


    def parse_string(self, text):
        '''
        returns a pyparsing.ParseResults objects that represents either a
        query, an expression or a list of values
        '''
        return self.statement.parseString(text)



class SearchStrategy(object):
    """
    Interface for adding search strategies to a view.
    """

    def search(self, text, session=None):
        '''
        :param text: the search string
        :param: the session to use for the search

        Return an iterator that iterates over mapped classes retrieved
        from the search.
        '''
        pass



class MapperSearch(SearchStrategy):

    """
    Mapper Search support three types of search expression:
    1. value searches: search that are just list of values, e.g. value1,
    value2, value3, searches all domains and registered columns for values
    2. expression searches: searched of the form domain=value, resolves the
    domain and searches specific columns from the mapping
    3. query searchs: searches of the form domain where ident.ident = value,
    resolve the domain and identifiers and search for value
    """

    _domains = {}
    _properties = {}

    def __init__(self):
        super(MapperSearch, self).__init__()
        self._results = ResultSet()
        self.parser = SearchParser()


    def add_meta(self, domain, cls, properties):
        """
        Adds search meta to the domain

        :param domain: a string, list or tuple of domains that will resolve
        to cls a search string, domain act as a shorthand to the class name
        :param cls: the class the domain will resolve to
        :param properties: a list of string names of the properties to
        search by default
        """
        check(isinstance(properties, list), _('MapperSearch.add_meta(): '\
        'default_columns argument must be list'))
        check(len(properties) > 0, _('MapperSearch.add_meta(): '\
        'default_columns argument cannot be empty'))
        if isinstance(domain, (list, tuple)):
            for d in domain:
                self._domains[d] = cls, properties
        else:
            self._domains[d] = cls, properties
        self._properties[cls] = properties


    def on_query(self, s, loc, tokens):
        """
        Called when the parser hits a query token.
        """
        # We build the queries by fetching the ids of the rows that
        # match the condition and then returning a query to return the
        # object that have ids in the built query.  This might seem
        # like a roundabout way but it works on databases don't
        # support union and/or intersect
        #
        # TODO: support 'not' as well, e.g sp where
        # genus.genus=Maxillaria and not genus.family=Orchidaceae
        domain, expr = tokens
        check(domain in self._domains, 'Unknown search domain: %s' % domain)
        cls = self._domains[domain][0]
        mapper = class_mapper(cls)
        expr_iter = iter(expr)
        op = None
        id_query = self._session.query(cls.id)
        clause = prev_clause = None
        for e in expr_iter:
            idents, cond, val = e
            #debug('idents: %s, cond: %s, val: %s' % (idents, cond, val))
            if len(idents) == 1:
                col = idents[0]
                check(col in mapper.c, 'The %s table does not have a '\
                       'column named %s' % \
                       (mapper.local_table.name, col))
                clause = cls.id.in_(id_query.filter(getattr(cls, col).\
                                           op(cond)(unicode(val))).statement)
            else:
                relations = idents[:-1]
                col = idents[-1]
                # TODO: do all the databases quote the same

                # TODO: need to either stick to a subset of conditions
                # that work on all database or just normalize the
                # conditions depending on the databases

                # TODO: the like condition takes fucking ages here on
                # sqlite if the search query is something like:
                # "children.column like something"
                where = "%s %s '%s'" % (col, cond, val)
                clause = cls.id.in_(id_query.join(*relations).\
                                    filter(where).statement)

            if op is not None:
                check(op in ('and', 'or'), 'Unsupported operator: %s' % op)
                op = getattr(sqlalchemy.sql, '%s_' % op)
                clause = op(prev_clause, clause)
            prev_clause = clause
            try:
                op = expr_iter.next()
            except StopIteration:
                pass
        self._results.add(self._session.query(cls).filter(clause))


    def on_domain_expression(self, s, loc, tokens):
        """
        Called when the parser hits a domain_expression token
        """
        domain, cond, values = tokens
        try:
            cls, properties = self._domains[domain]
        except KeyError:
            raise KeyError(_('Unknown search domain: %s' % domain))

	query = self._session.query(cls)

	# select all objects from the domain
        if values == '*':
            self._results.add(query)
            return

        # TODO: should probably create a normalize_cond() method
        # to convert things like contains and has into like conditions

        # TODO: i think that sqlite uses case insensitve like, there
        # is a pragma to change this so maybe we could send that
        # command first to handle case sensitive and insensitive
        # queries

        # here the equals sign is case insensitive but the double
        # equals is case sensitive

        mapper = class_mapper(cls)

        if db.engine.name == 'postgres':
            like = lambda col, val: \
                mapper.c[col].op('ILIKE')(val)
        else:
            like = lambda col, val: \
                func.upper(mapper.c[col]).like(val)

        if cond in ('like', 'ilike', 'contains', 'icontains', 'has', 'ihas'):
            condition = lambda col: \
                lambda val: like(col, '%%%s%%' % val)
        elif cond == '=':
            condition = lambda col: \
                lambda val: like(col, val)
        else:
            condition = lambda col: \
                lambda val: mapper.c[col].op(cond)(val)

        # TODO: can we use the properties directly instead of using
        # the columns names so that if the properties are setup
        # properly then they could be used directly in the search
        # string
        for col in properties:
            # TODO: i don't know how well this will work out if we're
            # search for numbers
            #
            ors = or_(*map(condition(col), values))
            self._results.add(query.filter(ors))
        return tokens


    def on_value_list(self, s, loc, tokens):
        """
        Called when the parser hits a value_list token
        """
#         debug('on_value_list()')
#         debug('  s: %s' % s)
#         debug('  loc: %s' % loc)
#         debug('  toks: %s' % tokens)
        # TODO: should also combine all the values into a single
        # string and search for that string

        # make searches case-insensitive, in postgres use ilike,
        # in other use upper()
        if db.engine.name == 'postgres':
            like = lambda table, col, val: \
                table.c[col].op('ILIKE')('%%%s%%' % val)
        else:
            like = lambda table, col, val: \
                           func.upper(table.c[col]).like('%%%s%%' % val)
        for cls, columns in self._properties.iteritems():
            q = self._session.query(cls)
            cv = [(c,v) for c in columns for v in tokens]
            # as of SQLAlchemy>=0.4.2 we convert the value to a unicode
            # object if the col is a Unicode or UnicodeText column in order
            # to avoid the "Unicode type received non-unicode bind param"
            def unicol(col, v):
                mapper = class_mapper(cls)
                if isinstance(mapper.c[col].type, (Unicode,UnicodeText)):
                    return unicode(v)
                else:
                    return v
            mapper = class_mapper(cls)
            q = q.filter(or_(*[like(mapper, c, unicol(c, v)) for c,v in cv]))
            #debug(q)
            self._results.add(q)



    def search(self, text, session=None):
        """
        Returns a ResultSet of database hits for the text search string.
        """
        if session is None:
            self._session = bauble.Session()
        else:
            self._session = session

        # this looks kinda ridiculous to add the parse actions and
        # then remove them but then it allows us to reuse the parser
        # for other things, particulary tests, without calling the
        # parse actions
        self.parser.query.setParseAction(self.on_query)
        self.parser.domain_expression.setParseAction(self.on_domain_expression)
        self.parser.value_list.setParseAction(self.on_value_list)

        self._results.clear()
        self.parser.parse_string(text)

        self.parser.query.parseAction = []
        self.parser.domain_expression.parseAction = []
        self.parser.value_list.parseAction = []
        return self._results



# TODO: it would handy if we could support some sort of smart slicing
# where we chould slice across the different sets and still return the
# query values using LIMIT queries
class ResultSet(object):
    '''
    A ResultSet represents a set of results returned from a query, it
    allows you to add results to the set and then iterate over all the
    results as if they were one set.  It will only return objects that
    are unique between all the results.
    '''
    def __init__(self, results=None):
        if results is not None:
            self._results = set(results)
        else:
            self._results = set()


    def add(self, results):
        if isinstance(results, (list, tuple, set)):
            self._results.update(results)
        else:
            self._results.add(results)


    def __len__(self):
        # it's possible, but unlikely that int() can truncate the value
        return int(self.count())


    def count(self):
        '''
        return the number of total results from all of the members of this
        results set, does not take into account duplicate results
        '''
        ctr = 0
        for r in self._results:
            if isinstance(r, Query):
                ctr += r.count()
            elif hasattr(r, '__iter__'):
                ctr += len(r)
            else:
                ctr += 1
        return ctr


    def __iter__(self):
        # If this ResultSet contains other ResultSets that are large
        # we'll be creating lots of large set objects. This shouldn't
        # be too much of a problem since the sets would only be
        # holding references to the same object
        self._iterset = set()
        self._iter = itertools.chain(*self._results)
        return self


    def next(self):
        '''
        returns unique items from the result set
        '''
        v = self._iter.next()
        if v not in self._iterset: # only return unique objects
            self._iterset.add(v)
            return v
        else:
            return self.next()


    def clear(self):
        """
        Clear out the set.
        """
        del self._results
        self._results = set()



class SearchView(pluginmgr.View):

    class ViewMeta(dict):

        class Meta(object):
            def __init__(self):
                self.children = None
                self.infobox = None
                self.context_menu_desc = None
                self.markup_func = None


            def set(self, children=None, infobox=None, context_menu=None,
                    markup_func=None):
                '''
                :param children: where to find the children for this type,
                    can be a callable of the form C{children(row)}
                :param infobox: the infobox for this type
                :param context_menu: a dict describing the context menu used
                when the user right clicks on this type
                :param markup_func: the function to call to markup search
                results of this type, if markup_func is None the instances
                __str__() function is called
                '''
                self.children = children
                self.infobox = infobox
                self.context_menu_desc = context_menu
                self.markup_func = markup_func


            def get_children(self, obj):
                '''
                :param obj: get the children from obj according to
                self.children, the returned object should support __len__,
                if you want to return a query then wrap it in a ResultSet
                '''
                if self.children is None:
                    return []
                if callable(self.children):
                    return self.children(obj)
                return getattr(obj, self.children)


        def __getitem__(self, item):
            if item not in self: # create on demand
                self[item] = self.Meta()
            return self.get(item)

    view_meta = ViewMeta()


    '''
    the search strategy is keyed by domain and each value will be a list of
    SearchStrategy instances
    '''
    search_strategies = [MapperSearch()]

    @classmethod
    def add_search_strategy(cls, strategy):
        cls.search_strategies.append(strategy())


    @classmethod
    def get_search_strategy(cls, name):
        for strategy in cls.search_strategies:
            if strategy.__class__.__name__ == name:
                return strategy


    def __init__(self):
        '''
        the constructor
        '''
        super(SearchView, self).__init__()
        self.create_gui()

        # we only need this for the timeout version of populate_results
        self.populate_callback_id = None

        # the context menu cache holds the context menus by type in the results
        # view so that we don't have to rebuild them every time
        self.context_menu_cache = {}
        self.infobox_cache = {}
        self.infobox = None

        # keep all the search results in the same session, this should
        # be cleared when we do a new search
        self.session = bauble.Session()


    def update_infobox(self):
        '''
        sets the infobox according to the currently selected row
        or remove the infobox is nothing is selected
        '''
        self.set_infobox_from_row(None)
        values = self.get_selected_values()
        if len(values) == 0:
            return
        try:
            self.set_infobox_from_row(values[0])
        except Exception, e:
            debug('SearchView.update_infobox: %s' % e)
            debug(traceback.format_exc())
            debug(values)
            self.set_infobox_from_row(None)


    def set_infobox_from_row(self, row):
        '''
        get the infobox from the view meta for the type of row and
        set the infobox values from row

        :param row: the row to use to update the infobox
        '''
        # remove the current infobox if there is one and stop
#        debug('set_infobox_from_row: %s --  %s' % (row, repr(row)))
        if row is None:
            if self.infobox is not None and self.infobox.parent == self.pane:
                self.pane.remove(self.infobox)
            return

        new_infobox = None
        selected_type = type(row)

        # check if we've already created an infobox of this type,
        # if not create one and put it in self.infobox_cache
        if selected_type in self.infobox_cache.keys():
            new_infobox = self.infobox_cache[selected_type]
        elif selected_type in self.view_meta and \
          self.view_meta[selected_type].infobox is not None:
            new_infobox = self.view_meta[selected_type].infobox()
            self.infobox_cache[selected_type] = new_infobox

        # remove any old infoboxes connected to the pane
        if self.infobox is not None and \
          type(self.infobox) != type(new_infobox):
            if self.infobox.parent == self.pane:
                self.pane.remove(self.infobox)

        # update the infobox and put it in the pane
        self.infobox = new_infobox
        if self.infobox is not None:
            self.pane.pack2(self.infobox, resize=False, shrink=True)
            self.pane.show_all()
            self.infobox.update(row)


    def get_selected_values(self):
        '''
        return all the selected rows
        '''
        model, rows = self.results_view.get_selection().get_selected_rows()
        if model is None:
            return None
        return [model[row][0] for row in rows]


    def on_results_view_select_row(self, view):
        '''
        add and removes the infobox which should change depending on
        the type of the row selected
        '''
        self.update_infobox()


    nresults_statusbar_context = 'searchview.nresults'

##     @staticmethod
##     def dump_garbage():
##         """
##         show us what's the garbage about
##         """

##         # force collection
##         print "\nGARBAGE:"
##         gc.collect()

##         print "\nGARBAGE OBJECTS:"
##         for x in gc.garbage:
##             s = str(x)
##             if len(s) > 80:
##                 s = s[:80]
##             print type(x),"\n  ", s


    def search(self, text):
        '''
        search the database using text
        '''
        # set the text in the entry even though in most cases the entry already
        # has the same text in it, this is in case this method was called from
        # outside the class so the entry and search results match
#        debug('SearchView.search(%s)' % text)

        # TODO: we should cancel any current running searches first

        results = ResultSet()
        error_msg = None
        error_details_msg = None
        self.session.clear() # clear out any old search results
        bold = '<b>%s</b>'
        try:
            for strategy in self.search_strategies:
                results.add(strategy.search(text, self.session))
        except ParseException, err:
            error_msg = _('Error in search string at column %s') % err.column
        except (BaubleError, AttributeError, Exception, SyntaxError), e:
            debug(traceback.format_exc())
            error_msg = _('** Error: %s') % utils.xml_safe_utf8(e)
            error_details_msg = traceback.format_exc()

        if error_msg:
            bauble.gui.error_msg(error_msg, error_details_msg)
            return

        # not error
        utils.clear_model(self.results_view)
        self.set_infobox_from_row(None)
        statusbar = bauble.gui.widgets.statusbar
        sbcontext_id = statusbar.get_context_id('searchview.nresults')
        statusbar.pop(sbcontext_id)
        if len(results) == 0:
            model = gtk.ListStore(str)
            model.append([bold % _('Couldn\'t find anything')])
            self.results_view.set_model(model)
        else:
            if len(results) > 5000:
                msg = _('This query returned %s results.  It may take a '\
                        'long time to get all the data. Are you sure you '\
                        'want to continue?') % len(results)
                if not utils.yes_no_dialog(msg):
                    return
            statusbar.push(sbcontext_id, _("Retrieving %s search " \
                                           "results...") % len(results))
            if len(results) > 1000:
                self.populate_results(results)
            else:
                task = self._populate_worker(results)
                while True:
                    try:
                        task.next()
                    except StopIteration:
                        break
                self.results_view.set_cursor(0)
            statusbar.pop(sbcontext_id)
            statusbar.push(sbcontext_id, _("%s search results") % len(results))


    def remove_children(self, model, parent):
        """
        remove all children of some parent in the model, reverse
        iterate through them so you don't invalidate the iter
        """
        while model.iter_has_child(parent):
            nkids = model.iter_n_children(parent)
            child = model.iter_nth_child(parent, nkids-1)
            model.remove(child)


    def on_test_expand_row(self, view, iter, path, data=None):
        '''
        look up the table type of the selected row and if it has
        any children then add them to the row
        '''
        expand = False
        model = view.get_model()
        row = model.get_value(iter, 0)
        view.collapse_row(path)
        self.remove_children(model, iter)
        try:
            kids = self.view_meta[type(row)].get_children(row)
            if len(kids) == 0:
                return True
        except saexc.InvalidRequestError, e:
#            debug(e)
            model = self.results_view.get_model()
            for found in utils.search_tree_model(model, row):
                model.remove(found.iter)
            return True
        except Exception, e:
            debug(e)
            debug(traceback.format_exc())
            return True
        else:
            self.append_children(model, iter, kids)
            return False


    def populate_results(self, results, check_for_kids=False):
        """
        :param results: a ResultSet instance
        :param check_for_kids: only used for testing

        This method adds results to the search view in a task.
        """
        def on_error(exc):
            error('SearchView.populate_results:')
            error(exc)
        def on_quit():
            try:
                self.results_view.set_cursor(0)
            except Exception, e:
                debug(e)
        return bauble.task.queue(self._populate_worker, on_quit, on_error,
                                 results, check_for_kids)


    def _populate_worker(self, results, check_for_kids=False):
        """
        Generator function for adding the search results to the
        model. This method is usually called by self.populate_results()
        """
        nresults = len(results)
        model = gtk.TreeStore(object)
        model.set_default_sort_func(lambda *args: -1)
        model.set_sort_column_id(-1, gtk.SORT_ASCENDING)
        utils.clear_model(self.results_view)

        # group the results by type. this is where all the results are
        # actually fetched from the database
        groups = []
        for key, group in itertools.groupby(results, lambda x: type(x)):
            groups.append(sorted(group, key=utils.natsort_key))

        chunk_size = 100
        update_every = 200
        steps_so_far = 0

        # iterate over slice of size "steps", yield after adding each
        # slice to the model
        #for obj in itertools.islice(itertools.chain(*groups), 0,None, steps):
        #for obj in itertools.islice(itertools.chain(results), 0,None, steps):
        for obj in itertools.chain(*groups):
            parent = model.append(None, [obj])
            obj_type = type(obj)
            if check_for_kids:
                kids = self.view_meta[obj_type].get_children(obj)
                if len(kids) > 0:
                    model.append(parent, ['-'])
            elif self.view_meta[obj_type].children is not None:
                model.append(parent, ['-'])

            #steps_so_far += chunk_size
            steps_so_far += 1
            if steps_so_far % update_every == 0:
                percent = float(steps_so_far)/float(nresults)
                if 0< percent < 1.0:
                    bauble.gui.progressbar.set_fraction(percent)
                yield
        self.results_view.freeze_child_notify()
        self.results_view.set_model(model)
        self.results_view.thaw_child_notify()


    def append_children(self, model, parent, kids):
        '''
        append object to a parent iter in the model

        :param model: the model the append to
        :param parent:  the parent iter
        :param kids: a list of kids to append
        @return: the model with the kids appended
        '''
        check(parent is not None, "append_children(): need a parent")
        for k in kids:
            i = model.append(parent, [k])
            if self.view_meta[type(k)].children is not None:
                model.append(i, ["_dummy"])
        return model


    def cell_data_func(self, coll, cell, model, iter):
        value = model[iter][0]
#        debug('%s(%s)' % (value, type(value)))
        if isinstance(value, basestring):
            cell.set_property('markup', value)
        else:
            try:
                func = self.view_meta[type(value)].markup_func
                if func is not None:
                    r = func(value)
                    if isinstance(r, (list,tuple)):
                        main, substr = r
                    else:
                        main = r
                        substr = '(%s)' % type(value).__name__
                else:
                    main = str(value)
                    substr = '(%s)' % type(value).__name__
                cell.set_property('markup', '%s\n%s' % \
                                  (_mainstr_tmpl % utils.utf8(main),
                                   _substr_tmpl % utils.utf8(substr)))

            except (saexc.InvalidRequestError, TypeError), e:
                debug(e)
                def remove():
                    model = self.results_view.get_model()
                    self.results_view.set_model(None) # detach model
                    for found in utils.search_tree_model(model, value):
                        treeview_model.remove(found.iter)
                    self.results_view.set_model(treeview_model)
                gobject.idle_add(remove)


    def get_expanded_rows(self):
        '''
        return all the rows in the model that are expanded
        '''
        expanded_rows = []
        self.results_view.map_expanded_rows(lambda view, path: expanded_rows.append(gtk.TreeRowReference(view.get_model(), path)))
        # seems to work better if we passed the reversed rows to
        # self.expand_to_all_refs
        expanded_rows.reverse()
        return expanded_rows


    def expand_to_all_refs(self, references):
        '''
        :param references: a list of TreeRowReferences to expand to

        Note: This method calls get_path() on each
        gtk.TreeRowReference in <references> which apparently
        invalidates the reference.
        '''
        for ref in references:
            if ref.valid():
                self.results_view.expand_to_path(ref.get_path())


    def on_view_button_release(self, view, event, data=None):
        '''
        popup a context menu on the selected row
        '''
        # TODO: should probably fix this so you can right click on something
        # that is not the selection, but get the path from where the click
        # happened, make that that selection and then popup the menu,
        # see the pygtk FAQ about this at
        #http://www.async.com.br/faq/pygtk/index.py?req=show&file=faq13.017.htp
        if event.button != 3:
            return # if not right click then leave

        values = self.get_selected_values()
        model, paths = self.results_view.get_selection().get_selected_rows()
        if len(paths) > 1:
            return
        selected_type = type(values[0])
        if self.view_meta[selected_type].context_menu_desc is None:
            # no context menu
            return

        menu = None
        try:
            menu = self.context_menu_cache[selected_type]
        except:
            menu = gtk.Menu()
            for label, func in self.view_meta[selected_type].context_menu_desc:
                if label == '--':
                    menu.add(gtk.SeparatorMenuItem())
                else:
                    def on_activate(item, f):
                        value = self.get_selected_values()[0]
                        result = False
                        try:
                            result = f(value)
                        except Exception, e:
                            msg = utils.xml_safe_utf8(str(e))
                            utils.message_details_dialog(msg,
                                                        traceback.format_exc(),
                                                         gtk.MESSAGE_ERROR)
                            debug(traceback.format_exc())
                        if result:
                            self.reset_view()
                    item = gtk.MenuItem(label)
                    item.connect('activate', on_activate, func)
                    menu.add(item)
            self.context_menu_cache[selected_type] = menu

        menu.show_all()
        menu.popup(None, None, None, event.button, event.time)


    def reset_view(self):
        """
        expire all the children in the model, collapse everything,
        reexpand the rows to the previous state where possible and
        update the infobox
        """
        # TODO: we should do some profiling to see how this method
        # performs on large datasets
        model, paths = self.results_view.get_selection().get_selected_rows()
        ref = gtk.TreeRowReference(model, paths[0])
        for obj in self.session:
            try:
                self.session.expire(obj)
            except saexc.InvalidRequestError, e:
                    model.remove(found)
        expanded_rows = self.get_expanded_rows()
        self.results_view.collapse_all()
        # expand_to_all_refs will invalidate the ref so get the path first
        path = None
        if ref.valid():
            path = ref.get_path()
        self.expand_to_all_refs(expanded_rows)
        self.results_view.set_cursor(path)



    def on_view_row_activated(self, view, path, column, data=None):
        '''
        expand the row on activation
        '''
        view.expand_row(path, False)


    def create_gui(self):
        '''
        create the interface
        '''
        # create the results view and info box
        self.results_view = gtk.TreeView() # will be a select results row
        self.results_view.set_headers_visible(False)
        self.results_view.set_rules_hint(True)
        #self.results_view.set_fixed_height_mode(True)
        #self.results_view.set_fixed_height_mode(False)

        selection = self.results_view.get_selection()
        selection.set_mode(gtk.SELECTION_MULTIPLE)
        self.results_view.set_rubber_banding(True)

        renderer = gtk.CellRendererText()
        renderer.set_fixed_height_from_font(2)
        renderer.set_property('ellipsize', pango.ELLIPSIZE_END)
        column = gtk.TreeViewColumn("Name", renderer)
        column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        column.set_cell_data_func(renderer, self.cell_data_func)
        self.results_view.append_column(column)

        # view signals
        self.results_view.connect("cursor-changed",
                                  self.on_results_view_select_row)
        self.results_view.connect("test-expand-row",
                                  self.on_test_expand_row)
        self.results_view.connect("button-release-event",
                                  self.on_view_button_release)
        self.results_view.connect("row-activated",
                                  self.on_view_row_activated)
        # scrolled window for the results view
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.add(self.results_view)

        # pane to split the results view and the infobox, the infobox
        # is created when a row in the results is selected
        self.pane = gtk.HPaned()
        self.pane.pack1(sw, resize=True, shrink=True)
        self.pack_start(self.pane)
        self.show_all()



def select_in_search_results(obj):
    """
    :param obj: the object the select
    @returns: a gtk.TreeIter to the selected row

    Search the tree model for obj if it exists then select it if not
    then add it and select it.

    The the obj is not in the model then we add it.
    """
    check(obj != None, 'select_in_search_results: arg is None')
    view = bauble.gui.get_view()
    if not isinstance(view, SearchView):
        return None
    model = view.results_view.get_model()
    found = utils.search_tree_model(model, obj)
    row_iter = None
    if len(found) > 0:
        row_iter = found[0]
    else:
        row_iter = model.append(None, [obj])
        model.append(row_iter, ['-'])
    view.results_view.set_cursor(model.get_path(row_iter))
    return row_iter


class DefaultCommandHandler(pluginmgr.CommandHandler):

    def __init__(self):
        super(DefaultCommandHandler, self).__init__()
        self.view = None

    command = None

    def get_view(self):
        if self.view is None:
            self.view = SearchView()
        return self.view

    def __call__(self, arg):
        self.view.search(arg)

