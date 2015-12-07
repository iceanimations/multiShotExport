'''
Created on Nov 24, 2015

@author: qurban.ali
'''
import pymel.core as pc
import tacticCalls as tc
import os.path as osp
import fillinout
import iutil
import imaya
import json

reload(tc)
reload(iutil)
reload(imaya)
reload(fillinout)

class Shot(object):
    def __init__(self, parent, shot):
        self.parentWin = parent
        self.shot = shot
        self.cache = True # determines whether to export cache or not
        self.preview = True # determines whether to export preview or not
        self.camera = True # determines whether to export camera or not
        self.cameraName = None
        self.startFrame = None
        self.endFrame = None
        self.assets = {} # contains all the assets in this shot retrieved from tactic as keys, with True or False as value
        self.displayLayers = {} # contais all the display layers found in the scene as keys, with True or False as value
        self.hdPreview = True # determines whether to export 720 preview or not
        self.fullHdPreview = True # determines whether to export 1080 preview or not
        self.jpgPreview = True # determines whether to export preview as jpg sequence or not
        self.bakeCamera = False # determines whether to bake camera or not before export
        self.nukeCamera = True # determines whether to export camera for nuke or not

        self.setup()
        self.saveToScene()

    def saveToScene(self):
        if not self.cameraName: return
        data = {'cache': self.cache, 'preview': self.preview,
                'camera': self.camera,
                'displayLayers': self.displayLayers, 'hdPreview': self.hdPreview,
                'fullHdPreview': self.fullHdPreview, 'jpgPreview': self.jpgPreview,
                'bakeCamera': self.bakeCamera, 'nukeCamera': self.nukeCamera,
                'assets': self.assets}
        pc.PyNode(self.cameraName).mseData.set(json.dumps(data))
    
    def addAttr(self):
        if self.cameraName:
            node = pc.PyNode(self.cameraName)
            if not node.hasAttr('mseData'):
                pc.addAttr(node, sn='mseData', ln='multiShotExportData', dt='string', h=True)
        
    def setup(self):
        '''initializes all the member variable according to the data
        stored on camera or to the default values'''
        errors = {}
        data = None
        # set the camera name
        for cam in pc.ls(type='camera'):
            if imaya.getNiceName(cam.firstParent().name()).lower() == self.shot.lower():
                self.cameraName = cam.firstParent().name()
        
        self.addAttr()
        
        # get the data from the camera attribute
        if self.cameraName:
            rawData = pc.PyNode(self.cameraName).mseData.get()
            if rawData:
                data = json.loads(rawData)
        
        # set the frame range
        frameRange, err = tc.getFrameRange(self.shot)
        if frameRange:
            self.startFrame, self.endFrame = frameRange
        errors.update(err)

        assets, err = tc.getAssetsInShot(self.shot)
        assets = [x['asset_code'] for x in assets]
        errors.update(err)
        if data:
            # set the assets
            for asset in assets:
                if data['assets'].has_key(asset):
                    self.assets[asset] = data['assets'][asset]
                else:
                    self.assets[asset] = True
            # set display layers
            for layer in imaya.getDisplayLayers():
                if data['displayLayers'].has_key(layer.name()):
                    self.displayLayers[layer.name()] = data['displayLayers'][layer.name()]
                else:
                    self.displayLayers[layer.name()] = layer.visibility.get()
            # set all remaining attributes
            self.cache = data['cache']
            self.preview = data['preview']
            self.camera = data['camera']
            self.hdPreview = data['hdPreview']
            self.fullHdPreview = data['fullHdPreview']
            self.jpgPreview = data['jpgPreview']
            self.bakeCamera = data['bakeCamera']
            self.nukeCamera = data['nukeCamera']
        else:
            # set the assets
            for asset in assets: 
                self.assets[asset] = True
            # set the display layers
            for layer in imaya.getDisplayLayers():
                self.displayLayers[layer.name()] = layer.visibility.get()
            self.bakeCamera = self.isCamBakeable()
            
    def updateAssets(self, assets):
        self.assets.clear()
        self.assets.update(assets)
        self.saveToScene()
    
    def updateLayers(self, layers):
        self.displayLayers.clear()
        self.displayLayers.update(layers)
        self.saveToScene()
            
    def switchToMe(self):
        if self.cameraName:
            try:
                pc.lookThru(self.cameraName)
                sl = pc.ls(sl=True)
                pc.select(self.cameraName)
                fillinout.fill()
                pc.select(sl)
            except Exception as ex:
                return str(ex)
            
    def isCamBakeable(self):
        return False
    
    def exportCache(self):
        pass
    
    def exportPreview(self):
        pass
    
    def exportCamera(self):
        pass

    def getCombinedMeshFromSet(self):
        pass
    
    def configureDisplayLayers(self):
        pass
    
    def setResolution(self, resolution):
        pass
    
    def bakeCam(self):
        pass
    
    def exportFBXCamera(self):
        pass
    
    def export(self):
        pass