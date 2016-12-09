"""
    Register datasources for use with TDVT runner.

"""

import configparser
import glob
import os.path
import logging

from ..resources import *
from .test_config import TestConfig,TestSet,build_config_name,build_tds_name

def LoadTest(config):
    """ Parse a datasource test suite config into a TestConfig object.
    [Datasource]
    Name = bigquery
    LogicalQueryFormat = bool_
    CommandLineOverride =

    [StandardTests]
    LogicalExclusions_Calcs = 
    LogicalExclusions_Staples = Filter.Trademark
    ExpressionExclusions_Standard = string.char,dateparse

    [LODTests]
    LogicalExclusions_Staples = 
    ExpressionExclusions_Calcs = 

    [StaplesDataTest]

    [NewExpressionTest1]
    Name = expression_test_dates.
    TDS = cast_calcs.bigquery_sql_dates.tds
    Exclusions = string.ascii
    TestPath = exprtests/standard/ 
    
    """
    CALCS_TDS = 'cast_calcs.'
    STAPLES_TDS = 'Staples.'

    standard_tests = 'StandardTests'
    lod_tests = 'LODTests'
    staples_data_test = 'StaplesDataTest'
    new_expression_test = 'NewExpressionTest'
    new_logical_test = 'NewLogicalTest'
    datasource_section = 'Datasource'

    #Check the ini sections to make sure there is nothing that is unrecognized. This should be empty by the time we are done.
    all_ini_sections = config.sections()

    #This is required.
    dsconfig = config[datasource_section]
    all_ini_sections.remove(datasource_section)
    test_config = TestConfig(dsconfig['Name'], dsconfig['LogicalQueryFormat'], dsconfig.get('CommandLineOverride', ''))

    #Add the standard test suites.
    if standard_tests in config.sections():
        try:
            standard = config[standard_tests]
            all_ini_sections.remove(standard_tests)
            
            test_config.add_logical_test('logical.calcs.', CALCS_TDS, standard.get('LogicalExclusions_Calcs', ''), test_config.get_logical_test_path('logicaltests/setup/calcs/setup.*.'))
            test_config.add_logical_test('logical.staples.', STAPLES_TDS, standard.get('LogicalExclusions_Staples', ''), test_config.get_logical_test_path('logicaltests/setup/staples/setup.*.'))
            test_config.add_expression_test('expression_test.', CALCS_TDS, standard.get('ExpressionExclusions_Standard', ''), 'exprtests/standard/')
        except KeyError as e:
            logging.debug(e)
            pass

    #Add the optional LOD tests.
    if lod_tests in config.sections():
        try:
            lod = config[lod_tests]
            all_ini_sections.remove(lod_tests)
            test_config.add_logical_test('logical.lod.', STAPLES_TDS, lod.get('LogicalExclusions_Staples', ''), test_config.get_logical_test_path('logicaltests/setup/lod/setup.*.'))
            test_config.add_expression_test('expression.lod.', CALCS_TDS, lod.get('ExpressionExclusions_Calcs', ''), 'exprtests/lodcalcs/setup.*.txt')
        except KeyError as e:
            logging.debug(e)
            pass

    #Add the optional Staples data check test.
    if staples_data_test in config.sections():
        try:
            staples_data = config[staples_data_test]
            all_ini_sections.remove(staples_data_test)
            test_config.add_expression_test('expression.staples.', STAPLES_TDS, '', 'exprtests/staples/setup.*.txt')
        except KeyError as e:
            logging.debug(e)
            pass

    #Add any extra expression tests.
    for section in config.sections():
        if new_expression_test in section:
            try:
                sect = config[section]
                all_ini_sections.remove(section)
                test_config.add_expression_test(sect.get('Name',''), sect.get('TDS',''), sect.get('Exclusions',''), sect.get('TestPath',''))
            except KeyError as e:
                logging.debug(e)
                pass

    #Add any extra logical tests.
    for section in config.sections():
        if new_logical_test in section:
            try:
                sect = config[section]
                all_ini_sections.remove(section)
                test_config.add_logical_test(sect.get('Name',''), sect.get('TDS',''), sect.get('Exclusions',''), sect.get('TestPath',''))
            except KeyError as e:
                logging.debug(e)
                pass
    if all_ini_sections:
        logging.debug("Found unparsed sections in the ini file.")
        for section in all_ini_sections:
            logging.debug("Unparsed section: {0}".format(section))

    logging.debug(test_config)
    return test_config
        
class TestRegistry(object):
    """Add a new datasource here and then add it to the appropriate registries below."""
    def __init__(self, ini_file):
        self.dsnames = {}
        self.suite_map = {}

        #Read all the datasource ini files and load the test configuration.
        ini_files = get_all_ini_files_local_first('config')
        for f in ini_files:
            logging.debug("Reading ini file [{}]".format(f))
            config = configparser.ConfigParser()
            try:
                config.read(f)
            except configparser.ParsingError as e:
                logging.debug(e)
                continue

            self.add_test(LoadTest(config))

        self.load_registry(ini_file)

    def load_registry(self, ini_file):
        try:
            #Create the test suites (groups of datasources to test)
            config = configparser.ConfigParser()
            registry_ini_file = get_ini_path_local_first('config/registry', ini_file)
            logging.debug("Reading registry ini file [{}]".format(registry_ini_file))
            config.read(registry_ini_file)
            ds = config['DatasourceRegistry']

            suite_all = self.interpret_ds_list(ds.get('all', ''))
            if suite_all:
                self.suite_map['all'] = suite_all
            suite_standard = self.interpret_ds_list(ds.get('standard', ''))
            if suite_standard:
                self.suite_map['standard'] = suite_standard
            suite_slow = self.interpret_ds_list(ds.get('slow', ''))
            if suite_slow:
                self.suite_map['slow'] = suite_slow

        except KeyError:
            #Create a simple default.
            self.suite_map['all'] = self.dsnames

    def interpret_ds_list(self, ds_list):
        if ds_list == '*':
            return [x for x in self.dsnames]
        return [x.strip() for x in ds_list.split(',')]

    def add_test(self, test_config):
        self.dsnames[test_config.dsname] = test_config

    def get_datasource_info(self, dsname):
        if dsname in self.dsnames:
            return self.dsnames[dsname]
        return None

    def get_datasources(self, suite):
        ds_to_run = []
        if not suite:
            return
        for ds in suite.split(','):
            ds = ds.strip()
            if ds in self.suite_map:
                ds_to_run.extend(self.suite_map[ds])
            elif ds:
                ds_to_run.append(ds)
        
        return ds_to_run

class WindowsRegistry(TestRegistry):
    """Windows specific test suites."""
    def __init__(self):
        super(WindowsRegistry, self).__init__('windows')


class MacRegistry(TestRegistry):
    """Mac specific test suites."""
    def __init__(self):
        super(MacRegistry, self).__init__('mac')

