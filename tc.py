#!/usr/bin/env python
# -*- coding: utf-8 -*-
# PYTHON_ARGCOMPLETE_OK
"""
tc.py <command> [<args>]

Where command is the type of build you with to invoke:
    linux        Neo4j Linux
    har          HA Robustness
"""

from __future__ import print_function
import requests as r
from argparse import ArgumentParser
import sys

try:
    import urlparse
except ImportError:
    # Renamed in Python3
    from urllib import parse as urlparse


# Some constants #

# Want to request json from the server
_headers = {'Accept': 'application/json',
            'Content-Type': 'application/xml'}

_requestbase = """
<build personal="{personal}" branchName="{branch}">
  <buildType id="{buildid}"/>
  <comment><text>Triggered from CLI</text></comment>
  <properties>
    <property name="remote" value="{remote}"/>
    <property name="branch" value="{branch}"/>{props}
  </properties>
</build>
"""

_requestpropertybase = '\n    <property name="{name}" value="{value}"/>'

_neo4jlinux_id = "JonasHaRequests_Neo4jCustom"
_har_id = "JonasHaRequests_HarBranchArtifacts"

_linux_jdks = ['openjdk-8', 'openjdk-7',
               'oracle-jdk-8', 'oracle-jdk-7',
               'ibmjdk-8', 'ibmjdk-7']

# End constants #


# Top level parsers

# All builds share teamcity information
_parser = ArgumentParser(add_help=False)
_required = _parser.add_argument_group('mandatory arguments')
_required.add_argument('-u', '--user', metavar='USERNAME',
                       help='TeamCity username', required=True)
_required.add_argument('-p', '--password',
                       help='TeamCity password', required=True)
_parser.add_argument('-r', '--remote', metavar='URL',
                         help='Public remote repo where branch exists',
                         default='origin')
_parser.add_argument('--teamcity', metavar='URL',
                         help='Url to TeamCity',
                         default='https://build.neohq.net')
_personal_parser = _parser.add_mutually_exclusive_group(required=False)
_personal_parser.add_argument('--personal', dest='personal',
                              action='store_true',
                              help='Start as personal build')
_personal_parser.add_argument('--no-personal', dest='personal',
                              action='store_false',
                              help='Do not start as personal build')
_parser.set_defaults(personal=False)

# All Neo4j builds share some obvious arguments
_neo4jparserbase = ArgumentParser(add_help=False)
_neo4jparserbase.add_argument('--maven-goals', metavar='GOALS',
                              help='Maven goal(s) to invoke',
                              default='clean verify')
_neo4jparserbase.add_argument('--maven-args', metavar='ARGS',
                              help='Additional Maven arguments',
                              default='-DrunITs -DskipBrowser')
_neo4jrequired = _neo4jparserbase.add_argument_group('mandatory arguments')
_neo4jrequired.add_argument('-b', '--branch',
                            help='Branch of Neo4j to checkout. Supports special "pr/1234" syntax', required=True)

# End top level parsers

def dict_as_properties(props):
    """
    Format a dictionary as xml property tags:

        <property name=NAME value=VALUE />

    """
    xml = ""
    for k, v in props.items():
        xml += _requestpropertybase.format(name=k, value=v)
    return xml


def request_xml(buildid, personal, branch, remote, props=None):
    """
    Format an XML build request
    """
    if props is None:
        props=""

    return _requestbase.format(buildid=buildid,
                               remote=remote,
                               branch=branch,
                               props=props,
                               personal=str(personal).lower())


def send_request(user, password, url, data):
    """
    Start a build, defined in data
    """
    resp = r.post(urlparse.urljoin(url, "httpAuth/app/rest/buildQueue"),
                  auth=(user, password),
                  headers=_headers,
                  data=data)

    if resp.ok:
        print("Build started. View status at")
        print(resp.json().get('webUrl'))
    else:
        print("Could not start build:")
        print(resp.status_code)
        try:
            print(resp.json())
        except:
            print(resp.text)
        exit(1)


def tc_mvn_args(original):
    """
    Add some useful maven arguments in TC
    """
    return "-DfailIfNoTests=false -Dmaven.test.failure.ignore=true --show-version " + original


def start_linux(user, password, url, personal, branch, remote, mvngoals, mvnargs, jdk):
    """
    Start a custom linux build
    """
    props = dict_as_properties({'project-default-jdk': "%{}%".format(jdk),
                                'maven-goals': mvngoals,
                                'maven-args': mvnargs})
    data = request_xml(_neo4jlinux_id, personal, branch, remote, props)
    send_request(user, password, url, data)

def start_ha(user, password, url, personal, branch, remote):
    """
    Start a custom ha robustness build
    """
    data = request_xml(_har_id, personal, branch, remote)
    send_request(user, password, url, data)


class TC(object):

    def __init__(self, cliargs):
        parser = ArgumentParser(
            description='Script for triggering builds on TeamCity',
            usage=__doc__)

        parser.add_argument('command', help='Type of build to invoke')

        # Only care about the first argument
        args = parser.parse_args(cliargs[:1])

        # If no method with that name exists on this object
        if not hasattr(self, args.command):
            print('Unrecognized command:', args.command)
            parser.print_help()
            exit(1)

        # Invoke the sub command method with rest of the args
        getattr(self, args.command)(cliargs[1:])

    def linux(self, subargs):
        parser = ArgumentParser(description="Neo4j Linux",
                                parents=[_parser, _neo4jparserbase])
        parser.add_argument('--jdk', help='JDK to build with',
                            default=_linux_jdks[0], choices=_linux_jdks)

        args = parser.parse_args(subargs)

        start_linux(args.user, args.password, args.teamcity, args.personal,
                    args.branch, args.remote,
                    args.maven_goals,
                    tc_mvn_args(args.maven_args),
                    args.jdk)

    def har(self, subargs):
        # Add to top group to keep a single group
        _required.add_argument('-b', '--branch', required=True,
                               help='Branch of Neo4j to checkout. Supports special "pr/1234" syntax')
        parser = ArgumentParser(description="HA Robustness",
                                parents=[_parser])

        args = parser.parse_args(subargs)

        start_ha(args.user, args.password, args.teamcity, args.personal,
                 args.branch, args.remote)


if __name__ == "__main__":
    TC(sys.argv[1:])
