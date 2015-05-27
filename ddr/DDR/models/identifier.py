# coding: utf-8

import os
import re
import string
import urlparse


MODELS = [
    'file',
    'file-tmp',
    'entity',
    'collection',
    'organization',
    'repository',
]

PARENTS = {
    'file': 'entity',
    'entity': 'collection',
    'collection': 'organization',
    'organization': 'repository',
    'repository': None,
}

# keywords that can legally appear in IDs
ID_COMPONENTS = [
    'repo', 'org', 'cid', 'eid', 'role', 'sha1', 'ext'
]

# used to match object id pattern and extract model and tokens
ID_PATTERNS = (
    (r'^(?P<repo>[\w]+)-(?P<org>[\w]+)-(?P<cid>[\d]+)-(?P<eid>[\d]+)-(?P<role>[\w]+)-(?P<sha1>[\w]+)$', 'file'),
    (r'^(?P<repo>[\w]+)-(?P<org>[\w]+)-(?P<cid>[\d]+)-(?P<eid>[\d]+)-(?P<role>[\w]+)$', 'file-tmp'),
    (r'^(?P<repo>[\w]+)-(?P<org>[\w]+)-(?P<cid>[\d]+)-(?P<eid>[\d]+)$', 'entity'),
    (r'^(?P<repo>[\w]+)-(?P<org>[\w]+)-(?P<cid>[\d]+)$', 'collection'),
    (r'^(?P<repo>[\w]+)-(?P<org>[\w]+)$', 'organization'),
    (r'^(?P<repo>[\w]+)$', 'repository'),
)

