'''
Created on Nov 24, 2015

@author: qurban.ali
'''
from shot_subm.src.backend import findAllConnectedGeosets
from createLayout.src import utilities as utils
import pymel.core as pc
import maya.cmds as cmds
import os.path as osp
from datetime import datetime
import subprocess
import fillinout
import shutil
import iutil
import imaya
import time
import json
import os
import re

reload(utils)
reload(iutil)
reload(imaya)
reload(fillinout)

# create a directory to temporarily export the files
tempLocation = osp.join(osp.expanduser('~'), 'multiShotExport')
if not osp.exists(tempLocation):
    os.mkdir(tempLocation)

openMotionPath = "\"R:/Pipe_Repo/Users/Qurban/Scripts/openMotion.mel\""
mel = """
source %s;
""" % openMotionPath
if not osp.exists(openMotionPath.strip('"')):
    print 'Could not find %s, Nuke camera won\'t be exported' % openMotionPath
pc.mel.eval(mel)

timeUnits = {
    'game': 15,
    'film': 24,
    'pal': 25,
    'ntsc': 30,
    'show': 48,
    'palf': 50,
    'ntscf': 60
}


class Shot(object):
    def __init__(self,
                 parent=None,
                 shot=None,
                 user=iutil.getUsername(),
                 frameRange=None,
                 assets=None):
        self.parentWin = parent
        self.shot = shot
        self.cache = True  # determines whether to export cache or not
        self.preview = True  # determines whether to export preview or not
        self.camera = True  # determines whether to export camera or not
        self.username = user
        self.cameraName = None
        self.startFrame = None
        self.endFrame = None
        # contains all the assets in this shot retrieved from tactic as
        # keys, with True or False as value
        self.geosets = {
        }
        # contais all the display layers found in the scene as keys, with True
        # or False as value
        self.displayLayers = {}
        # determines whether to export 720 preview or not
        self.hdPreview = False
        # determines whether to export 1080 preview or not
        self.fullHdPreview = True
        # determines whether to export preview as jpg sequence or not
        self.jpgPreview = True
        # determines whether to bake camera or not before export
        self.bakeCamera = True
        # determines whether to export camera for nuke or not
        self.nukeCamera = True
        # temp path to shot directory in user home
        self.tempPath = None
        self.dataSize = 0
        self.exportTime = 0

        self.setup(frameRange, assets)
        self.saveToScene()

    def saveToScene(self):
        # save the settings of each shot on the camera attribute
        if not self.cameraName:
            return
        data = {
            'cache': self.cache,
            'preview': self.preview,
            'camera': self.camera,
            'displayLayers': self.displayLayers,
            'hdPreview': self.hdPreview,
            'fullHdPreview': self.fullHdPreview,
            'jpgPreview': self.jpgPreview,
            'bakeCamera': self.bakeCamera,
            'nukeCamera': self.nukeCamera,
            'geosets': self.geosets,
            'frameRange': (self.startFrame, self.endFrame)
        }
        pc.PyNode(self.cameraName).mseData.set(json.dumps(data))

    def addAttr(self):
        if self.cameraName:
            node = pc.PyNode(self.cameraName)
            if not node.hasAttr('mseData'):
                pc.addAttr(
                    node,
                    sn='mseData',
                    ln='multiShotExportData',
                    dt='string',
                    h=True)

    def setup(self, frameRange, assets):
        '''initializes all the member variable according to the data
        stored on camera or to the default values'''
        data = None
        # set the camera name
        for cam in pc.ls(type='camera'):
            if imaya.getNiceName(
                    cam.firstParent().name()).lower() == self.shot.lower():
                self.cameraName = cam.firstParent().name()
        if not self.cameraName:
            return

        self.addAttr()

        # get the data from the camera attribute
        rawData = pc.PyNode(self.cameraName).mseData.get()
        if rawData:
            data = json.loads(rawData)
        # set the frame range
        if frameRange:
            self.startFrame, self.endFrame = frameRange
        if data:
            # set the assets
            for geoset in getGeoSets():
                name = imaya.getNiceName(geoset.name()).lower().replace(
                    '_geo_set', '')
                if geoset.name() in data['geosets']:
                    self.geosets[geoset.name()] = data['geosets'][
                        geoset.name()]
                else:
                    self.geosets[
                        geoset.name()] = name in assets if assets else True
            # set display layers
            for layer in imaya.getDisplayLayers():
                if layer.name() in data['displayLayers']:
                    self.displayLayers[layer.name()] = data['displayLayers'][
                        layer.name()]
                else:
                    self.displayLayers[layer.name()] = layer.visibility.get()
            # set the frame range
            fr = data.get('frameRange')
            if (self.startFrame and self.endFrame) is None:
                self.startFrame, self.endFrame = fr
            # set all remaining attributes
            self.cache = data['cache']
            self.preview = data['preview']
            self.camera = data['camera']
            self.hdPreview = False  # data['hdPreview']
            self.fullHdPreview = True  # data['fullHdPreview']
            self.jpgPreview = True  # data['jpgPreview']
            self.bakeCamera = True  # data['bakeCamera']
            self.nukeCamera = True  # data['nukeCamera']
        else:
            # set the assets
            for geoset in getGeoSets():
                name = imaya.getNiceName(geoset.name()).lower().replace(
                    '_geo_set', '')
                self.geosets[
                    geoset.name()] = name in assets if assets else True
            # set the display layers
            for layer in imaya.getDisplayLayers():
                self.displayLayers[layer.name()] = layer.visibility.get()
            self.bakeCamera = self.isCamBakeable()

    def addSelectedGeoSets(self):
        geosets = findAllConnectedGeosets()
        if geosets:
            self.geosets.clear()
            for geoset in getGeoSets():
                if geoset in geosets:
                    self.geosets[geoset.name()] = True
                else:
                    self.geosets[geoset.name()] = False
            self.saveToScene()

    def appendSelectedGeoSets(self):
        geosets = findAllConnectedGeosets()
        if geosets:
            for geoset in getGeoSets():
                if geoset in geosets:
                    if not self.geosets.get(geoset.name()):
                        self.geosets[geoset.name()] = True
            self.saveToScene()

    def removeSelectedGeoSets(self):
        geosets = findAllConnectedGeosets()
        if geosets:
            for geoset in getGeoSets():
                if geoset in geosets:
                    if self.geosets.get(geoset.name()):
                        self.geosets[geoset.name()] = False
            self.saveToScene()

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
            if pc.nt.ParentConstraint in [
                    obj.__class__
                    for obj in pc.PyNode(
                        self.cameraName).firstParent().getChildren()
            ]:
                flag = True
        except:
            pass
        return flag

    def export(self):
        if not self.cameraName:
            return
        # create the shot directory in user home
        self.tempPath = osp.join(tempLocation, self.getCameraNiceName())
        if not osp.exists(self.tempPath):
            os.mkdir(self.tempPath)
        errors = []
        self.switchToMe()
        hideFaceUi()
        hideShowCurves(True)
        t2 = time.time()
        if self.parentWin:
            self.parentWin.setStatus(
                '%s: Exporting Camera' % self.getCameraNiceName())
        else:
            print '%s: Exporting Camera' % self.getCameraNiceName()
        err = self.exportCamera()
        if err:
            errors.append(err)
            print err
        state = getDisplayLayerState()
        if self.parentWin:
            self.parentWin.setStatus(
                '%s: Exporting Preview' % self.getCameraNiceName())
        else:
            print '%s: Exporting Preview' % self.getCameraNiceName()
        err = self.exportPreview()
        restoreDisplayLayerState(state)
        if err:
            errors.append(err)
            print err
        if self.parentWin:
            self.parentWin.setStatus(
                '%s: Exporting Cache' % self.getCameraNiceName())
        else:
            print '%s: Exporting Cache' % self.getCameraNiceName()
        err = self.exportCache()
        if err:
            errors.extend(err)
            print err
        if self.parentWin:
            self.parentWin.setStatus(
                '%s: Exporting Animated Textures' % self.getCameraNiceName())
        else:
            print '%s: Exporting Animated Textures' % self.getCameraNiceName()
        err = self.exportAnimatedTextures()
        self.exportTime = time.time() - t2
        if err:
            errors.append(err)
            print err
        self.dataSize = iutil.get_directory_size(self.tempPath)
        showFaceUi()
        hideShowCurves(False)
        return errors

    def exportCache(self):
        if not self.cache:
            return
        errors = []
        try:
            pc.select(cl=True)
            if self.geosets:
                conf = getConf()
                conf['start_time'] = self.startFrame
                conf['end_time'] = self.endFrame
                conf['cache_dir'] = osp.join(self.tempPath, 'cache').replace(
                    '\\', '/')
                command = (
                    'doCreateGeometryCache3 {version} {{ "{time_range_mode}",'
                    '"{start_time}", "{end_time}", "{cache_file_dist}",'
                    '"{refresh_during_caching}", "{cache_dir}",'
                    '"{cache_per_geo}", "{cache_name}",'
                    '"{cache_name_as_prefix}", "{action_to_perform}",'
                    '"{force_save}", "{simulation_rate}", '
                    '"{sample_multiplier}", "{inherit_modf_from_cache}", '
                    '"{store_doubles_as_float}", "{cache_format}", '
                    '"{worldSpace}"}};').format(
                    **conf)
                meshes, err = self.makeMeshes()
                if err:
                    errors.extend(err)
                if meshes:
                    pc.select(meshes)
                    pc.Mel.eval(command)
                    pc.delete([mesh.firstParent() for mesh in meshes])
        except Exception as ex:
            errors.append(str(ex))
        return errors

    def makeMeshes(self):
        errors = []
        combinedMeshes = []
        for geoset in [
                pc.PyNode(gs) for gs, val in self.geosets.items() if val
        ]:
            meshes = [
                shape
                for transform in geoset.dsm.inputs()
                for shape in transform.getShapes(type="mesh", ni=True)
            ]
            if not meshes:
                errors.append(
                    '%s does not contain a valid Mesh' % geoset.name())
                continue
            combinedMesh = pc.createNode("mesh")
            try:
                name = geoset.cacheName.get()
            except AttributeError:
                errors.append('%s is not a valid geoset' % geoset.name())
                continue
            pc.rename(combinedMesh, name)
            combinedMeshes.append(combinedMesh)
            polyUnite = pc.createNode("polyUnite")
            for i in xrange(0, len(meshes)):
                meshes[i].outMesh >> polyUnite.inputPoly[i]
                meshes[i].worldMatrix[meshes[i].instanceNumber(
                )] >> polyUnite.inputMat[i]
            polyUnite.output >> combinedMesh.inMesh
        return combinedMeshes, errors

    def exportPreview(self):
        if not self.preview:
            return
        jpgPath = osp.join(self.tempPath, 'JPG')
        if not osp.exists(jpgPath):
            os.mkdir(jpgPath)
        jpgPath = osp.join(jpgPath, self.getCameraNiceName() + '.%05d.jpg')
        for layer, val in self.displayLayers.items():
            pc.PyNode(layer).visibility.set(int(val))
        overscan = pc.camera(self.cameraName, overscan=True, q=True)
        panZoomEnabled = pc.PyNode(self.cameraName).panZoomEnabled.get()
        pc.PyNode(self.cameraName).panZoomEnabled.set(0)
        pc.camera(self.cameraName, e=True, overscan=1)
        imgMgcPath = 'C:\\Program Files\\ImageMagick-6.9.1-Q8'
        if not osp.exists(imgMgcPath):
            imgMgcPath = r'R:\Pipe_Repo\Users\Qurban\applications\ImageMagick'
            print 'Could not find ImageMagick, loading from %s' % imgMgcPath
            if not osp.exists(imgMgcPath):
                print 'Could not find %s' % imgMgcPath
        try:
            path = self.playblast((1920, 1080)) + '.mov'
            # convert video preview to jpgs
            if self.startFrame != 0:
                startFrame = '-start_number %s ' % self.startFrame
            else:
                startFrame = ''
            subprocess.call(
                '\"' + osp.join(imgMgcPath,
                                'ffmpeg.exe') + '\" -i %s %s-q:v 2 %s' %
                (osp.normpath(path), startFrame, osp.normpath(jpgPath)),
                shell=True)
            # rename the files when self.frame == 0
            frameRange = list(
                reversed(range(self.startFrame, self.endFrame + 1)))
            if not startFrame:
                for image in sorted(os.listdir(osp.dirname(jpgPath))):
                    newName = re.sub(
                        '\.\d{5}\.',
                        '.' + str(frameRange.pop()).zfill(5) + '.', image)
                    imagePath = osp.join(osp.dirname(jpgPath), newName)
                    os.rename(osp.join(osp.dirname(jpgPath), image), imagePath)
            # add info to the jpgs
            cameraName = self.getCameraNiceName()
            time = getDateTime()
            jpgPath = osp.dirname(jpgPath)
            fps = '25'
            currentTimeUnit = pc.currentUnit(q=True, time=True)
            if currentTimeUnit in timeUnits:
                fps = str(timeUnits[currentTimeUnit])
            focalLength = str(pc.PyNode(self.cameraName).focalLength.get())
            for image in sorted(os.listdir(jpgPath)):
                imagePath = osp.join(jpgPath, image)
                subprocess.call(
                    '\"' + osp.join(imgMgcPath, 'convert.exe') + (
                        '\" %s -undercolor #00000060 -pointsize 35 '
                        '-channel RGBA -fill white -draw "text 20,30 %s" '
                        '-draw "text 850,30 %s" -draw "text 1680,30 %s" '
                        '-draw "text 20,1050 %s" -draw "text 800,1050 %s" '
                        '-draw "text 1680,1050 %s" %s') % (
                        imagePath, self.username, cameraName,
                        'Frame_' + image.split('.')[1],
                        'FocalLength_' + focalLength, 'Time_' + time,
                        'FPS_' + fps, imagePath),
                    shell=True)
            # convert labled jpgs to .mov
            movPath = osp.join(self.tempPath, 'preview',
                               self.getCameraNiceName() + '.mov')
            # extract audio
            audioPath = osp.normpath(
                osp.join(osp.dirname(movPath), 'audio.wav'))
            subprocess.call(
                '\"' + osp.join(imgMgcPath, 'ffmpeg.exe') +
                '\" -i %s -vn -acodec copy %s' % (movPath, audioPath),
                shell=True)
            os.remove(movPath)
            # create mov file from jpgs
            subprocess.call(
                '\"' + osp.join(imgMgcPath,
                                'ffmpeg.exe') + '\" ' + ' -framerate ' + fps +
                ' -start_number ' + str(self.startFrame) + ' -i ' + osp.join(
                    jpgPath, self.getCameraNiceName() + '.%05d.jpg') +
                ' -c:v libx264 -x264opts b_pyramid=0 -g 1 -bf 1 ' + movPath,
                shell=True)
            # add extracted audio
            temp_hd = osp.join(osp.dirname(movPath), 'temp_hd.mov')
            temp_hd_2 = osp.join(osp.dirname(movPath), 'temp_hd_2.mov')
            if osp.exists(audioPath) and osp.getsize(audioPath) == 0:
                try:
                    os.remove(audioPath)
                    audioPath2 = osp.normpath(
                        pc.ls(type='audio')[0].filename.get())
                    subprocess.call(
                        '\"' + osp.join(imgMgcPath, 'ffmpeg.exe') +
                        '\" -i %s -ss %s -t %s -codec copy %s' %
                        (audioPath2.replace('\\', '\\\\'),
                         self.startFrame / float(fps),
                         (self.endFrame - self.startFrame) / float(fps),
                         audioPath.replace('\\', '\\\\')))
                except:
                    pass
            subprocess.call(
                '\"' + osp.join(imgMgcPath, 'ffmpeg.exe') +
                ('\" -i %s -i %s %s -shortest %s') %
                (movPath, audioPath,
                    '-c:v libx264 -x264opts b_pyramid=0 -g 1 -bf 1', temp_hd),
                shell=True)
            os.rename(movPath, temp_hd_2)
            try:  # if audio in 0 KB in size and no preview is generated
                os.rename(temp_hd, movPath)
                os.remove(temp_hd_2)
            except WindowsError:
                os.rename(temp_hd_2, movPath)
            if osp.exists(audioPath):
                os.remove(audioPath)
        except Exception as ex:
            return str(ex)

        finally:
            pc.camera(self.cameraName, e=True, overscan=overscan)
            pc.PyNode(self.cameraName).panZoomEnabled.set(panZoomEnabled)

    def playblast(self, resolution, hd=False):
        try:
            audio = pc.ls(type='audio')[0]
        except IndexError:
            audio = ''
        path = osp.join(self.tempPath, 'preview')
        if hd:
            name = self.getCameraNiceName() + '_hd'
        else:
            name = self.getCameraNiceName()
        return pc.playblast(
            f=osp.join(path, name),
            format='qt',
            fo=1,
            st=self.startFrame,
            et=self.endFrame,
            s=audio,
            sequenceTime=0,
            clearCache=1,
            viewer=0,
            fp=4,
            percent=100,
            compression='H.264',
            quality=100,
            widthHeight=resolution,
            offScreen=1,
            orn=0)

    def exportCamera(self):
        if not self.camera:
            return
        try:
            path = osp.join(self.tempPath, 'camera')
            if not osp.exists(path):
                os.mkdir(path)
            orig_cam = pc.PyNode(self.cameraName)
            pc.select(orig_cam)
            if self.bakeCamera:
                # duplicate and and bake the camera
                duplicate_cam = pc.duplicate(
                    rr=True, name='mutishot_export_duplicate_camera')[0]
                for attr in [
                        'tx', 'ty', 'tz', 'sx', 'sy', 'sz', 'rx', 'ry', 'rz'
                ]:
                    duplicate_cam.attr(attr).set(lock=0)
                pc.parent(duplicate_cam, w=True)
                pc.select([orig_cam, duplicate_cam])
                constraints = set(pc.ls(type=pc.nt.ParentConstraint))
                pc.mel.eval(
                    'doCreateParentConstraintArgList 1 '
                    '{ "0","0","0","0","0","0","0","1","","1" };'
                )
                if constraints:
                    cons = set(pc.ls(type=pc.nt.ParentConstraint)).difference(
                        constraints).pop()
                else:
                    cons = pc.ls(type=pc.nt.ParentConstraint)[0]
                pc.select(cl=True)
                pc.select(duplicate_cam)
                pc.mel.eval(('bakeResults -simulation true -t "%s:%s" '
                             '-sampleBy 1'
                             '-disableImplicitControl true '
                             '-preserveOutsideKeys true'
                             '-sparseAnimCurveBake false'
                             '-removeBakedAttributeFromLayer false'
                             '-removeBakedAnimFromLayer false'
                             '-bakeOnOverrideLayer false '
                             '-minimizeRotation true'
                             '-controlPoints false -shape true {\"%s\"};') % (
                                self.startFrame, self.endFrame,
                                duplicate_cam.name()))
                pc.delete(cons)
                name = self.getCameraNiceName()
                try:
                    name2 = imaya.getNiceName(orig_cam.firstParent().name())
                except:
                    name2 = ''
                pc.rename(orig_cam, 'temp_cam_name_from_multiShotExport')
                try:
                    pc.rename(orig_cam.firstParent(),
                              'temp_group_name_from_multiShotExport')
                except:
                    pass
                pc.rename(duplicate_cam, name)
                for node in pc.listConnections(orig_cam.getShape()):
                    if isinstance(node, pc.nt.AnimCurve):
                        try:
                            attr = node.outputs(
                                plugs=True)[0].name().split('.')[-1]
                        except IndexError:
                            continue
                        attribute = '.'.join([duplicate_cam.name(), attr])
                        node.output.connect(attribute, f=True)
                pc.select(duplicate_cam)
            pc.exportSelected(
                osp.join(path, self.getCameraNiceName()).replace('\\', '/'),
                force=True,
                expressions=True,
                constructionHistory=False,
                channels=True,
                shader=False,
                constraints=False,
                options="v=0",
                typ=imaya.getFileType(),
                pr=False)
            if self.nukeCamera:
                pc.mel.openMotion(
                    osp.join(path, self.getCameraNiceName() + '.nk').replace(
                        '\\', '/'), '.txt')
            if self.bakeCamera:
                pc.delete(duplicate_cam)
                pc.rename(orig_cam, name)
                if name2:
                    pc.rename(orig_cam.firstParent(), name2)
        except Exception as ex:
            return str(ex)

    def getAnimatedTextures(self):
        ''' Use the conf to find texture attributes to identify texture
        attributes in the present scene/shot '''
        conf = getConf()
        texture_attrs = []
        for key, attrs in conf['texture_export_data']:
            for obj in [pc.PyNode(gs) for gs in self.geosets]:
                if re.match(key, obj.name()):
                    name = obj.name()
                    namespace = ':'.join(name.split(':')[:-1])
                    for attr in attrs:
                        nombre = namespace + '.' + attr.replace(':', '_')
                        attr = pc.Attribute(namespace + ':' + attr)
                        texture_attrs.append((nombre, attr))
        return texture_attrs

    def exportAnimatedTextures(self):
        ''' bake export animated textures from the scene '''
        try:
            conf = getConf()
            animatedTextures = self.getAnimatedTextures()
            if not animatedTextures:
                return False
            tempFilePath = osp.join(self.tempPath, 'tex')
            if osp.exists(tempFilePath):
                shutil.rmtree(tempFilePath)
            os.mkdir(tempFilePath)
            start_time = int(self.startFrame)
            end_time = int(self.endFrame)
            rx = conf['texture_resX']
            ry = conf['texture_resY']

            for curtime in range(start_time, end_time + 1):
                num = '%04d' % curtime
                pc.currentTime(curtime, e=True)

                for name, attr in animatedTextures:
                    fileImageName = osp.join(tempFilePath,
                                             '.'.join([name, num, 'jpg']))
                    newobj = pc.convertSolidTx(
                        attr,
                        samplePlane=True,
                        rx=rx,
                        ry=ry,
                        fil='jpg',
                        fileImageName=fileImageName)
                    pc.delete(newobj)
        except Exception as ex:
            return str(ex)


