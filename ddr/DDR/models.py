from datetime import datetime
import ConfigParser
import hashlib
import json
import logging
logger = logging.getLogger(__name__)
import os
import re

import envoy

from DDR import CONFIG_FILE
from DDR import natural_sort, natural_order_string
from DDR.control import CollectionControlFile, EntityControlFile
from DDR import dvcs
from DDR import storage



class NoConfigError(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

if not os.path.exists(CONFIG_FILE):
    raise NoConfigError('No config file!')
config = ConfigParser.ConfigParser()
config.read(CONFIG_FILE)
GITOLITE = config.get('workbench','gitolite')
ACCESS_FILE_APPEND = config.get('local','access_file_append')
ACCESS_FILE_EXTENSION = config.get('local','access_file_extension')


MODULE_PATH = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(MODULE_PATH, 'templates')
GITIGNORE_TEMPLATE = os.path.join(TEMPLATE_PATH, 'gitignore.tpl')

MODELS = ['collection', 'entity', 'file']

MODELS_DIR = '/usr/local/src/ddr-cmdln/ddr/DDR/models'



def make_object_id( model, repo, org=None, cid=None, eid=None, role=None, sha1=None ):
    if   (model == 'file') and repo and org and cid and eid and role and sha1:
        return '%s-%s-%s-%s-%s-%s' % (repo, org, cid, eid, role, sha1)
    elif (model == 'entity') and repo and org and cid and eid:
        return '%s-%s-%s-%s' % (repo, org, cid, eid)
    elif (model == 'collection') and repo and org and cid:
        return '%s-%s-%s' % (repo, org, cid)
    elif (model in ['org', 'organization']) and repo and org:
        return '%s-%s' % (repo, org)
    elif (model in ['repo', 'repository']) and repo:
        return repo
    return None

def split_object_id( object_id=None ):
    """Very naive function that splits an object ID into its parts
    TODO make sure it's actually an object ID first!
    """
    if object_id and isinstance(object_id, basestring):
        parts = object_id.strip().split('-')
        if len(parts) == 6:
            parts.insert(0, 'file')
            return parts
        elif len(parts) == 4:
            parts.insert(0, 'entity')
            return parts
        elif len(parts) == 3:
            parts.insert(0, 'collection')
            return parts
    return None

def id_from_path( path ):
    """Extract ID from path.
    
    >>> _id_from_path('.../ddr-testing-123/collection.json')
    'ddr-testing-123'
    >>> _id_from_path('.../ddr-testing-123/files/ddr-testing-123-1/entity.json')
    'ddr-testing-123-1'
    >>> _id_from_path('.../ddr-testing-123-1-master-a1b2c3d4e5.json')
    'ddr-testing-123-1-master-a1b2c3d4e5.json'
    >>> _id_from_path('.../ddr-testing-123/files/ddr-testing-123-1/')
    None
    >>> _id_from_path('.../ddr-testing-123/something-else.json')
    None
    
    @param path: absolute or relative path to a DDR metadata file
    @returns: DDR object ID
    """
    object_id = None
    model = model_from_path(path)
    if model == 'collection': return os.path.basename(os.path.dirname(path))
    elif model == 'entity': return os.path.basename(os.path.dirname(path))
    elif model == 'file': return os.path.splitext(os.path.basename(path))[0]
    return None

def model_from_id( object_id ):
    """Guess model by looking at object_id
    """
    LEGAL_LENGTHS = [
        1, # repository   (ddr)
        2, # organization (ddr-testing)
        3, # collection   (ddr-testing-123)
        4, # entity       (ddr-testing-123-1)
        6, # file         (ddr-testing-123-1-master-a1b2c3d4e5)
    ]
    parts = object_id.split('-')
    len_parts = len(parts)
    if (len_parts in LEGAL_LENGTHS):
        if   len_parts == 6: return 'file'
        elif len_parts == 4: return 'entity'
        elif len_parts == 3: return 'collection'
        #elif len_parts == 2: return 'organization'
        #elif len_parts == 1: return 'repository'
    return None

def model_from_path( path ):
    """Guess model from the path.
    
    >>> model_from_path('/var/www/media/base/ddr-testing-123/collection.json')
    'collection'
    >>> model_from_path('/var/www/media/base/ddr-testing-123/files/ddr-testing-123-1/entity.json')
    'entity'
    >>> model_from_path('/var/www/media/base/ddr-testing-123/files/ddr-testing-123-1/files/ddr-testing-123-1-master-a1b2c3d4e5.json')
    'file'
    
    @param path: absolute or relative path to metadata JSON file.
    @returns: model
    """
    if 'collection.json' in path: return 'collection'
    elif 'entity.json' in path: return 'entity'
    elif ('master' in path) or ('mezzanine' in path): return 'file'
    return None

def parent_id( object_id ):
    """Given a DDR object ID, returns the parent object ID.
    
    TODO not specific to elasticsearch - move this function so other modules can use
    
    >>> _parent_id('ddr')
    None
    >>> _parent_id('ddr-testing')
    'ddr'
    >>> _parent_id('ddr-testing-123')
    'ddr-testing'
    >>> _parent_id('ddr-testing-123-1')
    'ddr-testing-123'
    >>> _parent_id('ddr-testing-123-1-master-a1b2c3d4e5')
    'ddr-testing-123-1'
    """
    parts = object_id.split('-')
    if   len(parts) == 2: return '-'.join([ parts[0], parts[1] ])
    elif len(parts) == 3: return '-'.join([ parts[0], parts[1] ])
    elif len(parts) == 4: return '-'.join([ parts[0], parts[1], parts[2] ])
    elif len(parts) == 6: return '-'.join([ parts[0], parts[1], parts[2], parts[3] ])
    return None

def model_fields( model ):
    """
    THIS FUNCTION IS A PLACEHOLDER.
    It's a step on the way to refactoring (COLLECTION|ENTITY|FILE)_FIELDS.
    It gives ddr-public a way to know the order of fields until we have a better solution.
    """
    # TODO model .json files should live in /etc/ddr/models
    if model in ['collection', 'entity', 'file']:
        json_path = os.path.join(MODELS_DIR, '%s.json' % model)
        with open(json_path, 'r') as f:
            data = json.loads(f.read())
        fields = []
        for field in data:
            f = {'name':field['name'],}
            if field.get('form',None) and field['form'].get('label',None):
                f['label'] = field['form']['label']
            fields.append(f)
        return fields
    return []



def _write_json(data, path):
    """Write JSON using consistent formatting and sorting.
    
    For versioning and history to be useful we need data fields to be written
    in a format that is easy to edit by hand and in which values can be compared
    from one commit to the next.  This function prints JSON with nice spacing
    and indentation and with sorted keys, so fields will be in the same relative
    position across commits.
    
    >>> data = {'a':1, 'b':2}
    >>> path = '/tmp/ddrlocal.models.write_json.json'
    >>> _write_json(data, path)
    >>> with open(path, 'r') as f:
    ...     print(f.readlines())
    ...
    ['{\n', '    "a": 1,\n', '    "b": 2\n', '}']
    """
    json_pretty = json.dumps(data, indent=4, separators=(',', ': '), sort_keys=True)
    with open(path, 'w') as f:
        f.write(json_pretty)

def _guess_drive_label(path):
    label = storage.drive_label(path)
    if not label:
        hostname = envoy.run('hostname').std_out.strip()
        ppath = path.replace(os.sep, '-')[1:]
        label = '%s_%s' % (hostname, ppath)
    return label



INVENTORY_LEVELS = ['meta', 'access', 'all']

class Repository( object ):
    id = None
    keyword = None
    title = None
    description = None
    organizations = {}
    
    def __init__( self, path=None ):
        if path:
            self.read(path)
    
    def read( self, path ):
        with open(path, 'r') as f:
            data = json.loads(f.read())
        self.id = data['id']
        self.keyword = data['keyword']
        self.title = data['title']
        self.description = data['description']
    
    def json( self ):
        return {'id': self.id,
                'keyword': self.keyword,
                'title': self.title,
                'description': self.description,}
        
    def write( self, path ):
        _write_json(self.json(), path)



"""
Sample organization.json file:
    {
        "id": "ddr-testing",
        "org": "testing",
        "repo": "ddr"
    }
"""

ORGANIZATION_FIELDS = ['id', 'repo', 'org',]

class Organization( object ):
    path = None
    id = None
    repo = None
    org = None
    keyword = None
    stores = []
    filename = 'organization.json'
    
    def __init__(self, **kwargs):
        self.path = kwargs.get('path', None)
        for k in kwargs.keys():
            if k in ORGANIZATION_FIELDS:
                self.__setattr__(k, kwargs[k])
        if self.path:
            self.stores = self._stores()
    
    def json( self ):
        data = {}
        for f in ORGANIZATION_FIELDS:
            data[f] = getattr(self, f)
        return data
    
    @staticmethod
    def load(path):
        o = Organization(path=path)
        opath = os.path.join(path, o.filename)
        with open(opath, 'r') as f:
            data = json.loads(f.read())
        for k in data.keys():
            if k in ORGANIZATION_FIELDS:
                o.__setattr__(k, data[k])
        return o
    
    @staticmethod
    def file_is_valid( path ):
        """Indicates whether a organization.json file is valid.
        
        @param path: Absolute path to file.
        @returns True if valid, list of faults if not.
        """
        faults = []
        if not os.path.exists(path):
            faults.append('File does not exist.')
        try:
            with open(path, 'r') as f:
                data = json.loads(f.read())
        except:
            data = None
            faults.append('Not a valid JSON file.')
        if data:
            if not data.get('repo', None): faults.append('missing field: repo')
            if not data.get('org', None):  faults.append('missing field: org')
            if not data.get('id', None):   faults.append('missing field: id')
        if len(faults) == 0:
            return True
        return faults
    
    @staticmethod
    def is_valid( path ):
        """Indicates whether the path represents a valid Organization.
        
        @param path
        @returns True/False
        """
        git_dir = os.path.join(path, '.git')
        orgjson = os.path.join(path, Organization.filename)
        if os.path.exists(git_dir) and os.path.exists(orgjson):
            o = Organization.load(path)
            if o and isinstance(o, Organization):
                return True
        return False
    
    def commit( self, git_name, git_mail, message ):
        repo = dvcs.repository(self.path)
        repo.git.add(self.filename)
        for store in self.stores:
            spath = os.path.join(self.path, store.filename())
            repo.git.add(spath)
        repo.git.commit('--author=%s <%s>' % (git_name, git_mail), '-m', message)
    
    def save( self ):
        opath = os.path.join(self.path, self.filename)
        _write_json(self.json(), opath)
        for store in self.stores:
            spath = os.path.join(self.path, store.filename())
            store.save(spath)
    
    @staticmethod
    def organizations( path ):
        odirs = []
        for x in os.listdir(path):
            odir = os.path.join(path,x)
            if Organization.is_valid(odir):
                odirs.append(odir)
        odirs = sorted(odirs, key=lambda o: natural_order_string(o))
        organizations = []
        for odir in odirs:
            o = Organization.load(odir)
            organizations.append(o)
        return organizations
    
    def _store_files( self ):
        """Gets list of paths to store files in the repo.
        """
        if self.path and os.path.exists(self.path):
            excludes = ['.git', 'organization.json']
            pattern = re.compile('.json$')
            return [f for f in os.listdir(self.path) if (f not in excludes) and pattern.search(f)]
        return []
    
    def _stores( self ):
        self.stores = []
        for f in self._store_files():
            spath = os.path.join(self.path, f)
            s = Store.load(spath)
            self.stores.append(s)
        return self.stores
    
    def store( self, label ):
        for s in self.stores:
            if s.label == label:
                return s
        return None
    
    def remove_store( self, store ):
        """NOTE: Does not do the commit!"""
        repo = dvcs.repository(self.path)
        spath = os.path.join(self.path, store.filename())
        repo.git.rm(spath)
        self.stores.remove(store)
    
    def collection( self, cid ):
        """Lists the stores that contain collection and level
        """
        instances = []
        for store in self.stores:
            for c in store.collections:
                if c['id'] == cid:
                    c['label'] = store.label
                    instances.append(c)
        return instances
    
    def collections( self, server_url=None, server_label='', server_location='' ):
        """Builds a data structure of all the repo remotes keyed to their UUIDs
        
        This function loads each of the store records for the organization.
        For each collection record it adds the location field and store label
        from the store record.  This is suitable for loading into a search engine.
        
        >> from DDR.inventory import Organization
        >> org = Organization('/var/www/media/base/ddr-testing')
        >> collections = org.collections()
        >> for c in collections:
        >>     print(c)
        {'uuid':'43935...', 'id':'ddr-testing-141', 'label':'HMWF1TB2013', 'location':'Heart Mountain, WY'},
        {'uuid':'64393...', 'id':'ddr-testing-141', 'label':'pnr_tmp-ddr', 'location':'Pasadena, CA'},
        {'uuid':'36493...', 'id':'ddr-testing-141', 'label':'WD5000BMV-2', 'location':'Pasadena, CA'},
        {'uuid':'35ea6...', 'id':'ddr-testing-141', 'label':'mits.densho.org', 'location':'Seattle, WA'},
        ...
        
        If server_url is present (and server_label, server_location), a list of CIDs is
        retrieved from the Gitolite server and integrated.
        
        @param server_url: (optional) USER@SERVER for Gitolite server to include in this list
        @param server_label: (optional) Label string to insert into server records.
        @param server_location: (optional) Location string to insert into server records.
        @returns list of dicts.
        """
        repos = []
        for store in self.stores:
            for c in store.collections:
                c['store'] = store.label
                c['location'] = store.location
                repos.append(c)
        if server_url:
            cids = Organization.collections_on_server(server_url)
            if not server_label:
                server_label = server_url.split('@')[1]
            for cid in cids:
                c = {'cid':cid, 'uuid':'', 'level':'meta', 'location':server_location, 'store': server_label}
                repos.append(c)
        return repos
    
    def collections_dict( self, fieldname ):
        """Similar to Organization.collections except returns collections in dict.
        
        >> from DDR.inventory import Organization
        >> org = Organization('/var/www/media/base/ddr-testing')
        >> collections = org.collections(key='uuid')
        >> for c in collections:
        >>     print(c)
        {'uuid':'43935...', 'id':'ddr-testing-141', 'label':'HMWF1TB2013', 'location':'Heart Mountain, WY'},
        {'uuid':'64393...', 'id':'ddr-testing-141', 'label':'pnr_tmp-ddr', 'location':'Pasadena, CA'},
        {'uuid':'36493...', 'id':'ddr-testing-141', 'label':'WD5000BMV-2', 'location':'Pasadena, CA'},
        {'uuid':'35ea6...', 'id':'ddr-testing-141', 'label':'mits.densho.org', 'location':'Seattle, WA'},
        ...
        
        @param fieldname: Name of field to use as dictionary key.
        @returns dict.
        """
        repos = {}
        for s in self.stores:
            for c in s.collections:
                c['store'] = s.label
                c['location'] = s.location
                if c.get(fieldname, None):
                    key = c.pop(fieldname)
                    repos[key] = c
        return repos
    
    @staticmethod
    def collections_on_server( server_url ):
        """List CIDs for collections on the specified Gitolite server.
        
        The equivalent of 'ssh git@SERVER info', without the 'hello' message
        and the regexes at the beginning.
        
        @param server_url
        @returns cids
        """
        cids = []
        status,lines = dvcs.gitolite_info(server_url)
        lines.reverse()
        for line in lines:
            # skip first 2 lines
            # skip regexes (contain 'hello', or 'R W C', '[', ']', '+')
            line = line.strip()
            hello = False; regex = False
            if 'hello' in line:
                hello = True
            regex_matches = [line for subst in ['R W C', '[', ']', '+'] if subst in line]
            if line and (not hello) and (not len(regex_matches) == 4):
                cid = line.split('\t')[-1]
                if Collection.id_is_valid(cid):
                    cids.append(cid)
        return natural_sort(cids)
    
    def whereis( self, server_url, server_label=None, server_location=None ):
        """Lists all repos known to this Organization by collection ID

        This is the output of Organization.collections(), with the server info, in a dict,
        keys: collection ID
        values: lists of repos for that collection ID.
        """
        collections = {}
        known_repos = self.collections(server_url=server_url,
                                       server_label=server_label,
                                       server_location=server_location )
        for repo in known_repos:
            if not collections.get(repo['cid'], None):
                collections[repo['cid']] = []
            if repo not in collections[repo['cid']]:
                collections[repo['cid']].append(repo)
        return collections
    
    def collection_whereis( self, label, repo=None, uuid=None, cid=None ):
        """Adds Store locations to annex whereis information 
        
        for each file in a collection,
            num copies
            for each copy,
                label
                location
        @param label: Store label
        @param repo: (optional) Collection GitPython repo object
        @param uuid: (optional) UUID
        @param cid: (optional)
        @returns whereis info for the collection
        """
        s = self.store(label)
        if not repo:
            c = s.collection(uuid=uuid, cid=cid)
            repo = dvcs.repository(c['path'])
        whereis = dvcs.annex_whereis(repo)
        for f in whereis:
            f['basename'] = os.path.basename(f['path'])
            for r in f['remotes']:
                r['location'] = s.location
        return whereis



"""
Sample STORE.json:

{
  "collections": [
    {
      "cid": "ddr-testing-135",
      "level": "all",
      "path": "/var/www/media/base/ddr-testing-135",
      "uuid": "92681372-1b1b-11e3-8ff4-1f1cfa6efa5e",
      "entities": [
        { "eid": "ddr-testing-135-32", "level": "access" },
        { "eid": "ddr-testing-135-64", "level": "meta" },
        ...
    },
    ...

NOTE: ['collections']['entities'] is optional; overrides the collection setting.
"""

STORE_FIELDS = ['repo', 'org', 'label', 'location', 'purchase_date', 'collections',]
COLLECTION_FIELDS = ['uuid', 'cid', 'level', 'entities',]

class Store( object ):
    store_base = None
    path = None
    repo = None
    org = None
    label = None
    location = None
    purchase_date = None
    collections = []
    
    def __init__(self, **kwargs):
        self.path = kwargs.get('path', None)
        for k in kwargs.keys():
            if k in STORE_FIELDS:
                self.__setattr__(k, kwargs[k])
    
    def json( self ):
        data = {}
        for f in STORE_FIELDS:
            data[f] = getattr(self, str(f))
        return data
    
    @staticmethod
    def load(path):
        """
        @param path: Path including basename
        """
        s = Store(path=path)
        with open(path, 'r') as f:
            data = json.loads(f.read())
        for k in data.keys():
            if k in STORE_FIELDS:
                s.__setattr__(k, data[k])
        s.store_base = os.path.dirname(os.path.dirname(path))
        # add path to collections
        for c in s.collections:
            c['path'] = os.path.join(s.store_base, c['cid'])
        return s
    
    def save( self, path ):
        _write_json(self.json(), path)
    
    @staticmethod
    def file_is_valid( path ):
        """Indicates whether a STORE.json file is valid.
        
        @param path: Absolute path to file.
        @returns True if valid, list of faults if not.
        """
        faults = []
        data = None
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    data = json.loads(f.read())
            except:
                faults.append('Not a valid JSON file.')
        else:
            faults.append('File does not exist.')
        if data:
            if not data.get('repo', None):          faults.append('missing field: repo')
            if not data.get('org', None):           faults.append('missing field: org')
            if not data.get('label', None):         faults.append('missing field: label')
            if not data.get('location', None):      faults.append('missing field: location')
            if not data.get('purchase_date', None): faults.append('missing field: purchase_date')
            if not data.get('collections', None):   faults.append('missing field: collections')
            cindex = 0
            if data.get('collections', None):
                for c in data['collections']:
                    cindex = cindex + 1
                    if not c.get('uuid', None):  faults.append('collection %s missing field: uuid'  % cindex)
                    if not c.get('cid', None):   faults.append('collection %s missing field: cid'   % cindex)
                    if not c.get('level', None): faults.append('collection %s missing field: level' % cindex)
                    if c.get('entities', None):
                        eindex = 0
                        for e in c['entities']:
                            eindex = eindex + 1
                            if not e.get('eid', None):
                                faults.append('collection %s object %s missing field: eid' % (cindex, eindex))
                            if not e.get('level', None):
                                faults.append('collection %s object %s missing field: level' % (cindex, eindex))
        if len(faults) == 0:
            return True
        return faults
    
    def filename( self ):
        return '%s.json' % self.label
    
    def collection( self, uuid=None, cid=None ):
        if uuid or cid:
            for c in self.collections:
                if uuid and (c['uuid'] == uuid):
                    return c
                elif cid and (c['cid'] == cid):
                    return c
        return None
    
    @staticmethod
    def guess_collection_level( collection_path ):
        """Try to guess a collection's level by looking at git-annex-find
        
        If git-annex-find lists no files it's probably a metadata-only repo.
        If there are only files ending with the access suffix, probably access.
        If mixture of access and others, probably master.
        
        @param collection_path: Absolute path to collection
        @returns 'metadata', 'access', 'master', or 'unknown'
        """
        try:
            annex_files = dvcs.annex_find(collection_path)
        except:
            return 'error: annex'
        if len(annex_files) == 0:
            return 'metadata'
        # tally up the access and master copies
        access = 0
        master = 0
        for f in annex_files:
            # access files end in '-a'
            # TODO replace with access file string from settings
            if os.path.splitext(f)[0][-2:] == '-a':
                access = access + 1
            else:
                master = master + 1
        if access and not master:
            return 'access'
        elif access and master:
            return 'master'
        return 'unknown'
    
    @staticmethod
    def analyze( path, force_level=None ):
        """Reports all the valid* collections in the specified directory.
        
        * Valid according to Collection.is_valid anyway.
        
        >> from DDR.inventory import Store
        >> Store.analyze('/var/www/media/base')
        
        @param path
        @return label,collections
        """
        label = _guess_drive_label(path)
        
        def looks_like_a_collection( path ):
            """Indicates whether the path points to a valid Collection.
            
            @param path
            @returns True/False
            """
            git_dir_exists   = os.path.exists(os.path.join(path, '.git'))
            annex_dir_exists = os.path.exists(os.path.join(path, '.git', 'annex'))
            control_exists   = os.path.exists(os.path.join(path, 'control'))
            if git_dir_exists and annex_dir_exists and control_exists:
                return True
            return False
        def get_uuid(cpath):
            repo = dvcs.repository(cpath)
            if repo:
                return repo.git.config('annex.uuid')
            return None
        def get_cid(cpath):
            """
            TODO This assumes presence of collection.json, which is managed by ddrlocal.models!!!
            """
            cjson = os.path.join(cpath, 'collection.json')
            with open(cjson, 'r') as f:
                data = json.loads(f.read())
            for field in data:
                cid = field.get('id', None)
                if cid:
                    return cid
            return None
        
        # collections:
        collections = []
        dirs = os.listdir(path)
        dirs.sort()
        for d in dirs:
            cpath = os.path.join(path, d)
            if looks_like_a_collection(cpath):
                uuid = get_uuid(cpath)
                cid = get_cid(cpath)
                if force_level:
                    level = force_level
                else:
                    level = Store.guess_collection_level(cpath)
                if uuid and cid:
                    c = { 'uuid':uuid, 'cid':cid, 'level':level }
                    collections.append(c)
        return label,collections
    
    @staticmethod
    def _file_level(collection, path):
        level = collection['level']
        if collection.get('entities', None):
            eid = Store._file_eid(path)
            entity = collection['entities'].get(eid, None)
            if entity:
                level = entity['level']
        return level
    
    @staticmethod
    def _file_eid(path):
        """
        TODO This seems like the kind of function that should be present elsewhere.
        """
        fn,ext = os.path.splitext(os.path.basename(path))
        parts = fn.split('-')
        repo = parts[0]; org = parts[1]; cid = parts[2]; eid = parts[3]
        return '-'.join([repo,org,cid,eid])

    def apply( self, cids=[], confirmed=False ):
        """Change collection repos to reflect level settings in STORE.json.
        
        This function examines each annex file in the specified collections
        and decides if it should be there.
        Files that should be present but are not are git-annex-gotten.
        Files that are present but should not be are git-annex-dropped.
        
        @param cids: (optional) List of collection IDs; changes will only be applied to these collections.
        @param confirmed: Confirm that you actually want to write changes to disk
        @returns list of actions performed along with their results
        """
        def is_access_file(path):
            """Indicates whether filename ends with accessfile suffix.
            """
            access_suffix = ACCESS_FILE_APPEND + ACCESS_FILE_EXTENSION
            if (access_suffix in path) and path.endswith(access_suffix):
                return True
            return False
        def file_should_exist(path, level):
            """
            @param path
            @param level
            @return True,False,None
            """
            if   level in ['meta']:          return False
            elif level in ['master', 'all']: return True
            elif level in ['access']:
                if is_access_file(path): return True
                else:                    return False
            return None
        logger.debug('Store.apply( cids=%s, confirmed=%s )' % (cids, confirmed))
        logger.debug('self.path: %s' % self.path)
        logger.debug('self.label: %s' % self.label)
        logger.debug('self.location: %s' % self.location)
        subset = []
        for collection in self.collections:
            if cids:
                if (collection['cid'] in cids):
                    subset.append(collection)
            else:
                subset.append(collection)
        logger.debug('selected: %s' % [c['cid'] for c in subset])
        actions = []
        for collection in subset:
            logger.debug('COLLECTION %s -- %s -- %s' % (collection['cid'], collection['level'], collection['path']))
            repo = dvcs.repository(collection['path'])
            collection_annex_files = [f['path'] for f in dvcs.annex_whereis(repo)]
            for fpath in collection_annex_files:
                logger.debug('    %s' % fpath)
                fpath_abs = os.path.join(collection['path'], fpath)
                flevel = Store._file_level(collection, fpath)
                exists = os.path.exists(fpath_abs)
                should_exist = file_should_exist(fpath, flevel)
                logger.debug('        level:%s -- exists:%s -- should_exist:%s' % (flevel, exists, should_exist))
                # MUST DECIDE!
                action = ''
                if   (should_exist == True)  and      exists:  pass
                elif (should_exist == True)  and (not exists): action = 'get'
                elif (should_exist == False) and      exists:  action = 'drop'
                elif (should_exist == False) and (not exists): pass
                logger.debug('        action: %s' % action)
                # do or do not there is no try
                result = 'noop'
                if confirmed and action:
                    if   action == 'get':  result = dvcs.annex_get(repo, fpath)
                    elif action == 'drop': result = dvcs.annex_drop(repo, fpath)
                if result == 'noop':
                    logger.debug('        result: noop')
                else:
                    logger.debug(result)
                if action:
                    actions.append( {'action':action, 'path':fpath, 'result':result} )
        return actions



class Collection( object ):
    path = None
    path_rel = None
    root = None
    uid = None
    annex_path = None
    changelog_path = None
    control_path = None
    gitignore_path = None
    annex_path_rel = None
    changelog_path_rel = None
    control_path_rel = None
    gitignore_path_rel = None
    git_url = None
    
    def _path_absrel( self, filename, rel=False ):
        if rel:
            return filename
        return os.path.join(self.path, filename)
    
    def __init__( self, path, uid=None ):
        self.path = path
        self.path_rel = os.path.split(self.path)[1]
        self.root = os.path.split(self.path)[0]
        if not uid:
            uid = os.path.basename(self.path)
        self.uid  = uid
        self.annex_path = os.path.join(self.path, '.git', 'annex')
        self.annex_path_rel = os.path.join('.git', 'annex')
        self.changelog_path     = self._path_absrel('changelog'  )
        self.control_path       = self._path_absrel('control'    )
        self.files_path         = self._path_absrel('files'      )
        self.gitignore_path     = self._path_absrel('.gitignore' )
        self.changelog_path_rel = self._path_absrel('changelog',  rel=True)
        self.control_path_rel   = self._path_absrel('control',    rel=True)
        self.files_path_rel     = self._path_absrel('files',      rel=True)
        self.gitignore_path_rel = self._path_absrel('.gitignore', rel=True)
        self.git_url = '{}:{}'.format(GITOLITE, self.uid)
    
    def entity_path( self, entity_uid ):
        return os.path.join(self.files_path, entity_uid)
    
    def changelog( self ):
        if os.path.exists(self.changelog_path):
            return open(self.changelog_path, 'r').read()
        return '%s is empty or missing' % self.changelog_path
    
    def control( self ):
        if not os.path.exists(self.control_path):
            CollectionControlFile.create(self.control_path, self.uid)
        return CollectionControlFile(self.control_path)
    
    def gitignore( self ):
        if not os.path.exists(self.gitignore_path):
            with open(GITIGNORE_TEMPLATE, 'r') as fr:
                gt = fr.read()
            with open(self.gitignore_path, 'w') as fw:
                fw.write(gt)
        with open(self.gitignore_path, 'r') as f:
            return f.read()
    
    @staticmethod
    def id_is_valid( cid ):
        """Indicates whether the string looks like a valid collection ID.
        """
        if len(cid.split('-')) == 3:
            return True
        return False
    
    @staticmethod
    def is_valid( collection_path ):
        """Indicates whether the directory represents a valid collection repository.
        
        NOTE: This does not validate higher levels of "collection-ness" like JSON files.
        
        @param collection_path: Absolute path to collection dir.
        @returns True or False
        """
        changelog_path = os.path.join(collection_path, 'changelog')
        control_path = os.path.join(collection_path, 'control')
        score = []
        if os.path.isdir(collection_path): score.append(1)
        # looks like collection dirname
        if len(os.path.basename(collection_path).split('-')) == 3: score.append(1)
        # changelog
        if os.path.exists(changelog_path): score.append(1)
        # control
        if os.path.exists(control_path):
            score.append(1)
            config = ConfigParser.ConfigParser()
            config.read(control_path)
            if config.has_section('Entities'):
                score.append(1)
        if score == 5:
            return True
        return False
    
    @staticmethod
    def collections( collections_root, repository, organization ):
        collections = []
        regex = '^{}-{}-[0-9]+$'.format(repository, organization)
        uid = re.compile(regex)
        for x in os.listdir(collections_root):
            m = uid.search(x)
            if m:
                colldir = os.path.join(collections_root,x)
                if 'collection.json' in os.listdir(colldir):
                    collections.append(colldir)
        collections = sorted(collections, key=lambda c: natural_order_string(c))
        return collections
    
    def entities( self ):
        """Returns relative paths to entities."""
        entities = []
        cpath = self.path
        if cpath[-1] != '/':
            cpath = '{}/'.format(cpath)
        if os.path.exists(self.files_path):
            for uid in os.listdir(self.files_path):
                epath = os.path.join(self.files_path, uid)
                e = Entity(epath)
                entities.append(e)
        entities = sorted(entities, key=lambda e: natural_order_string(e.uid))
        return entities



class Entity( object ):
    path = None
    path_rel = None
    root = None
    parent_path = None
    uid = None
    parent_uid = None
    changelog_path = None
    control_path = None
    files_path = None
    changelog_path_rel = None
    control_path_rel = None
    files_path_rel = None
    
    def _path_absrel( self, filename, rel=False ):
        """
        NOTE: relative == relative to collection root
        """
        if rel:
            p = self.path.replace('%s/' % self.parent_path, '')
            return os.path.join(p, filename)
        return os.path.join(self.path, filename)
    
    def __init__( self, path, uid=None ):
        self.path = path
        self.parent_path = os.path.split(os.path.split(self.path)[0])[0]
        self.root = os.path.split(self.parent_path)[0]
        self.path_rel = self.path.replace('%s/' % self.root, '')
        if not uid:
            uid = os.path.basename(self.path)
        self.uid = uid
        self.parent_uid = os.path.split(self.parent_path)[1]
        self.changelog_path     = self._path_absrel('changelog'  )
        self.control_path       = self._path_absrel('control'    )
        self.files_path         = self._path_absrel('files'      )
        self.changelog_path_rel = self._path_absrel('changelog',  rel=True)
        self.control_path_rel   = self._path_absrel('control',    rel=True)
        self.files_path_rel     = self._path_absrel('files',      rel=True)
    
    def changelog( self ):
        if os.path.exists(self.changelog_path):
            return open(self.changelog_path, 'r').read()
        return '%s is empty or missing' % self.changelog_path
    
    def control( self ):
        if not os.path.exists(self.control_path):
            EntityControlFile.create(self.control_path, self.parent_uid, self.uid)
        return EntityControlFile(self.control_path)
    
    def files( self ):
        """Returns relative paths to payload files."""
        files = []
        prefix_path = self.files_path
        if prefix_path[-1] != '/':
            prefix_path = '{}/'.format(prefix_path)
        for f in os.listdir(self.files_path):
            files.append(f.replace(prefix_path, ''))
        files = sorted(files, key=lambda f: natural_order_string(f))
        return files
    
    @staticmethod
    def checksum_algorithms():
        return ['md5', 'sha1', 'sha256']
    
    def checksums( self, algo ):
        checksums = []
        def file_checksum( path, algo, block_size=1024 ):
            if algo == 'md5':
                h = hashlib.md5()
            elif algo == 'sha1':
                h = hashlib.sha1()
            elif algo == 'sha256':
                h = hashlib.sha256()
            else:
                return None
            f = open(path, 'rb')
            while True:
                data = f.read(block_size)
                if not data:
                    break
                h.update(data)
            f.close()
            return h.hexdigest()
        if algo not in Entity.checksum_algorithms():
            raise Error('BAD ALGORITHM CHOICE: {}'.format(algo))
        for f in self.files():
            fpath = os.path.join(self.files_path, f)
            cs = file_checksum(fpath, algo)
            if cs:
                checksums.append( (cs, fpath) )
        return checksums
