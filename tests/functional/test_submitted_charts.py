# -*- coding: utf-8 -*-
"""Check submitted charts

New Openshift or chart-verifier will trigger (automatically or manually) a recursive checking on
existing submitted charts under `charts/` directory with the specified Openshift and chart-verifier
version.

Besides, during workflow development, engineers would like to check if the changes will break checks
on existing submitted charts.
"""
import os
import tempfile
import json
import base64
import pathlib
import logging
import shutil
from dataclasses import dataclass
from string import Template

import git
import yaml
import pytest
from pytest_bdd import (
    given,
    scenario,
    then,
    when,
)

from functional.utils import get_name_and_version_from_report, github_api, get_run_id, get_run_result, get_all_charts

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@pytest.fixture
def secrets():
    @dataclass
    class Secret:
        test_repo: str
        fork_repo: str
        cluster_token: str
        bot_token: str
        bot_name: str
        pr_base_branch: str
        api_server: str
        vendor_type: str
        fork_branches: list

        submitted_charts: list = None
        owners_file_content: str = """\
chart:
  name: ${chart_name}
  shortDescription: Test chart for testing chart submission workflows.
publicPgpKey: null
users:
- githubUsername: ${bot_name}
vendor:
  label: ${vendor}
  name: ${vendor}
"""
        test_chart: str = 'tests/data/vault-0.13.0.tgz'
        test_report: str = 'tests/data/report.yaml'
        chart_name, chart_version = get_name_and_version_from_report(
            test_report)

    # test_repo = os.environ.get("TEST_REPO")
    # if not test_repo:
    #     raise Exception("TEST_REPO environment variable not defined")

    # fork_repo = os.environ.get("FORK_REPO")
    # if not fork_repo:
    #     raise Exception("FORK_REPO environment variable not defined")
    # bot_name = fork_repo.split("/")[0]

    # cluster_token = os.environ.get("CLUSTER_TOKEN")
    # if not cluster_token:
    #     raise Exception("CLUSTER_TOKEN environment variable not defined")

    # api_server = os.environ.get("API_SERVER")
    # if not api_server:
    #     raise Exception("API_SERVER environment variable not defined")

    # bot_token = os.environ.get("BOT_TOKEN")
    # if not bot_token:
    #     bot_name = "github-actions[bot]"
    #     bot_token = os.environ.get("GITHUB_TOKEN")
    #     if not bot_token:
    #         raise Exception("BOT_TOKEN environment variable not defined")

    vendor_type = os.environ.get("VENDOR_TYPE")
    if not vendor_type:
        logger.info(
            f"VENDOR_TYPE environment variable not defined, default to `partner`")
        vendor_type = 'partner'

    bot_name = 'abai-test-bot'
    test_repo = fork_repo = f'{bot_name}/charts'
    api_server, cluster_token = '', ''
    bot_token = os.environ.get("BOT_TOKEN")

    pr_base_branch = 'test-charts'
    fork_branches = []
    # test_repo = str(base64.b64decode(test_repo), encoding="utf-8")
    # fork_repo = str(base64.b64decode(fork_repo), encoding="utf-8")
    secrets = Secret(test_repo, fork_repo, cluster_token, bot_token, bot_name, pr_base_branch, api_server, vendor_type, fork_branches)

    yield secrets

    # Teardown step to cleanup branches
    logger.info(f"Delete '{test_repo}:{pr_base_branch}-gh-pages'")
    github_api(
        'delete', f'https://api.github.com/repos/{test_repo}/git/refs/heads/{pr_base_branch}-gh-pages', bot_token)
    for fork_branch in secrets.fork_branches:
        logger.info(f"Delete '{fork_repo}:{fork_branch}'")
        github_api(
            'delete', f'https://api.github.com/repos/{fork_repo}/git/refs/heads/{fork_branch}', bot_token)


@scenario('features/check_submitted_charts.feature', "A new Openshift or chart-verifier version is specified either by a cron job or manually")
def test_submitted_chart_with_():
    """A new Openshift or chart-verifier version is specified either by a cron job or manually."""


@given("there's a github workflow for testing existing charts")
def theres_github_workflow_for_testing_charts():
    """there's a github workflow for testing existing charts."""


@when("a new Openshift or chart-verifier version is specified")
def new_openshift_or_verifier_version_is_specified():
    """a new Openshift or chart-verifier version is specified."""
    # TODO: specify api-server and openshift cluster token


