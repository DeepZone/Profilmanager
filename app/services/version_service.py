from __future__ import annotations

from dataclasses import dataclass

from app.extensions import db
from app.models import AuditLog, Setting


class VersionServiceError(ValueError):
    pass


@dataclass(frozen=True)
class AppVersion:
    major: int
    minor: int
    build: int

    def as_string(self) -> str:
        return f"{self.major}.{self.minor}.{self.build}"


class VersionService:
    VERSION_MAJOR_KEY = "app_version_major"
    VERSION_MINOR_KEY = "app_version_minor"
    VERSION_BUILD_KEY = "app_version_build"
    RELEASE_SHA_KEY = "app_release_sha"

    @classmethod
    def _validate_non_negative_int(cls, value, field_name: str) -> int:
        if not isinstance(value, int):
            raise VersionServiceError(f"{field_name} muss eine Ganzzahl sein.")
        if value < 0:
            raise VersionServiceError(f"{field_name} darf nicht negativ sein.")
        return value

    @classmethod
    def _get_setting(cls, key: str) -> Setting | None:
        return Setting.query.filter_by(key=key).first()

    @classmethod
    def _upsert_setting(cls, key: str, value: int) -> None:
        setting = cls._get_setting(key)
        if setting:
            setting.value = str(value)
        else:
            db.session.add(Setting(key=key, value=str(value)))

    @classmethod
    def _parse_setting_int(cls, key: str, raw_value: str | None) -> int:
        if raw_value is None:
            raise VersionServiceError(f"Setting {key} ist nicht gesetzt.")
        try:
            parsed = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise VersionServiceError(f"Setting {key} ist ungültig: {raw_value}") from exc
        return cls._validate_non_negative_int(parsed, key)

    @classmethod
    def initialize_version_if_missing(cls) -> AppVersion:
        changed = False
        defaults = {
            cls.VERSION_MAJOR_KEY: 0,
            cls.VERSION_MINOR_KEY: 2,
            cls.VERSION_BUILD_KEY: 7683,
        }
        for key, default_value in defaults.items():
            if cls._get_setting(key) is None:
                db.session.add(Setting(key=key, value=str(default_value)))
                changed = True

        if changed:
            db.session.commit()

        major_setting = cls._get_setting(cls.VERSION_MAJOR_KEY)
        minor_setting = cls._get_setting(cls.VERSION_MINOR_KEY)
        build_setting = cls._get_setting(cls.VERSION_BUILD_KEY)
        return AppVersion(
            major=cls._parse_setting_int(cls.VERSION_MAJOR_KEY, major_setting.value),
            minor=cls._parse_setting_int(cls.VERSION_MINOR_KEY, minor_setting.value),
            build=cls._parse_setting_int(cls.VERSION_BUILD_KEY, build_setting.value),
        )

    @classmethod
    def get_version(cls) -> AppVersion:
        cls.initialize_version_if_missing()
        major = cls._parse_setting_int(
            cls.VERSION_MAJOR_KEY, cls._get_setting(cls.VERSION_MAJOR_KEY).value
        )
        minor = cls._parse_setting_int(
            cls.VERSION_MINOR_KEY, cls._get_setting(cls.VERSION_MINOR_KEY).value
        )
        build = cls._parse_setting_int(
            cls.VERSION_BUILD_KEY, cls._get_setting(cls.VERSION_BUILD_KEY).value
        )
        return AppVersion(major=major, minor=minor, build=build)

    @classmethod
    def get_version_string(cls) -> str:
        return cls.get_version().as_string()

    @classmethod
    def _audit_version_change(
        cls,
        previous: AppVersion,
        new: AppVersion,
        user_id: int | None = None,
        reason: str | None = None,
    ) -> None:
        if user_id is None:
            return

        details = (
            f"from={previous.as_string()} to={new.as_string()}"
            + (f" reason={reason}" if reason else "")
        )
        db.session.add(AuditLog(user_id=user_id, action="version_changed", details=details))


    @classmethod
    def bump_build_for_release(cls, release_id: str | None) -> AppVersion:
        version = cls.get_version()
        if not release_id:
            return version

        release_setting = cls._get_setting(cls.RELEASE_SHA_KEY)
        if release_setting and release_setting.value == release_id:
            return version

        new_version = AppVersion(
            major=version.major,
            minor=version.minor,
            build=version.build + 1,
        )
        cls._upsert_setting(cls.VERSION_BUILD_KEY, new_version.build)

        if release_setting:
            release_setting.value = release_id
        else:
            db.session.add(Setting(key=cls.RELEASE_SHA_KEY, value=release_id))

        db.session.commit()
        return new_version

    @classmethod
    def increment_build(cls, user_id: int | None = None, reason: str | None = None) -> AppVersion:
        version = cls.get_version()
        new_version = AppVersion(major=version.major, minor=version.minor, build=version.build + 1)

        cls._upsert_setting(cls.VERSION_BUILD_KEY, new_version.build)
        cls._audit_version_change(version, new_version, user_id=user_id, reason=reason)
        db.session.commit()
        return new_version
