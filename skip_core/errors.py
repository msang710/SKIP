class CoreError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code

    def result(self):
        return {'schema': 'skip-core/v1', 'status': 'error', 'code': self.code,
                'error': str(self), 'enforcement': 'advisory'}


def require(condition, code, message):
    if not condition:
        raise CoreError(code, message)
