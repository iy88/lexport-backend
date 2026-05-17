class AppError(Exception):
    def __init__(self, code, message, http_status=400):
        self.code = code
        self.message = message
        self.http_status = http_status

    def to_response(self):
        return {
            'success': False,
            'error': {'code': self.code, 'message': self.message}
        }, self.http_status


class ValidationError(AppError):
    def __init__(self, message):
        super().__init__('VALIDATION_ERROR', message, 400)


class AuthenticationError(AppError):
    def __init__(self, message, http_status=401):
        super().__init__('AUTH_ERROR', message, http_status)


class ConflictError(AppError):
    def __init__(self, message):
        super().__init__('CONFLICT', message, 409)


class NotFoundError(AppError):
    def __init__(self, message):
        super().__init__('NOT_FOUND', message, 404)
