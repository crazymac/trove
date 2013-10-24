#    Copyright 2012 OpenStack Foundation
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

import os
import jinja2

from trove.common import cfg
from trove.common.exception import HeatTemplateNotFound

CONF = cfg.CONF

ENV = jinja2.Environment(loader=jinja2.ChoiceLoader([
    jinja2.FileSystemLoader("/etc/trove/templates"),
    jinja2.PackageLoader("trove", "templates")
]))


class SingleInstanceConfigTemplate(object):
    """ This class selects a single configuration file by database type for
    rendering on the guest """

    def __init__(self, service_type, flavor_dict, instance_id):
        """ Constructor

        :param service_type: The database type.
        :type name: str.
        :param flavor_dict: dict containing flavor details for use in jinja.
        :type flavor_dict: dict.
        :param instance_id: trove instance id
        :type: instance_id: str

        """
        self.flavor_dict = flavor_dict
        template_filename = "%s.config.template" % service_type
        self.template = ENV.get_template(template_filename)
        self.instance_id = instance_id

    def render(self):
        """ Renders the jinja template

        :returns: str -- The rendered configuration file

        """
        server_id = self._calculate_unique_id()
        self.config_contents = self.template.render(
            flavor=self.flavor_dict, server_id=server_id)
        return self.config_contents

    def _calculate_unique_id(self):
        """
        Returns a positive unique id based off of the instance id

        :return: a positive integer
        """
        return abs(hash(self.instance_id) % (2 ** 31))


class HeatTemplate(object):
    """ implments a service based heat orchestration of images"""

    @classmethod
    def read_template(cls, path):
        if os.path.isfile(path):
            with open(path, "r") as raw_template:
                output = raw_template.read()
                return output

    @classmethod
    def get_template(cls, service_type):
        """fetch templates from the base directory"""
        heat_template_file_path = (CONF.heat_template_basedir +
                                   "%(service_type)s.heat.template" %
                                   {'service_type': service_type})
        output = cls.read_template(heat_template_file_path)
        if not output:
            raise HeatTemplateNotFound(template_path=heat_template_file_path)
        else:
            return output
