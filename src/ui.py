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
import imaya
import iutil
import os

reload(qutil)
reload(cui)
reload(appUsageApp)
reload(tc)
reload(be)
reload(iutil)

from pprint import pprint

tempLocation = osp.join(osp.expanduser('~'), 'multiShotExport')
rootPath = qutil.dirname(__file__, 2)
uiPath = osp.join(rootPath, 'ui')
iconPath = osp.join(rootPath, 'icons')
__title__ = 'Multi Shot Export'
directoryKey = 'multiShotExport_Directory_key'

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
        self.smoothGeosets = None
        directory = qutil.getOptionVar(directoryKey)
        self.lastDirectory = directory if directory else ''
        self.directoryBox.setText(self.lastDirectory)
        
        self.populateProjects()
        self.label.hide()
        self.directoryBox.hide()
        self.browseButton.hide()
        
        self.projectBox.currentIndexChanged[str].connect(self.setProject)
        self.epBox.currentIndexChanged[str].connect(self.populateSequences)
        self.seqBox.currentIndexChanged[str].connect(self.populateShots)
        self.exportButton.clicked.connect(self.export)
        self.toggleCollapseButton.clicked.connect(self.toggleItems)
        self.browseButton.clicked.connect(self.setDirectory)
        self.directoryBox.textChanged.connect(self.handleDirectoryChange)
        self.geosetDialogButton.clicked.connect(self.showGeosetDialog)
        
        self.shotBox = cui.MultiSelectComboBox(self, '--Shots--')
        self.shotBox.setStyleSheet('QPushButton{min-width: 100px;}')
        self.shotBox.selectionDone.connect(self.showSelectedItems)
        self.horizontalLayout_2.insertWidget(2, self.shotBox)
        
        self.toggleCollapseButton.setIcon(QIcon(osp.join(iconPath, 'ic_toggle_collapse')))

        self.setContext(*be.getProjectContext())
        self.progressBar.hide()
        
        appUsageApp.updateDatabase('shot_subm')
        
    def showGeosetDialog(self):
        dialog = GeosetDialog(self)
        dialog.exec_()
        self.smoothGeosets = dialog.getSmoothGeosets()
        
    def setDirectory(self):
        directory = QFileDialog.getExistingDirectory(self, __title__, self.lastDirectory)
        if directory:
            self.directoryBox.setText(directory)
            self.lastDirectory = directory
    
    def handleDirectoryChange(self, text):
        qutil.addOptionVar(directoryKey, text)
        
    def clearStatus(self):
        self.statusBar().clearMessage()
        qApp.processEvents()
        
    def showProgressBar(self, m):
        self.progressBar.setValue(0)
        self.progressBar.setMaximum(m)
        self.progressBar.show()
        qApp.processEvents()
        
    def updateProgressBar(self, val):
        self.progressBar.setValue(val)
        qApp.processEvents()
        
    def hideProgressBar(self):
        self.progressBar.setMaximum(0)
        self.progressBar.setValue(0)
        self.progressBar.hide()
        qApp.processEvents()
        
    def setStatus(self, msg, timeout=0):
        self.statusBar().showMessage(msg, timeout)
        qApp.processEvents()
        
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
        
    def getSelectedShots(self):
        return [item.shot for item in self.items if item.getTitle() in self.shotBox.getSelectedItems()]
    
    def getSeq(self):
        seq = self.seqBox.currentText()
        if seq == '--Select Sequence--':
            seq = ''
        return seq
    
    def isDirectory(self):
        return self.addDirectoryButton.isChecked()
    
    def getDirectory(self):
        return self.directoryBox.text()
    
    def export(self):
        if not osp.exists('C:\\Program Files\\ImageMagick-6.9.1-Q8'):
            self.showMessage(msg='Image Magick library is not installed on this system. Could not continue',
                             icon=QMessageBox.Warning)
            return
        if self.isDirectory():
            if not osp.exists(self.getDirectory()):
                self.showMessage(msg='The system could not find the path specified\n%s'%self.getDirectory())
                return
        shots = self.getSelectedShots()
        if any([shot.preview for shot in shots]):
            if not self.smoothGeosets:
                btn = self.showMessage(msg='Geosets not selected to make them smooth',
                                       ques='Do you want to make all Geosets smooth?',
                                       icon=QMessageBox.Question,
                                       btns=QMessageBox.Yes|QMessageBox.Cancel)
                if btn == QMessageBox.Cancel:
                    return
        if be.sceneModified():
            btn = self.showMessage(msg='Scene contains unsaved changes',
                                   ques='Do you want to save changes?',
                                   icon=QMessageBox.Question,
                                   btns=QMessageBox.Yes|QMessageBox.No|QMessageBox.Cancel)
            if btn == QMessageBox.Cancel: return
            if btn == QMessageBox.Yes: be.saveScene()
        errors = {}
        try:
            self.setBusy()
            try:
                be.clearHomeDirectory()
            except Exception as ex:
                self.showMessage(msg=str(ex), icon=QMessageBox.Critical)
                return
            if shots:
                be.displaySmoothness(False)
                if any([shot.preview for shot in shots]):
                    imaya.toggleViewport2Point0(True)
                    imaya.toggleTextureMode(True)
                    be.displaySmoothness(True, self.smoothGeosets)
                time1 = time2 = dataSize = 0
                self.showProgressBar(len(shots))
                for i, shot in enumerate(shots):
                    err = shot.export()
                    time1 += shot.exportTime
                    time2 += shot.saveTime
                    dataSize += shot.dataSize
                    if err: errors[shot.cameraName] = err
                    self.updateProgressBar(i + 1)
                if time1 > 60: time1 /= 60.0; time1 = str(round(time1, 2)) + ' Min'
                else: time1 = str(round(time1, 2)) + ' Sec'
                if time2 > 60: time2 /= 60.0; time2 = str(round(time2, 2)) + ' Min'
                else: time2 = str(round(time2, 2)) + ' Sec'
                self.setStatus('Data: %s MB  -  Export Time: %s  -  Save Time: %s'%(dataSize, time1, time2))
                if not os.environ['USERNAME'] in ['qurban.ali', 'talha.ahmed']:
                    be.backupMayaFile(self.getSeq())
            if errors:
                self.showMessage(msg='Errors occurred while exporting Shots',
                                 details=qutil.dictionaryToDetails(errors),
                                 icon=QMessageBox.Critical)
        except Exception as ex:
            self.showMessage(msg=str(ex), icon=QMessageBox.Critical)
        finally:
            self.releaseBusy()
            self.hideProgressBar()
            #self.clearStatus()
            be.displaySmoothness(False)
            imaya.toggleTextureMode(False)
            imaya.toggleViewport2Point0(False)

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
        self.geosetButton = []
        self.update()
        
        self.style = ('background-image: url(%s);\n'+
                      'background-repeat: no-repeat;\n'+
                      'background-position: center right')
        self.iconLabel.setStyleSheet(self.style%osp.join(iconPath,
                                                         'ic_collapse.png').replace('\\', '/'))
        self.switchButton.setIcon(QIcon(osp.join(iconPath, 'ic_switch_camera.png')))
        self.appendButton.setIcon(QIcon(osp.join(iconPath, 'ic_append_char.png')))
        self.removeButton.setIcon(QIcon(osp.join(iconPath, 'ic_remove_char.png')))
        self.addButton.setIcon(QIcon(osp.join(iconPath, 'ic_add_char.png')))

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
        self.addButton.clicked.connect(self.addSelectedGeoSets)
        self.appendButton.clicked.connect(self.appendSelectedGeoSets)
        self.removeButton.clicked.connect(self.removeSelectedGeoSets)
        self.browseButton.clicked.connect(self.openLocation)
        
        self.splitter.setSizes([(self.width() * 40) / 100, (self.width() * 40) / 100, (self.width() * 20) / 100])
        
    def openLocation(self):
        self.shot.openLocation()