# used to match path pattern and extract model and tokens
PATH_PATTERNS = (
    # file
    #(r'^/var/www/media/ddr/(?P<repo0>[\w]+)-(?P<org0>[\w]+)-(?P<cid0>[\d]+)/files/(?P<repo1>[\w]+)-(?P<org1>[\w]+)-(?P<cid1>[\d]+)-(?P<eid1>[\d]+)/files/(?P<repo>[\w]+)-(?P<org>[\w]+)-(?P<cid>[\d]+)-(?P<eid>[\d]+)-(?P<role>[\w]+)-(?P<sha1>[\w\d]+)\.(?P<ext>[\w]+)$', 'file-ext-abs', 'file'),
    #(r'^/var/www/media/ddr/(?P<repo0>[\w]+)-(?P<org0>[\w]+)-(?P<cid0>[\d]+)/files/(?P<repo1>[\w]+)-(?P<org1>[\w]+)-(?P<cid1>[\d]+)-(?P<eid1>[\d]+)/files/(?P<repo>[\w]+)-(?P<org>[\w]+)-(?P<cid>[\d]+)-(?P<eid>[\d]+)-(?P<role>[\w]+)-(?P<sha1>[\w\d]+)\.json$', 'file-meta-abs'),
    #(r'^/var/www/media/ddr/(?P<repo0>[\w]+)-(?P<org0>[\w]+)-(?P<cid0>[\d]+)/files/(?P<repo1>[\w]+)-(?P<org1>[\w]+)-(?P<cid1>[\d]+)-(?P<eid1>[\d]+)/files/(?P<repo>[\w]+)-(?P<org>[\w]+)-(?P<cid>[\d]+)-(?P<eid>[\d]+)-(?P<role>[\w]+)-(?P<sha1>[\w\d]+)$', 'file-abs', 'file'),
    (r'(?P<basepath>[\w/]+/ddr/)(?P<repo0>[\w]+)-(?P<org0>[\w]+)-(?P<cid0>[\d]+)/files/(?P<repo1>[\w]+)-(?P<org1>[\w]+)-(?P<cid1>[\d]+)-(?P<eid1>[\d]+)/files/(?P<repo>[\w]+)-(?P<org>[\w]+)-(?P<cid>[\d]+)-(?P<eid>[\d]+)-(?P<role>[\w]+)-(?P<sha1>[\w\d]+)\.(?P<ext>[\w]+)$', 'file-ext-abs', 'file'),
    (r'(?P<basepath>[\w/]+/ddr/)(?P<repo0>[\w]+)-(?P<org0>[\w]+)-(?P<cid0>[\d]+)/files/(?P<repo1>[\w]+)-(?P<org1>[\w]+)-(?P<cid1>[\d]+)-(?P<eid1>[\d]+)/files/(?P<repo>[\w]+)-(?P<org>[\w]+)-(?P<cid>[\d]+)-(?P<eid>[\d]+)-(?P<role>[\w]+)-(?P<sha1>[\w\d]+)\.json$', 'file-meta-abs'),
    (r'(?P<basepath>[\w/]+/ddr/)(?P<repo0>[\w]+)-(?P<org0>[\w]+)-(?P<cid0>[\d]+)/files/(?P<repo1>[\w]+)-(?P<org1>[\w]+)-(?P<cid1>[\d]+)-(?P<eid1>[\d]+)/files/(?P<repo>[\w]+)-(?P<org>[\w]+)-(?P<cid>[\d]+)-(?P<eid>[\d]+)-(?P<role>[\w]+)-(?P<sha1>[\w\d]+)$', 'file-abs', 'file'),
    
    (r'^files/(?P<repo0>[\w]+)-(?P<org0>[\w]+)-(?P<cid0>[\d]+)-(?P<eid0>[\d]+)/files/(?P<repo>[\w]+)-(?P<org>[\w]+)-(?P<cid>[\d]+)-(?P<eid>[\d]+)-(?P<role>[\w]+)-(?P<sha1>[\w\d]+)\.(?P<ext>[\w]+)$', 'file-ext-rel', 'file'),
    (r'^files/(?P<repo0>[\w]+)-(?P<org0>[\w]+)-(?P<cid0>[\d]+)-(?P<eid0>[\d]+)/files/(?P<repo>[\w]+)-(?P<org>[\w]+)-(?P<cid>[\d]+)-(?P<eid>[\d]+)-(?P<role>[\w]+)-(?P<sha1>[\w\d]+)\.json$', 'file-meta-rel', 'file'),
    (r'^files/(?P<repo0>[\w]+)-(?P<org0>[\w]+)-(?P<cid0>[\d]+)-(?P<eid0>[\d]+)/files/(?P<repo>[\w]+)-(?P<org>[\w]+)-(?P<cid>[\d]+)-(?P<eid>[\d]+)-(?P<role>[\w]+)-(?P<sha1>[\w\d]+)$', 'file-rel', 'file'),
    
    # entity
    #(r'^/var/www/media/ddr/(?P<repo0>[\w]+)-(?P<org0>[\w]+)-(?P<cid0>[\d]+)/files/(?P<repo>[\w]+)-(?P<org>[\w]+)-(?P<cid>[\d]+)-(?P<eid>[\d]+)', 'entity-abs', 'entity'),
    (r'(?P<basepath>[\w/]+/ddr/)(?P<repo0>[\w]+)-(?P<org0>[\w]+)-(?P<cid0>[\d]+)/files/(?P<repo>[\w]+)-(?P<org>[\w]+)-(?P<cid>[\d]+)-(?P<eid>[\d]+)', 'entity-abs', 'entity'),
    (r'^files/(?P<repo>[\w]+)-(?P<org>[\w]+)-(?P<cid>[\d]+)-(?P<eid>[\d]+)$', 'entity-rel', 'entity'),
    
    # collection
    (r'(?P<basepath>[\w/]+/ddr/)(?P<repo>[\w]+)-(?P<org>[\w]+)-(?P<cid>[\d]+)', 'collection'),
    (r'^collection.json$', 'collection-meta-rel', 'collection'),
    # organization
    #(r'(?P<base>[\w/]+/ddr/)(?P<repo>[\w]+)-(?P<org>[\w]+)/organization.json$', 'organization-meta-abs', 'organization'),
    (r'(?P<basepath>[\w/]+/ddr/)(?P<repo>[\w]+)-(?P<org>[\w]+)$', 'organization-abs', 'organization'),
    (r'^organization.json$', 'organization-meta-rel', 'organization'),
    # repository
    #(r'^/var/www/media/ddr/(?P<repo>[\w]+)/repository.json$', 'repository-meta-abs', 'repository'),
    (r'(?P<basepath>[\w/]+/ddr/)(?P<repo>[\w]+)/repository.json$', 'repository-meta-abs', 'repository'),
    (r'^repository.json$', 'repository-meta-rel', 'repository'),
)

