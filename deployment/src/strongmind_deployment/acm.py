import re
from pydantic import BaseModel
from pulumi import Output, ResourceOptions
from pulumi_aws import acm, route53
import pulumi


class AcmCertificateArgs(BaseModel):
    stack: str
    zone_id: str
    cert_fqdn: str = None
    tags: dict = None
    domain: str = "aws2.strongmind.com"


class AcmCertificate(pulumi.ComponentResource):
    def __init__(
        self, name: str, args: AcmCertificateArgs, opts: pulumi.ResourceOptions = None
    ):
        super().__init__(
            "strongmind:global_build:commons:AcmCertificate", name, None, opts
        )
        child_opts = pulumi.ResourceOptions(parent=self)

        name = self.get_name(args.stack, name)

        if args.cert_fqdn:
            full_name = args.cert_fqdn
        else:
            full_name = f"{name}.{args.domain}"

        self.cert = self.create_certificate(full_name, args.tags, child_opts)
        domain_validation_options = self.cert.domain_validation_options

        self.validation_dns_record_value = self.create_validation_record(
            domain_validation_options, args.zone_id, child_opts
        )
        self.cert_validation = self.validate_certificate(
            self.validation_dns_record_value, child_opts
        )

    def create_certificate(
        self, full_name: str, tags: dict, opts: pulumi.ResourceOptions
    ):
        cert_name = f"acm_certificate_{full_name.replace('.', '_')}"
        return acm.Certificate(
            cert_name,
            domain_name=full_name,
            validation_method="DNS",
            tags=tags,
            opts=opts,
        )

    def create_validation_record(
        self,
        domain_validation_options: list,
        zone_id: str,
        opts: pulumi.ResourceOptions,
    ):
        resource_record_value = domain_validation_options[0].resource_record_value

        def remove_trailing_period(value):
            return re.sub("\\.$", "", value)

        if type(resource_record_value) != str:
            resource_record_value = resource_record_value.apply(remove_trailing_period)
        # Generate a unique name for the DNS validation record
        record_name = f"validation_record_{domain_validation_options[0].resource_record_name.replace('.', '_')}"
        return route53.Record(
            record_name,
            name=domain_validation_options[0].resource_record_name,
            type=domain_validation_options[0].resource_record_type,
            zone_id=zone_id,
            records=[resource_record_value],
            ttl=1,
            opts=ResourceOptions(parent=self, depends_on=[self.cert]),
        )

    def validate_certificate(
        self, resource_record_value: str, opts: pulumi.ResourceOptions
    ):
        try:
            # Try to import the existing certificate
            return acm.CertificateValidation.get(
                "cert_validation",
                self.cert.arn,
                opts=ResourceOptions(
                    parent=self, depends_on=[self.validation_dns_record_value]
                ),
            )
        except Exception:
            # If the certificate doesn't exist, create a new one
            return acm.CertificateValidation(
                "cert_validation",
                certificate_arn=self.cert.arn,
                validation_record_fqdns=[resource_record_value],
                opts=ResourceOptions(
                    parent=self, depends_on=[self.validation_dns_record_value]
                ),
            )

    def get_name(self, stack: str, name: str):
        if "prod" in stack:
            return f"{name}.prod"
        elif "stage" in stack:
            return f"{name}.stage"
        elif "dev" in stack:
            return f"{name}.dev"
