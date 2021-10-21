"""
core.py
=================================================
Base workflow implementation
"""

import logging

from functools import partial
from typing import Union, Optional, List, Sequence

from .constants import (
    ON_ENTER_STATE_CHECK_DECORATOR,
    ON_EXIT_STATE_CHECK_DECORATOR,
    ON_ENTER_STATE_HOOK_DECORATOR,
    ON_EXIT_STATE_HOOK_DECORATOR,
    ON_ENTER_STATE_PREFIX,
    ON_EXIT_STATE_PREFIX,
    BEFORE_TRANSITION_PREFIX,
    AFTER_TRANSITION_PREFIX,
    CHECK_TRANSITION_PREFIX,
)
from .exceptions import (
    ForbiddenTransition,
    InvalidTransition,
    TransitionDoesNotExist,
    TransitionNotFound,
    TransitionUnavailable,
    TransitionAmbiguous,
)

try:
    from django.db import transaction
    from django.utils.timezone import now
except ImportError:
    # Fallback if Django is not installed
    from .utils import transaction, now


logger = logging.getLogger(__name__)


def update_decorated_functions(obj: dict, states, function):
    for state in states:
        if state in obj:
            obj[state].append(function)
        else:
            obj[state] = [
                function,
            ]


class Workflow:
    """
    Workflow base implementation.

    Attributes:
        initial_state(string): initial state of the model
        states(list): The list of states, it can be a list of strings or dicts or a mix of them. Example:

                ``states = ["draft", "submitted", "completed", "rejected"]``
        transitions(list): List of transitions. Example:

            .. code-block::

               transitions = [
                   {
                       "name": "submit",
                       "source": "draft",
                       "destination": "submitted",
                       "date_field": "submission_date"
                   },
                   {
                       "name": "complete",
                       "source": "submitted",
                       "destination": "completed"
                   }
               ]

    """

    wildcard_state = "*"
    state_field_name = "state"
    states = []
    transitions = []
    db_logging = False
    db_logging_class = None

    events = {
        # "name": "method name"
    }

    event_manager_classes = ()

    def __init__(self, model):

        self.model = model
        self._check_initial_state()
        self.event_managers = [
            klass(model) for klass in self._get_event_manager_classes()
        ]

        super().__init__()

        self._on_enter_state_check = {}
        self._on_exit_state_check = {}
        self._on_enter_state_hook = {}
        self._on_exit_state_hook = {}

        self._gather_decorated_functions()

    def _gather_decorated_functions(self):
        """
        Construct _on_enter_state_checks and _on_exit_state_checks.
        """

        for attr in dir(self):
            if attr.startswith("__"):
                continue

            func = getattr(self, attr)
            if not callable(func):
                continue

            for deco in (
                ON_ENTER_STATE_CHECK_DECORATOR,
                ON_EXIT_STATE_CHECK_DECORATOR,
                ON_ENTER_STATE_HOOK_DECORATOR,
                ON_EXIT_STATE_HOOK_DECORATOR,
            ):

                if hasattr(func, deco):
                    update_decorated_functions(
                        getattr(self, deco), getattr(func, deco), func
                    )

    def process_event(self, name, data):
        """
        Helper to dispatch an event to a workflow method.

        Args:
            name (str): event name
            data (dict): event data

        Returns:
            Any: the method output
        """
        if name not in self.events:
            return

        func = getattr(self, self.events[name])
        return func(data)

    def _check_initial_state(self):
        pass

    def _get_event_manager_classes(self):
        """
        Return the list of event manager classes.

        Returns:
            list: List of event manager classes
        """
        return self.event_manager_classes

    def _get_model_state(self) -> str:
        """
        Get the state of the workflow using the state name defined
        in the class

        Returns:
            str: current workflow state
        """

        return getattr(self.model, self.state_field_name)

    @property
    def state(self) -> str:
        """
        Return the current workflow state.

        Returns:
            str: current workflow state
        """
        return self._get_model_state()

    def _update_model_state(self, value):
        """
        Update the state of the model

        Args:
            value (str): new state value
        """
        logger.debug("Updating model {} to {}".format(self.state_field_name, value))

        setattr(self.model, self.state_field_name, value)

    def update_transition_date(self, transition):
        """
        This function is called after a transition with the transition
        dictionary. If this dictionary has a ``date_field`` attribute,
        update this field of the model with current date.

        Args:
            transition (dict): the transition dictionary as defined
            in the workflow.
        """
        if "date_field" not in transition:
            return
        setattr(self.model, transition["date_field"], now())

    @classmethod
    def _check_state(cls, source: Union[List[str], str], state: str) -> bool:
        """

        Check if the state of the model is compatible the provided source

        Args:
            source (str or list): source state
            state (str): destination state

        Returns:
            True if state matches the given source
        """
        if source == cls.wildcard_state:
            return True

        return state in source if isinstance(source, list) else source == state

    def _pre_transition_check(self, transition):
        """
        Check if transition can be performed from the current state.

        Args:
            transition (dict): desired transition
        Returns:
            None
        Raises:
            InvalidTransition
        """

        if self._check_state(transition["source"], self._get_model_state()):
            return True

        raise InvalidTransition(
            transition=transition["name"],
            current_state=self._get_model_state(),
            to_state=transition["destination"],
        )

    @classmethod
    def _get_transition_by_name(cls, name):
        """

        Return the transition dict by name

        Args:
            name (str): name of the transition

        Returns:
            dict: dictionary describing the transition, or empty dict if
                  the transition does not exist.
        """
        try:
            return next(trans for trans in cls.transitions if trans["name"] == name)
        except StopIteration:
            return {}

    @classmethod
    def is_transition(cls, name):
        """
        Check if an attribute is a transition

        Args:
            name (str): name of the transition

        Returns:
            bool: True if the name matches a transition, False otherwise
        """
        return bool(cls._get_transition_by_name(name))

    def _finalize_transition(self, transition):
        """
        Update the model state and save it.
        """
        self.update_transition_date(transition)
        logger.debug("Saving model.")
        # This could be optimized with ``update_fields`` however the
        # library cannot know which fields were modified.
        self.model.save()

    def _on_enter_state(self, transition):
        """
        Call hooks when entering a state.

        Args:
            transition (dict): the transition to enter
        """
        state = transition["destination"]
        functions = self._on_enter_state_hook.get(state, [])
        _on_enter_state = getattr(
            self, "{}{}".format(ON_ENTER_STATE_PREFIX, state), None
        )

        if _on_enter_state:
            functions.append(_on_enter_state)

        logger.debug("Entering {} {}".format(self.state_field_name, state))
        for func in functions:
            func(transition)

    def _on_exit_state(self, transition):
        """
        Call hooks when exiting a state.

        Args:
            transition (dict): the transition to enter
        """
        state = self._get_model_state()
        functions = self._on_exit_state_hook.get(state, [])
        _on_exit_state = getattr(self, "{}{}".format(ON_EXIT_STATE_PREFIX, state), None)
        if _on_exit_state:
            functions.append(_on_exit_state)

        logger.debug("Leaving {} {}".format(self.state_field_name, state))
        for func in functions:
            func(transition)

    def _before_transition(self, transition, *args, **kwargs):
        """
        Call hooks before running a transition.

        Args:
            transition (dict): the transition to enter
        """

        before_transition = getattr(
            self, "{}{}".format(BEFORE_TRANSITION_PREFIX, transition["name"]), None
        )
        if not before_transition:
            return

        logger.debug("Before transition {}".format(transition["name"]))
        before_transition(*args, **kwargs)

    def _after_transition(self, transition, result):
        """
        Call hooks after running a transition

        Args:
            transition (dict): the transition to enter
        """
        after_transition = getattr(
            self, "{}{}".format(AFTER_TRANSITION_PREFIX, transition["name"]), None
        )
        if not after_transition:
            return

        logger.debug("After transition {}".format(transition["name"]))
        after_transition(result)

    def _check_on_enter_state(self, state):
        return all(func() for func in self._on_enter_state_check.get(state, []))

    def _check_on_exit_state(self, state):
        return all(func() for func in self._on_exit_state_check.get(state, []))

    def check_transition_condition(
        self, transition, *args, raise_exceptions=True, **kwargs
    ):
        """
        Check that the transition is allowed:
        * Call condition function.
        * Call entering new state conditions
        * Call exiting old state conditions

        Args:
            transition (dict): transition to check

        Raises:
            ForbiddenTransition: if the transition is forbidden
        """
        valid_transition = True
        check_transition_function = getattr(
            self, "{}{}".format(CHECK_TRANSITION_PREFIX, transition["name"]), None
        )

        if check_transition_function and not check_transition_function(*args, **kwargs):
            valid_transition = False

        if (
            valid_transition
            and self._check_on_enter_state(transition["destination"])
            and self._check_on_exit_state(self._get_model_state())
        ):
            return True

        if raise_exceptions:
            raise ForbiddenTransition(
                transition=transition["name"],
                current_state=self._get_model_state(),
                to_state=transition["destination"],
            )

        return False

    def pre_transition(self, name, *args, **kwargs):
        transition = self._get_transition_by_name(name)

        #  Check if transition is valid
        self._pre_transition_check(transition)

        #  Check conditions if exist
        self.check_transition_condition(transition, *args, **kwargs)

        # Call before transition
        self._before_transition(transition, *args, **kwargs)

        # Call on_exit of the current state
        self._on_exit_state(transition)

    def post_transition(self, name, result, *args, **kwargs):
        transition = self._get_transition_by_name(name)
        source = self._get_model_state()

        # Change state
        self._update_model_state(transition["destination"])

        self._on_enter_state(transition)

        self._after_transition(transition, result)

        # save model
        self._finalize_transition(transition)

        # log in db
        # transition can be from a specific state or from a list of states or
        # from any state for logging we send the exact source state
        _transition = dict(transition, source=source)
        self._log_db(_transition, *args, **kwargs)

        # Create events
        self.create_events(_transition)

    @transaction.atomic
    def default_transition(self, name, *args, **kwargs):
        """
        Transition will be executed by following these steps:
            1) Check if transition is valid
            2) Check conditions if any
            3) Call before transition hook
            4) Call on_exit hook of the current state
            5) Call the transition if implemented
            5) Change state
            6) Call on_enter of the destination state
            7) Call after transition hook
            8) Save model

        Args:
            name (str): transition name
        """
        self.pre_transition(name, *args, **kwargs)
        self.post_transition(name, None, *args, **kwargs)

    def run_transition(self, name, *args, **kwargs):
        """
        Private method: perform the transition.
        TBD: is this method really needed?
        """

        # Check transition
        if not self.is_transition(name):
            raise TransitionDoesNotExist(transition=name)

        # TODO: handle the case when the names of the transition and
        # the method are different
        trans = getattr(self, name, None)
        if trans:
            return trans(*args, **kwargs)

        return self.default_transition(name, *args, **kwargs)

    def rollback(self, current_state, target_state, exc):
        self._update_model_state(current_state)

    def get_all_transitions(self):
        """
        Return the transitions list.

        Returns:
           list: list of all transitions
        """
        return self.transitions

    def get_available_transitions(
        self, state: Optional[str] = None, return_all: bool = True
    ):
        """
        Get the list of available transitions from a given state,
        If no state is given, return available transitions from current state

        Args:
            state (str): optional: source state
            return_all (bool): optional: return all transitions from the source state
            and do not check if the transitions are valid (useful is provided state
            is not the current state, as checks cannot be performed)

        Returns:
            list: list of transitions available from the given or current state
        """

        state = state or self._get_model_state()

        return [
            trans
            for trans in self.transitions
            if self._check_state(trans["source"], state)
            and (
                return_all
                or self.check_transition_condition(trans, raise_exceptions=False)
            )
        ]

    def get_next_available_states(
        self, state: Optional[str] = None, return_all: bool = True
    ) -> Sequence[dict]:
        """
        Return the list of available next states from a given state
        If no state is given, the current state will be used

        Args:
            state (str): optional: source state
            return_all (bool): optional: return all states and do not check if
            the transitions to reach them are valid (useful is provided state
            is not the current state, as checks cannot be performed)

        Returns:
            list: list of dictionaries. Each dictionary contains the name
            of a state reachable from the given or current state ("state"),
            the name of the transition ("transition") and the label
            of the transition if it exists ("transition_label")
        """
        state = state or self._get_model_state()

        return [
            {
                "state": trans["destination"],
                "transition": trans["name"],
                "transition_label": trans.get("label"),
            }
            for trans in self.get_available_transitions(
                state=state, return_all=return_all
            )
        ]

    def get_transition(self, target_state: str) -> dict:
        """
        Return the transition to call to get to the target state

        Args:
            target_state (str): state to reach

        Returns:
            dict: transition that allows the workflow to
            reach the desired state.
        """
        state = self._get_model_state()

        potential_transition = [
            trans
            for trans in self.get_available_transitions(state=state)
            if trans["destination"] == target_state
        ]

        if potential_transition:
            # Return first transition
            return getattr(self, potential_transition[0]["name"])

        raise TransitionNotFound(current_state=state, to_state=target_state)

    def _get_next_transition(self):
        """
        Return the next transition that can be reached.
        The workflow must be unambiguous (a single transition must be possible).
        """
        state = self._get_model_state()
        transitions = self.get_available_transitions(state, return_all=False)
        if not transitions:
            raise TransitionUnavailable(current_state=state)
        elif len(transitions) > 1:
            raise TransitionAmbiguous(l=len(transitions))
        return transitions[0]

    def advance_workflow(self):
        """
        Advance the workflow.
        """
        transition = self._get_next_transition()
        getattr(self, transition["name"])()

    def _log_db(self, transition, *args, **kwargs):
        """
        Log transition to DB if enabled.

        Args:
            transition(dict): the current transition
        """
        if not self.db_logging:
            return

        params = {"args": args, "kwargs": kwargs}

        self.db_logging_class.log(
            transition=transition["name"],
            from_state=transition["source"],
            to_state=transition["destination"],
            model=self.model,
            params=params,
        )

    def create_events(self, transition):
        if not self.event_managers:
            return

        for manager in self.event_managers:
            manager.push_event(transition)

    def __getattr__(self, item):
        try:
            return object.__getattribute__(self, item)

        except AttributeError:
            if self.is_transition(item):
                return partial(self.default_transition, item)
            raise

    @classmethod
    def generate_graph(cls, dpi=150, edges_conf={}):
        """
        This method generates a Graphviz visualisation of a workflow,
        if pydot is installed and there is at least one transition.
        """
        try:
            import pydot
        except ImportError:
            return

        graph = pydot.Dot(graph_type="digraph", dpi=dpi)
        is_empty = True

        for trans in cls.transitions:
            sources = trans["source"]
            if not isinstance(sources, list):
                sources = [sources]

            for source in sources:
                is_empty = False
                edge = pydot.Edge(
                    source, trans["destination"], label=trans["name"], **edges_conf
                )
                graph.add_edge(edge)

        if not is_empty:
            return graph


