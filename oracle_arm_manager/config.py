import os
from dataclasses import dataclass
from typing import List

class ConfigurationError(Exception):
    """自訂設定異常"""
    pass

REQUIRED_ENV_VARS: List[str] = [
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

CAPACITY_KEYWORDS: List[str] = ["capacity", "quota", "limit"]


@dataclass
class RetryConfig:
    max_retries: int
    delay_1: int
    delay_2: int


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
    
    # 消除魔術數字的新增設定
    jitter_min: float
    jitter_max: float
    retry: RetryConfig

    def __repr__(self) -> str:
        """覆寫預設的 __repr__ 以保護機密資訊 (Secrets) 不被印出至日誌中"""
        return (
            f"<OracleArmConfig "
            f"user='{self.user[:15]}...[MASKED]', "
            f"tenancy='{self.tenancy[:15]}...[MASKED]', "
            f"compartment_id='{self.compartment_id[:15]}...[MASKED]', "
            f"region_list={self.region_list}, "
            f"shape='{self.shape}', "
            f"key_content='***HIDDEN***', "
            f"fingerprint='***HIDDEN***', "
            f"ssh_key='***HIDDEN***', "
            f"max_instances={self.max_instances}>"
        )


def get_env(var_name: str, default_val: str = "") -> str:
    val = os.getenv(var_name, "").strip()
    return val if val else default_val


def validate_required_env() -> None:
    missing = [name for name in REQUIRED_ENV_VARS if not get_env(name)]
    if missing:
        raise ConfigurationError(f"缺少必要的環境變數: {', '.join(missing)}")


def load_config() -> OracleArmConfig:
    validate_required_env()

    regions_raw = get_env("OCI_CONFIG_REGION")
    region_list = [r.strip() for r in regions_raw.split(",") if r.strip()]

    if not region_list:
        raise ConfigurationError("OCI_CONFIG_REGION 必須設定至少一個可用區域")

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
        max_instances=int(get_env("OCI_MAX_INSTANCES", "1")),
        ocpus=float(get_env("OCI_OCPUS", "4")),
        memory_gbs=float(get_env("OCI_MEMORY_GBS", "24")),
        boot_volume_size=int(get_env("OCI_BOOT_VOLUME_SIZE", "50")),
        boot_volume_vpus_per_gb=int(get_env("OCI_BOOT_VOLUME_VPUS_PER_GB", "10")),
        cost_threshold=float(get_env("OCI_COST_THRESHOLD", "0.1")),
        shape=get_env("OCI_SHAPE", "VM.Standard.A1.Flex"),
        
        # 可配置化延遲與重試，並給定預設值
        jitter_min=float(get_env("JITTER_MIN", "0")),
        jitter_max=float(get_env("JITTER_MAX", "60")),
        retry=RetryConfig(
            max_retries=int(get_env("RETRY_MAX", "2")),
            delay_1=int(get_env("RETRY_DELAY_1", "60")),
            delay_2=int(get_env("RETRY_DELAY_2", "30")),
        )
    )
