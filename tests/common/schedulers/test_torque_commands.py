# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file except in compliance
# with the License. A copy of the License is located at
#
# http://aws.amazon.com/apache2.0/
#
# or in the "LICENSE.txt" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES
# OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions and
# limitations under the License.
import pytest

from assertpy import assert_that
from common.schedulers.torque_commands import (
    TorqueHost,
    TorqueJob,
    TorqueResourceList,
    add_nodes,
    delete_nodes,
    get_compute_nodes_info,
    get_jobs_info,
    get_pending_jobs_info,
    wait_nodes_initialization,
)
from tests.common import read_text


@pytest.mark.parametrize(
    "qmgr_output, hosts, expected_succeeded_hosts",
    [
        ("", ["ip-10-0-0-157", "ip-10-0-0-155"], ["ip-10-0-0-157", "ip-10-0-0-155"]),
        (
            "qmgr obj=ip-10-0-0-157 svr=default: Node name already exists",
            ["ip-10-0-0-157", "ip-10-0-0-155"],
            ["ip-10-0-0-157", "ip-10-0-0-155"],
        ),
        ("qmgr obj=ip-10-0-0-157 svr=default: Error", ["ip-10-0-0-157", "ip-10-0-0-155"], ["ip-10-0-0-155"]),
        ("unexpected error message", ["ip-10-0-0-157", "ip-10-0-0-155"], []),
        ("", [], []),
    ],
    ids=["all_successful", "already_existing", "failed_one_node", "unexpected_err_message", "no_nodes"],
)
def test_add_nodes(qmgr_output, hosts, expected_succeeded_hosts, mocker):
    mock = mocker.patch(
        "common.schedulers.torque_commands.check_command_output", return_value=qmgr_output, autospec=True
    )
    succeeded_hosts = add_nodes(hosts, slots=4)

    if hosts:
        mock.assert_called_with(
            '/opt/torque/bin/qmgr -c "create node {0} np=4"'.format(",".join(hosts)), log_error=False
        )
    if expected_succeeded_hosts:
        assert_that(succeeded_hosts).contains_only(*expected_succeeded_hosts)
    else:
        assert_that(succeeded_hosts).is_empty()


@pytest.mark.parametrize(
    "qmgr_output, hosts, expected_succeeded_hosts",
    [
        ("", ["ip-10-0-0-157", "ip-10-0-0-155"], ["ip-10-0-0-157", "ip-10-0-0-155"]),
        (
            "qmgr obj=ip-10-0-0-157 svr=default: Unknown node",
            ["ip-10-0-0-157", "ip-10-0-0-155"],
            ["ip-10-0-0-157", "ip-10-0-0-155"],
        ),
        ("qmgr obj=ip-10-0-0-157 svr=default: Error", ["ip-10-0-0-157", "ip-10-0-0-155"], ["ip-10-0-0-155"]),
        ("unexpected error message", ["ip-10-0-0-157", "ip-10-0-0-155"], []),
        ("", [], []),
    ],
    ids=["all_successful", "already_existing", "failed_one_node", "unexpected_err_message", "no_nodes"],
)
def test_delete_nodes(qmgr_output, hosts, expected_succeeded_hosts, mocker):
    mock = mocker.patch(
        "common.schedulers.torque_commands.check_command_output", return_value=qmgr_output, autospec=True
    )
    succeeded_hosts = delete_nodes(hosts)

    if hosts:
        mock.assert_called_with('/opt/torque/bin/qmgr -c "delete node {0} "'.format(",".join(hosts)), log_error=False)
    if expected_succeeded_hosts:
        assert_that(succeeded_hosts).contains_only(*expected_succeeded_hosts)
    else:
        assert_that(succeeded_hosts).is_empty()


def test_wait_nodes_initialization(mocker, test_datadir):
    pbsnodes_output = read_text(test_datadir / "pbsnodes_output.xml")
    mock = mocker.patch(
        "common.schedulers.torque_commands.check_command_output", return_value=pbsnodes_output, autospec=True
    )

    hosts = ["ip-10-0-1-242", "ip-10-0-0-196"]
    result = wait_nodes_initialization(hosts)

    mock.assert_called_with("/opt/torque/bin/pbsnodes -x {0}".format(" ".join(hosts)), raise_on_error=False)
    assert_that(result).is_true()


