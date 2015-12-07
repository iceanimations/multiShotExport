'''
Created on Nov 24, 2015

@author: qurban.ali
'''
from uiContainer import uic
from PyQt4.QtGui import *
from PyQt4.QtCore import *
import os.path as osp
import backend as be
import tacticCalls as tc
import qutil
import cui
import appUsageApp
import qtify_maya_window as qtfy

reload(qutil)
reload(cui)
reload(appUsageApp)
reload(tc)
reload(be)

rootPath = qutil.dirname(__file__, 2)
uiPath = osp.join(rootPath, 'ui')
iconPath = osp.join(rootPath, 'icons')
__title__ = 'Multi Shot Export'

Form1, Base1 = uic.loadUiType(osp.join(uiPath, 'main.ui'))
class ShotExporter(Form1, Base1, cui.TacticUiBase):
    def __init__(self, parent=qtfy.getMayaWindow()):
        '''
        @param items: objects of QCheckbox or QRadioButton
        '''
        super(ShotExporter, self).__init__(parent)
        self.setupUi(self)
        self.setWindowTitle(__title__)
        self.setStyleSheet(cui.styleSheet)
        self.setServer()

        self.items = []
        self.collapsed = True
        
        self.populateProjects()
        self.label.hide()
        self.directoryBox.hide()
        self.browseButton.hide()
        
        self.projectBox.currentIndexChanged[str].connect(self.setProject)
        self.epBox.currentIndexChanged[str].connect(self.populateSequences)
        self.seqBox.currentIndexChanged[str].connect(self.populateShots)
        self.exportButton.clicked.connect(self.export)
        self.toggleCollapseButton.clicked.connect(self.toggleItems)
        
        self.shotBox = cui.MultiSelectComboBox(self, '--Shots--')
        self.shotBox.setStyleSheet('QPushButton{min-width: 100px;}')
        self.shotBox.selectionDone.connect(self.showSelectedItems)
        self.horizontalLayout_2.insertWidget(2, self.shotBox)
        
        self.toggleCollapseButton.setIcon(QIcon(osp.join(iconPath, 'ic_toggle_collapse')))
        
        pro = qutil.getOptionVar(tc.projectKey)
        ep = qutil.getOptionVar(tc.episodeKey)
        #self.setContext(pro, ep, None)
        
        appUsageApp.updateDatabase('shot_subm')
        
    def setSatus(self, msg, timeout=3000):
        self.statusBar().showMessage(msg, timeout)
        
    def showSelectedItems(self, shots):
        for item in self.items:
            if item.getTitle() in shots:
                item.show()
            else: item.hide()
        
    def setBusy(self):
        qApp.setOverrideCursor(Qt.WaitCursor)
        qApp.processEvents()
        
    def releaseBusy(self):
        qApp.restoreOverrideCursor()
        qApp.processEvents()
                
    def toggleItems(self):
        self.collapsed = not self.collapsed
        for item in self.items:
            item.toggleCollapse(self.collapsed)

    def populateShots(self, seq):
        errors = {}
        self.setBusy()
        try:
            for item in self.items:
                item.deleteLater()
            del self.items[:]
            self.shotBox.clearItems()
            if seq == '--Select Sequence--' or not seq: return
            shots, err = tc.getShots(seq)
            if not shots: return
            errors.update(err)
            #shots = [shot.split('_')[-1] for shot in shots.keys()]
            self.populateShotItems(shots)
            self.shotBox.addItems(shots)
        except Exception as ex:
            self.releaseBusy()
            self.showMessage(msg=str(ex), icon=QMessageBox.Critical)
        finally:
            self.releaseBusy()
        if errors:
            self.showMessage(msg='Error occurred while retrieving Assets for selected Sequence',
                             icon=QMessageBox.Critical,
                             details=qutil.dictionaryToDetails(errors))
            
    def populateShotItems(self, shots):
        for shot in sorted(shots):
            item = Item(self, shot, be.Shot(self, shot))
            self.itemLayout.addWidget(item)
            self.items.append(item)
            item.hide()
            
    def showMessage(self, **kwargs):
        return cui.showMessage(self, __title__, **kwargs)
        
    def closeEvent(self, event):
        self.deleteLater()
    
    def export(self):
        pass


