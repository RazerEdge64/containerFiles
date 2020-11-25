# -*- coding: utf-8 -*-
from ..describe import Description, autoDescribeRoute
from ..rest import Resource, filtermodel, setResponseHeader, setContentDisposition
from girder.api import access
from girder.constants import AccessType, TokenScope, SortDir
from girder.exceptions import RestException
from ...models.requisition import Requisition as RequisitionModel
from girder.utility import ziputil
from girder.utility.model_importer import ModelImporter
from girder.utility.progress import ProgressContext


class Requisition(Resource):
    """API Endpoint for Requisitions."""
    
    def __init__(self):
        super().__init__()
        self.resourceName = 'requisition'
        self._model = RequisitionModel()

        #@@@@@@@@@@@@@@@@@@@@@--ROUTES--@@@@@@@@@@@@@@@@@@

        self.route('POST', (), self.createRequisition)
        self.route('DELETE', (':id',), self.deleteRequisition)
        # self.route('POST', (':id', ), self.updateRole)
        self.route('GET', (), self.searchRequisition)
        #@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

    #------------CREATING A NEW Requisition---------------------    
    @access.user(scope=TokenScope.DATA_WRITE) #Significance of TokenScope.
    @filtermodel(model=RequisitionModel)   #Check what it is.
    @autoDescribeRoute(   
        Description('Create a new Requisition.')
        .responseClass('Requisition')
        .param('slideId', 'Slide ID', strip=True)
        #.param('creatorId', 'User ID of the owner who created this role.', required=True)
        .param('age', 'Age of the Patient.', required=False,
               default='', strip=True)
        .param('bloodGroup', "Patient's blood Group.", required=False,
               default='', strip=True)
        .param('history', "Patient's history.", required=False,
               default='', strip=True)
        .errorResponse('Could not create Role, write access was denied', 403)    #Need to change message
    )
    def createRequisition(self, slideId,  age, bloodGroup, history):
        user = self.getCurrentUser()
        newRequisition = self._model.createRequisition(slideId=slideId, creatorId=user['_id'],
        age=age, bloodGroup=bloodGroup, history=history)
        return newRequisition
    
    #------------DELETING A REQUISITION-------------------------

    @access.user(scope=TokenScope.DATA_WRITE)
    @filtermodel(model=RequisitionModel)
    @autoDescribeRoute(
        Description('Delete a requisition by ID.')
        .modelParam('id', model=RequisitionModel, level=AccessType.ADMIN)
        .errorResponse('Invalid Requisition ID, cannot delete.')
        .errorResponse('Admin access was denied for the requisition.', 403)
    )
    def deleteRequisition(self, requisition):
        self._model.remove(requisition)
        return {'message': 'Deleted requisition for %s.' % requisition['slideId']}
    
    # #-------------UPDATING A ROLE------------------------

    # @access.user(scope=TokenScope.DATA_WRITE)
    # @filtermodel(model=RequisitionModel)
    # @autoDescribeRoute(
    #     Description('Update a role.')
    #     .responseClass('Role')
    #     .modelParam('id', model=RoleModel, level=AccessType.WRITE)
    #     .param('name', 'Name of the folder.', required=False, strip=True)
    #     .param('description', 'Description for the role.', required=False, strip=True)
    #     .errorResponse('ID was invalid.')
    #     .errorResponse('Write access was denied for the role or its new parent object.', 403)
    # )
    # def updateRole(self, role, name, description):
        
    #     if name is not None:
    #         role['name'] = name
    #     if description is not None:
    #         role['description'] = description

    #     role = self._model.updateRole(role)

    #     return role

    #------------------GETTING ALL THE ROLES-----------------

    @access.public(scope=TokenScope.DATA_READ)
    @filtermodel(model=RequisitionModel)
    @autoDescribeRoute(
        Description('List or search for Requisitions.')
        .responseClass('Requisition', array=True)
        .pagingParams(defaultSort='age')
    )
    def searchRequisition(self):

        return list(self._model._searchRequisition())
    