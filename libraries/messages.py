# !/usr/bin/env python
# -*- coding: utf-8 -*-

# This file is part of the uPiot project, https://github.com/gepd/upiot/
#
# MIT License
#
# Copyright (c) 2017 GEPD
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import sublime
import sublime_plugin

import collections
import threading

from .paths import getPluginName
from .tools import findInOpendView
from .I18n import I18n

global session

session = {}
close_panel = False
viewer_name = 'Deviot Viewer'


class Messages:
    port = None
    window = None
    text_queue = collections.deque()
    text_queue_lock = threading.Lock()

    def __init__(self, output_view=None):
        self.translate = I18n().translate
        self.output_view = output_view
        self._init_text = None
        self._name = None        

    def initial_text(self, text, *args):
        """Intial message
        
        Sets the initial string to be push when the Messages instance is created
        
        Arguments:
            text {str} -- string to display
            *args {str} -- arguments to be replaced in the text string
        """
        self._init_text = self.translate(text, *args)

    def panel_name(self, text, *args):
        """Panel name
        
        Sets the name of the panel when it will be a ST window
        
        Arguments:
            text {str} -- string to name the panel
            *args {str} -- arguments to be replaced in the text string
        """
        self._name = self.translate(text, *args).strip('\\n')

    def create_panel(self, direction='down', in_file=False):
        """
        Start the print module, if the window was already created
        it's recovered.
        """
        global session

        self.window = sublime.active_window()

        if(not self.output_view and not self.recover_panel(self._name)):
            self.select_output(in_file)

        self.window.run_command("show_panel", {"panel": "output.deviot"})

        # print initial message
        if(self._init_text):
            self.print(self._init_text)

        # store the session to close the panel in the future
        if(self._name):
            session[self._name] = self


    def select_output(self, in_file):
        """Panel Output
        
        Selects where the content will be printed, it can be the ST console
        or in a new buffer (view)
        
        Arguments:
            in_file {bool} -- if it's true a new view will be created
        
        Keyword Arguments:
            name {str} -- name of the new view (default: {''})
        """
        if(in_file):
            self.output_view = self.new_file_panel(direction='right')
        else:
            package_name = getPluginName()
            syntax = "Packages/{0}/Console.tmLanguage".format(package_name)

            self.output_view = self.window.create_output_panel('deviot')
            self.output_view.assign_syntax(syntax)

    def set_focus(self):
        """Set focus

        Sets the focus to the console window
        """
        window = sublime.active_window()
        window.focus_view(self.output_view)

    def print(self, text, *args):
        """
        Adds the string in the deque list
        """
        # translate strings before append
        text = I18n().translate(text, *args)

        self.text_queue_lock.acquire()
        try:
            if(type(text) == bytes):
                text = text.decode('utf-8')
            self.text_queue.append(text)
        finally:
            self.text_queue_lock.release()

        sublime.set_timeout(self.service_text_queue, 0)

    def service_text_queue(self):
        """
        Handles the deque list to print the messages
        """
        self.text_queue_lock.acquire()

        is_empty = False
        try:
            if(len(self.text_queue) == 0):
                return

            characters = self.text_queue.popleft()
            is_empty = (len(self.text_queue) == 0)

            self.send_to_file(characters)

        finally:
            self.text_queue_lock.release()

        if(not is_empty):
            sublime.set_timeout(self.service_text_queue, 1)

    def send_to_file(self, text):
        """
        Prints the text in the window
        """
        text = text.replace('\r\n', '\n'). replace('\r', '\n').replace('\\n', '\n')
        self.output_view.set_read_only(False)
        self.output_view.run_command('append', {'characters': text})
        self.output_view.set_read_only(True)
        self.output_view.run_command("move_to", {"extend": True, "to": "eof"})

    def recover_panel(self, name):
        """
        Recover the message window object
        """

        window, view = findInOpendView(name)

        if(view):
            self.output_view = view
        return bool(view)

    def new_file_panel(self, direction):
        """Create an empty new file sheet

        Creates an empty sheet to be used as console

        Arguments:
            name {str} -- name to set in the ST view
            direction {str} -- Where the window will be located. options available:
                                'self', 'left', 'right', 'up', 'down'

        Returns:
            obj -- Sublime Text view buffer
        """
        window = sublime.active_window()

        word_wrap = {'setting': 'word_wrap'}
        options = {'direction': direction, 'give_focus': True}

        window.run_command('deviot_create_pane', options)

        view = window.new_file()
        view.set_name(self._name)
        view.run_command('toggle_setting', word_wrap)
        view.set_scratch(True)

        return view

    def on_pre_close(self, view):
        self.window = view.window()

    def on_close(self, view):
        if(view.name() not in session):
            return

        if(check_empty_panel(self.window)):
            self.window.run_command("destroy_pane", args={"direction": "self"})
            self.window = None

def check_empty_panel(window):
    """
    If there is an empty panel will make it active

    Returns:
        bool -- True if there is an empty panel false if not
    """
    num = window.num_groups()

    for n in range(0, num):
        if(not window.views_in_group(n)):
            window.focus_group(n)
            return True
    return False