def saveShotToDirectory(src, des):
    t = time.time()
    error = ''
    try:
        shutil.copytree(src, des)
    except Exception as ex:
        error = str(ex)
    saveTime = time.time() - t
    return saveTime, error


def isGeoSetValid(geoset):
    return pc.PyNode(geoset).hasAttr('cacheName')


def saveScene():
    cmds.file(save=True, f=True)


def sceneModified():
    return cmds.file(q=True, modified=True)


def clearHomeDirectory():
    for phile in os.listdir(tempLocation):
        path = osp.join(tempLocation, phile)
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
            ("(?i).*smart_car_02.*", ["layeredTexture1.outColor"]),
            ("(?i).*smart_car_aaber.*", ["layeredTexture1.outColor"]),
            ("(?i).*badr_robot.*", ["shader:layeredTexture1.outColor"]),
            ("(?i).*nano_regular.*", ["layeredTexture1.outColor"]),
            ("(?i).*nano_docking.*", ["layeredTexture1.outColor"]),
            ("(?i).*nano_covered.*", ["layeredTexture1.outColor"]),
            ("(?i).*nano_with_bowling_arm.*", ["layeredTexture1.outColor"]),
            ("(?i).*nano_shawarma.*",
                ["NanoShawarmaExpRenderPlaneMtl.outColor"]),
            ("(?i).*smart_car.*", ["layeredTexture1.outColor"])]
    conf["texture_resX"] = 1024
    conf["texture_resY"] = 1024
    conf["worldSpace"] = 1
    return conf


