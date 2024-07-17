class GitObject(object):
    def __init__(self, data=None):
        if data != None:
            self.deserialize()
        else:
            self.init()
    
    def init(self):
        pass

    def serialize(self, repo):
        raise Exception("Unimplemented")

    def deserialize(self, data):
        raise Exception("Unimplemented")
    
class GitCommit(GitObject):
    pass

class GitTree(GitObject):
    pass

class GitTag(GitObject):
    pass

class GitBlob(GitObject):
    fmt = b'blob'

    def serialize(self):
        return self.blobdata
    
    def deserialize(self, data):
        self.blobdata = data