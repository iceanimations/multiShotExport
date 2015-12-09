'''
Created on Nov 24, 2015

@author: qurban.ali
'''
import pymel.core as pc
import tacticCalls as tc
import os.path as osp
import fillinout
import shutil
import iutil
import imaya
import json
import os

reload(tc)
reload(iutil)
reload(imaya)
reload(fillinout)

# create a directory to temporarily export the files 
tempLocation = osp.join(osp.expanduser('~'), 'multiShotExport')
if not osp.exists(tempLocation):
    os.mkdir(tempLocation)

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
        self.geosets = {} # contains all the assets in this shot retrieved from tactic as keys, with True or False as value
        self.displayLayers = {} # contais all the display layers found in the scene as keys, with True or False as value
        self.hdPreview = True # determines whether to export 720 preview or not
        self.fullHdPreview = True # determines whether to export 1080 preview or not
        self.jpgPreview = True # determines whether to export preview as jpg sequence or not
        self.bakeCamera = False # determines whether to bake camera or not before export
        self.nukeCamera = True # determines whether to export camera for nuke or not
        self.tempPath = None # temp path to shot directory in user home
        
        #TODO: add nano texture export feature

        self.setup()
        self.saveToScene()

    def saveToScene(self):
        # save the settings of each shot on the camera attribute
        if not self.cameraName: return
        data = {'cache': self.cache, 'preview': self.preview,
                'camera': self.camera,
                'displayLayers': self.displayLayers, 'hdPreview': self.hdPreview,
                'fullHdPreview': self.fullHdPreview, 'jpgPreview': self.jpgPreview,
                'bakeCamera': self.bakeCamera, 'nukeCamera': self.nukeCamera,
                'geosets': self.geosets}
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
            # create the shot directory in user home
            self.tempPath = osp.join(tempLocation, self.getCameraNiceName())
            if not osp.exists(self.tempPath):
                os.mkdir(self.tempPath)
        
        # set the frame range
        frameRange, err = tc.getFrameRange(self.shot)
        if frameRange:
            self.startFrame, self.endFrame = frameRange
        errors.update(err)

        assets, err = tc.getAssetsInShot(self.shot)
        assets = [x['asset_code'].lower() for x in assets]
        errors.update(err)
        if data:
            # set the assets
            for geoset in getGeoSets():
                name = imaya.getNiceName(geoset.name()).lower().replace('_geo_set', '')
                if not geoset.name() in data['geosets'].keys():
                    data['geosets'][geoset.name()] = name in assets
            # remove extra goesets from self.geosets
            extraKeys = []
            for geoset in data['geosets'].keys():
                if geoset not in [gs.name() for gs in getGeoSets()]:
                    extraKeys.append(geoset)
            for ek in extraKeys: self.geosets.remove(ek)
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
            for geoset in getGeoSets():
                name = imaya.getNiceName(geoset.name()).lower().replace('_geo_set', '')
                self.geosets[geoset.name()] = name in assets
            # set the display layers
            for layer in imaya.getDisplayLayers():
                self.displayLayers[layer.name()] = layer.visibility.get()
            self.bakeCamera = self.isCamBakeable()
            
    def updateGeoSets(self, assets):
        self.geosets.clear()
        self.geosets.update(assets)
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
            
    def getCameraNiceName(self):
        return imaya.getNiceName(self.cameraName)
            
    def isCamBakeable(self):
        flag = False
        try:
            if pc.nt.ParentConstraint in [obj.__class__ for obj in pc.PyNode(self.cameraName).firstParent().getChildren()]:
                flag = True
        except:
            pass
        return flag
    
    def export(self):
        if not self.cameraName: return
        errors = []
        self.switchToMe()
        err = self.exportCamera()
        if err: errors.append(err)
        #TODO: restore the displayLayer states
        err = self.exportPreview()
        if err: errors.append(err)
        return errors
    
    def exportCache(self):
        if not self.cache: return
        pc.select(cl=True)
        if self.geosets:
            conf = getConf()
            conf['start_time'] = self.startFrame
            conf['end_time'] = self.endFrame
            conf['cache_dir'] = osp.join(self.tempPath, 'cache')
            command =  'doCreateGeometryCache3 {version} {{ "{time_range_mode}", "{start_time}", "{end_time}", "{cache_file_dist}", "{refresh_during_caching}", "{cache_dir}", "{cache_per_geo}", "{cache_name}", "{cache_name_as_prefix}", "{action_to_perform}", "{force_save}", "{simulation_rate}", "{sample_multiplier}", "{inherit_modf_from_cache}", "{store_doubles_as_float}", "{cache_format}", "{worldSpace}"}};'.format(**conf)
            meshes = self.MakeMeshes()
            pc.select(meshes)
            pc.Mel.eval(command)
            pc.delete(meshes)
    
    def makeMeshes(self):
        errors = []
        combinedMeshes = []
        for geoset in [pc.PyNode(gs) for gs in self.geosets]:
            meshes = [shape
                      for transform in geoset.dsm.inputs()
                      for shape in transform.getShapes(type = "mesh",
                                                       ni = True)]
            if not meshes:
                errors.append('%s does not contain a valid Mesh'%geoset.name())
                continue
            combinedMesh = pc.createNode("mesh")
            try:
                name = geoset.cacheName.get()
            except AttributeError:
                errors.append('%s is not a valid geoset'%geoset.name())
                continue
            pc.rename(combinedMesh, name)
            combinedMeshes.append(combinedMesh)
            polyUnite = pc.createNode("polyUnite")
            for i in xrange(0, len(meshes)):
                meshes[i].outMesh >> polyUnite.inputPoly[i]
                meshes[i].worldMatrix[0] >> polyUnite.inputMat[i]
            polyUnite.output >> combinedMesh.inMesh
        return combinedMeshes
    
    def exportPreview(self):
        if not self.preview: return
        for layer, val in self.displayLayers:
            layer.visibility.set(val)
        try:
            if self.hdPreview:
                self.playblast((1280, 720))
            if self.fullHdPreview:
                self.playblast((1920, 1080), hd=True)
            if self.jpgPreview:
                #TODO: Add the code to export preview as jpg sequence
                pass
        except Exception as ex:
            return str(ex)

    def playblast(self, resolution, hd=False):
        try:
            audio = pc.ls(type='audio')[0]
        except IndexError:
            audio = ''
        if hd:
            path = osp.join(self.tempPath, 'preview', 'HD')
        else:
            path = osp.join(self.tempPath, 'preview')
        pc.playblast(f=osp.join(path, self.getCameraNiceName()),
                     format='qt', fo=1, st=self.startFrame, et=self.endFrame,
                     s=audio, sequenceTime=0, clearCache=1, viewer=0,
                     showOrnaments=1, fp=4, percent=100, compression="H.264",
                     quality=100, widthHeight=resolution,
                     offScreen=1, orn=0)
    
    def exportCamera(self):
        if not self.camera: return
        try:
            path = osp.join(self.tempPath, 'camera')
            orig_cam = pc.PyNode(self.cameraName)
            pc.select(orig_cam)
            if self.bakeCamera:
                # duplicate and and bake the camera
                duplicate_cam = pc.duplicate(rr=True, name='mutishot_export_duplicate_camera')[0]
                pc.parent(duplicate_cam, w=True)
                pc.select([orig_cam, duplicate_cam])
                constraints = set(pc.ls(type=pc.nt.ParentConstraint))
                pc.mel.eval('doCreateParentConstraintArgList 1 { "1","0","0","0","0","0","0","1","","1" };')
                if constraints:
                    cons = set(pc.ls(type=pc.nt.ParentConstraint)).difference(constraints).pop()
                else:
                    cons = pc.ls(type=pc.nt.ParentConstraint)[0]
                pc.select(cl=True)
                pc.select(duplicate_cam)
                pc.mel.eval('bakeResults -simulation true -t "%s:%s" -sampleBy 1 -disableImplicitControl true -preserveOutsideKeys true -sparseAnimCurveBake false -removeBakedAttributeFromLayer false -removeBakedAnimFromLayer false -bakeOnOverrideLayer false -minimizeRotation true -controlPoints false -shape true {\"%s\"};'%(self.plItem.inFrame, self.plItem.outFrame, duplicate_cam.name()))
                pc.delete(cons)
                name = self.getCameraNiceName()
                name2 = imaya.getNiceName(orig_cam.firstParent().name())
                pc.rename(orig_cam, 'temp_cam_name_from_multiShotExport')
                pc.rename(orig_cam.firstParent(), 'temp_group_name_from_multiShotExport')
                pc.rename(duplicate_cam, name)
                for node in pc.listConnections(orig_cam.getShape()):
                    if isinstance(node, pc.nt.AnimCurve):
                        try:
                            attr = node.outputs(plugs=True)[0].name().split('.')[-1]
                        except IndexError:
                            continue
                        attribute = '.'.join([duplicate_cam.name(), attr])
                        node.output.connect(attribute, f=True)
                pc.select(duplicate_cam)
            pc.exportSelected(osp.join(path, self.getCameraNiceName()).replace('\\', '/'),
                              force=True,
                              expressions = True,
                              constructionHistory = False,
                              channels = True,
                              shader = False,
                              constraints = False,
                              options="v=0",
                              typ=imaya.getFileType(),
                              pr = False)
            if self.nukeCamera:
                pc.exportSelected(osp.join(path, self.getCameraNiceName()).replace('\\', '/'),
                                  force=True, options="v=0;", typ="FBX export", pr=True)
            if self.bakeCamera:
                pc.delete(duplicate_cam)
                pc.rename(orig_cam, name)
                pc.rename(orig_cam.firstParent(), name2)
        except Exception as ex:
            return str(ex)
    
