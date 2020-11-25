# -*- coding: utf-8 -*-
import copy
import datetime
import json
import os
import logging

from bson.objectid import ObjectId
from .model_base import AccessControlledModel
from girder import events
from girder.constants import AccessType
from girder.exceptions import ValidationException, GirderException
from girder.utility.model_importer import ModelImporter
from girder.utility.progress import noProgress, setResponseTimeLimit


class Role(AccessControlledModel):

    def initialize(self):
        self.name = 'role'
        #self.ensureIndices(('parentId', 'name', 'lowerName', 'creatorId'))
        self.ensureTextIndex({
            'name': 10,
            'description': 1
        })

        self.exposeFields(level=AccessType.READ, fields=(
            '_id', 'name', 'description', 'creatorId'))
    
    #---------------------VALIDATE OVERRIDING-------------------

    def validate(self, doc, allowRename=False):
              
        return doc

    #-------------------CREATING ROLE-------------------

    def createRole(self, name, creatorId, description='',):
        
        now = datetime.datetime.utcnow()

        role = {
            'name': name,
            'description': description,
            'creatorId': creatorId,
            'created': now,
            'modified': now,
        }

        return self.save(role)

    #--------------------DELETING ROLE---------------------

    def remove(self, role):
        # Delete this folder
        logging.error('Reached in this delete snippet.')
        super().remove(role)

    #--------------------UPDATING ROLE----------------------

    def updateRole(self, role):
    
        role['modified'] = datetime.datetime.utcnow()

        # Validate and save the folder
        return self.save(role)

    #--------------------SEARCHING ROLES--------------------

    def _searchRole(self):

        return self.find()
    