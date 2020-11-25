# -*- coding: utf-8 -*-
import copy
import datetime
import json
import os

from bson.objectid import ObjectId
from .model_base import AccessControlledModel
from girder import events
from girder.constants import AccessType
from girder.exceptions import ValidationException, GirderException
from girder.utility.model_importer import ModelImporter
from girder.utility.progress import noProgress, setResponseTimeLimit


class Requisition(AccessControlledModel):

    def initialize(self):
        self.name = 'requisition'
        #self.ensureIndices(('parentId', 'name', 'lowerName', 'creatorId'))
        # self.ensureTextIndex({
        #     'history': 10,
        #     'bloodGroup': 1
        # })

        self.exposeFields(level=AccessType.READ, fields=(
            '_id', 'slideId','creatorId', 'age', 'bloodGroup', 'history', 'created', 'updated'))
    
    #---------------------VALIDATE OVERRIDING-------------------

    def validate(self, doc, allowRename=False):
              
        
        return doc

    #-------------------CREATING ROLE-------------------

    def createRequisition(self, slideId, creatorId, age, bloodGroup, history):
        
        now = datetime.datetime.utcnow()

        requisition = {
            'slideId': slideId,
            'age': age,
            'creatorId': creatorId,
            'bloodGroup':bloodGroup,
            'history':history,
            'created': now,
            'updated': now,
        }

        return self.save(requisition)

    #--------------------DELETING ROLE---------------------

    def remove(self, requisition):
        # Delete this folder
        super().remove(requisition)

    # #--------------------UPDATING ROLE----------------------

    # def updateRole(self, role):
    
    #     role['modified'] = datetime.datetime.utcnow()

    #     # Validate and save the folder
    #     return self.save(role)

    # #--------------------SEARCHING ROLES--------------------

    def _searchRequisition(self):

        return self.find()
    