# used to match URL pattern and extract model and tokens
URL_PATTERNS = (
    # ddr-local
    (r'/ui/(?P<repo>[\w]+)-(?P<org>[\w]+)-(?P<cid>[\d]+)-(?P<eid>[\d]+)-(?P<role>[\w]+)-(?P<sha1>[\w]+)$', 'file'),
    (r'/ui/(?P<repo>[\w]+)-(?P<org>[\w]+)-(?P<cid>[\d]+)-(?P<eid>[\d]+)-(?P<role>[\w]+)$', 'file-tmp'),
    (r'/ui/(?P<repo>[\w]+)-(?P<org>[\w]+)-(?P<cid>[\d]+)-(?P<eid>[\d]+)$', 'entity'),
    (r'/ui/(?P<repo>[\w]+)-(?P<org>[\w]+)-(?P<cid>[\d]+)$', 'collection'),
    (r'/ui/(?P<repo>[\w]+)-(?P<org>[\w]+)$', 'organization'),
    (r'/ui/(?P<repo>[\w]+)$', 'repository'),
    # ddr-public
    (r'^/(?P<repo>[\w]+)/(?P<org>[\w]+)/(?P<cid>[\d]+)/(?P<eid>[\d]+)/(?P<role>[\w]+)/(?P<sha1>[\w]+)$', 'file'),
    (r'^/(?P<repo>[\w]+)/(?P<org>[\w]+)/(?P<cid>[\d]+)/(?P<eid>[\d]+)/(?P<role>[\w]+)$', 'file-tmp'),
    (r'^/(?P<repo>[\w]+)/(?P<org>[\w]+)/(?P<cid>[\d]+)/(?P<eid>[\d]+)$', 'entity'),
    (r'^/(?P<repo>[\w]+)/(?P<org>[\w]+)/(?P<cid>[\d]+)$', 'collection'),
    (r'^/(?P<repo>[\w]+)/(?P<org>[\w]+)$', 'organization'),
    (r'^/(?P<repo>[\w]+)$', 'repository'),
)

# used to generate IDs from model and tokens
ID_FORMATS = {
    'file':         '{repo}-{org}-{cid}-{eid}-{role}-{sha1}',
    'file-tmp':     '{repo}-{org}-{cid}-{eid}-{role}',
    'entity':       '{repo}-{org}-{cid}-{eid}',
    'collection':   '{repo}-{org}-{cid}',
    'organization': '{repo}-{org}',
    'repository':   '{repo}',
}

# used to generate paths from model and tokens
PATH_FORMATS = {
    'file-abs': '{basepath}/{repo}-{org}-{cid}/files/{repo}-{org}-{cid}-{eid}/files/{repo}-{org}-{cid}-{eid}-{role}-{sha1}.{ext}',
    'file-rel': 'files/{repo}-{org}-{cid}-{eid}/files/{repo}-{org}-{cid}-{eid}-{role}-{sha1}.{ext}',
    'entity-abs': '{basepath}/{repo}-{org}-{cid}/files/{repo}-{org}-{cid}-{eid}',
    'entity-rel': 'files/{repo}-{org}-{cid}-{eid}',
    'collection-abs': '{basepath}/{repo}-{org}-{cid}',
    'organization-abs': '{basepath}/{repo}-{org}',
    'repository-abs': '{basepath}/{repo}',
}

# used to generate URIs from model and tokens
URL_FORMATS = {
}

ADDITIONAL_PATHS = {
    'file': {
        'json_path': '{id}.json',
        'access_path': '{id}-a.jpg',
    },
    'entity': {
        'json_path': 'entity.json',
        'changelog_path': 'changelog',
        'control_path': 'control',
        'files_path': 'files/',
    },
    'collection': {
        'json_path': 'collection.json',
        'gitignore_path': '.gitignore',
        'git_path': '.git/',
        'annex_path': '.git/annex/',
    },
    'organization': {
        'json_path': 'organization.json',
    },
    'repository': {
        'json_path': 'repository.json',
    },
}





    
def identify_object(i, text, patterns):
    """split ID,path,url into model and tokens and assign to identifier
    """
    groupdict = {}
    for tpl in patterns:
        pattern = tpl[0]
        model = tpl[-1]
        m = re.match(pattern, text)
        if m:
            i.model = model
            groupdict = m.groupdict()
            break
    if not groupdict:
        raise Exception('Could not identify object: "%s"' % text)
    i.basepath = groupdict.get('basepath', None)
    i.idparts = [
        key
        for key in groupdict.iterkeys()
        if key in ID_COMPONENTS
    ]
    # set object attributes with numbers as ints
    for key in i.idparts:
        if groupdict[key].isdigit():
            setattr(i, key, int(groupdict[key]))
        else:
            setattr(i, key, groupdict[key])
    return groupdict