Form2, Base2 = uic.loadUiType(osp.join(uiPath, 'item.ui'))
class Item(Form2, Base2):
    def __init__(self, parent=None, title='', shot=None):
        '''
        @param items: objects of QCheckbox or QRadioButton
        '''
        super(Item, self).__init__(parent)
        self.setupUi(self)
        
        self.parentWin = parent
        self.collapsed = False
        self.shot = shot
        self.setTitle(title)
        self.displayLayerButtons = []
        self.assetButtons = []
        self.update()
        
        self.style = ('background-image: url(%s);\n'+
                      'background-repeat: no-repeat;\n'+
                      'background-position: center right')
        self.iconLabel.setStyleSheet(self.style%osp.join(iconPath,
                                                         'ic_collapse.png').replace('\\', '/'))
        self.switchButton.setIcon(QIcon(osp.join(iconPath, 'ic_switch_camera.png')))

        self.titleFrame.mouseReleaseEvent = self.collapse
        self.cacheButton.clicked.connect(self.handleCacheButton)
        self.previewButton.clicked.connect(self.handlePreviewButton)
        self.cameraButton.clicked.connect(self.handleCameraButton)
        self.cSelectAllButton.clicked.connect(self.cSelectAll)
        self.pSelectAllButton.clicked.connect(self.pSelectAll)
        self.bakeButton.clicked.connect(self.handleBakeButton)
        self.nukeButton.clicked.connect(self.handleNukeButton)
        self.hdButton.clicked.connect(self.handleHdButton)
        self.fullHdButton.clicked.connect(self.handleFullHdButton)
        self.jpgButton.clicked.connect(self.handlJpgButton)
        self.switchButton.clicked.connect(self.switchToMe)
        
    def toggleCacheSelectAllButton(self):
        # Check the Select All button is all the asset buttons get selected
        self.cSelectAllButton.setChecked(all([btn.isChecked() for btn in self.assetButtons]))
        # update the assets on the camera attribute
        self.shot.updateAssets({btn.text(): btn.isChecked() for btn in self.assetButtons})
    
    def togglePreviewSelectAllButton(self):
        # Check the Select All button is all the layer buttons get selected
        self.pSelectAllButton.setChecked(all([btn.isChecked() for btn in self.displayLayerButtons]))
        # update the layers on the camera attribute
        self.shot.updateLayers({btn.text(): btn.isChecked() for btn in self.displayLayerButtons})
        
    def switchToMe(self):
        error = self.shot.switchToMe()
        if error:
            self.parentWin.showMessage(msg=error, icon=QMessageBox.Critical)
            
    def saveToScene(self):
        self.shot.saveToScene()

    def handlJpgButton(self, val):
        self.shot.jpgPreview = val
        self.saveToScene()
        
    def handleFullHdButton(self, val):
        self.shot.fullHdPreview = val
        self.saveToScene()
        
    def handleHdButton(self, val):
        self.shot.hdPreview = val
        self.saveToScene()
        
    def handleNukeButton(self, val):
        self.shot.nukeCamera = val
        self.saveToScene()
        
    def handleBakeButton(self, val):
        self.shot.bakeCamera = val
        self.saveToScene()
        
    def pSelectAll(self, val):
        for btn in self.displayLayerButtons:
            btn.setChecked(val)
    
    def cSelectAll(self, val):
        for btn in self.assetButtons:
            btn.setChecked(val)
        
    def handleCameraButton(self, val):
        self.shot.camera = val
        self.saveToScene()
        
    def handlePreviewButton(self, val):
        self.shot.preview = val
        self.saveToScene()
        
    def handleCacheButton(self, val):
        self.shot.cache = val
        self.saveToScene()
        
    def update(self, shot=None):
        if shot: self.shot = shot
        if self.shot.startFrame and self.shot.endFrame:
            self.frLabel.setText('(%s - %s)'%(self.shot.startFrame, self.shot.endFrame))
        self.cacheButton.setChecked(self.shot.cache)
        self.previewButton.setChecked(self.shot.preview)
        self.cameraButton.setChecked(self.shot.camera)
        if self.shot.cameraName:
            self.cameraNameLabel.setText(self.shot.cameraName)
        else:
            self.cameraNameLabel.setText('Not Found')
            self.mainBox.setEnabled(False)
            self.switchButton.setEnabled(False)
        self.bakeButton.setChecked(self.shot.bakeCamera)
        self.nukeButton.setChecked(self.shot.nukeCamera)
        self.hdButton.setChecked(self.shot.hdPreview)
        self.fullHdButton.setChecked(self.shot.fullHdPreview)
        self.jpgButton.setChecked(self.shot.jpgPreview)
        
        # populate the asset buttons
        for btn in self.assetButtons:
            btn.delteLater()
        del self.assetButtons[:]
        for asset, val in self.shot.assets.items():
            btn = QCheckBox(asset)
            btn.toggled.connect(self.toggleCacheSelectAllButton)
            btn.setChecked(val)
            self.assetButtons.append(btn)
            self.assetLayout.addWidget(btn)
        # populate the display layer buttons
        for btn in self.displayLayerButtons:
            btn.delteLater()
        del self.displayLayerButtons[:]
        for layer, val in self.shot.displayLayers.items():
            btn = QCheckBox(layer)
            btn.toggled.connect(self.togglePreviewSelectAllButton)
            btn.setChecked(val)
            self.displayLayerButtons.append(btn)
            self.layerLayout.addWidget(btn)
    
    def getTitle(self):
        return self.titleLabel.text()
    
    def setTitle(self, title):
        self.titleLabel.setText(title)

    def collapse(self, event=None):
        if self.collapsed:
            self.mainBox.show()
            self.collapsed = False
            path = osp.join(iconPath, 'ic_collapse.png')
        else:
            self.mainBox.hide()
            self.collapsed = True
            path = osp.join(iconPath, 'ic_expand.png')
        path = path.replace('\\', '/')
        self.iconLabel.setStyleSheet(self.style%path)
        
    def toggleCollapse(self, state):
        self.collapsed = state
        self.collapse()