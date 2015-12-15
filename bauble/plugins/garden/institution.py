# -*- coding: utf-8 -*-
#
# Copyright 2008-2010 Brett Adams
# Copyright 2015 Mario Frasca <mario@anche.no>.
#
# This file is part of bauble.classic.
#
# bauble.classic is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# bauble.classic is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with bauble.classic. If not, see <http://www.gnu.org/licenses/>.
#
# Description: edit and store information about the institution in the bauble
# meta
#

import os

import gtk

import logging
logger = logging.getLogger(__name__)

import bauble.editor as editor
import bauble.meta as meta
import bauble.paths as paths
import bauble.pluginmgr as pluginmgr
import bauble.utils as utils
from bauble.i18n import _


class Institution(object):
    '''
    Institution is a "live" object. When properties are changed the changes
    are immediately reflected in the database.

    Institution values are stored in the Bauble meta database and not in
    its own table
    '''
    __properties = ('name', 'abbreviation', 'code',
                    'contact', 'technical_contact', 'email',
                    'tel', 'fax', 'address')

    table = meta.BaubleMeta.__table__

    def __init__(self):
        # initialize properties to None
        map(lambda p: setattr(self, p, None), self.__properties)

        for prop in self.__properties:
            db_prop = utils.utf8('inst_' + prop)
            result = self.table.select(self.table.c.name == db_prop).execute()
            row = result.fetchone()
            if row:
                setattr(self, prop, row['value'])
            result.close()

    def write(self):
        for prop in self.__properties:
            value = getattr(self, prop)
            db_prop = utils.utf8('inst_' + prop)
            if value is not None:
                value = utils.utf8(value)
            result = self.table.select(self.table.c.name == db_prop).execute()
            row = result.fetchone()
            result.close()
            # have to check if the property exists first because sqlite doesn't
            # raise an error if you try to update a value that doesn't exist
            # and do an insert and then catching the exception if it exists
            # and then updating the value is too slow
            if not row:
                logger.debug('insert: %s = %s' % (prop, value))
                self.table.insert().execute(name=db_prop, value=value)
            else:
                logger.debug('update: %s = %s' % (prop, value))
                self.table.update(
                    self.table.c.name == db_prop).execute(value=value)


class InstitutionPresenter(editor.GenericEditorPresenter):

    widget_to_field_map = {'inst_name': 'name',
                           'inst_abbr': 'abbreviation',
                           'inst_code': 'code',
                           'inst_contact': 'contact',
                           'inst_tech': 'technical_contact',
                           'inst_email': 'email',
                           'inst_tel': 'tel',
                           'inst_fax': 'fax',
                           'inst_addr_tb': 'address'
                           }

    def __init__(self, model, view):
        super(InstitutionPresenter, self).__init__(
            model, view, refresh_view=True)

    def set_model_attr(self, attr, value, validator):
        super(InstitutionPresenter, self).set_model_attr(attr, value,
                                                         validator)
        self._dirty = True

    def on_inst_register_clicked(self, *args, **kwargs):
        pass

    def on_inst_addr_tb_changed(self, widget, value=None, attr=None):
        return self.on_textbuffer_changed(widget, value, attr='address')


def start_institution_editor():
    glade_path = os.path.join(paths.lib_dir(),
                              "plugins", "garden", "institution.glade")
    from bauble.editor import GenericEditorView
    view = GenericEditorView(
        glade_path,
        parent=None,
        root_widget_name='inst_dialog')
    view._tooltips = {
        'inst_name': _('The full name of the institution.'),
        'inst_abbr': _('The standard abbreviation of the '
                       'institution.'),
        'inst_code': _('The intitution code should be unique among '
                       'all institions.'),
        'inst_contact': _('The name of the person to contact for '
                          'information related to the institution.'),
        'inst_tech': _('The email address or phone number of the '
                       'person to contact for technical '
                       'information related to the institution.'),
        'inst_email': _('The email address of the institution.'),
        'inst_tel': _('The telephone number of the institution.'),
        'inst_fax': _('The fax number of the institution.'),
        'inst_addr': _('The mailing address of the institition.')
        }

    o = Institution()
    inst_pres = InstitutionPresenter(o, view)
    response = inst_pres.start()
    if response == gtk.RESPONSE_OK:
        o.write()
        inst_pres.commit_changes()
    else:
        inst_pres.session.rollback()
    inst_pres.session.close()


class InstitutionCommand(pluginmgr.CommandHandler):
    command = ('inst', 'institution')
    view = None

    def __call__(self, cmd, arg):
        InstitutionTool.start()


class InstitutionTool(pluginmgr.Tool):
    label = _('Institution')

    @classmethod
    def start(cls):
        start_institution_editor()