@when("the vendor type is specified, e.g. partner, and/or redhat")
def vendor_type_is_specified():
    """the vendor type is specified, e.g. partner, and/or redhat."""


@when("workflow for testing existing charts is triggered")
def workflow_is_triggered():
    """workflow for testing existing charts is triggered."""


@then("submission tests are run for existing charts")
def submission_tests_run_for_submitted_charts(secrets):
    """submission tests are run for existing charts."""

    pr_number_list = []

    repo = git.Repo(os.getcwd())
    if os.environ.get('WORKFLOW_DEVELOPMENT'):
        logger.info("Wokflow development enabled")
        repo.git.add(A=True)
        repo.git.commit('-m', 'Checkpoint')

    # Get SHA from 'dev-gh-pages' branch
    logger.info(
        f"Create '{secrets.test_repo}:{secrets.pr_base_branch}-gh-pages' from '{secrets.test_repo}:dev-gh-pages'")
    r = github_api(
        'get', f'https://api.github.com/repos/{secrets.test_repo}/git/ref/heads/dev-gh-pages', secrets.bot_token)
    j = json.loads(r.text)
    sha = j['object']['sha']

    # Create a new gh-pages branch for testing
    data = {'ref': f'refs/heads/{secrets.pr_base_branch}-gh-pages', 'sha': sha}
    r = github_api(
        'post', f'https://api.github.com/repos/{secrets.test_repo}/git/refs', secrets.bot_token, json=data)

    # Make PR's from a temporary directory
    old_cwd = os.getcwd()
    dr = tempfile.mkdtemp(prefix='tci-')
    logger.info(f'Worktree directory: {dr}')
    repo.git.worktree('add', '--detach', dr, f'HEAD')

    # Run submission flow test on the main branch charts
    os.chdir(dr)
    repo = git.Repo(dr)
    prod_branch = 'main'
    repo.git.fetch(
        f'https://github.com/{secrets.test_repo}.git', f'{prod_branch}:{prod_branch}', '-f')
    repo.git.checkout(prod_branch, 'charts')
    repo.git.restore('--staged', 'charts')
    secrets.submitted_charts = get_all_charts('charts', secrets.vendor_type)
    logger.info(
        f"Found charts for {secrets.vendor_type}: {secrets.submitted_charts}")

    visited_charts = set()
    for vendor_type, vendor_name, chart_name, chart_version in secrets.submitted_charts:
        chart_dir = f'charts/{vendor_type}/{vendor_name}/{chart_name}'
        visited_charts.add(chart_dir)
        fork_branch = f'{secrets.pr_base_branch}-{vendor_type}-{vendor_name}-{chart_name}-{chart_version}'
        secrets.fork_branches.append(fork_branch)
        # Modify the OWNERS file so the bot account can test chart submission flow
        values = {'bot_name': secrets.bot_name,
                  'vendor': vendor_name, 'chart_name': chart_name}
        content = Template(secrets.owners_file_content).substitute(values)
        with open(f'{chart_dir}/OWNERS', 'w') as fd:
            fd.write(content)

        # Push OWNERS file to the test_repo
        if chart_dir not in visited_charts:
            logger.info(
                f"Push OWNERS file to '{secrets.test_repo}:{secrets.pr_base_branch}'")
            repo.git.add(f'{chart_dir}/OWNERS')
            repo.git.commit(
                '-m', f"Add {vendor_type} {vendor_name} {chart_name} OWNERS file")
            repo.git.push(f'https://x-access-token:{secrets.bot_token}@github.com/{secrets.test_repo}',
                        f'HEAD:refs/heads/{secrets.pr_base_branch}', '-f')

        # Push chart files to fork_repo:fork_branch
        repo.git.add(f'{chart_dir}/{chart_version}')
        repo.git.commit(
            '-m', f"Add {vendor_type} {vendor_name} {chart_name} {chart_version} chart files")
        repo.git.push(f'https://x-access-token:{secrets.bot_token}@github.com/{secrets.fork_repo}',
                      f'HEAD:refs/heads/{fork_branch}', '-f')

        # Create PR from fork_repo:fork_branch to test_repo:pr_base_branch
        actions_bot_name = 'github-actions[bot]'
        if secrets.bot_name == actions_bot_name:
            head = fork_branch
        else:
            head = f'{secrets.bot_name}:{fork_branch}'
        data = {'head': head, 'base': secrets.pr_base_branch,
                'title': fork_branch}

        logger.info(
            f"Create PR with chart files from '{secrets.fork_repo}:{fork_branch}' to '{secrets.test_repo}:{secrets.pr_base_branch}'")
        r = github_api(
            'post', f'https://api.github.com/repos/{secrets.test_repo}/pulls', secrets.bot_token, json=data)
        j = json.loads(r.text)
        pr_number_list.append(
            (vendor_type, vendor_name, chart_name, chart_version, j['number']))

    os.chdir(old_cwd)
    r = github_api(
        'get', f'https://api.github.com/repos/{secrets.test_repo}/releases', secrets.bot_token)
    releases = json.loads(r.text)
    for vendor_type, vendor_name, chart_name, chart_version, pr_number in pr_number_list:
        # Check PRs are merged
        chart = f'{vendor_type} {vendor_name} {chart_name} {chart_version}'
        run_id = get_run_id(secrets, pr_number)
        conclusion = get_run_result(secrets, run_id)
        if conclusion == 'success':
            logger.info(f"Workflow run for {chart} was 'success'")
        else:
            logger.warning(
                f"Workflow for the submitted PR did not success, run id: {run_id}, chart: {chart}")
            continue

        r = github_api(
            'get', f'https://api.github.com/repos/{secrets.test_repo}/pulls/{pr_number}/merge', secrets.bot_token)
        if r.status_code == 204:
            logger.info(f"PR for {chart} merged sucessfully")
        else:
            logger.warning(
                f"Workflow for submitted PR success but PR not merged, chart: {chart}")
            continue

        # Check index.yaml is updated
        repo = git.Repo(os.getcwd())
        old_branch = repo.active_branch.name
        repo.git.fetch(f'https://github.com/{secrets.test_repo}.git',
                       '{0}:{0}'.format(f'{secrets.pr_base_branch}-gh-pages'), '-f')
        repo.git.checkout(f'{secrets.pr_base_branch}-gh-pages')
        with open('index.yaml', 'r') as fd:
            try:
                index = yaml.safe_load(fd)
            except yaml.YAMLError as err:
                logger.warning(f"error parsing index.yaml of {chart}: {err}")
                continue

        entry = vendor_name + '-' + chart_name
        if entry not in index['entries']:
            logger.warning(
                f"{chart} not added to index")
            continue

        version_list = [release['version']
                        for release in index['entries'][entry]]
        if chart_version not in version_list:
            logger.warning(
                f"{chart} not added to index")
            continue

        logger.info(
            f"Index updated correctly for {chart}, cleaning up local branch")
        repo.git.checkout(old_branch)
        repo.git.branch('-D', f'{secrets.pr_base_branch}-gh-pages')

        # Check release is published
        for release in releases:
            expected_tag = f'{vendor_name}-{chart_name}-{chart_version}'
            if release['tag_name'] == expected_tag:
                logger.info(f"Released '{expected_tag}' successfully")

                chart_tar = f'{chart_name}-{chart_version}.tgz'
                expected_chart_asset = f'{vendor_name}-{chart_tar}'
                logger.info(
                    f"Check '{expected_chart_asset}' is in release assets")
                release_id = release['id']
                r = github_api(
                    'get', f'https://api.github.com/repos/{secrets.test_repo}/releases/{release_id}/assets', secrets.bot_token)
                asset_list = json.loads(r.text)
                asset_names = [asset['name'] for asset in asset_list]

                logger.info(f"Delete release '{expected_tag}'")
                github_api(
                    'delete', f'https://api.github.com/repos/{secrets.test_repo}/releases/{release_id}', secrets.bot_token)

                logger.info(f"Delete release tag '{expected_tag}'")
                github_api(
                    'delete', f'https://api.github.com/repos/{secrets.test_repo}/git/refs/tags/{expected_tag}', secrets.bot_token)

                if expected_chart_asset not in asset_names:
                    logger.warning(
                        f"Missing release asset: {expected_chart_asset}")
                    break
        else:
            logger.warning(f"'{expected_tag}' not in the release list")


@then("all results are reported back to the caller")
def all_results_report_back_to_caller():
    """all results are reported back to the caller."""
