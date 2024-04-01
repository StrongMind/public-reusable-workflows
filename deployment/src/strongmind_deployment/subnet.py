
from enum import Enum
from typing import List
class SubnetType(str, Enum): 
    """
    A type of subnet within a VPC.
    """

    PUBLIC = "Public"
    """
    A subnet whose hosts can directly communicate with the internet.
    """
    PRIVATE = "Private"
    """
    A subnet whose hosts can not directly communicate with the internet, but can initiate outbound network traffic via a NAT Gateway.
    """
    ISOLATED = "Isolated"
    """
    A subnet whose hosts have no connectivity with the internet.
    """
    UNUSED = "Unused"
    """
    A subnet range which is reserved, but no subnet will be created.
    """

    def __str__(self):
        return self.value

class SubnetSpec:
    def __init__(self, type: SubnetType,  cidr_blocks: List[str]) -> None:
        self.type = type
        self.cidr_blocks = cidr_blocks
    
    @staticmethod
    def get_subnet_by_type(specs: 'List[SubnetSpec]', type: SubnetType):
        """
        Get the subnet spec with the specified type from the list of subnet specs.
        """
        for spec in specs:
            if spec.type == type:
                return spec
        return None

    @staticmethod
    def trim_cidr_block_to_prefix(cidr_block: str) -> str:
        """
        Trims the CIDR block to the specified prefix.
        """
        return ".".join(cidr_block.split(".")[:2])

    @staticmethod
    def get_standard_subnet_specs(cidr_block: str)-> 'List[SubnetSpec]':
        """
        Returns a standard allocation of subnets for a /16 VPC CIDR block.
        This requires 3 AZ's be available.

        The allocation is as follows:
        - 3 public subnets - 1 per AZ, with a mask of /20
        - 3 private subnets - 1 per AZ, with a mask of /19
        - 3 isolated subnets - 1 per AZ, with a mask of /21
        - 3 unused subnets - 1 per AZ, with a mask of /21
            -> these unused subnets are purposely reserved for future use. It's not necessary
               to identify them here, but we do so for clarity.
        """

        cidr_prefix = SubnetSpec.trim_cidr_block_to_prefix(cidr_block)
        subnet_specs = [
            SubnetSpec(
                type=SubnetType.PRIVATE,
                cidr_blocks=[
                    f"{cidr_prefix}.0.0/19",
                    f"{cidr_prefix}.64.0/19",
                    f"{cidr_prefix}.128.0/19",
                ],
            ),
            SubnetSpec(
                type=SubnetType.PUBLIC,
                cidr_blocks=[
                    f"{cidr_prefix}.32.0/20",
                    f"{cidr_prefix}.96.0/20",
                    f"{cidr_prefix}.160.0/20",
                ],
            ),
            SubnetSpec(
                type=SubnetType.ISOLATED,
                cidr_blocks=[
                    f"{cidr_prefix}.48.0/21",
                    f"{cidr_prefix}.112.0/21",
                    f"{cidr_prefix}.176.0/21",
                ],
            ),
            # explicitly define remaining cidrs
            SubnetSpec(
                type=SubnetType.UNUSED,
                cidr_blocks=[
                    f"{cidr_prefix}.56.0/21",
                    f"{cidr_prefix}.120.0/21",
                    f"{cidr_prefix}.184.0/21",
                ],
            ),
            SubnetSpec(
                type=SubnetType.UNUSED,
                cidr_blocks=[
                    f"{cidr_prefix}.192.0/19",
                    f"{cidr_prefix}.224.0/20",
                    f"{cidr_prefix}.240.0/20",
                ],
            ),
        ]

        return subnet_specs
