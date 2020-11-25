# -*- coding: utf-8 -*-
from ..describe import Description, autoDescribeRoute
from ..rest import Resource, filtermodel, setResponseHeader, setContentDisposition
from girder.api import access
from girder.constants import AccessType, TokenScope, SortDir
from girder.exceptions import RestException
from ...models.role import Role as RoleModel
from girder.utility import ziputil
from girder.utility.model_importer import ModelImporter
from girder.utility.progress import ProgressContext


class Role(Resource):
    """API Endpoint for Roles."""
    
    def __init__(self):
        super().__init__()
        self.resourceName = 'role'
        self._model = RoleModel()

        #@@@@@@@@@@@@@@@@@@@@@--ROUTES--@@@@@@@@@@@@@@@@@@

        self.route('POST', (), self.createRole)
        self.route('DELETE', (':id',), self.deleteRole)
        self.route('POST', (':id', ), self.updateRole)
        self.route('GET', (), self.searchRole)
        #@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

    #------------CREATING A NEW ROLE---------------------    
    @access.user(scope=TokenScope.DATA_WRITE) #Significance of TokenScope.
    @filtermodel(model=RoleModel)   #Check what it is.
    @autoDescribeRoute(   
        Description('Create a new Role.')
        .responseClass('Role')
        .param('name', 'Name of the role.', strip=True)
        #.param('creatorId', 'User ID of the owner who created this role.', required=True)
        .param('description', 'Description for the role.', required=False,
               default='', strip=True)
        .errorResponse('Could not create Role, write access was denied', 403)    #Need to change message
    )
    def createRole(self, name,  description):
        user = self.getCurrentUser()
        newRole = self._model.createRole(name=name, creatorId=user['_id'], description=description)
        return newRole
    
    #------------DELETING A ROLE-------------------------

    @access.user(scope=TokenScope.DATA_WRITE)
    @filtermodel(model=RoleModel)
    @autoDescribeRoute(
        Description('Delete a role by ID.')
        .modelParam('id', model=RoleModel, level=AccessType.ADMIN)
        .errorResponse('Invalid Role ID, cannot delete.')
        .errorResponse('Admin access was denied for the role.', 403)
    )
    def deleteRole(self, role):
        self._model.remove(role)
        return {'message': 'Deleted role %s.' % role['name']}
    
    #-------------UPDATING A ROLE------------------------

    @access.user(scope=TokenScope.DATA_WRITE)
    @filtermodel(model=RoleModel)
    @autoDescribeRoute(
        Description('Update a role.')
        .responseClass('Role')
        .modelParam('id', model=RoleModel, level=AccessType.WRITE)
        .param('name', 'Name of the folder.', required=False, strip=True)
        .param('description', 'Description for the role.', required=False, strip=True)
        .errorResponse('ID was invalid.')
        .errorResponse('Write access was denied for the role or its new parent object.', 403)
    )
    def updateRole(self, role, name, description):
        
        if name is not None:
            role['name'] = name
        if description is not None:
            role['description'] = description

        role = self._model.updateRole(role)

        return role

    #------------------GETTING ALL THE ROLES-----------------

    @access.public(scope=TokenScope.DATA_READ)
    @filtermodel(model=RoleModel)
    @autoDescribeRoute(
        Description('List or search for RRRRole.')
        .responseClass('Role', array=True)
        .pagingParams(defaultSort='name')
    )
    def searchRole(self):

        return list(self._model._searchRole())
    