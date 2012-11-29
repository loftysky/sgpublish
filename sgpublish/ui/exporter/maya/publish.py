import contextlib
import os
import tempfile
import subprocess
import functools
import glob
import time
import datetime
import re

from PyQt4 import QtGui, QtCore
Qt = QtCore.Qt

from maya import cmds

import uifutures
import mayatools.playblast

from ..publish import Widget as Base
from ... import utils as ui_utils

__also_reload__ = [
    '...utils',
    '..publish',
    'mayatools.playblast',
    'uifutures',
]


class PlayblastPicker(QtGui.QDialog):

    def __init__(self, parent):
        super(PlayblastPicker, self).__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        
        self.setWindowModality(Qt.WindowModal)
        self.setLayout(QtGui.QVBoxLayout())
        
        self.layout().addWidget(QtGui.QLabel("Pick a playblast:"))
        
        self._list_widget = QtGui.QListWidget()
        self.layout().addWidget(self._list_widget)
        self._list_widget.setMinimumWidth(self.parent().sizeHint().width() - 40)
        self._populate_list()
        self._list_widget.currentTextChanged.connect(self._selection_changed)
        
        buttons = QtGui.QHBoxLayout()
        self.layout().addLayout(buttons)
        
        self._playblast_button = QtGui.QPushButton("New")
        self._playblast_button.clicked.connect(self._on_playblast)
        self._playblast_button.setSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)
        buttons.addWidget(self._playblast_button)
        
        buttons.addStretch()
        
        self._cancel_button = QtGui.QPushButton("Cancel")
        self._cancel_button.clicked.connect(self._on_cancel)
        buttons.addWidget(self._cancel_button)
        self._cancel_button.setSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)
        
        self._select_button = QtGui.QPushButton("Open")
        self._select_button.setEnabled(False)
        self._select_button.clicked.connect(self._on_select)
        buttons.addWidget(self._select_button)
        self._select_button.setSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Fixed)
    
    def _populate_list(self):
        if not os.path.exists('/var/tmp/srv_playblast'):
            return
        for name in os.listdir('/var/tmp/srv_playblast'):
            if glob.glob(os.path.join('/var/tmp/srv_playblast', name, '*.jpg')):
                self._list_widget.addItem(name)
    
    def currentPath(self):
        name = str(self._list_widget.currentItem().text())
        path = os.path.join('/var/tmp/srv_playblast', name)
        return path if os.path.exists(path) else None
        
    def _selection_changed(self, name):
        path = self.currentPath()
        self._select_button.setEnabled(path is not None)
    
    def _on_playblast(self):
        self.hide()
        self.parent().playblast()
    
    def _on_cancel(self):
        self.hide()
    
    def _on_select(self):
        path = self.currentPath()
        if path is not None:
            self.hide()
            self.parent().setFrames(path + '/*.jpg')


class Widget(Base):
    
    beforePlayblast = QtCore.pyqtSignal()
    afterPlayblast = QtCore.pyqtSignal()
    viewerClosed = QtCore.pyqtSignal()
    
    def _setup_ui(self):
        
        super(Widget, self)._setup_ui()
        
        self._playblast = QtGui.QPushButton(ui_utils.icon('silk/pictures', size=12, as_icon=True), "Playblast")
        self._playblast.clicked.connect(self._on_playblast)
        self._movie_layout.addWidget(self._playblast)
        self._playblast.setFixedHeight(self._movie_path.sizeHint().height())
        self._playblast.setFixedWidth(self._playblast.sizeHint().width() + 2)
        
        # For dev only!
        self._playblast.setEnabled('KS_DEV_ARGS' in os.environ)
        
        self._msgbox = None
    
    def take_full_screenshot(self):
        
        # Playblast the first screenshot.
        path = tempfile.NamedTemporaryFile(suffix=".jpg", prefix="publish.", delete=False).name
        frame = cmds.currentTime(q=True)
        mayatools.playblast.playblast(
            frame=[frame],
            format='image',
            completeFilename=path,
            viewer=False,
            p=100,
            framePadding=4,
        )
        self.setThumbnail(path)
    
    def _on_movie_browse(self):
        
        existing = str(self._movie_path.text())
        
        res = cmds.fileDialog2(
            dialogStyle=2, # Maya styled.
            caption="Select Movie or First Frame",
            fileFilter='Movie or Frame (*.mov *.exr *.tif *.tiff *.jpg *.jpeg)',
            fileMode=1, # A single existing file.
            startingDirectory=os.path.dirname(existing) if existing else cmds.workspace(query=True, rootDirectory=True)
        )
        
        if res:
            self._movie_path.setText(res[0])
    
    def _on_playblast(self):
        self._picker = PlayblastPicker(self)
        self._picker.show()
    
    def playblast(self):
        
        minTime = cmds.playbackOptions(q=True, minTime=True)
        maxTime = cmds.playbackOptions(q=True, maxTime=True)
        
        scene_name = os.path.splitext(os.path.basename(cmds.file(q=True, sceneName=True)))[0]
        
        # Assume that we won't be calling this multiple times within 1 second.
        directory = os.path.join(
            '/var/tmp/playblasts',
            scene_name,
            datetime.datetime.utcnow().strftime('%y%m%d_%H%M%S'),
        )
        os.makedirs(directory)
        
        self.beforePlayblast.emit()
        try:
            mayatools.playblast.playblast(
                startTime=minTime,
                endTime=maxTime,
                format='image',
                viewer=False,
                p=100,
                framePadding=4,
                filename=directory + '/frame',
            )
        finally:
            self.afterPlayblast.emit()
        
        self.setFrames(directory + '/frame.####.jpg')
    
    def setFrames(self, path):

        frame_rate = cmds.playbackOptions(q=True, framesPerSecond=True)
        
        # Open a viewer, and wait for it to close.
        houdini_path = re.sub(r'(#+)', lambda m: '$F%d' % len(m.group(1)), path)
        proc = subprocess.Popen(['mplay', '-C', '-T', '-R', '-r', str(int(frame_rate)), houdini_path])
        self._player_waiter = thread = QtCore.QThread()
        thread.run = functools.partial(self._wait_for_player, proc)
        thread.start()
        
        self._msgbox = msgbox = QtGui.QMessageBox(
            QtGui.QMessageBox.Warning,
            'Close Playblast Viewer',
            'Please close the playblast viewer before publishing.',
            QtGui.QMessageBox.Ignore,
            self
        )
        msgbox.setWindowModality(Qt.WindowModal)
        msgbox.buttonClicked.connect(msgbox.hide)
        msgbox.show()
        
        self._movie_path.setText(path)
    
    def _wait_for_player(self, proc):
        proc.wait()
        self.viewerClosed.emit()
        if self._msgbox:
            self._msgbox.hide()
            self._msgbox = None