def format_id(groupdict, model):
    """
    @param model: str
    @groupdict: dict of ID parts and values e.g. {'repo':'ddr','org':'test',}
    """
    return ID_FORMATS[model].format(**groupdict)

def format_path(groupdict, model, which):
    key = '-'.join([model, which])
    try:
        template = PATH_FORMATS[key]
        return template.format(**groupdict)
    except KeyError:
        return None

def format_url(groupdict, model, which):
    """
    @param groupdict: dict
    @param model: str 
    @param which: str 'public' or 'editor'
    """
    pass

def additional_paths(i):
    paths = ADDITIONAL_PATHS[i.model]
    for key,val in paths.iteritems():
        print(key,val)
        key_abs = '%s_abs' % key
        path_abs = os.path.join(i.path_abs, val)
        setattr(i, key_abs, path_abs)
        key_rel = '%s_rel' % key
        path_rel = os.path.join(i.path_rel, val)
        setattr(i, key_rel, path_rel)


class Identifier(object):
    raw = None
    method = None
    model = None
    idparts = []
    basepath = None
    id = None
    
    def __repr__(self):
        return "<Identifier %s>" % (self.id)
    
    def path_abs(self):
        if not self.basepath:
            raise Exception('%s basepath not set.'% self)
        assert False
    
    def path_rel(self):
        assert False
    
    def url(self, domain=None):
        assert False
    
    def parent_id(self):
        parent_model = PARENTS[self.model]
        print('parent_model %s' % parent_model)
        assert False
    
    def collection_id(self):
        assert False
    
    def collection_path(self, relative=False):
        assert False
    
    def json_path(self, relative=False):
        assert False
    
    @staticmethod
    def from_id(object_id, base_path=None):
        """Return Identified given object ID
        
        >>> Identifier.from_id('ddr-testing-123-456')
        <Identifier ddr-testing-123-456>
        
        @param object_id: str
        """
        if base_path and not os.path.isabs(base_path):
            raise Exception('Base path is not absolute: %s' % base_path)
        i = Identifier()
        i.method = 'id'
        i.raw = object_id
        i.id = object_id
        if base_path and not i.basepath:
            i.basepath = base_path
        groupdict = identify_object(i, object_id, ID_PATTERNS)
        return i
    
    @staticmethod
    def from_idparts(idpartsdict, base_path=None):
        """Return Identified given dict of idparts
        
        >>> idparts = {'model':'entity', 'repo':'ddr', 'org':'testing', 'cid':123, 'eid':456}
        >>> Identifier.from_idparts(idparts)
        <Identifier ddr-testing-123-456>
        
        @param idparts: dict
        """
        if base_path and not os.path.isabs(base_path):
            raise Exception('Base path is not absolute: %s' % base_path)
        i = Identifier()
        i.method = 'idparts'
        i.raw = idpartsdict
        i.model = idpartsdict['model']
        i.idparts = [key for key in idpartsdict.iterkeys()]
        i.id = format_id(idpartsdict, i.model)
        if base_path and not i.basepath:
            i.basepath = base_path
        return i
    
    @staticmethod
    def from_path(path_abs):
        """Return Identified given absolute path.
        
        >>> Identifier.from_id('ddr-testing-123-456')
        <Identifier ddr-testing-123-456>
        
        @param path_abs: str
        """
        if not os.path.isabs(path_abs):
            raise Exception('Path is not absolute: %s' % path_abs)
        i = Identifier()
        i.method = 'path'
        i.raw = path_abs
        # rm trailing slash
        if path_abs[-1] == os.sep:
            path_abs = path_abs[:-1]
        groupdict = identify_object(i, path_abs, PATH_PATTERNS)
        i.id = format_id(groupdict, i.model)
        return i
    
    @staticmethod
    def from_url(url, base_path=None):
        """Return Identified given URL or URI.
        
        >>> Identifier.from_id('http://ddr.densho.org/ddr/testing/123/456')
        <Identifier ddr-testing-123-456>
        >>> Identifier.from_id('http://ddr.densho.org/ddr/testing/123/456/')
        <Identifier ddr-testing-123-456>
        >>> Identifier.from_id('http://192.168.56.101/ui/ddr-testing-123-456')
        <Identifier ddr-testing-123-456>
        >>> Identifier.from_id('http://192.168.56.101/ui/ddr-testing-123-456/files/')
        <Identifier ddr-testing-123-456>
        
        @param path_abs: str
        """
        if base_path and not os.path.isabs(base_path):
            raise Exception('Base path is not absolute: %s' % base_path)
        i = Identifier()
        i.method = 'url'
        i.raw = url
        if base_path and not i.basepath:
            i.basepath = base_path
        path = urlparse.urlparse(url).path
        # rm trailing slash
        if path[-1] == os.sep:
            path = path[:-1]
        groupdict = identify_object(i, path, URL_PATTERNS)
        i.id = format_id(groupdict, i.model)
        return i
    
    
        