def displaySmoothness(smooth=True, geosets=None):
    pc.setAttr("hardwareRenderingGlobals.ssaoEnable", smooth)
    pc.select([mesh for _set in getGeoSets() for mesh in _set.members()])
    if smooth:
        pc.setAttr("hardwareRenderingGlobals.ssaoAmount", 0.5)
        if geosets:
            pc.select([
                mesh for _set in geosets for mesh in pc.PyNode(_set).members()
            ])
    imaya.displaySmoothness(smooth)
    pc.select(cl=True)


def getGeoSets():
    return [
        geoset for geoset in pc.ls(exactType=pc.nt.ObjectSet)
        if geoset.name().lower().endswith('_geo_set')
    ]


def getDisplayLayerState():
    return {
        layer: layer.visibility.get()
        for layer in imaya.getDisplayLayers()
    }


def restoreDisplayLayerState(state):
    for layer, val in state.items():
        layer.visibility.set(int(val))


def getProjectContext():
    return (imaya.getFileInfo(utils.projectKey),
            imaya.getFileInfo(utils.episodeKey),
            imaya.getFileInfo(utils.sequenceKey))


def getDateTime():
    return str(datetime.now()).split('.')[0].replace('-', '/').replace(
        ' ', '_').replace(':', '-')


def hideFaceUi():
    sel = pc.ls(sl=True)
    pc.select(pc.ls(regex='(?i).*:?UI_grp'))
    pc.Mel.eval('HideSelectedObjects')
    pc.select(sel)


