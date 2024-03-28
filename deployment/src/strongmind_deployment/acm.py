import re

from pulumi import Output, ResourceOptions
from pulumi_aws import acm, route53
import pulumi


class AcmCertificateArgs:
    def __init__(
        self,
        zone_id: str,
        cert_fqdn: str,
    ):
        self.zone_id = zone_id
        self.cert_fqdn = cert_fqdn


class AcmCertificate(pulumi.ComponentResource):
    def __init__(
        self, name: str, args: AcmCertificateArgs, opts: pulumi.ResourceOptions = None
    ):
        super().__init__("strongmind:global_build:commons:acmcert", name, None, opts)
        self.child_opts = pulumi.ResourceOptions(parent=self)
        self.args: AcmCertificateArgs = args
        self.create_resources()

    def create_resources(self):

        self.cert = self.create_certificate()
        self.domain_validation_options = self.cert.domain_validation_options

        self.validation_record = self.create_validation_record(
            self.domain_validation_options
        )
        self.cert_validation = self.validate_certificate(self.validation_record)

    def create_certificate(self):
        cert_name = f"acm_certificate_{self.args.cert_fqdn.replace('.', '_')}"
        return acm.Certificate(
            cert_name,
            domain_name=self.args.cert_fqdn,
            validation_method="DNS",
            opts=self.child_opts,
        )

    def create_validation_record(self, domain_validation_options: list):
        resource_record_value = domain_validation_options[0].resource_record_value

        def remove_trailing_period(value):
            return re.sub("\\.$", "", value)

        if type(resource_record_value) != str:
            resource_record_value = resource_record_value.apply(remove_trailing_period)
   
        return route53.Record(
            "cert_validation_record",
            name=domain_validation_options[0].resource_record_name,
            type=domain_validation_options[0].resource_record_type,
            zone_id=self.args.zone_id,
            records=[resource_record_value],
            ttl=1,
            opts=ResourceOptions(parent=self, depends_on=[self.cert]),
        )

    def validate_certificate(self, resource_record_value: str):
        try:
            # Try to import the existing certificate
            return acm.CertificateValidation.get(
                "cert_validation",
                self.cert.arn,
                opts=ResourceOptions(parent=self, depends_on=[self.validation_record]),
            )
        except Exception:
            # If the certificate doesn't exist, create a new one
            return acm.CertificateValidation(
                "cert_validation",
                certificate_arn=self.cert.arn,
                validation_record_fqdns=[resource_record_value],
                opts=ResourceOptions(parent=self, depends_on=[self.validation_record]),
            )
