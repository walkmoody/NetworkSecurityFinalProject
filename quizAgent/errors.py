"""Controlled quiz workflow and mock-backend failures."""


class QuizError(Exception):
    pass


class ValidationError(QuizError):
    pass


class AttemptConflict(QuizError):
    pass
