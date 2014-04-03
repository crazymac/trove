#  Copyright 2014 Mirantis Inc.
#  All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import testtools

from trove.common import utils

VALID = "2014-04-04T11:19:04"
PATTERN = "2014-04-04T11:19:%s"


class TestTimestampUtils(testtools.TestCase):

    def setUp(self):
        super(TestTimestampUtils, self).setUp()

    def tearDown(self):
        super(TestTimestampUtils, self).tearDown()

    def test_success_to_load_utc_datetime_timestamp(self):

        ts = utils.load_utc_datetime_timestamp(VALID)
        self.assertEqual(VALID.replace("T", " "), str(ts))

    def test_failed_to_load_utc_datetime_timestamp(self):
        self.assertRaises(
            ValueError, utils.load_utc_datetime_timestamp,
            VALID.replace("T", " "))

    def test_find_latest(self):
        timestamps = []
        for i in range(10, 60):
            timestamps.append(PATTERN % i)
        latest = utils.find_latest_timestamp(timestamps)
        self.assertEqual(timestamps.pop().replace(
            "T", " "), str(latest))

    def test_find_closest(self):
        before = PATTERN % 00
        in_the_middle = PATTERN % 20
        after_all = "2014-04-04T11:20:00"
        timestamps = []
        for i in range(10, 60, 20):
            timestamps.append(PATTERN % i)
        before_closest = utils.find_closest_timestamp(
            before, timestamps)
        in_the_middle_closest = utils.find_closest_timestamp(
            in_the_middle, timestamps)
        after_all_closest = utils.find_closest_timestamp(
            after_all, timestamps)

        self.assertIsNotNone(before_closest)
        self.assertIsNotNone(in_the_middle_closest)
        self.assertIsNotNone(after_all_closest)

        self.assertTrue(str(utils.load_utc_datetime_timestamp(
            before)) < before_closest)
        self.assertTrue(str(utils.load_utc_datetime_timestamp(in_the_middle))
                        < in_the_middle_closest)
        self.assertTrue(str(utils.load_utc_datetime_timestamp(after_all))
                        > after_all_closest)
