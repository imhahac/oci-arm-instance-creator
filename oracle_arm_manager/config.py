import os
from dataclasses import dataclass
from typing import List

from oracle_arm_manager.exceptions import ConfigurationError
from oracle_arm_manager.constants import (
    DEFAULT_OCPUS, DEFAULT_MEMORY_GBS, DEFAULT_BOOT_VOLUME_SIZE,
    DEFAULT_BOOT_VOLUME_VPUS, DEFAULT_MAX_INSTANCES, DEFAULT_COST_THRESHOLD,
    DEFAULT_SHAPE, MIN_BOOT_VOLUME_SIZE, MIN_OCPUS, MIN_MEMORY_GBS
)

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
            f"ssh_key='***HIDDEN***', "
            f"max_instances={self.max_instances}>"
        )
        
    def validate(self) -> None:
        """驗證所有設定值是否合法"""
        if self.ocpus < MIN_OCPUS:
            raise ConfigurationError(f"OCPU 數量不能小於 {MIN_OCPUS}")
        if self.memory_gbs < MIN_MEMORY_GBS:
            raise ConfigurationError(f"記憶體數量不能小於 {MIN_MEMORY_GBS}")
        if self.boot_volume_size < MIN_BOOT_VOLUME_SIZE:
            raise ConfigurationError(f"Boot Volume 大小不能小於 {MIN_BOOT_VOLUME_SIZE}GB")
        if self.max_instances < 1:
            raise ConfigurationError("最大實例數量不能小於 1")
        if not self.region_list:
            raise ConfigurationError("OCI_CONFIG_REGION 必須設定至少一個可用區域")

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

    config = OracleArmConfig(
        user=get_env("OCI_CONFIG_USER"),
        key_content=get_env("OCI_CONFIG_KEY_CONTENT"),
        fingerprint=get_env("OCI_CONFIG_FINGERPRINT"),
        tenancy=get_env("OCI_CONFIG_TENANCY"),
        compartment_id=get_env("OCI_COMPARTMENT_ID"),
        region_list=region_list,
        ssh_key=get_env("OCI_SSH_KEY"),
        image_id=get_env("OCI_IMAGE_ID"),
        subnet_id=get_env("OCI_SUBNET_ID"),
        max_instances=int(get_env("OCI_MAX_INSTANCES", str(DEFAULT_MAX_INSTANCES))),
        ocpus=float(get_env("OCI_OCPUS", str(DEFAULT_OCPUS))),
        memory_gbs=float(get_env("OCI_MEMORY_GBS", str(DEFAULT_MEMORY_GBS))),
        boot_volume_size=int(get_env("OCI_BOOT_VOLUME_SIZE", str(DEFAULT_BOOT_VOLUME_SIZE))),
        boot_volume_vpus_per_gb=int(get_env("OCI_BOOT_VOLUME_VPUS_PER_GB", str(DEFAULT_BOOT_VOLUME_VPUS))),
        cost_threshold=float(get_env("OCI_COST_THRESHOLD", str(DEFAULT_COST_THRESHOLD))),
        shape=get_env("OCI_SHAPE", DEFAULT_SHAPE),
        
        # 可配置化延遲與重試，並給定預設值
        jitter_min=float(get_env("JITTER_MIN", "0")),
        jitter_max=float(get_env("JITTER_MAX", "60")),
        retry=RetryConfig(
            max_retries=int(get_env("RETRY_MAX", "2")),
            delay_1=int(get_env("RETRY_DELAY_1", "60")),
            delay_2=int(get_env("RETRY_DELAY_2", "30")),
        )
    )
    
    config.validate()
    return config