@pytest.mark.parametrize(
    "pbsnodes_mocked_response, expected_output",
    [
        (
            "pbsnodes_output.xml",
            {
                "ip-10-0-0-196": TorqueHost(name="ip-10-0-0-196", slots=1000, state=["down", "offline"], jobs=None),
                "ip-10-0-1-242": TorqueHost(name="ip-10-0-1-242", slots=4, state=["free"], jobs=None),
                "ip-10-0-1-237": TorqueHost(
                    name="ip-10-0-1-237",
                    slots=4,
                    state=["job-exclusive"],
                    jobs="1/136.ip-10-0-0-196.eu-west-1.compute.internal,2/137.ip-10-0-0-196.eu-west-1.compute.internal,"
                    "0,3/138.ip-10-0-0-196.eu-west-1.compute.internal",
                ),
            },
        ),
        ("pbsnodes_empty.xml", {}),
        ("pbsnodes_error.xml", {}),
    ],
    ids=["mixed_output", "empty_output", "errored_output"],
)
def test_get_compute_nodes_info(pbsnodes_mocked_response, expected_output, mocker, test_datadir):
    pbsnodes_output = read_text(test_datadir / pbsnodes_mocked_response)
    mock = mocker.patch(
        "common.schedulers.torque_commands.check_command_output", return_value=pbsnodes_output, autospec=True
    )

    nodes = get_compute_nodes_info(hostname_filter=["host1"])

    mock.assert_called_with("/opt/torque/bin/pbsnodes -x host1", raise_on_error=False)
    assert_that(nodes).is_equal_to(expected_output)


@pytest.mark.parametrize(
    "qstat_mocked_response, expected_output",
    [
        (
            "qstat_output.xml",
            [
                TorqueJob(
                    id="149.ip-10-0-0-196.eu-west-1.compute.internal",
                    state="R",
                    resources_list=TorqueResourceList(nodes_resources=[(1, 2)], nodes_count=1, ncpus=None),
                ),
                TorqueJob(
                    id="150.ip-10-0-0-196.eu-west-1.compute.internal",
                    state="R",
                    resources_list=TorqueResourceList(nodes_resources=[(2, 1)], nodes_count=2, ncpus=None),
                ),
                TorqueJob(
                    id="151.ip-10-0-0-196.eu-west-1.compute.internal",
                    state="R",
                    resources_list=TorqueResourceList(nodes_resources=None, nodes_count=None, ncpus=2),
                ),
                TorqueJob(
                    id="152.ip-10-0-0-196.eu-west-1.compute.internal",
                    state="Q",
                    resources_list=TorqueResourceList(nodes_resources=[(1, 2), (2, 3)], nodes_count=3, ncpus=None),
                ),
                TorqueJob(
                    id="166[1].ip-10-0-0-196.eu-west-1.compute.internal",
                    state="Q",
                    resources_list=TorqueResourceList(nodes_resources=[(1, 4), (8, 1)], nodes_count=9, ncpus=None),
                ),
                TorqueJob(
                    id="166[2].ip-10-0-0-196.eu-west-1.compute.internal",
                    state="Q",
                    resources_list=TorqueResourceList(nodes_resources=[(1, 4), (8, 1)], nodes_count=9, ncpus=None),
                ),
                TorqueJob(
                    id="166[3].ip-10-0-0-196.eu-west-1.compute.internal",
                    state="Q",
                    resources_list=TorqueResourceList(nodes_resources=[(1, 4), (8, 1)], nodes_count=9, ncpus=None),
                ),
            ],
        ),
        ("qstat_empty_xml.xml", []),
        ("qstat_empty.xml", []),
    ],
    ids=["mixed_output", "emptyxml", "empty_output"],
)
def test_get_jobs_info(qstat_mocked_response, expected_output, mocker, test_datadir):
    qstat_output = read_text(test_datadir / qstat_mocked_response)
    mock = mocker.patch(
        "common.schedulers.torque_commands.check_command_output", return_value=qstat_output, autospec=True
    )

    jobs = get_jobs_info()

    mock.assert_called_with("/opt/torque/bin/qstat -t -x")
    assert_that(jobs).is_equal_to(expected_output)