class Transition:
    """
    @transition decorator.
    """

    def __call__(self, func):
        #  TODO: Check if it is a valid transition
        @transaction.atomic
        def wrapped_func(workflow, *args, **kwargs):
            workflow.pre_transition(func.__name__, *args, **kwargs)
            result = func(workflow, *args, **kwargs)
            workflow.post_transition(func.__name__, result, *args, **kwargs)
            return result

        return wrapped_func


class BaseDecorator:
    """
    Base class for hook decorators.
    """

    type = None

    def __init__(self, state):
        self.states = (
            state
            if isinstance(state, list)
            else [
                state,
            ]
        )
        super().__init__()

    def __call__(self, func):
        setattr(func, self.type, self.states)
        return func


class OnEnterStateCheck(BaseDecorator):
    """
    Wrap a function with this decorator so that it is ran before a transition
    that would enter the given state. This function must return True to carry
    on with the transition.

    Example:

    .. code-block::

       @on_enter_state_check(ROCKET_STATES.ON_LAUNCHPAD)
       def has_enough_fuel(self, result):
           if self.model.fuel > 10:
               return True
           # Transition is aborted if there is not enough fuel
    """

    type = ON_ENTER_STATE_CHECK_DECORATOR


class OnExitStateCheck(BaseDecorator):
    """
    Wrap a function with this decorator so that it is ran before a transition
    that would exit the given state. This function must return True to carry
    on with the transition.

    Example:

    .. code-block::

       @on_exit_state_check(ROCKET_STATES.ON_LAUNCHPAD)
       def is_it_a_beautiful_day(self, result):
           if datetime.today().day == 7:
                return True
           # Transition is aborted if the day is not the 7th
    """

    type = ON_EXIT_STATE_CHECK_DECORATOR


class OnEnterState(BaseDecorator):
    """
    Wrap a function with this decorator to run it before
    entering a state, after the transition is ran.

    Example:

    .. code-block::

       @on_enter_state(ROCKET_STATES.ON_LAUNCHPAD)
       def start_countdown(self, result):
           print("Launch is imminent!")
    """

    type = ON_ENTER_STATE_HOOK_DECORATOR


class OnExitState(BaseDecorator):
    """
    Wrap a function with this decorator to run it after
    exiting a state, before the transition is ran.

    Example:

    .. code-block::

       @on_exit_state(ROCKET_STATES.ON_LAUNCHPAD)
       def warn_aliens(self, result):
           print("Beware aliens, a rocket has left the launchpad!")
    """

    type = ON_EXIT_STATE_HOOK_DECORATOR