def showFaceUi():
    sel = pc.ls(sl=True)
    pc.select(pc.ls(regex='(?i).*:?UI_grp'))
    pc.showHidden(b=True)
    pc.select(sel)


def hideShowCurves(flag):
    sel = pc.ls(sl=True)
    try:
        if flag:
            pc.select(pc.ls(type=pc.nt.NurbsCurve))
            pc.Mel.eval('HideSelectedObjects')
        else:
            pc.select(pc.ls(type=pc.nt.NurbsCurve))
            pc.showHidden(b=True)
    except:
        pass
    pc.select(sel)


def submitDeadlineJob(jobInfo, pluginInfo, pyScript):
    tempdir = osp.join(osp.dirname(tempLocation), 'mseDeadlineInfo')
    if not osp.exists(tempdir):
        os.mkdir(tempdir)
    jobInfoFile = osp.normpath(osp.join(tempdir, 'jobInfo.job'))
    pluginInfoFile = osp.normpath(osp.join(tempdir, 'pluginInfo.job'))
    pyFile = osp.normpath(osp.join(tempdir, 'mseDeadline.py'))
    with open(jobInfoFile, 'w+') as f:
        f.write(jobInfo)
    with open(pluginInfoFile, 'w+') as f:
        f.write(pluginInfo)
    with open(pyFile, 'w+') as f:
        f.write(pyScript)
    subprocess.call(
        subprocess.list2cmdline([
            r'C:\Program Files\Thinkbox\Deadline8\bin\deadlinecommand.exe',
            jobInfoFile, pluginInfoFile, pyFile
        ]))


