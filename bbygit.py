import argparse
import collections
import configparser
from datetime import datetime
import grp, pwd
from fnmatch import fnmatch
import hashlib
from math import ceil
import os
import re
import sys
import zlib
from git_obj import GitObject, GitCommit, GitTree, GitTag, GitBlob


argparser = argparse.ArgumentParser(description='git cli argument parser')
#for subcommands after 'git' (dest param is field for subparser name)
argsubparsers = argparser.add_subparsers(title='Commands', dest='command')
argsubparsers.required = True

argsp = argsubparsers.add_parser(name="init", help="Initialize a new, empty, repository")
argsp.add_argument("path",
                   metavar="directory",
                   nargs="?",
                   default=".",
                   help="Where to create the repository.")

def main(argv=sys.argv[1:]): #get all args except script name
    args = argparser.parse_args(argv)
    match args.command:
        case "add": cmd_add(args)
        case "cat-file": cmd_cat_file(args)
        case "check-ignore": cmd_check_ignore(args)
        case "checkout": cmd_checkout(args)
        case "commit": cmd_commit(args)
        case "hash_object": cmd_hash_object(args)
        case "init": cmd_init(args)
        case "log": cmd_log(args)
        case "ls-files": cmd_ls_files(args)
        case "ls-tree": cmd_ls_tree(args)
        case "rev_parse": cmd_rev_parse(args)
        case "rm": cmd_rm(args),
        case "show-ref": cmd_show_ref(args)
        case "status": cmd_status(args)
        case "tag": cmd_tag(args)
        case _: print('Command doesn\'t exist')


class GitRepository(object):
    worktree = None #files in VC
    gitdir = None #git data
    conf = None

    def __init__(self, path, force=False) -> None:
        self.worktree = path
        self.gitdir = os.path.join(path, ".git")

        if not (force or os.path.isdir(self.gitdir)):
            raise Exception(f"Not a Git repository {path}")
        
        self.conf = configparser.ConfigParser()
        cf = repo_file(self, "config")

        #read the config file lines into array if the file exists
        if cf and os.path.exists(cf):
            self.conf.read([cf])
        elif not force:
            raise Exception("Configuration file missing")
        
        if not force:
            version = int(self.conf.get("core", "repositoryformatversion"))
            if version != 0:
                raise Exception(f"Unsupported repositoryformatversion: {version}")
            

def repo_path(repo, *path):
    return os.path.join(repo.gitdir, *path)


def repo_file(repo, *path, mkdir=False):
    #creates directory for file if dir doesn't exist
    if repo_dir(repo, *path[:-1], mkdir=mkdir):
        return repo_path(repo, *path)

def repo_dir(repo, *path, mkdir=False):
    path = repo_path(repo, *path)

    if os.path.exists(path):
        if os.path.isdir(path):
            return path
        else:
            raise Exception(f'Not a directory: {path}')
    
    if mkdir:
        os.makedirs(path)
        return path
    else:
        return None
    

'''creates object store, reference store, reference to HEAD, config file, description'''
def repo_create(path):
    repo = GitRepository(path, True)

    if os.path.exists(repo.worktree):
        if not os.path.isdir(repo.worktree):
            raise Exception(f"{path} is not a directory")
        if os.path.exists(repo.gitdir) and os.listdir(repo.gitdir):
            raise Exception(f"{path} is not empty")
    else:
        os.mkdir(repo.worktree)
    
    #create subdirectories for repo
    assert repo_dir(repo, "branches", mkdir=True)
    assert repo_dir(repo, "objects", mkdir=True)
    assert repo_dir(repo, "refs", "tags", mkdir=True)
    assert repo_dir(repo, "refs", "heads", mkdir=True)

    #.git/description
    with open(repo_file(repo, "description"), "w+") as f:
        f.write("Unnamed repository. Edit this file to name the repository. \n")
    
    #.git/HEAD
    with open(repo_file(repo, "HEAD"), "w+") as f:
        f.write("ref: refs/heads/master\n")

    #.git/config
    with open(repo_file(repo, "config"), "w+") as f:
        config = repo_default_config()
        config.write(f)
    
    return repo

def repo_default_config():
    conf = configparser.ConfigParser()
    
    conf.add_section("core")
    conf.set("core", "repositoryformatversion", "0")
    conf.set("core", "filemode", "false")
    conf.set("core", "bare", "false")

    return conf

def cmd_init(args):
    repo_create(args.path)

'''find the root of the current repository'''
def repo_find(path=".", required=True):
    path = os.path.realpath(path)

    if os.path.isdir(os.path.join(path, "git")):
        return GitRepository(path)
    
    #if haven't found repo, look in parent
    parent = os.path.realpath(os.path.join(path, ".."))
    if parent == path:
        if required:
            raise Exception("No git directory.")
        else:
            return None
    
    #keep searching if bottommost folder hasn't been reached
    return repo_find(parent, required)


def object_read(repo, sha):
    #create directories to make searching faster
    path = repo_file(repo, "objects", sha[:2], sha[2:])

    if not os.path.isfile(path):
        return None
    
    #open repo file
    with open(path, "rb") as f:
        raw = zlib.decompress(f.read())
        #object type
        x = raw.find(b' ')
        fmt = raw[:x]
        #object size
        y = raw.find(b'\x00', x)
        size = int(raw[x:y].decode("ascii"))
        if size != len(raw)-y-1:
            raise Exception("Malformed object {0}: bad length".format(sha))
        
        #object constructors
        match fmt:
            case b'commit': c=GitCommit
            case b'tree': c=GitTree
            case b'tag': c=GitTag
            case b'blob': c=GitBlob
            case _:
                raise Exception("Unknown type {0} for object {1}".format(fmt.decode()))

        #constructor and return object
        return c(raw[y+1:])
    
def object_write(obj: GitObject, repo=None):
    data = obj.serialize()
    #header
    result = obj.fmt + b' ' + str(len(data)).encode() + b'\x00' + data
    #hash
    sha = hashlib.sha1(result).hexdigest()
    if repo:
        path = repo_file(repo, "objects", sha[:2], sha[2:], mkdir=True)
        if not os.path.exists(path):
            with open(path, "wb") as f:
                f.write(zlib.compress(result))
    return sha
    