#             self.parentWin.showMessage(msg='Errors occurred while getting path from TACTIC',
#                                        icon=QMessageBox.Critical,
#                                        details=iutil.dictionaryToDetails(err))
        
    def addSelectedGeoSets(self):
        self.shot.addSelectedGeoSets()
        self.update()
    
    def appendSelectedGeoSets(self):
        self.shot.appendSelectedGeoSets()
        self.update()
    
    def removeSelectedGeoSets(self):
        self.shot.removeSelectedGeoSets()
        self.update()
        
    def toggleCacheSelectAllButton(self):
        # Check the Select All button is all the asset buttons get selected
        self.cSelectAllButton.setChecked(all([btn.isChecked() for btn in self.geosetButton]))
        # update the assets on the camera attribute
        self.shot.updateGeoSets({btn.text(): btn.isChecked() for btn in self.geosetButton})
    
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
        for btn in self.geosetButton:
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
        if self.shot.startFrame is not None and self.shot.endFrame is not None:
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
        for btn in self.geosetButton:
            btn.deleteLater()
        del self.geosetButton[:]
        for asset, val in self.shot.geosets.items():
            btn = QCheckBox(asset)
            btn.setChecked(val)
            btn.toggled.connect(self.toggleCacheSelectAllButton)
            self.geosetButton.append(btn)
            self.assetLayout.addWidget(btn)
            if not be.isGeoSetValid(asset):
                btn.setChecked(False)
                btn.setEnabled(False)
        # populate the display layer buttons
        for btn in self.displayLayerButtons:
            btn.deleteLater()
        del self.displayLayerButtons[:]
        for layer, val in self.shot.displayLayers.items():
            btn = QCheckBox(layer)
            btn.setChecked(val)
            btn.toggled.connect(self.togglePreviewSelectAllButton)
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