def export(shots,
           user=iutil.getUsername(),
           smoothMeshes=True,
           viewport2point0=True,
           textureMode=True,
           uploadToTactic=False):
    errors = {}
    try:
        clearHomeDirectory()
    except Exception as ex:
        errors['Could not clear the temp directory'] = str(ex)
    shotObjs = []
    if uploadToTactic:
        import tacticCalls as tc
        tc.setServer(project=imaya.FileInfo.get(utils.projectKey))
    for shot in shots:
        shotObjs.append(Shot(shot=shot, user=user))
    if any([shot.preview for shot in shotObjs]):
        pass
        displaySmoothness(smoothMeshes)
        imaya.toggleViewport2Point0(viewport2point0)
        imaya.toggleTextureMode(textureMode)
    for shot in shotObjs:
        err = shot.export()
        if uploadToTactic:
            er = tc.uploadShotToTactic(shot.tempPath)
            if er:
                err.append(er)
        if err:
            errors[shot.cameraName] = err
    return errors


def assignMissingShaders():
    shaders = []
    for se in pc.ls(type='shadingEngine'):
        if not se.surfaceShader.inputs():
            shader = pc.shadingNode('lambert', asShader=True)
            shader.outColor.connect(se.surfaceShader)
            shaders.append(shader)
    return shaders