#        # set various IDs (i.collection_id, i.entity_id, etc)
#        for model,pattern in ID_FORMATS:
#            try:
#                field = '%s_id' % model
#                text = pattern.format(**groupdict)
#                setattr(i, field, text)
#            except:
#                pass
# 
#        for attr,pattern in PATH_REL_FORMATS:
#            try:
#                text = pattern.format(**groupdict)
#                setattr(i, attr, text)
#            except:
#                pass
#        if i.model == 'entity':
#            i.changelog_path_rel = os.path.join(i.entity_path_rel, 'changelog')
#            i.control_path_rel = os.path.join(i.entity_path_rel, 'control')
#            i.files_path_rel = os.path.join(i.entity_path_rel, 'files')
#        elif i.model == 'file':
#            i.access_rel = i.json_path_rel.replace('.json', '-a.jpg')
#        
#        if base_path:
#            i.base_path = base_path
#            if i.collection_id:
#                i.collection_path = os.path.join(base_path, i.collection_id)
# 
#        if hasattr(i, 'collection_path') and i.collection_path:
#            # prepend base_path to all i.*_rel attributes
#            d = {}
#            for key,val in i.__dict__.iteritems():
#                if '_rel' in key:
#                    field = key.replace('_rel', '')
#                    path = os.path.join(i.collection_path, val)
#                    d[field] = path
#            for key,val in d.iteritems():
#                setattr(i,key,val)
# 
#        if i.collection_path and i.model == 'collection':
#            i.git_path = os.path.join(i.collection_path, '.git')
#            i.annex_path = os.path.join(i.collection_path, '.git', 'annex')
#            i.gitignore_path = os.path.join(i.collection_path, '.gitignore')
        
        #if i.model == 'repository':
        #    pass
        # 
        #elif i.model == 'organization':
        #    pass
        # 
        #elif i.model == 'collection':
        #    i.json_path_rel = 'collection.json'
        #    i.changelog_path_rel = 'changelog'
        #    i.control_path_rel = 'control'
        #    i.entities_path_rel = 'files'
        #    i.gitignore_path_rel = '.gitignore'
        #    if base_path:
        #        i.json_path = os.path.join(base_path, i.json_path_rel)
        #        i.changelog_path = os.path.join(base_path, i.changelog_path_rel)
        #        i.control_path = os.path.join(base_path, i.control_path_rel)
        #        i.entities_path = os.path.join(base_path, i.entities_path_rel)
        #        i.gitignore_path = os.path.join(base_path, i.gitignore_path_rel)
        #        i.git_path = os.path.join(base_path, '.git')
        #        i.annex_path = os.path.join(base_path, '.git', 'annex')
        # 
        #elif i.model == 'entity':
        #    pass
        # 
        #elif i.model == 'file-tmp':
        #    pass
        # 
        #elif i.model == 'file':
        #    pass
        # 
        #if i.collection_path:
        #    pass
            
        return i