Form3, Base3 = uic.loadUiType(osp.join(uiPath, 'geosets.ui'))
class GeosetDialog(Form3, Base3):
    def __init__(self, parent=None):
        super(GeosetDialog, self).__init__(parent)
        self.setupUi(self)
        self.parentWin = parent
        self.setWindowTitle('Smooth Box')
        
        self.appendButton.setIcon(QIcon(osp.join(iconPath, 'ic_append_char.png')))
        self.removeButton.setIcon(QIcon(osp.join(iconPath, 'ic_remove_char.png')))
        self.addButton.setIcon(QIcon(osp.join(iconPath, 'ic_add_char.png')))
        
        self.items = []
        
        self.okButton.clicked.connect(self.ok)
        self.selectAllButton.clicked.connect(self.selectAll)
        self.addButton.clicked.connect(self.addSelection)
        self.appendButton.clicked.connect(self.appendSelection)
        self.removeButton.clicked.connect(self.removeSelection)
        
        self.populate()
        self.checkSelectAllButton()
        
    def addSelection(self):
        geosets = [geoset.name() for geoset in be.findAllConnectedGeosets()]
        if geosets:
            for item in self.items:
                item.setChecked(item.text() in geosets)
    
    def appendSelection(self):
        geosets = [geoset.name() for geoset in be.findAllConnectedGeosets()]
        if geosets:
            for item in self.items:
                if item.text() in geosets:
                    item.setChecked(True)
    
    def removeSelection(self):
        geosets = [geoset.name() for geoset in be.findAllConnectedGeosets()]
        if geosets:
            for item in self.items:
                if item.text() in geosets:
                    item.setChecked(False)
        
    def selectAll(self):
        for item in self.items:
            item.setChecked(self.selectAllButton.isChecked())
    
    def checkSelectAllButton(self):
        self.selectAllButton.setChecked(all([item.isChecked() for item in self.items]))

    def closeEvent(self, event):
        self.deleteLater()

    def populate(self):
        for geoset in be.getGeoSets():
            chbox = QCheckBox(geoset.name(), self)
            self.itemsLayout.addWidget(chbox)
            chbox.toggled.connect(self.checkSelectAllButton)
            self.items.append(chbox)
            if self.parentWin.smoothGeosets:
                chbox.setChecked(geoset.name() in self.parentWin.smoothGeosets)
            else:
                chbox.setChecked(True)

    def getSmoothGeosets(self):
        return [item.text() for item in self.items if item.isChecked()]

    def ok(self):
        self.accept()