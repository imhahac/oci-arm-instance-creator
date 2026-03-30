import os
from dataclasses import dataclass
from typing import List

REQUIRED_ENV_VARS = [
    "OCI_CONFIG_USER",
    "OCI_CONFIG_KEY_CONTENT",
    "OCI_CONFIG_FINGERPRINT",
    "OCI_CONFIG_TENANCY",
    "OCI_COMPARTMENT_ID",
    "OCI_SSH_KEY",
    "OCI_IMAGE_ID",
    "OCI_SUBNET_ID",
    "OCI_CONFIG_REGION",
]

CAPACITY_KEYWORDS = ["capacity", "quota", "limit"]


@dataclass
class OracleArmConfig:
    user: str
    key_content: str
    fingerprint: str
    tenancy: str
    compartment_id: str
    region_list: List[str]
    ssh_key: str
    image_id: str
    subnet_id: str
    max_instances: int
    ocpus: float
    memory_gbs: float
    boot_volume_size: int
    boot_volume_vpus_per_gb: int
    cost_threshold: float
    shape: str


def get_env(var_name: str) -> str:
    value = os.getenv(var_name, "")
    return value.strip()


def validate_required_env() -> None:
    missing = [name for name in REQUIRED_ENV_VARS if not get_env(name)]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")


def load_config() -> OracleArmConfig:
    validate_required_env()

    regions_raw = get_env("OCI_CONFIG_REGION")
    region_list = [r.strip() for r in regions_raw.split(",") if r.strip()]

    return OracleArmConfig(
        user=get_env("OCI_CONFIG_USER"),
        key_content=get_env("OCI_CONFIG_KEY_CONTENT"),
        fingerprint=get_env("OCI_CONFIG_FINGERPRINT"),
        tenancy=get_env("OCI_CONFIG_TENANCY"),
        compartment_id=get_env("OCI_COMPARTMENT_ID"),
        region_list=region_list,
        ssh_key=get_env("OCI_SSH_KEY"),
        image_id=get_env("OCI_IMAGE_ID"),
        subnet_id=get_env("OCI_SUBNET_ID"),
        max_instances=int(get_env("OCI_MAX_INSTANCES") or 1),
        ocpus=float(get_env("OCI_OCPUS") or 4),
        memory_gbs=float(get_env("OCI_MEMORY_GBS") or 24),
        boot_volume_size=int(get_env("OCI_BOOT_VOLUME_SIZE") or 50),
        boot_volume_vpus_per_gb=int(get_env("OCI_BOOT_VOLUME_VPUS_PER_GB") or 10),
        cost_threshold=float(get_env("OCI_COST_THRESHOLD") or 0.1),
        shape=get_env("OCI_SHAPE") or "VM.Standard.A1.Flex",
    )
