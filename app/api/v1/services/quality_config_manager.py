"""
Quality Configuration Manager

This module provides configuration management for the comprehensive quality assurance system,
allowing customization of quality rules, thresholds, and processing options.
"""

import json
import logging
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class QualityConfigLevel(Enum):
    """Quality configuration levels with predefined settings"""

    MINIMAL = "minimal"
    BASIC = "basic"
    STANDARD = "standard"
    COMPREHENSIVE = "comprehensive"
    CUSTOM = "custom"


@dataclass
class TierConfig:
    """Configuration for a specific quality tier"""

    enabled: bool = True
    timeout_seconds: int = 30
    retry_count: int = 2
    severity_threshold: str = "medium"  # low, medium, high, critical
    auto_fix: bool = True
    custom_rules: Dict[str, Any] = None

    def __post_init__(self):
        if self.custom_rules is None:
            self.custom_rules = {}


@dataclass
class LanguageConfig:
    """Language-specific quality configuration"""

    formatters: List[str] = None
    linters: List[str] = None
    type_checkers: List[str] = None
    test_frameworks: List[str] = None
    security_scanners: List[str] = None
    complexity_threshold: int = 10
    line_length_limit: int = 88
    custom_patterns: Dict[str, Any] = None

    def __post_init__(self):
        if self.formatters is None:
            self.formatters = []
        if self.linters is None:
            self.linters = []
        if self.type_checkers is None:
            self.type_checkers = []
        if self.test_frameworks is None:
            self.test_frameworks = []
        if self.security_scanners is None:
            self.security_scanners = []
        if self.custom_patterns is None:
            self.custom_patterns = {}


@dataclass
class QualityConfig:
    """Comprehensive quality configuration"""

    # Global settings
    config_level: QualityConfigLevel = QualityConfigLevel.STANDARD
    project_id: str = ""
    language: str = "python"

    # Tier configurations
    tier1_prompt_enhancement: TierConfig = None
    tier2_real_time_validation: TierConfig = None
    tier3_code_quality: TierConfig = None
    tier4_semantic_validation: TierConfig = None

    # Language-specific configurations
    language_configs: Dict[str, LanguageConfig] = None

    # Processing options
    parallel_processing: bool = True
    max_workers: int = 4
    cache_results: bool = True
    generate_reports: bool = True

    # Quality thresholds
    min_quality_score: int = 70
    max_issues_per_file: int = 20
    max_processing_time: int = 300  # seconds

    # Custom configurations
    custom_rules: Dict[str, Any] = None
    excluded_patterns: List[str] = None

    def __post_init__(self):
        if self.tier1_prompt_enhancement is None:
            self.tier1_prompt_enhancement = TierConfig()
        if self.tier2_real_time_validation is None:
            self.tier2_real_time_validation = TierConfig()
        if self.tier3_code_quality is None:
            self.tier3_code_quality = TierConfig()
        if self.tier4_semantic_validation is None:
            self.tier4_semantic_validation = TierConfig()
        if self.language_configs is None:
            self.language_configs = {}
        if self.custom_rules is None:
            self.custom_rules = {}
        if self.excluded_patterns is None:
            self.excluded_patterns = []

    @property
    def level(self) -> QualityConfigLevel:
        """Alias for config_level for backward compatibility"""
        return self.config_level

    @property
    def settings(self) -> Dict[str, Any]:
        """Generate settings dict for backward compatibility"""
        return {
            "enable_prompt_enhancement": self.tier1_prompt_enhancement.enabled,
            "enable_real_time_validation": self.tier2_real_time_validation.enabled,
            "enable_code_quality": self.tier3_code_quality.enabled,
            "enable_semantic_validation": self.tier4_semantic_validation.enabled,
            "parallel_processing": self.parallel_processing,
            "max_workers": self.max_workers,
            "min_quality_score": self.min_quality_score,
            "max_processing_time": self.max_processing_time,
        }


