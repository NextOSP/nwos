# -*- encoding: utf-8 -*-
# Part of NextOSP. See LICENSE file for full copyright and licensing details.

import logging
import operator
import re
import secrets
from io import BytesIO
from unittest.mock import patch

import requests

import nwos
from nwos.modules.registry import Registry
from nwos.tests.common import BaseCase, HttpCase, tagged
from nwos.tools import config
from nwos.addons.web.controllers.database import (
    DATABASE_CREATION_PROGRESS,
    Database,
    ONBOARDING_MODULES,
    ONBOARDING_OPTIONAL_MODULES,
    ONBOARDING_SOP_FIELDS,
    ONBOARDING_SOP_SECTIONS,
    _get_database_localization_data,
    _update_database_creation_progress,
)


class TestDatabaseManager(HttpCase):
    def test_database_manager(self):
        if not config['list_db']:
            return
        res = self.url_open('/web/database/manager')
        self.assertEqual(res.status_code, 200)

        # check that basic existing db actions are present
        self.assertIn('.o_database_backup', res.text)
        self.assertIn('.o_database_duplicate', res.text)
        self.assertIn('.o_database_delete', res.text)

        # check that basic db actions are present
        self.assertIn('o_database_create_start', res.text)
        self.assertIn('.o_database_restore', res.text)
        self.assertEqual(res.text.count('data-step-indicator='), 5)
        self.assertEqual(res.text.count('class="o_onboarding_step'), 5)
        self.assertEqual(res.text.count('data-sop-app='), len(ONBOARDING_MODULES))
        self.assertIn('Step 5 of 5', res.text)
        self.assertIn('Tailor your workflows', res.text)
        self.assertIn('Suggested SOP', res.text)
        self.assertIn('name="currency_code"', res.text)
        self.assertIn('Fiscal localization / tax template', res.text)
        self.assertIn('Detailed activity', res.text)
        self.assertIn('o_creation_elapsed', res.text)


class TestDatabaseOnboardingConfiguration(BaseCase):
    def setUp(self):
        self.controller = Database()

    def test_boolean_coercion_and_module_selection(self):
        for value in ('1', 'true', 'TRUE', 'on', 'yes'):
            self.assertTrue(self.controller._post_is_true({'field': value}, 'field'))
        for value in (None, '', '0', 'false', 'off', 'no', 'unexpected'):
            self.assertFalse(self.controller._post_is_true({'field': value}, 'field'))

        self.assertEqual(
            self.controller._get_onboarding_modules({
                'install_inventory': '1',
                'sop_inventory_barcode': '1',  # Not available in this edition.
                'sop_purchase_agreements': '1',  # Parent app was not selected.
            }),
            ['stock'],
        )
        self.assertEqual(
            self.controller._get_onboarding_modules({
                'install_purchase': '1',
                'sop_purchase_agreements': '1',
                'install_employees': 'true',
                'sop_hr_attendance': 'on',
                'sop_hr_skills': 'yes',
            }),
            ['purchase', 'hr', 'purchase_requisition', 'hr_attendance', 'hr_skills'],
        )
        self.assertEqual(
            self.controller._get_onboarding_modules({
                'install_stock_requests': '1',
            }),
            ['nwos_stock_request'],
        )

    def test_sop_catalog_is_whitelisted(self):
        self.assertEqual(len(ONBOARDING_SOP_SECTIONS), len(ONBOARDING_MODULES))
        self.assertEqual(
            {section['option'] for section in ONBOARDING_SOP_SECTIONS},
            set(ONBOARDING_MODULES),
        )
        self.assertEqual(len(ONBOARDING_SOP_FIELDS), len(set(ONBOARDING_SOP_FIELDS)))
        self.assertTrue(set(ONBOARDING_OPTIONAL_MODULES).issubset(ONBOARDING_SOP_FIELDS))

        currencies, country_currencies = _get_database_localization_data()
        self.assertIn('VND', {currency['code'] for currency in currencies})
        self.assertEqual(country_currencies['vn'], 'VND')

    def test_sop_validation_is_scoped_and_strict(self):
        # Stale answers for an unselected app are ignored.
        self.controller._validate_onboarding_sop({
            'sop_profile_submitted': '1',
            'sop_sales_acceptance': 'not-valid',
            'sop_hr_expiry_notice_days': '1.5',
        })

        with self.assertRaises(ValueError):
            self.controller._validate_onboarding_sop({
                'sop_profile_submitted': '1',
                'install_sales': '1',
                'sop_sales_acceptance': 'not-valid',
            })
        with self.assertRaises(ValueError):
            self.controller._validate_onboarding_sop({
                'sop_profile_submitted': '1',
                'install_employees': '1',
                'sop_hr_expiry_notice_days': '1.5',
            })
        with self.assertRaises(ValueError):
            self.controller._validate_onboarding_sop({
                'sop_profile_submitted': '1',
                'install_purchase': '1',
                'sop_purchase_approval': '1',
                'sop_purchase_approval_amount': 'nan',
            })
        with self.assertRaises(ValueError):
            self.controller._validate_onboarding_sop({
                'sop_profile_submitted': '1',
                'currency_code': 'NOT-A-CURRENCY',
            })
        with self.assertRaises(ValueError):
            self.controller._validate_onboarding_sop({
                'sop_profile_submitted': '1',
                'install_stock_requests': '1',
                'sop_stock_request_approval_amount': 'infinite',
            })
        # A hidden dependent value is ignored while its controlling answer is off.
        self.controller._validate_onboarding_sop({
            'sop_profile_submitted': '1',
            'install_purchase': '1',
            'sop_purchase_approval_amount': 'nan',
        })

    def test_detailed_creation_progress_events(self):
        token = 'test-detailed-creation-progress'
        self.addCleanup(DATABASE_CREATION_PROGRESS.pop, token, None)
        _update_database_creation_progress(
            token, 'validating', 3,
            'Setup request received',
            'Checking workspace inputs.',
        )
        _update_database_creation_progress(
            token, 'database', 16,
            'Creating the database',
            'Initializing core records.',
            'success',
        )
        payload = DATABASE_CREATION_PROGRESS[token]
        self.assertEqual(payload['stage'], 'database')
        self.assertEqual(payload['percent'], 16)
        self.assertEqual(len(payload['logs']), 2)
        self.assertEqual(payload['logs'][0]['id'], 1)
        self.assertEqual(payload['logs'][1]['level'], 'success')
        self.assertIn('started_at', payload)


