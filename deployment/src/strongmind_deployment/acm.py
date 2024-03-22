import re
from dataclasses import dataclass
from pulumi import Output, ResourceOptions
from pulumi_aws import acm, route53
import pulumi


@dataclass
class AcmCertificateArgs:
    stack: str
    zone_id: str
    tags: dict = None
    domain: str = "prod.aws2.strongmind.com"


class AcmCertificate(pulumi.ComponentResource):
    def __init__(
        self, name: str, args: AcmCertificateArgs, opts: pulumi.ResourceOptions = None
    ):
        super().__init__("pkg:index:AcmCertificate", name, None, opts)
        child_opts = pulumi.ResourceOptions(parent=self)
        if args.stack != "prod":
            name = f"{args.stack}-{name}"
        domain = args.domain
        full_name = f"*.{domain}"

        self.cert = acm.Certificate(
            "cert",
            domain_name=full_name,
            validation_method="DNS",
            tags=args.tags,
            opts=child_opts,
        )

        domain_validation_options = self.cert.domain_validation_options
        pulumi.export("domain_validation_options", domain_validation_options)
        resource_record_value = domain_validation_options[0].resource_record_value

        def remove_trailing_period(value):
            return re.sub("\\.$", "", value)

        if type(resource_record_value) != str:
            resource_record_value = resource_record_value.apply(remove_trailing_period)

        self.cert_validation_record = route53.Record(
            "cert_validation_record",
            name=domain_validation_options[0].resource_record_name,
            type=domain_validation_options[0].resource_record_type,
            zone_id=args.zone_id,
            records=[resource_record_value],
            ttl=1,
            opts=ResourceOptions(parent=self, depends_on=[self.cert]),
        )

        self.cert_validation_cert = acm.CertificateValidation(
            "cert_validation",
            certificate_arn=self.cert.arn,
            validation_record_fqdns=[self.cert_validation_record.name],
            opts=ResourceOptions(parent=self, depends_on=[self.cert_validation_record]),
        )
