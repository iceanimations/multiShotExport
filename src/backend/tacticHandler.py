'''
Created on Mar 10, 2017

@author: qurban.ali
'''
import tacticCalls as tc
import os.path as osp
import subprocess
import time

def openShotLocation(shot):
    path, errors = tc.getShotPath(shot)
    if errors:
        pass
        #pc.warning(str(errors))
    path = osp.normpath(path)
    subprocess.Popen('explorer %s'%path)
    
def getShotFrameRange(shot):
    frameRange, err = tc.getFrameRange(shot)
    return frameRange, err
    
def getAssetsInShot(shot):
    assets, err = tc.getAssetsInShot(shot)
    assets = [x['asset_code'].lower() for x in assets]
    return assets, err

def backupMayaFile(seq):
    return tc.checkin(seq, 'ANIMATION/MSE', '')

def uploadToTactic(path):
    errors = []
    t1 = time.time()
    err = tc.uploadShotToTactic(path)
    if err: errors.append(err)
    saveTime = time.time() - t1
    return saveTime, errors