#!/usr/bin/env python
# -*- coding: utf-8 -*-

#############################################################################
#  Copyright Kitware Inc.
#
#  Licensed under the Apache License, Version 2.0 ( the "License" );
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#############################################################################

import json
import os
import pymongo
import six
import time

from girder.constants import SortDir
from girder.exceptions import FilePathException, ValidationException
from girder.models.file import File
from girder.models.item import Item
from girder.models.setting import Setting
from girder.models.upload import Upload
from girder.plugins.jobs.constants import JobStatus
from girder.plugins.jobs.models.job import Job

from .base import TileGeneralException
from .. import constants
from ..tilesource import AvailableTileSources, TileSourceException


class ImageItem(Item):
    # We try these sources in this order.  The first entry is the fallback for
    # items that antedate there being multiple options.
    def initialize(self):
        super(ImageItem, self).initialize()
        self.ensureIndices(['largeImage.fileId'])
        File().ensureIndices([([
            ('isLargeImageThumbnail', pymongo.ASCENDING),
            ('attachedToType', pymongo.ASCENDING),
            ('attachedToId', pymongo.ASCENDING),
        ], {})])

    def createImageItem(self, item, fileObj, user=None, token=None,
                        createJob=True, notify=False):
        # Using setdefault ensures that 'largeImage' is in the item
        if 'fileId' in item.setdefault('largeImage', {}):
            # TODO: automatically delete the existing large file
            raise TileGeneralException('Item already has a largeImage set.')
        if fileObj['itemId'] != item['_id']:
            raise TileGeneralException('The provided file must be in the '
                                       'provided item.')
        if (item['largeImage'].get('expected') is True and
                'jobId' in item['largeImage']):
            raise TileGeneralException('Item is scheduled to generate a '
                                       'largeImage.')

        item['largeImage'].pop('expected', None)
        item['largeImage'].pop('sourceName', None)

        item['largeImage']['fileId'] = fileObj['_id']
        job = None
        for sourceName in AvailableTileSources:
            if getattr(AvailableTileSources[sourceName], 'girderSource',
                       False):
                if AvailableTileSources[sourceName].canRead(item):
                    item['largeImage']['sourceName'] = sourceName
                    break
        if 'sourceName' not in item['largeImage'] and not createJob:
            raise TileGeneralException(
                'A job must be used to generate a largeImage.')
        if 'sourceName' not in item['largeImage']:
            # No source was successful
            del item['largeImage']['fileId']
            job = self._createLargeImageJob(item, fileObj, user, token)
            item['largeImage']['expected'] = True
            item['largeImage']['notify'] = notify
            item['largeImage']['originalId'] = fileObj['_id']
            item['largeImage']['jobId'] = job['_id']

        self.save(item)
        return job

    def _createLargeImageJob(self, item, fileObj, user, token):
        import large_image_tasks.tasks
        from girder_worker_utils.transforms.girder_io import GirderUploadToItem
        from girder_worker_utils.transforms.contrib.girder_io import GirderFileIdAllowDirect
        from girder_worker_utils.transforms.common import TemporaryDirectory

        outputName = os.path.splitext(fileObj['name'])[0] + '.tiff'
        if outputName == fileObj['name']:
            outputName = (os.path.splitext(fileObj['name'])[0] + '.' +
                          time.strftime('%Y%m%d-%H%M%S') + '.tiff')
        try:
            localPath = File().getLocalFilePath(fileObj)
        except (FilePathException, AttributeError):
            localPath = None
        job = large_image_tasks.tasks.create_tiff.delay(
            girder_job_title=u'TIFF Conversion: %s' % fileObj['name'],
            girder_job_other_fields={'meta': {
                'creator': 'large_image',
                'itemId': str(item['_id']),
                'task': 'createImageItem',
            }},
            inputFile=GirderFileIdAllowDirect(str(fileObj['_id']), fileObj['name'], localPath),
            outputName=outputName,
            outputDir=TemporaryDirectory(),
            girder_result_hooks=[
                GirderUploadToItem(str(item['_id']), True),
            ]
        )
        return job.job

    @classmethod
    def _loadTileSource(cls, item, **kwargs):
        if 'largeImage' not in item:
            raise TileSourceException('No large image file in this item.')
        if item['largeImage'].get('expected'):
            raise TileSourceException('The large image file for this item is '
                                      'still pending creation.')

        sourceName = item['largeImage']['sourceName']

        tileSource = AvailableTileSources[sourceName](item, **kwargs)
        return tileSource

    def getMetadata(self, item, **kwargs):
        tileSource = self._loadTileSource(item, **kwargs)
        return tileSource.getMetadata()

    def getTile(self, item, x, y, z, mayRedirect=False, **kwargs):
        tileSource = self._loadTileSource(item, **kwargs)
        tileData = tileSource.getTile(x, y, z, mayRedirect=mayRedirect)
        tileMimeType = tileSource.getTileMimeType()
        return tileData, tileMimeType

    def delete(self, item, skipFileIds=None):
        deleted = False
        if 'largeImage' in item:
            job = None
            if 'jobId' in item['largeImage']:
                try:
                    job = Job().load(item['largeImage']['jobId'], force=True, exc=True)
                except ValidationException:
                    # The job has been deleted, but we still need to clean up
                    # the rest of the tile information
                    pass
            if (item['largeImage'].get('expected') and job and
                    job.get('status') in (
                    JobStatus.QUEUED, JobStatus.RUNNING)):
                # cannot cleanly remove the large image, since a conversion
                # job is currently in progress
                # TODO: cancel the job
                # TODO: return a failure error code
                return False

            # If this file was created by the worker job, delete it
            if 'jobId' in item['largeImage']:
                # To eliminate all traces of the job, add
                # if job:
                #     Job().remove(job)
                del item['largeImage']['jobId']

            if 'originalId' in item['largeImage']:
                # The large image file should not be the original file
                assert item['largeImage']['originalId'] != \
                    item['largeImage'].get('fileId')

                if ('fileId' in item['largeImage'] and (
                        not skipFileIds or
                        item['largeImage']['fileId'] not in skipFileIds)):
                    file = File().load(id=item['largeImage']['fileId'], force=True)
                    if file:
                        File().remove(file)
                del item['largeImage']['originalId']

            del item['largeImage']

            item = self.save(item)
            deleted = True
        self.removeThumbnailFiles(item)
        return deleted

    def getThumbnail(self, item, width=None, height=None, **kwargs):
        """
        Using a tile source, get a basic thumbnail.  Aspect ratio is
        preserved.  If neither width nor height is given, a default value is
        used.  If both are given, the thumbnail will be no larger than either
        size.

        :param item: the item with the tile source.
        :param width: maximum width in pixels.
        :param height: maximum height in pixels.
        :param **kwargs: optional arguments.  Some options are encoding,
            jpegQuality, jpegSubsampling, tiffCompression, fill.  This is also
            passed to the tile source.
        :returns: thumbData, thumbMime: the image data and the mime type OR
            a generator which will yield a file.
        """
        # check if a thumbnail file exists with a particular key
        keydict = dict(kwargs, width=width, height=height)
        if 'fill' in keydict and (keydict['fill']).lower() == 'none':
            del keydict['fill']
        keydict = {k: v for k, v in six.viewitems(keydict) if v is not None}
        key = json.dumps(keydict, sort_keys=True, separators=(',', ':'))
        existing = File().findOne({
            'attachedToType': 'item',
            'attachedToId': item['_id'],
            'isLargeImageThumbnail': True,
            'thumbnailKey': key
        })
        if existing:
            if kwargs.get('contentDisposition') != 'attachment':
                contentDisposition = 'inline'
            else:
                contentDisposition = kwargs['contentDisposition']
            return File().download(existing, contentDisposition=contentDisposition)
        tileSource = self._loadTileSource(item, **kwargs)
        thumbData, thumbMime = tileSource.getThumbnail(
            width, height, **kwargs)
        # The logic on which files to save could be more sophisticated.
        maxThumbnailFiles = int(Setting().get(
            constants.PluginSettings.LARGE_IMAGE_MAX_THUMBNAIL_FILES))
        saveFile = maxThumbnailFiles > 0
        if saveFile:
            # Make sure we don't exceed the desired number of thumbnails
            self.removeThumbnailFiles(item, maxThumbnailFiles - 1)
            # Save the thumbnail as a file
            thumbfile = Upload().uploadFromFile(
                six.BytesIO(thumbData), size=len(thumbData),
                name='_largeImageThumbnail', parentType='item', parent=item,
                user=None, mimeType=thumbMime, attachParent=True)
            thumbfile.update({
                'isLargeImageThumbnail': True,
                'thumbnailKey': key,
            })
            # Ideally, we would check that the file is still wanted before we
            # save it.  This is probably imposible without true transactions in
            # Mongo.
            File().save(thumbfile)
        # Return the data
        return thumbData, thumbMime

    def removeThumbnailFiles(self, item, keep=0, sort=None, **kwargs):
        """
        Remove all large image thumbnails from an item.

        :param item: the item that owns the thumbnails.
        :param keep: keep this many entries.
        :param sort: the sort method used.  The first (keep) records in this
            sort order are kept.
        :param **kwargs: additional parameters to determine which files to
            remove.
        :returns: a tuple of (the number of files before removal, the number of
            files removed).
        """
        if not sort:
            sort = [('_id', SortDir.DESCENDING)]
        query = {
            'attachedToType': 'item',
            'attachedToId': item['_id'],
            'isLargeImageThumbnail': True,
        }
        query.update(kwargs)
        present = 0
        removed = 0
        for file in File().find(query, sort=sort):
            present += 1
            if keep > 0:
                keep -= 1
                continue
            File().remove(file)
            removed += 1
        return (present, removed)

    def getRegion(self, item, **kwargs):
        """
        Using a tile source, get an arbitrary region of the image, optionally
        scaling the results.  Aspect ratio is preserved.

        :param item: the item with the tile source.
        :param **kwargs: optional arguments.  Some options are left, top,
            right, bottom, regionWidth, regionHeight, units, width, height,
            encoding, jpegQuality, jpegSubsampling, and tiffCompression.  This
            is also passed to the tile source.
        :returns: regionData, regionMime: the image data and the mime type.
        """
        tileSource = self._loadTileSource(item, **kwargs)
        regionData, regionMime = tileSource.getRegion(**kwargs)
        return regionData, regionMime

    def getPixel(self, item, **kwargs):
        """
        Using a tile source, get a single pixel from the image.

        :param item: the item with the tile source.
        :param **kwargs: optional arguments.  Some options are left, top.
        :returns: a dictionary of the color channel values, possibly with
            additional information
        """
        tileSource = self._loadTileSource(item, **kwargs)
        return tileSource.getPixel(**kwargs)

    def tileSource(self, item, **kwargs):
        """
        Get a tile source for an item.

        :param item: the item with the tile source.
        :return: magnification, width of a pixel in mm, height of a pixel in mm.
        """
        return self._loadTileSource(item, **kwargs)

    def getAssociatedImagesList(self, item, **kwargs):
        """
        Return a list of associated images.

        :param item: the item with the tile source.
        :return: a list of keys of associated images.
        """
        tileSource = self._loadTileSource(item, **kwargs)
        return tileSource.getAssociatedImagesList()

    def getAssociatedImage(self, item, imageKey, *args, **kwargs):
        """
        Return an associated image.

        :param item: the item with the tile source.
        :param imageKey: the key of the associated image to retreive.
        :param **kwargs: optional arguments.  Some options are width, height,
            encoding, jpegQuality, jpegSubsampling, and tiffCompression.
        :returns: imageData, imageMime: the image data and the mime type, or
            None if the associated image doesn't exist.
        """
        tileSource = self._loadTileSource(item, **kwargs)
        return tileSource.getAssociatedImage(imageKey, *args, **kwargs)
