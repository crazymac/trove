#Licensed under the Apache License, Version 2.0 (the "License");
#you may not use this file except in compliance with the License.
#You may obtain a copy of the License at
#
#http://www.apache.org/licenses/LICENSE-2.0
#
#Unless required by applicable law or agreed to in writing, software
#distributed under the License is distributed on an "AS IS" BASIS,
#WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#See the License for the specific language governing permissions and
#limitations under the License.


import testtools
import mock
import re
from tempfile import NamedTemporaryFile

from trove.common import template
from trove.common import utils
from trove.common import exception
from trove.tests.unittests.util import util


class TemplateTest(testtools.TestCase):
    def setUp(self):
        super(TemplateTest, self).setUp()
        util.init_db()
        self.env = template.ENV
        self.template = self.env.get_template("mysql/config.template")
        self.flavor_dict = {'ram': 1024}
        self.server_id = "180b5ed1-3e57-4459-b7a3-2aeee4ac012a"

    def tearDown(self):
        super(TemplateTest, self).tearDown()

    def validate_template(self, contents, teststr, test_flavor, server_id):
        # expected query_cache_size = {{ 8 * flavor_multiplier }}M
        flavor_multiplier = test_flavor['ram'] / 512
        found_group = None
        for line in contents.split('\n'):
            m = re.search('^%s.*' % teststr, line)
            if m:
                found_group = m.group(0)
        if not found_group:
            raise "Could not find text in template"
            # Check that the last group has been rendered
        memsize = found_group.split(" ")[2]
        self.assertEqual(memsize, "%sM" % (8 * flavor_multiplier))
        self.assertIsNotNone(server_id)
        self.assertTrue(server_id > 1)

    def test_rendering(self):
        rendered = self.template.render(flavor=self.flavor_dict,
                                        server_id=self.server_id)
        self.validate_template(rendered,
                               "query_cache_size",
                               self.flavor_dict,
                               self.server_id)

    def test_single_instance_config_rendering(self):
        config = template.SingleInstanceConfigTemplate('mysql',
                                                       self.flavor_dict,
                                                       self.server_id)
        self.validate_template(config.render(), "query_cache_size",
                               self.flavor_dict, self.server_id)


class EntityLoaderTest(testtools.TestCase):
    def setUp(self):
        super(EntityLoaderTest, self).setUp()
        self.uuid_id = utils.generate_uuid()

    def tearDown(self):
        super(EntityLoaderTest, self).tearDown()

    def test_heat_template_load_fail(self):
        self.assertRaises(exception.TroveError,
                          template.load_heat_template,
                          'mysql-blah')

    def test_heat_template_load_success(self):
        htmpl = template.load_heat_template('mysql')
        self.assertNotEqual(None, htmpl)

    def test_guest_info_load_fail(self):
        self.assertRaises(exception.TroveError,
                          template.load_guest_info,
                          'mysql-blah')

    def test_guest_info_load_success(self):
        self.assertNotEqual(None,
                            template.load_guest_info(
                                'mysql',
                                guest_id=str(self.uuid_id),
                                tenant_id=str(self.uuid_id)))

    def test_guest_info_render_fail(self):
        self.assertRaises(exception.TroveError,
                          template.load_guest_info, 'mysql')

    def test_guest_info_render_success(self):
        tmplt = template.load_guest_info('mysql',
                                         guest_id=str(self.uuid_id),
                                         tenant_id=str(self.uuid_id))
        guest_id = ''.join(tmplt.split('\n')[:1])
        tenant_id = ''.join(tmplt.split('\n')[1:2])
        self.assertEqual('guest_id = %s' % self.uuid_id, guest_id)
        self.assertEqual('tenant_id = %s' % self.uuid_id, tenant_id)

    def test_load_guest_conf(self):
        import jinja2
        template.os.path.isfile = mock.Mock(return_value=True)
        template.stream_to_template = mock.Mock(
            return_value=jinja2.Template('Hello {{ datastore_info }}'))
        tmplt = template.load_guest_conf('mysql',
                                         guest_id=str(self.uuid_id),
                                         tenant_id=str(self.uuid_id))
        self.assertNotEqual(None, tmplt)

    def test_load_guest_conf_with_check(self):
        guest_info = template.load_guest_info(
            'mysql', guest_id=str(self.uuid_id),
            tenant_id=str(self.uuid_id))

        template.os.path.isfile = mock.Mock(return_value=True)
        template.stream_to_template = mock.Mock(
            return_value=template.jinja2.Template("\n{{ datastore_info }}\n"))

        guest_conf = template.load_guest_conf(
            'mysql', guest_id=str(self.uuid_id),
            tenant_id=str(self.uuid_id))
        self.assertTrue(guest_info in guest_conf)
