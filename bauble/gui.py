#
# gui.py
#
# Description: TODO: finish the descriptions and check the other files have
#

import os, time, thread, re
import gtk
import gobject
import sqlobject
import views
from views import views
from editors import editors
from tables import tables
from prefs import *
import utils


#
# GUI
#
class GUI:
    
    current_view_pref = "gui.current_view"
    
    def __init__(self, bauble):
        self.bauble = bauble
        self.create_gui()
        
        # load the last view open from the prefs
        #self.set_current_view(views.search.SearchView)
        #return
        v = Preferences[self.current_view_pref]
        if v is None: 
            v = 'views.search' # search is the default view
        for view, module in views.modules.iteritems():
            if module == v:
                self.set_current_view(view)
            
    def create_gui(self):            
        # create main window
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_default_size(800, 600)
        self.window.connect("destroy", self.on_quit)        
        self.window.set_title("Bauble")
    
        # top level vbox for menu, content, status bar
        main_vbox = gtk.VBox(False)
        self.window.add(main_vbox)

        menubar = self.create_main_menu()
        main_vbox.pack_start(menubar, False, True, 0)
        
        # TODO: don't use the toolbar for now, the only thing on the
        # toolbar right now is the add button, we should put all of this on 
        # the menu
        # put all of the toolbar 
        toolbar = self.create_toolbar()
        main_vbox.pack_start(toolbar, False, True, 0)
                
        self.content_hbox = gtk.HBox(False) # empty for now        
        #self.content_frame = gtk.Frame()
        #self.content_hbox.pack_start(self.content_frame)
        main_vbox.pack_start(self.content_hbox)

        # last part of main_vbox is status bar
        status_box = gtk.HBox(False)        
        self.statusbar = gtk.Statusbar()
        self.statusbar.set_has_resize_grip(False)     
        status_box.pack_start(self.statusbar, expand=True, fill=True)

        # create the progress bar and add it to the status pane
        self.progressbar = gtk.ProgressBar()
        self.progressbar.set_size_request(100, -1)
        self.progressbar.set_fraction(1.0)
        status_box.pack_start(self.progressbar, expand=False, fill=False)
        
        #main_vbox.pack_start(self.statusbar, expand=False, fill=False)
        main_vbox.pack_start(status_box, expand=False, fill=False)
                
        # show everything
        self.window.show_all()


    def pb_pulse_worker(self, from_thread):
        self.pb_lock.acquire() # ********** critical
        while not self.stop_pulse:
            #print "pulse"
            if not from_thread: 
                gtk.gdk.threads_enter()
            self.progressbar.pulse()
            if not from_thread: 
                gtk.gdk.threads_leave()
            time.sleep(.1)
#        self.progressbar.set_fraction(1.0
        if not from_thread: gtk.gdk.threads_enter()
        self.progressbar.set_fraction(1.0)
        if not from_thread: gtk.gdk.threads_leave()
        self.pb_lock.release()
        

  
    def pulse_progressbar(self, from_thread=False):
        """
        create a seperate thread the run the progress bar
        """
        if not hasattr(self, "pb_lock"):
            self.pb_lock = thread.allocate_lock()
        self.stop_pulse = False
        self.progressbar.set_pulse_step(.1)
        self.progressbar.set_fraction(1.0)
        id = thread.start_new_thread(self.pb_pulse_worker, (from_thread,))
        

    def stop_progressbar(self):
        """
        stop a progress bar
        """
        self.stop_pulse = True
        #self.pb_lock.acquire()
        #self.progressbar.set_fraction(1.0)
        #self.pb_lock.release()

    
    def create_toolbar(self):
        toolbar = gtk.Toolbar()

    # TODO: for now remove this toolbar and just put everything under a menu
    # item

        # add all views modules
