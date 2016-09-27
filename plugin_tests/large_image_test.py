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
import time

from girder import config
from tests import base

from . import common


# boiler plate to start and stop the server

os.environ['GIRDER_PORT'] = os.environ.get('GIRDER_TEST_PORT', '20200')
config.loadConfig()  # Must reload config to pickup correct port


def setUpModule():
    base.enabledPlugins.append('large_image')
    base.startServer(False)


def tearDownModule():
    base.stopServer()


# Test large_image endpoints
class LargeImageLargeImageTest(common.LargeImageCommonTest):
    def _createThumbnails(self, spec):
        from girder.plugins.jobs.constants import JobStatus

        resp = self.request(
            method='PUT', path='/large_image/thumbnails', user=self.admin,
            params={'spec': json.dumps(spec)})
        self.assertStatusOk(resp)
        job = resp.json
        starttime = time.time()
        while True:
            self.assertTrue(time.time() - starttime < 30)
            resp = self.request('/job/%s' % str(job['_id']))
            self.assertStatusOk(resp)
            if resp.json.get('status') == JobStatus.SUCCESS:
                return True
            if resp.json.get('status') == JobStatus.ERROR:
                return False
            time.sleep(0.1)

    def testThumbnailFileJob(self):
        # Create files via a job
        file = self._uploadFile(os.path.join(
            os.environ['LARGE_IMAGE_DATA'], 'sample_image.ptif'))
        itemId = str(file['itemId'])

        # We should report zero thumbnails
        item = self.model('item').load(itemId, user=self.admin)
        present, removed = self.model(
            'image_item', 'large_image').removeThumbnailFiles(item, keep=10)
        self.assertEqual(present, 0)

        # Test PUT thumbnails
        resp = self.request(method='PUT', path='/large_image/thumbnails',
                            user=self.user)
        self.assertStatus(resp, 403)
        resp = self.request(method='PUT', path='/large_image/thumbnails',
                            user=self.admin)
        self.assertStatus(resp, 400)
        self.assertIn('\'spec\' is required', resp.json['message'])
        resp = self.request(
            method='PUT', path='/large_image/thumbnails', user=self.admin,
            params={'spec': json.dumps({})})
        self.assertStatus(resp, 400)
        self.assertIn('must be a JSON list', resp.json['message'])

        # Run a job to create two sizes of thumbnails
        self.assertTrue(self._createThumbnails([
            {'width': 160, 'height': 100},
            {'encoding': 'PNG'}
        ]))
        # We should report two thumbnails
        present, removed = self.model(
            'image_item', 'large_image').removeThumbnailFiles(item, keep=10)
        self.assertEqual(present, 2)

        # Run a job to create two sizes of thumbnails, one different than
        # before
        self.assertTrue(self._createThumbnails([
            {'width': 160, 'height': 100},
            {'width': 160, 'height': 160},
        ]))
        # We should report three thumbnails
        present, removed = self.model(
            'image_item', 'large_image').removeThumbnailFiles(item, keep=10)
        self.assertEqual(present, 3)

        # Asking for a bad thumbnail specification should just do nothing
        self.assertFalse(self._createThumbnails(['not a dictionary']))
        present, removed = self.model(
            'image_item', 'large_image').removeThumbnailFiles(item, keep=10)
        self.assertEqual(present, 3)

        # Test DELETE thumbnails
        resp = self.request(method='DELETE', path='/large_image/thumbnails',
                            user=self.user)
        self.assertStatus(resp, 403)
        resp = self.request(
            method='DELETE', path='/large_image/thumbnails', user=self.admin,
            params={'spec': json.dumps({})})
        self.assertStatus(resp, 400)
        self.assertIn('must be a JSON list', resp.json['message'])

        # Delete one set of thumbnails
        resp = self.request(
            method='DELETE', path='/large_image/thumbnails', user=self.admin,
            params={'spec': json.dumps([{'encoding': 'PNG'}])})
        self.assertStatusOk(resp)
        present, removed = self.model(
            'image_item', 'large_image').removeThumbnailFiles(item, keep=10)
        self.assertEqual(present, 2)

        # Try to delete some that don't exist
        resp = self.request(
            method='DELETE', path='/large_image/thumbnails', user=self.admin,
            params={'spec': json.dumps([{'width': 200, 'height': 200}])})
        self.assertStatusOk(resp)
        present, removed = self.model(
            'image_item', 'large_image').removeThumbnailFiles(item, keep=10)
        self.assertEqual(present, 2)

        # Delete them all
        resp = self.request(
            method='DELETE', path='/large_image/thumbnails', user=self.admin)
        self.assertStatusOk(resp)
        present, removed = self.model(
            'image_item', 'large_image').removeThumbnailFiles(item, keep=10)
        self.assertEqual(present, 0)