@tagged('-at_install', 'post_install', '-standard', 'database_operations')
class TestDatabaseOperations(BaseCase):
    def setUp(self):
        self.password = secrets.token_hex()

        # monkey-patch password verification
        self.verify_admin_password_patcher = patch(
            'nwos.tools.config.verify_admin_password', self.password.__eq__,
        )
        self.startPatcher(self.verify_admin_password_patcher)

        self.assertEqual(len(config['db_name']), 1)
        self.db_name = config['db_name'][0]

        # monkey-patch db-filter
        self.addCleanup(operator.setitem, config, 'dbfilter', config['dbfilter'])
        config['dbfilter'] = self.db_name + '.*'

        self.base_databases = self.list_dbs_filtered()
        self.session = requests.Session()
        self.session.get(self.url('/web/database/manager'))

    def tearDown(self):
        self.assertEqual(
            self.list_dbs_filtered(),
            self.base_databases,
            'No database should have been created or removed at the end of this test',
        )

    def list_dbs_filtered(self):
        return set(db for db in nwos.service.db.list_dbs(True) if re.match(config['dbfilter'], db))

    def url(self, path):
        return HttpCase.base_url() + path

    def assertDbs(self, dbs):
        self.assertEqual(self.list_dbs_filtered() - self.base_databases, set(dbs))

    def url_open_drop(self, dbname):
        res = self.session.post(self.url('/web/database/drop'), data={
            'master_pwd': self.password,
            'name': dbname,
        }, allow_redirects=False)
        res.raise_for_status()
        return res

    def test_database_creation(self):
        # check verify_admin_password patch
        self.assertTrue(nwos.tools.config.verify_admin_password(self.password))

        # create a database
        test_db_name = self.db_name + '-test-database-creation'
        self.assertNotIn(test_db_name, self.list_dbs_filtered())
        res = self.session.post(self.url('/web/database/create'), data={
            'master_pwd': self.password,
            'name': test_db_name,
            'login': 'admin',
            'password': 'admin',
            'lang': 'en_US',
            'phone': '',
        }, allow_redirects=False)
        self.assertEqual(res.status_code, 303)
        self.assertIn('/nwos', res.headers['Location'])
        self.assertDbs([test_db_name])

        # delete the created database
        res = self.url_open_drop(test_db_name)
        self.assertEqual(res.status_code, 303)
        self.assertIn('/web/database/manager', res.headers['Location'])
        self.assertDbs([])

    def test_database_duplicate(self):
        # duplicate this database
        test_db_name = self.db_name + '-test-database-duplicate'
        self.assertNotIn(test_db_name, self.list_dbs_filtered())
        res = self.session.post(self.url('/web/database/duplicate'), data={
            'master_pwd': self.password,
            'name': self.db_name,
            'new_name': test_db_name,
        }, allow_redirects=False)
        self.assertEqual(res.status_code, 303)
        self.assertIn('/web/database/manager', res.headers['Location'])
        self.assertDbs([test_db_name])

        # delete the created database
        res = self.url_open_drop(test_db_name)
        self.assertIn('/web/database/manager', res.headers['Location'])
        self.assertDbs([])

    def test_database_restore(self):
        test_db_name = self.db_name + '-test-database-restore'
        self.assertNotIn(test_db_name, self.list_dbs_filtered())

        # backup the current database inside a temporary zip file
        res = self.session.post(
            self.url('/web/database/backup'),
            data={
                'master_pwd': self.password,
                'name': self.db_name,
            },
            allow_redirects=False,
            stream=True,
        )
        res.raise_for_status()
        datetime_pattern = r'\d\d\d\d-\d\d-\d\d_\d\d-\d\d-\d\d'
        self.assertRegex(
            res.headers.get('Content-Disposition'),
            fr"attachment; filename\*=UTF-8''{self.db_name}_{datetime_pattern}\.zip"
        )
        backup_file = BytesIO()
        backup_file.write(res.content)
        self.assertGreater(backup_file.tell(), 0, "The backup seems corrupted")

        # upload the backup under a new name (create a duplicate)
        with self.subTest(DEFAULT_MAX_CONTENT_LENGTH=None), \
             patch.object(nwos.http, 'DEFAULT_MAX_CONTENT_LENGTH', None):
            backup_file.seek(0)
            self.session.post(
                self.url('/web/database/restore'),
                data={
                    'master_pwd': self.password,
                    'name': test_db_name,
                    'copy': True,
                },
                files={
                    'backup_file': backup_file,
                },
                allow_redirects=False
            ).raise_for_status()
            self.assertDbs([test_db_name])
            self.url_open_drop(test_db_name)

        # upload the backup again, this time simulating that the file is
        # too large under the default size limit, the default size limit
        # shouldn't apply to /web/database URLs
        with self.subTest(DEFAULT_MAX_CONTENT_LENGTH=1024), \
             patch.object(nwos.http, 'DEFAULT_MAX_CONTENT_LENGTH', 1024):
            backup_file.seek(0)
            self.session.post(
                self.url('/web/database/restore'),
                data={
                    'master_pwd': self.password,
                    'name': test_db_name,
                    'copy': True,
                },
                files={
                    'backup_file': backup_file,
                },
                allow_redirects=False
            ).raise_for_status()
        self.assertDbs([test_db_name])
        self.url_open_drop(test_db_name)


    def test_database_http_registries(self):
        # This test is about dropping a connection inside one worker and
        # make sure that the other workers behave correctly.

        #
        # Setup
        #

        # duplicate this database
        test_db_name = self.db_name + '-test-database-duplicate'
        res = self.session.post(self.url('/web/database/duplicate'), data={
            'master_pwd': self.password,
            'name': self.db_name,
            'new_name': test_db_name,
        }, allow_redirects=False)

        # get a registry and a cursor on that new database
        registry = Registry(test_db_name)
        cr = registry.cursor()
        self.assertIn(test_db_name, Registry.registries)

        # delete the created database but keep the cursor
        with patch('nwos.sql_db.close_db') as close_db:
            res = self.url_open_drop(test_db_name)
        close_db.assert_called_once_with(test_db_name)

        # simulate that some customers were connected to that dropped db
        session_store = nwos.http.root.session_store
        session = session_store.new()
        session.update(nwos.http.get_default_session(), db=test_db_name)
        session.context['lang'] = nwos.http.DEFAULT_LANG
        self.session.cookies['session_id'] = session.sid

        # make it possible to inject the registry back
        patcher = patch.dict(Registry.registries, {test_db_name: registry})
        registries = patcher.start()
        self.addCleanup(patcher.stop)

        #
        # Tests
        #

        # The other worker doesn't have a registry in its LRU cache for
        # that session database.
        with self.subTest(msg="Registry.init() fails"):
            session_store.save(session)
            registries.pop('test_db_name', None)
            with self.assertLogs('nwos.sql_db', logging.INFO) as capture:
                res = self.session.get(self.url('/web/health'))
            self.assertEqual(res.status_code, 200)
            self.assertEqual(session_store.get(session.sid)['db'], None)
            self.assertEqual(capture.output, [
                "INFO:nwos.sql_db:Connection to the database failed",
            ])


        # The other worker has a registry in its LRU cache for that
        # session database. But it doesn't have a connection to the sql
        # database.
        with self.subTest(msg="Registry.cursor() fails"):
            session_store.save(session)
            registries[test_db_name] = registry
            with self.assertLogs('nwos.sql_db', logging.INFO) as capture, \
                 patch.object(Registry, '__new__', return_value=registry):
                res = self.session.get(self.url('/web/health'))
            self.assertEqual(res.status_code, 200)
            self.assertEqual(session_store.get(session.sid)['db'], None)
            self.assertEqual(capture.output, [
                "INFO:nwos.sql_db:Connection to the database failed",
            ])

        # The other worker has a registry in its LRU cache for that
        # session database. It also has a (now broken) connection to the
        # sql database.
        with self.subTest(msg="Registry.check_signaling() fails"):
            session_store.save(session)
            registries[test_db_name] = registry
            with self.assertLogs('nwos.sql_db', logging.ERROR) as capture, \
                 patch.object(Registry, '__new__', return_value=registry), \
                 patch.object(Registry, 'cursor', return_value=cr):
                res = self.session.get(self.url('/web/health'))
            self.assertEqual(res.status_code, 200)
            self.assertEqual(session_store.get(session.sid)['db'], None)
            self.maxDiff = None
            self.assertRegex(capture.output[0], (
                r"^ERROR:nwos\.sql_db:bad query:(?s:.*?)"
                r"ERROR: terminating connection due to administrator command\s+"
                r"server closed the connection unexpectedly\s+"
                r"This probably means the server terminated abnormally\s+"
                r"before or while processing the request\.$"
            ))
