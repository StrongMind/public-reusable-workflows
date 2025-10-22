import hashlib
import os

import pulumi.runtime
import pytest

from tests.shared import assert_outputs_equal, assert_output_equals
from tests.mocks import get_pulumi_mocks


@pytest.fixture
def app_name(faker):
    return faker.word()


@pytest.fixture
def environment(faker):
    return faker.word()


@pytest.fixture
def stack(faker, app_name, environment):
    return f"{app_name}-{environment}"


@pytest.fixture
def master_db_password(faker):
    return faker.password(length=30)


@pytest.fixture
def pulumi_mocks(faker, master_db_password):
    return get_pulumi_mocks(faker, master_db_password)


@pytest.fixture
def namespace(app_name, stack):
    return f"{app_name}-{stack}"


@pytest.fixture
def component_kwargs(namespace):
    return {
        "namespace": namespace,
    }


@pytest.fixture
def sut(pulumi_set_mocks, component_kwargs):
    from strongmind_deployment.database import DatabaseComponent
    
    sut = DatabaseComponent("database", **component_kwargs)
    return sut


def describe_database_component():
    @pulumi.runtime.test
    def it_exists(sut):
        assert sut

    @pulumi.runtime.test
    def it_has_a_password(sut):
        assert sut.db_password

    @pulumi.runtime.test
    def it_has_an_md5_password_hashed_with_the_username_as_a_salt(sut):
        def check_password(args):
            pwd, hashed_pwd = args
            m = hashlib.md5()

            string_to_hash = f"{pwd}{sut.db_username}"
            m.update(string_to_hash.encode())
            assert hashed_pwd.startswith('md5')
            assert hashed_pwd == f"md5{m.hexdigest()}"

        return pulumi.Output.all(sut.db_password.result, sut.hashed_password).apply(check_password)

    @pulumi.runtime.test
    def it_has_a_password_with_30_chars(sut):
        def check_password(pwd):
            assert len(pwd) == 30

        return sut.db_password.result.apply(check_password)

    @pulumi.runtime.test
    def it_has_a_password_with_no_special_chars(sut):
        def check_special(special):
            assert special is False

        return sut.db_password.special.apply(check_special)

    @pulumi.runtime.test
    def it_creates_a_aurora_postgres_cluster(sut):
        def check_rds_cluster_engine(args):
            cluster_engine, engine_mode, engine_version = args
            assert cluster_engine == 'aurora-postgresql'
            assert engine_mode == 'provisioned'
            assert engine_version == '15.4'

        return pulumi.Output.all(
            sut.rds_serverless_cluster.engine,
            sut.rds_serverless_cluster.engine_mode,
            sut.rds_serverless_cluster.engine_version
        ).apply(check_rds_cluster_engine)

    @pulumi.runtime.test
    def it_sets_the_name_to_the_namespace(sut, namespace):
        return assert_output_equals(sut.rds_serverless_cluster.cluster_identifier, namespace)

    @pulumi.runtime.test
    def it_sets_the_master_username(sut, namespace):
        return assert_output_equals(sut.rds_serverless_cluster.master_username,
                                    f'{namespace}'.replace('-', '_'))

    @pulumi.runtime.test
    def it_sets_apply_immediately(sut):
        return assert_output_equals(sut.rds_serverless_cluster.apply_immediately, True)

    @pulumi.runtime.test
    def it_sets_the_master_password(sut):
        return assert_outputs_equal(sut.rds_serverless_cluster.master_password, sut.db_password.result)

    @pulumi.runtime.test
    def it_turns_on_deletion_protection(sut):
        return assert_output_equals(sut.rds_serverless_cluster.deletion_protection, True)

    @pulumi.runtime.test
    def it_sets_skip_final_snapshot_to_false(sut):
        return assert_output_equals(sut.rds_serverless_cluster.skip_final_snapshot, False)

    @pulumi.runtime.test
    def it_sets_final_snapshot_identifier(sut, namespace):
        return assert_output_equals(sut.rds_serverless_cluster.final_snapshot_identifier,
                                    f"{namespace}-final-snapshot")

    @pulumi.runtime.test
    def it_sets_the_backup_retention_period_to_14_days(sut):
        return assert_output_equals(sut.rds_serverless_cluster.backup_retention_period, 14)

    @pulumi.runtime.test
    def it_sets_a_serverlessv2_scaling_configuration(sut):
        def check_rds_cluster_scaling_configuration(args):
            min_capacity, max_capacity = args
            assert min_capacity == 1
            assert max_capacity == 128

        return pulumi.Output.all(
            sut.rds_serverless_cluster.serverlessv2_scaling_configuration.min_capacity,
            sut.rds_serverless_cluster.serverlessv2_scaling_configuration.max_capacity,
        ).apply(check_rds_cluster_scaling_configuration)

    @pulumi.runtime.test
    def it_has_a_default_db_name(sut):
        return sut.db_name == "app"

    @pulumi.runtime.test
    def it_creates_cluster_instances(sut):
        assert len(sut.cluster_instances) == 3  # 1 writer + 2 readers

    @pulumi.runtime.test
    def it_has_writer_instances(sut):
        # First instance should be the writer
        assert sut.cluster_instances[0]

    @pulumi.runtime.test
    def it_has_reader_instances(sut):
        # Should have 2 reader instances
        assert len(sut.cluster_instances) >= 3

    @pulumi.runtime.test
    def it_keeps_backward_compatibility_for_cluster_instance(sut):
        # rds_serverless_cluster_instance should point to first instance
        assert sut.rds_serverless_cluster_instance == sut.cluster_instances[0]

    @pulumi.runtime.test
    def it_has_endpoint_property(sut):
        assert sut.endpoint == sut.rds_serverless_cluster.endpoint

    @pulumi.runtime.test
    def it_has_reader_endpoint_property(sut):
        assert sut.reader_endpoint == sut.rds_serverless_cluster.reader_endpoint

    @pulumi.runtime.test
    def it_does_not_create_proxy_without_subnets(sut):
        # Without vpc_subnet_ids, proxy should not be created
        assert sut.rds_proxy is None

    def describe_with_vpc_subnet_ids():
        @pytest.fixture
        def vpc_subnet_ids(faker):
            return [faker.word(), faker.word()]

        @pytest.fixture
        def component_kwargs(component_kwargs, vpc_subnet_ids):
            component_kwargs['vpc_subnet_ids'] = vpc_subnet_ids
            return component_kwargs

        @pulumi.runtime.test
        def it_creates_rds_proxy(sut):
            assert sut.rds_proxy is not None

        @pulumi.runtime.test
        def it_creates_proxy_secret(sut):
            assert sut.proxy_secret is not None

        @pulumi.runtime.test
        def it_creates_proxy_role(sut):
            assert sut.proxy_role is not None

        @pulumi.runtime.test
        def it_has_proxy_endpoint_property(sut):
            assert sut.proxy_endpoint == sut.rds_proxy.endpoint

    def describe_with_md5_passwords_on():
        @pytest.fixture
        def component_kwargs(component_kwargs):
            component_kwargs['md5_hash_db_password'] = True
            return component_kwargs

        @pulumi.runtime.test
        def it_sets_the_master_password(sut):
            return assert_outputs_equal(sut.rds_serverless_cluster.master_password, sut.hashed_password)

    def describe_when_given_engine_version():
        @pytest.fixture
        def engine_version(faker):
            return faker.word()

        @pytest.fixture
        def component_kwargs(component_kwargs, engine_version):
            component_kwargs['db_engine_version'] = engine_version
            return component_kwargs

        @pulumi.runtime.test
        def it_sets_the_engine_version(sut, engine_version):
            return assert_output_equals(sut.rds_serverless_cluster.engine_version, engine_version)

    def describe_when_given_a_snapshot_to_restore_from():
        @pytest.fixture
        def snapshot_identifier(faker):
            return f'arn:aws:rds:us-west-2:448312246740:cluster-snapshot:{faker.word()}'

        @pytest.fixture
        def component_kwargs(component_kwargs, snapshot_identifier):
            component_kwargs['snapshot_identifier'] = snapshot_identifier
            return component_kwargs

        @pulumi.runtime.test
        def it_restores_the_snapshot(sut, snapshot_identifier):
            return assert_output_equals(sut.rds_serverless_cluster.snapshot_identifier, snapshot_identifier)

    def describe_with_optional_database_options():
        @pytest.fixture
        def db_name(faker):
            return faker.word()

        @pytest.fixture
        def db_username(faker):
            return faker.word()

        @pytest.fixture
        def component_kwargs(component_kwargs, db_name, db_username):
            component_kwargs['db_name'] = db_name
            component_kwargs['db_username'] = db_username
            return component_kwargs

        @pulumi.runtime.test
        def it_should_set_the_db_name(sut, db_name):
            return assert_output_equals(sut.rds_serverless_cluster.database_name, db_name)

        @pulumi.runtime.test
        def it_should_put_the_db_name_in_the_url(sut, db_name):
            def check_the_db_url(db_url):
                assert db_url.split('/')[-1] == db_name

            return sut.get_database_url().apply(check_the_db_url)

        @pulumi.runtime.test
        def it_should_set_the_db_username(sut, db_username):
            return assert_output_equals(sut.rds_serverless_cluster.master_username, db_username)

    def describe_when_given_a_kms_key():
        @pytest.fixture
        def kms_key(faker):
            return f'arn:aws:kms:us-west-2:448312246740:key/{faker.word()}'

        @pytest.fixture
        def component_kwargs(component_kwargs, kms_key):
            component_kwargs['kms_key_id'] = kms_key
            return component_kwargs

        @pulumi.runtime.test
        def it_encrypts(sut):
            return assert_output_equals(sut.rds_serverless_cluster.storage_encrypted, True)

        @pulumi.runtime.test
        def it_encrypts_with_provided_key(sut, kms_key):
            return assert_output_equals(sut.rds_serverless_cluster.kms_key_id, kms_key)

    def describe_with_custom_instance_counts():
        @pytest.fixture
        def component_kwargs(component_kwargs):
            component_kwargs['writer_instance_count'] = 2
            component_kwargs['reader_instance_count'] = 3
            return component_kwargs

        @pulumi.runtime.test
        def it_creates_correct_number_of_instances(sut):
            assert len(sut.cluster_instances) == 5  # 2 writers + 3 readers