class QualityConfigManager:
    """
    Manager for quality configuration with support for:
    - Predefined configuration levels
    - Project-specific configurations
    - Language-specific settings
    - Runtime configuration updates
    """

    def __init__(self, config_dir: str = "quality_configs"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        self._config_cache: Dict[str, QualityConfig] = {}
        self._default_configs = self._initialize_default_configs()

    def _initialize_default_configs(self) -> Dict[QualityConfigLevel, QualityConfig]:
        """Initialize default configurations for each quality level"""
        configs = {}

        # MINIMAL Configuration
        minimal_config = QualityConfig(
            config_level=QualityConfigLevel.MINIMAL,
            tier1_prompt_enhancement=TierConfig(enabled=False),
            tier2_real_time_validation=TierConfig(
                enabled=True, severity_threshold="critical", auto_fix=False
            ),
            tier3_code_quality=TierConfig(
                enabled=True, severity_threshold="high", auto_fix=True
            ),
            tier4_semantic_validation=TierConfig(enabled=False),
            parallel_processing=False,
            max_workers=1,
            min_quality_score=50,
        )
        configs[QualityConfigLevel.MINIMAL] = minimal_config

        # BASIC Configuration
        basic_config = QualityConfig(
            config_level=QualityConfigLevel.BASIC,
            tier1_prompt_enhancement=TierConfig(
                enabled=True, severity_threshold="high"
            ),
            tier2_real_time_validation=TierConfig(
                enabled=True, severity_threshold="medium", auto_fix=True
            ),
            tier3_code_quality=TierConfig(
                enabled=True, severity_threshold="medium", auto_fix=True
            ),
            tier4_semantic_validation=TierConfig(
                enabled=True, severity_threshold="high", auto_fix=False
            ),
            parallel_processing=True,
            max_workers=2,
            min_quality_score=60,
        )
        configs[QualityConfigLevel.BASIC] = basic_config

        # STANDARD Configuration (Default)
        standard_config = QualityConfig(
            config_level=QualityConfigLevel.STANDARD,
            tier1_prompt_enhancement=TierConfig(enabled=True),
            tier2_real_time_validation=TierConfig(enabled=True),
            tier3_code_quality=TierConfig(enabled=True),
            tier4_semantic_validation=TierConfig(enabled=True),
            parallel_processing=True,
            max_workers=4,
            min_quality_score=70,
        )
        configs[QualityConfigLevel.STANDARD] = standard_config

        # COMPREHENSIVE Configuration
        comprehensive_config = QualityConfig(
            config_level=QualityConfigLevel.COMPREHENSIVE,
            tier1_prompt_enhancement=TierConfig(
                enabled=True, timeout_seconds=60, retry_count=3
            ),
            tier2_real_time_validation=TierConfig(
                enabled=True, timeout_seconds=45, severity_threshold="low"
            ),
            tier3_code_quality=TierConfig(
                enabled=True, timeout_seconds=120, severity_threshold="low"
            ),
            tier4_semantic_validation=TierConfig(
                enabled=True, timeout_seconds=180, severity_threshold="low"
            ),
            parallel_processing=True,
            max_workers=8,
            min_quality_score=85,
            max_processing_time=600,
        )
        configs[QualityConfigLevel.COMPREHENSIVE] = comprehensive_config

        # Initialize language-specific configurations
        for config in configs.values():
            config.language_configs = self._get_default_language_configs()

        return configs

    def _get_default_language_configs(self) -> Dict[str, LanguageConfig]:
        """Get default language-specific configurations"""
        return {
            "python": LanguageConfig(
                formatters=["black", "isort"],
                linters=["flake8", "pylint", "ruff"],
                type_checkers=["mypy"],
                test_frameworks=["pytest"],
                security_scanners=["bandit"],
                complexity_threshold=10,
                line_length_limit=88,
            ),
            "javascript": LanguageConfig(
                formatters=["prettier"],
                linters=["eslint"],
                type_checkers=[],
                test_frameworks=["jest"],
                security_scanners=["npm-audit"],
                complexity_threshold=15,
                line_length_limit=80,
            ),
            "typescript": LanguageConfig(
                formatters=["prettier"],
                linters=["eslint", "tslint"],
                type_checkers=["tsc"],
                test_frameworks=["jest"],
                security_scanners=["npm-audit"],
                complexity_threshold=12,
                line_length_limit=80,
            ),
            "go": LanguageConfig(
                formatters=["gofmt", "goimports"],
                linters=["golint", "go vet"],
                type_checkers=["go build"],
                test_frameworks=["go test"],
                security_scanners=["gosec"],
                complexity_threshold=8,
                line_length_limit=100,
            ),
            "php": LanguageConfig(
                formatters=["php-cs-fixer"],
                linters=["phpcs", "phpstan"],
                type_checkers=["psalm"],
                test_frameworks=["phpunit"],
                security_scanners=["psalm"],
                complexity_threshold=10,
                line_length_limit=120,
            ),
        }

    def get_config(
        self,
        project_id: str,
        language_or_level="python",
        config_level: Optional[QualityConfigLevel] = None,
    ) -> QualityConfig:
        """
        Get quality configuration for a project.

        Args:
            project_id: Project identifier
            language_or_level: Programming language or QualityConfigLevel (for backward compatibility)
            config_level: Quality configuration level

        Returns:
            QualityConfig: Configuration object
        """
        # Handle backward compatibility where second argument could be QualityConfigLevel
        if isinstance(language_or_level, QualityConfigLevel):
            language = "python"  # default language
            config_level = language_or_level
        else:
            language = language_or_level
            if config_level is None:
                config_level = QualityConfigLevel.STANDARD

        cache_key = f"{project_id}_{language}_{config_level.value}"

        # Check cache first
        if cache_key in self._config_cache:
            return self._config_cache[cache_key]

        # Try to load project-specific configuration
        config_file = self.config_dir / f"{project_id}_{language}.json"
        if config_file.exists():
            try:
                config = self._load_config_from_file(config_file)
                self._config_cache[cache_key] = config
                return config
            except Exception as e:
                logger.warning(f"Failed to load project config {config_file}: {e}")

        # Use default configuration
        default_config = self._default_configs[config_level]
        config = self._customize_config_for_project(
            default_config, project_id, language
        )

        # Cache the configuration
        self._config_cache[cache_key] = config

        return config

    def save_config(self, config: QualityConfig) -> bool:
        """
        Save configuration to file.

        Args:
            config: Configuration to save

        Returns:
            bool: True if saved successfully
        """
        try:
            config_file = (
                self.config_dir / f"{config.project_id}_{config.language}.json"
            )
            config_dict = asdict(config)

            # Convert enums to strings for JSON serialization
            config_dict["config_level"] = config.config_level.value

            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config_dict, f, indent=2, default=str)

            # Update cache
            cache_key = (
                f"{config.project_id}_{config.language}_{config.config_level.value}"
            )
            self._config_cache[cache_key] = config

            logger.info(
                f"Saved quality config for {config.project_id}_{config.language}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False

    def _load_config_from_file(self, config_file: Path) -> QualityConfig:
        """Load configuration from JSON file"""
        with open(config_file, "r", encoding="utf-8") as f:
            config_dict = json.load(f)

        # Convert string back to enum
        if "config_level" in config_dict:
            config_dict["config_level"] = QualityConfigLevel(
                config_dict["config_level"]
            )

        # Create TierConfig objects
        for tier_key in [
            "tier1_prompt_enhancement",
            "tier2_real_time_validation",
            "tier3_code_quality",
            "tier4_semantic_validation",
        ]:
            if tier_key in config_dict and config_dict[tier_key]:
                config_dict[tier_key] = TierConfig(**config_dict[tier_key])
        # Create LanguageConfig objects
        if "language_configs" in config_dict:
            language_configs = {}
            for lang, lang_config in config_dict["language_configs"].items():
                language_configs[lang] = LanguageConfig(**lang_config)
            config_dict["language_configs"] = language_configs

        return QualityConfig(**config_dict)

    def _customize_config_for_project(
        self, base_config: QualityConfig, project_id: str, language: str
    ) -> QualityConfig:
        """Customize configuration for specific project and language"""
        # Create a deep copy of the base configuration
        import copy

        config = copy.deepcopy(base_config)

        # Set project-specific values
        config.project_id = project_id
        config.language = language

        # Apply language-specific customizations
        if language in config.language_configs:
            lang_config = config.language_configs[language]

            # Adjust complexity threshold based on language
            if language == "python":
                config.tier4_semantic_validation.custom_rules["max_complexity"] = (
                    lang_config.complexity_threshold
                )
            elif language == "javascript":
                config.tier4_semantic_validation.custom_rules["max_complexity"] = (
                    lang_config.complexity_threshold + 5
                )

        return config

    def update_config(
        self, project_id: str, language: str, updates: Dict[str, Any]
    ) -> bool:
        """
        Update specific configuration values.

        Args:
            project_id: Project identifier
            language: Programming language
            updates: Dictionary of configuration updates

        Returns:
            bool: True if updated successfully
        """
        try:
            # Get current configuration
            current_config = self.get_config(project_id, language)

            # Apply updates
            for key, value in updates.items():
                if hasattr(current_config, key):
                    setattr(current_config, key, value)
                else:
                    logger.warning(f"Unknown configuration key: {key}")

            # Save updated configuration
            return self.save_config(current_config)

        except Exception as e:
            logger.error(f"Failed to update config: {e}")
            return False

    def get_language_config(self, language: str) -> LanguageConfig:
        """Get language-specific configuration"""
        default_configs = self._get_default_language_configs()
        return default_configs.get(language, LanguageConfig())

    def list_project_configs(self) -> List[Dict[str, str]]:
        """List all project configurations"""
        configs = []
        for config_file in self.config_dir.glob("*.json"):
            try:
                parts = config_file.stem.split("_")
                if len(parts) >= 2:
                    project_id = "_".join(parts[:-1])
                    language = parts[-1]
                    configs.append(
                        {
                            "project_id": project_id,
                            "language": language,
                            "config_file": str(config_file),
                        }
                    )
            except Exception as e:
                logger.warning(f"Error parsing config file {config_file}: {e}")

        return configs

    def delete_config(self, project_id: str, language: str) -> bool:
        """Delete project configuration"""
        try:
            config_file = self.config_dir / f"{project_id}_{language}.json"
            if config_file.exists():
                config_file.unlink()

                # Remove from cache
                cache_keys = [
                    k
                    for k in self._config_cache.keys()
                    if k.startswith(f"{project_id}_{language}_")
                ]
                for key in cache_keys:
                    del self._config_cache[key]

                logger.info(f"Deleted config for {project_id}_{language}")
                return True
            else:
                logger.warning(f"Config file not found: {config_file}")
                return False

        except Exception as e:
            logger.error(f"Failed to delete config: {e}")
            return False

    def export_config(self, project_id: str, language: str, output_file: str) -> bool:
        """Export configuration to a file"""
