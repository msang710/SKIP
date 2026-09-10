class CoreError(ValueError):
    def __init__(self, code, message, *, details=None):
        super().__init__(message)
        self.code = code
        self.details = details

    def result(self):
        return {'schema': 'skip-core/v1', 'status': 'error', 'code': self.code,
                'error': str(self), 'enforcement': 'advisory',
                **({'details':self.details} if self.details is not None else {})}


def require(condition, code, message):
    if not condition:
        raise CoreError(code, message)
