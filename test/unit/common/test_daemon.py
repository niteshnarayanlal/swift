# Copyright (c) 2010-2012 OpenStack Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# TODO(clayg): Test kill_children signal handlers

import os
from six import StringIO
from six.moves import reload_module
import unittest
from getpass import getuser
import logging
from test.unit import tmpfile
from mock import patch

from swift.common import daemon, utils


class MyDaemon(daemon.Daemon):

    def __init__(self, conf):
        self.conf = conf
        self.logger = utils.get_logger(None, 'server', log_route='server')
        MyDaemon.forever_called = False
        MyDaemon.once_called = False

    def run_forever(self):
        MyDaemon.forever_called = True

    def run_once(self):
        MyDaemon.once_called = True

    def run_raise(self):
        raise OSError

    def run_quit(self):
        raise KeyboardInterrupt


class TestDaemon(unittest.TestCase):

    def test_create(self):
        d = daemon.Daemon({})
        self.assertEqual(d.conf, {})
        self.assertTrue(isinstance(d.logger, utils.LogAdapter))

    def test_stubs(self):
        d = daemon.Daemon({})
        self.assertRaises(NotImplementedError, d.run_once)
        self.assertRaises(NotImplementedError, d.run_forever)


class TestRunDaemon(unittest.TestCase):

    def setUp(self):
        utils.HASH_PATH_SUFFIX = 'endcap'
        utils.HASH_PATH_PREFIX = 'startcap'
        utils.drop_privileges = lambda *args: None
        utils.capture_stdio = lambda *args: None

    def tearDown(self):
        reload_module(utils)

    def test_run(self):
        d = MyDaemon({})
        self.assertFalse(MyDaemon.forever_called)
        self.assertFalse(MyDaemon.once_called)
        # test default
        d.run()
        self.assertEqual(d.forever_called, True)
        # test once
        d.run(once=True)
        self.assertEqual(d.once_called, True)

    def test_run_daemon(self):
        sample_conf = "[my-daemon]\nuser = %s\n" % getuser()
        with tmpfile(sample_conf) as conf_file:
            with patch.dict('os.environ', {'TZ': ''}):
                daemon.run_daemon(MyDaemon, conf_file)
                self.assertEqual(MyDaemon.forever_called, True)
                self.assertTrue(os.environ['TZ'] is not '')
            daemon.run_daemon(MyDaemon, conf_file, once=True)
            self.assertEqual(MyDaemon.once_called, True)

            # test raise in daemon code
            MyDaemon.run_once = MyDaemon.run_raise
            self.assertRaises(OSError, daemon.run_daemon, MyDaemon,
                              conf_file, once=True)

            # test user quit
            MyDaemon.run_forever = MyDaemon.run_quit
            sio = StringIO()
            logger = logging.getLogger('server')
            logger.addHandler(logging.StreamHandler(sio))
            logger = utils.get_logger(None, 'server', log_route='server')
            daemon.run_daemon(MyDaemon, conf_file, logger=logger)
            self.assertTrue('user quit' in sio.getvalue().lower())


if __name__ == '__main__':
    unittest.main()
