from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


class ResetPasswordService:
    PURPOSE = "reset-password"

    @staticmethod
    def _serializer(secret_key: str) -> URLSafeTimedSerializer:
        return URLSafeTimedSerializer(secret_key=secret_key, salt=ResetPasswordService.PURPOSE)

    @staticmethod
    def create_token(secret_key: str, user_id: int) -> str:
        serializer = ResetPasswordService._serializer(secret_key)
        return serializer.dumps({"user_id": user_id})

    @staticmethod
    def resolve_user_id(secret_key: str, token: str, max_age_seconds: int) -> int | None:
        serializer = ResetPasswordService._serializer(secret_key)
        try:
            payload = serializer.loads(token, max_age=max_age_seconds)
        except (BadSignature, SignatureExpired):
            return None

        user_id = payload.get("user_id")
        return user_id if isinstance(user_id, int) else None
