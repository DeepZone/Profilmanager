import re


def normalize_dial_code(dial_code: str | None) -> str:
    value = (dial_code or "").strip()
    digits = "".join(ch for ch in value if ch.isdigit())
    if not digits:
        return "0"
    if value.startswith("+"):
        return f"0{digits}"
    if digits.startswith("0"):
        return digits
    return f"0{digits}"


def sanitize_branch_segment(value: str | None, fallback: str = "x") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", (value or "").strip()).strip("-._")
    return cleaned.lower() or fallback


def sanitize_path_segment(value: str | None, fallback: str = "unknown") -> str:
    cleaned = (value or "").strip().replace("/", "-").replace("\\", "-")
    return cleaned or fallback


def build_branch_name(user_shortcode: str, dial_code: str | None, provider_name: str) -> str:
    shortcode = sanitize_branch_segment(user_shortcode, fallback="usr")
    prefix = normalize_dial_code(dial_code)
    provider = sanitize_branch_segment(provider_name, fallback="provider")
    return f"{shortcode}_{prefix}_{provider}"


def build_repo_paths(dial_code: str | None, provider_name: str, filename: str) -> dict[str, str]:
    prefix = normalize_dial_code(dial_code)
    provider_segment = sanitize_path_segment(provider_name, fallback="provider")
    base = f"providers-{prefix}/{provider_segment}"
    sanitized_filename = sanitize_path_segment(filename, fallback="profile.tar")
    is_export_file = sanitized_filename.lower().endswith(".export")
    upload_path = (
        f"{base}/gui_importe/{sanitized_filename}"
        if is_export_file
        else f"{base}/providerprofile/{sanitized_filename}"
    )
    return {
        "base": base,
        "gui_importe": f"{base}/gui_importe",
        "providerprofile": f"{base}/providerprofile",
        "tr069_nachlader": f"{base}/tr069_nachlader",
        "upload_path": upload_path,
    }