# TODO: remove the local paths, pass username as argument, enable uploading
deadlineCode = '''
import sys
import subprocess
#subprocess.call(r'net use r: /del', shell=True)
#subprocess.call(r'net use r: //ICE-TACTIC/pipeline /user:qurban.ali 13490',
        shell=True)
process = subprocess.Popen(r'\\\\ICE-TACTIC\\pipeline\mount\\mount.bat',
        shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
print process.communicate()[0]
from pprint import pprint
import os
upload=True
if os.environ['USERNAME'] in ['qurban.ali', 'talha.ahmed']:
    sys.path.insert(0, 'D:/My/Tasks/workSpace')
    sys.path.insert(0, 'D:/My/Tasks/workSpace/utilities')
    upload=False
sys.path.append('R:/Python_Scripts/plugins')
sys.path.append('R:/Python_Scripts/plugins/utilities')
sys.path.append('R:/Pipe_Repo/Projects/TACTIC')
print os.environ['USERNAME']
import multiShotExport as mse
print mse
from pprint import pprint
import maya.cmds as cmds
pprint(mse.export({shots}, user='{user}', uploadToTactic=upload))
print 'multishot finished'
'''
pool = 'multishottest' if iutil.getUsername() in ['qurban.ali', 'talha.ahmed'
                                                  ] else 'multishot'
deadlineJobInfo = '''
Plugin=MayaBatch
Name={name}
Comment=
Department=
Pool=%s
SecondaryPool=
Group=none
Priority=50
TaskTimeoutMinutes=0
EnableAutoTimeout=False
ConcurrentTasks=1
LimitConcurrentTasksToNumberOfCpus=True
MachineLimit=0
Whitelist=
LimitGroups=
JobDependencies=
OnJobComplete=Nothing
Frames=1
ChunkSize=1
''' % pool

deadlinePluginInfo = '''
Version={version}
Build=64bit
ProjectPath=
SceneFile={sceneFile}
StrictErrorChecking=False
UseLegacyRenderLayers=0
ScriptJob=True
ScriptFilename=mseDeadline.py
'''