#        button = gtk.MenuToolButton(gtk.STOCK_FIND_AND_REPLACE)
#        button.set_label("View")
#        menu = gtk.Menu()
#        for name, view in sorted(views.iteritems()):
#            item = gtk.MenuItem(name)
#            item.connect("activate", self.on_activate_view, view)
#            menu.append(item)
#        
#        menu.show_all()
#        button.set_menu(menu)
#        toolbar.insert(button, 0)
        
        # add all editors modules
        button = gtk.MenuToolButton(gtk.STOCK_ADD)
        #button.add_accelerator("show_menu", self.accel_group, ord("a"), 
        #                       gtk.gdk.CONTROL_MASK, gobject.SIGNAL_ACTION)
        menu = gtk.Menu()
        #for editor in sorted(editors.values(), \
        for editor in sorted(editors.all(), \
            cmp=lambda x, y: cmp(x.label, y.label)):
            if editor.standalone:
                item = gtk.MenuItem(editor.label)
                item.connect("activate", self.on_activate_editor, editor)
                menu.append(item)
        menu.show_all()
        button.set_menu(menu)
        toolbar.insert(button, 0)
        
        return toolbar
    
    
    def set_current_view(self, view_class):
        """
        set the current view, view is a class and will be instantiated
        here, that way the same view won't be created again if the current
        view os of the same type
        """
        #current_view = self.content_frame.get_child()
        current_view = self.get_current_view()
        if type(current_view) == view_class: return
        elif current_view != None:
            self.content_hbox.remove(current_view)
            #self.content_frame.remove(current_view)
            current_view.destroy()
            current_view = None
        new_view = view_class()#self.bauble)    
        #self.content_frame.set_label(view_class.__name__)
        self.content_hbox.pack_start(new_view)
        #self.content_frame.add(new_view)
        
        
    def get_current_view(self):
        #return self.content_frame.get_child()
        kids = self.content_hbox.get_children()
        if len(kids) == 0:
            return None
        else: return kids[0]        
        
        
    def on_activate_view(self, menuitem, view):
        """
        set the selected view as current
        """
        self.set_current_view(view)


    def on_activate_editor(self, menuitem, editor):
        """
        show the dialog of the selected editor
        """
        e = editor()
        e.start()
        
        
    def create_main_menu(self):
        """
        get the main menu from the UIManager XML description, add its actions
        and return the menubar
        """
        ui_manager = gtk.UIManager()
        
        # add accel group
        self.accel_group = ui_manager.get_accel_group()
        self.window.add_accel_group(self.accel_group)

        # TODO: get rid of new, open, and just have a connection
        # menu item
        
        # create and addaction group for menu actions
        menu_actions = gtk.ActionGroup("MenuActions")
        menu_actions.add_actions([("file", None, "_File"), 
                                  ("file_new", gtk.STOCK_NEW, "_New", None, 
                                   None, self.on_file_menu_new), 
                                  ("file_open", gtk.STOCK_OPEN, "_Open", None, 
                                   None, self.on_file_menu_open), 
                                  ("file_quit", gtk.STOCK_QUIT, "_Quit", None, 
                                   None, self.on_quit), 
                                  ("edit", None, "_Edit"), 
                                  ("edit_cut", gtk.STOCK_CUT, "_Cut", None, 
                                   None, self.on_edit_menu_cut), 
                                  ("edit_copy", gtk.STOCK_COPY, "_Copy", None, 
                                   None, self.on_edit_menu_copy), 
                                  ("edit_paste", gtk.STOCK_PASTE, "_Paste", 
                                   None, None, self.on_edit_menu_paste), 
                                  ("edit_preferences", None , "_Preferences", 
                                   "<control>P", None, self.on_edit_menu_prefs), 
                                  ("tools", None, "_Tools"),
                                   ("export", None, "_Export", None, 
                                   None, self.on_tools_menu_export), 
                                   ("import", None, "_Import", None, 
                                   None, self.on_tools_menu_import), 
                                   ("label", None, "_Label Maker", None, 
                                   None, self.on_tools_menu_label_maker), 
                                  ])
        ui_manager.insert_action_group(menu_actions, 0)

        # load ui
        #ui_manager.add_ui_from_file(self.bauble.path + os.sep + "bauble.ui")
        ui_filename = utils.get_main_dir() + os.sep + "bauble.ui"
        ui_manager.add_ui_from_file(ui_filename)

        # get menu bar from ui manager
        mb = ui_manager.get_widget("/MenuBar")
        return mb
    
    
    def on_tools_menu_label_maker(self, widget, data=None):
        import tools.labels
        
        # TODO: really the Label Maker tool should only be sensitive if the 
        # search view is visible but right now since we only have one view 
        # we won't worry about that
        
        # get all of the current plants from the view
        view = self.get_current_view()
        if not isinstance(view, views.Search):
            raise Error("GUI.on_tools_menu_label_maker: can only "\
                        "make labels from the search vew")
                        
        # TODO: this assumes a but too much about SearchView's internal workings
        model = view.results_view.get_model()
        if model is None:
            utils.message_dialog("Search for something first.")
            return
        
        plants = []
        for row in model:
            value = row[0]
            # right now we don't create labels for all plants under
            # families and genera
            if isinstance(value, tables.Family):
                print "family: " + str(value)
            elif isinstance(value, tables.Genera):
                print "genera: " + str(value)
            elif isinstance(value, tables.Plantnames):
                for acc in value.accessions:
                    plants += acc.plants
            elif isinstance(value, tables.Accessions):
                plants += value.plants
            elif isinstance(value, tables.Plants):
                plants.append(value)            
            elif isinstance(value, tables.Locations):
                plants += value.plants
            
        #print plants
        d = tools.labels.LabelMaker(plants)
        response = d.run()
        if response == gtk.RESPONSE_ACCEPT:
            pdf_filename = d.create_pdf()
            print pdf_filename
            utils.startfile(pdf_filename)        
        d.destroy()
        
        
    def on_tools_menu_export(self, widget, data=None):
        import tools.import_export
        d = tools.import_export.ExportDialog()
        d.run()
        d.destroy()


    def on_tools_menu_import(self, widget, data=None):
        import tools.import_export
        d = tools.import_export.ImportDialog()
        d.run()
        d.destroy()

        
    def on_edit_menu_prefs(self, widget, data=None):
        p = PreferencesMgr()
        p.run()
        p.destroy()

        
    def on_edit_menu_cut(self, widget, data=None):
        pass

    
    def on_edit_menu_copy(self, widget, data=None):
        pass

    
    def on_edit_menu_paste(self, widget, data=None):
        pass

        
    def on_file_menu_new(self, widget, date=None):
        self.bauble.create_database()
        # TODO: reset the view
            
        
    def on_file_menu_open(self, widget, data=None):        
        """
        open the connection manager
        """
        from bauble import bauble
        from conn_mgr import ConnectionManagerDialog
        cm = ConnectionManagerDialog()
        r = cm.run()
        if r == gtk.RESPONSE_CANCEL or r == gtk.RESPONSE_CLOSE or \
           r == gtk.RESPONSE_NONE or r == gtk.RESPONSE_DELETE_EVENT:
            #if r != gtk.RESPONSE_ACCEPT:
            cm.destroy()
            return
        uri = cm.get_connection_uri()
        name = cm.get_connection_name()
        cm.destroy()
            #gtk.gdk.threads_leave()
        bauble.open_database(uri, name, True)
        
        # TODO reset the view
            

    def save_state(self):
        """
        this is usually called from bauble.py when it shuts down
        """        
        current_view = self.get_current_view()
        if current_view is not None:
            # get label of view
            for label, view in views.iteritems(): 
                if view == current_view.__class__:
                    Preferences[self.current_view_pref] = views.modules[view]
        Preferences.save()
        
    def on_quit(self, widget, data=None):
        self.bauble.quit()
        
        