@pytest.mark.parametrize(
    "pending_jobs, max_slots, expected_filtered_jobs",
    [
        (
            [
                TorqueJob(
                    id="149.ip-10-0-0-196.eu-west-1.compute.internal",
                    state="Q",
                    resources_list=TorqueResourceList(nodes_resources=[(1, 2)], nodes_count=1, ncpus=None),
                )
            ],
            None,
            [
                TorqueJob(
                    id="149.ip-10-0-0-196.eu-west-1.compute.internal",
                    state="Q",
                    resources_list=TorqueResourceList(nodes_resources=[(1, 2)], nodes_count=1, ncpus=None),
                )
            ],
        ),
        (
            [
                TorqueJob(
                    id="149.ip-10-0-0-196.eu-west-1.compute.internal",
                    state="R",
                    resources_list=TorqueResourceList(nodes_resources=[(1, 2)], nodes_count=1, ncpus=None),
                )
            ],
            None,
            [],
        ),
        (
            [
                TorqueJob(
                    id="149.ip-10-0-0-196.eu-west-1.compute.internal",
                    state="Q",
                    resources_list=TorqueResourceList(nodes_resources=[(1, 2), (1, 5)], nodes_count=2, ncpus=None),
                )
            ],
            4,
            [],
        ),
        (
            [
                TorqueJob(
                    id="149.ip-10-0-0-196.eu-west-1.compute.internal",
                    state="Q",
                    resources_list=TorqueResourceList(nodes_resources=[(1, 2), (1, 5)], nodes_count=2, ncpus=None),
                )
            ],
            5,
            [
                TorqueJob(
                    id="149.ip-10-0-0-196.eu-west-1.compute.internal",
                    state="Q",
                    resources_list=TorqueResourceList(nodes_resources=[(1, 2), (1, 5)], nodes_count=2, ncpus=None),
                )
            ],
        ),
        (
            [
                TorqueJob(
                    id="149.ip-10-0-0-196.eu-west-1.compute.internal",
                    state="Q",
                    resources_list=TorqueResourceList(nodes_resources=[(1, 2), (1, 5)], nodes_count=2, ncpus=None),
                ),
                TorqueJob(
                    id="150.ip-10-0-0-196.eu-west-1.compute.internal",
                    state="Q",
                    resources_list=TorqueResourceList(nodes_resources=None, nodes_count=None, ncpus=4),
                ),
                TorqueJob(
                    id="151.ip-10-0-0-196.eu-west-1.compute.internal",
                    state="Q",
                    resources_list=TorqueResourceList(nodes_resources=[(1, 2), (1, 6)], nodes_count=2, ncpus=None),
                ),
                TorqueJob(
                    id="14.ip-10-0-0-196.eu-west-1.compute.internal",
                    state="R",
                    resources_list=TorqueResourceList(nodes_resources=[(1, 2), (1, 5)], nodes_count=2, ncpus=None),
                ),
            ],
            5,
            [
                TorqueJob(
                    id="149.ip-10-0-0-196.eu-west-1.compute.internal",
                    state="Q",
                    resources_list=TorqueResourceList(nodes_resources=[(1, 2), (1, 5)], nodes_count=2, ncpus=None),
                ),
                TorqueJob(
                    id="150.ip-10-0-0-196.eu-west-1.compute.internal",
                    state="Q",
                    resources_list=TorqueResourceList(nodes_resources=None, nodes_count=None, ncpus=4),
                ),
            ],
        ),
        ([], 5, []),
    ],
    ids=["no_filter", "skip_state", "max_slots", "max_slots_no_filter", "mix", "empty"],
)
def test_get_pending_jobs_info(pending_jobs, max_slots, expected_filtered_jobs, mocker):
    mock = mocker.patch("common.schedulers.torque_commands.get_jobs_info", return_value=pending_jobs, autospec=True)

    assert_that(get_pending_jobs_info(max_slots)).is_equal_to(expected_filtered_jobs)
    mock.assert_called_with()