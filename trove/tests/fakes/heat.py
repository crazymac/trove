#    Copyright 2014 Mirantis Inc.
#    All Rights Reserved.
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
import yaml
from trove.common import utils
from heatclient import exc
CLIENT_DATA = {}


class Stack(object):
    def __init__(self, name, template, parameters):
        self.id = utils.generate_uuid()
        self.name = name + '-' + self.id
        self.template = template
        self.parameters = parameters
        self.created_at = utils.utcnow()
        self.updated = utils.utcnow()
        self.stack_status = "CREATE_COMPLETE"
        self.resources = self._build_resources(template)
        self.action = "CREATE"

    def output(self):
        return {
            'stack': {
                'id': self.id
            }
        }

    def _build_resources(self, template):
        result = []
        yamled = yaml.load(template)
        resources = yamled.get("Resources")
        for resource, description in resources:
            result.append(Resource(resource, description))
        return result


class Resource(object):

    def __init__(self, name, description):
        self.name = name
        self.description = description
        self.resource_status = 'CREATE_COMPLETE'
        self.physical_resource_id = utils.generate_uuid()


class Resources(object):

    def get(self, stack_id, resource_name):
        stack = Stacks().get(stack_id)
        resources = stack.resouces
        return resources.get(resource_name)


class Stacks(object):
    _stacks = {}

    def create(self, stack_name=None, template=None,
               parameters=None, disable_rollback=False):
        if parameters["AvailabilityZone"] != "nova":
            raise exc.HTTPException
        stack = Stack(stack_name, template, parameters)
        self._stacks.update({stack.id: stack,
                            stack.name: stack})
        return stack.output()

    def get(self, stack_id_or_name):
        return self._stacks.get(stack_id_or_name)

    def delete(self, stack_id_or_name):
        del self._stacks[stack_id_or_name]

    def update(self):
        pass


class FakeClient(object):

    def __init__(self, context):
        self.context = context
        self.stacks = Stacks()
        self.resources = Resources()


def get_client_data(context):
    if context not in CLIENT_DATA:
        CLIENT_DATA.update(
            {context: {'heat': FakeClient(context)}})
    return CLIENT_DATA[context]


def fake_create_heat_client(context):
    return get_client_data(context)['heat']
