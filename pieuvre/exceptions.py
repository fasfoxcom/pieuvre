"""
exceptions.py
=================================================
Exception definitions.
"""


class WorkflowBaseError(Exception):
    """
    Base exception for workflow errors
    """

    message = "Error {transition}: {current_state} -> {to_state}"

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def __str__(self):
        return self.message.format(**self.kwargs)


class InvalidTransition(WorkflowBaseError):
    """
    Raised when trying to perform a transition from an invalid state
    """

    message = "Invalid transition {transition}: {current_state} -> {to_state}"


class ForbiddenTransition(WorkflowBaseError):
    """
    Raised when condition is not valid to perform the transition
    """

    message = "Transition forbidden {transition}: {current_state} -> {to_state}"


class TransitionDoesNotExist(WorkflowBaseError):
    """
    Raised when transition is not defined
    """

    message = "Transition {transition} does not exist"


class TransitionNotFound(WorkflowBaseError):
    """
    Raised when transition does not apply to current state and/or destination
    """

    message = "Transition not found from {current_state} to {to_state}"


class WorkflowValidationError(WorkflowBaseError):
    """
    Raised by the application when the transition fails
    """

    message = "Workflow validation failed"

    def __init__(self, errors=None, **kwargs):
        self.errors = errors
        super().__init__(**kwargs)

    def get_errors(self):
        return self.errors or []