def makeSetsUniqueName():
    '''Create an attribute on geo sets to set a unique name if the sets are duplicate'''
    pass

def clearHomeDirectory():
    for phile in os.listdir(tempLocation):
        path = osp.join(tempLocation, phile)
        print 'removing %s'%path
        if osp.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
def getConf():
    conf = dict()
    conf["version"] = 6
    conf["time_range_mode"] = 0
    conf["cache_file_dist"] = "OneFile"
    conf["refresh_during_caching"] = 0
    conf["cache_per_geo"] = "1"
    conf["cache_name"] = ""
    conf["cache_name_as_prefix"] = 0
    conf["action_to_perform"] = "export"
    conf["force_save"] = 0
    conf["simulation_rate"] = 1
    conf["sample_multiplier"] = 1
    conf["inherit_modf_from_cache"] = 1
    conf["store_doubles_as_float"] = 1
    conf["cache_format"] = "mcc"
    conf["do_texture_export"] = 1
    conf["texture_export_data"] = [
            ("(?i).*nano_regular.*", ["ExpRenderPlaneMtl.outColor"]),
            ("(?i).*nano_docking.*", ["ExpRenderPlaneMtl.outColor"]),
            ("(?i).*nano_covered.*", ["ExpRenderPlaneMtl.outColor"]),
            ("(?i).*nano_with_bowling_arm.*", ["ExpRenderPlaneMtl.outColor"]),
            ("(?i).*nano_shawarma.*", ["NanoShawarmaExpRenderPlaneMtl.outColor"])]
    conf["texture_resX"] = 1024
    conf["texture_resY"] = 1024
    conf["worldSpace"] = 1
    return conf

def getGeoSets():
    return [geoset for geoset in pc.ls(exactType=pc.nt.ObjectSet)
            if geoset.name().lower().endswith('_geo_set')]