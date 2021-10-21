import uuid

from unittest import TestCase

from pieuvre import (
    Workflow,
    InvalidTransition,
    TransitionDoesNotExist,
    ForbiddenTransition,
    TransitionNotFound,
    transition,
    on_enter_state_check,
    on_exit_state_check,
)


class MyOrder(object):
    """
    Use this object to mock a django model.

    After changing the value of the state, is_saved is True
    if save method is called.
    This allow us to check if the save is called or not.
    """

    def __init__(self, state="draft"):
        self.uuid = uuid.uuid4()
        self.is_saved = True
        self._state = state
        self.allow_submit = True
        self.allow_leaving_draft_state = True
        self.allow_entering_submitted_state = True

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        self.is_saved = False
        self._state = value

    def save(self):
        self.is_saved = True


class LoggingModel(object):

    logs = {}

    @classmethod
    def log(cls, **kwargs):
        cls.logs = kwargs


class MyWorkflow(Workflow):

    event_manager_classes = ()
    db_logging = True
    db_logging_class = LoggingModel

    states = ["draft", "submitted", "completed", "rejected"]

    transitions = [
        {"name": "submit", "source": "draft", "destination": "submitted"},
        {"name": "complete", "source": "submitted", "destination": "completed"},
        {"name": "reject", "source": "*", "destination": "rejected"},
    ]

    def before_submit(self):
        # To test later if this implementation is called
        setattr(self.model, "before_submit_called", True)

    @transition()
    def submit(self):

        # To test later if this implementation is called
        setattr(self.model, "submit_called", True)

    def after_submit(self, res):
        # To test later if this implementation is called
        setattr(self.model, "after_submit_called", True)

    def on_enter_submitted(self, transition):
        # To test later if this implementation is called
        setattr(self.model, "on_enter_submitted_called", True)

    def on_exit_draft(self, transition):
        # To test later if this implementation is called
        setattr(self.model, "on_exit_draft_called", True)

    def check_submit(self):
        return self.model.allow_submit

    @on_exit_state_check("draft")
    def check_leaving_draft(self):
        return self.model.allow_leaving_draft_state

    @on_enter_state_check("submitted")
    def check_entering_submitted(self):
        return self.model.allow_entering_submitted_state

    @on_enter_state_check("submitted")
    def another_submitted_check(self):
        return True


class TestWorkflow(TestCase):
    def setUp(self):
        self.model = MyOrder()
        self.workflow = MyWorkflow(model=self.model)

    def test_get_model_state(self):
        self.assertEqual(self.workflow._get_model_state(), "draft")

    def test_update_model_state(self):
        self.workflow.update_model_state("new_state")

        self.assertEqual(self.model.state, "new_state")

    def test_check_state(self):
        self.assertTrue(self.workflow._check_state("draft", "draft"))
        self.assertTrue(self.workflow._check_state("*", "draft"))
        self.assertTrue(self.workflow._check_state(["draft", "completed"], "draft"))
        self.assertFalse(self.workflow._check_state("completed", "draft"))
        self.assertFalse(self.workflow._check_state(["completed", "rejected"], "draft"))

    def test_pre_transition_check(self):
        valid_transition = {
            "name": "submit",
            "source": "draft",
            "destination": "submitted",
        }
        invalid_transition = {
            "name": "complete",
            "source": "submitted",
            "destination": "completed",
        }

        self.assertTrue(self.workflow._pre_transition_check(valid_transition))

        with self.assertRaises(InvalidTransition) as e:
            self.workflow._pre_transition_check(invalid_transition)
        e = e.exception
        self.assertEqual(e.kwargs["transition"], invalid_transition["name"])
        self.assertEqual(e.kwargs["current_state"], "draft")
        self.assertEqual(e.kwargs["to_state"], invalid_transition["destination"])

    def test_get_transition_by_name(self):
        self.assertEqual(
            self.workflow._get_transition_by_name("submit"),
            {"name": "submit", "source": "draft", "destination": "submitted"},
        )

        self.assertEqual(
            self.workflow._get_transition_by_name("invalid_transition"), {}
        )

    def test_is_transition(self):
        self.assertTrue(self.workflow.is_transition("submit"))

        self.assertFalse(self.workflow.is_transition("invalid_transition"))

    def test_finalize_transition(self):
        self.model.is_saved = False
        self.workflow.finalize_transition(
            {"name": "submit", "source": "draft", "destination": "submitted"}
        )

        self.assertTrue(self.model.is_saved)

    def test_on_enter_state(self):
        self.assertIsNone(
            self.workflow._on_enter_state(
                {"name": "reject", "source": "*", "destination": "rejected"}
            )
        )

        self.workflow._on_enter_state(
            {"name": "submit", "source": "draft", "destination": "submitted"}
        )
        self.assertTrue(self.model.on_enter_submitted_called)

    def test_on_exit_state(self):
        self.assertIsNone(
            self.workflow._on_exit_state(
                {"name": "reject", "source": "*", "destination": "rejected"}
            )
        )

        self.workflow._on_exit_state(
            {"name": "submit", "source": "draft", "destination": "submitted"}
        )
        self.assertTrue(self.model.on_exit_draft_called)

    def test_before_transition(self):
        self.assertIsNone(
            self.workflow._before_transition(
                {"name": "reject", "source": "*", "destination": "rejected"}
            )
        )

        self.workflow._before_transition(
            {"name": "submit", "source": "draft", "destination": "submitted"}
        )
        self.assertTrue(self.model.before_submit_called)

    def test_after_transition(self):
        self.assertIsNone(
            self.workflow._after_transition(
                {"name": "reject", "source": "*", "destination": "rejected"}, None
            )
        )

        self.workflow._after_transition(
            {"name": "submit", "source": "draft", "destination": "submitted"}, None
        )
        self.assertTrue(self.model.after_submit_called)

    def test_check_transition(self):
        transition_with_check = {
            "name": "submit",
            "source": "draft",
            "destination": "submitted",
        }
        transition_without_check = {
            "name": "complete",
            "source": "submitted",
            "destination": "completed",
        }

        self.assertTrue(
            self.workflow.check_transition_condition(transition_without_check)
        )

        # check is valid
        self.assertTrue(
            self.workflow.check_transition_condition(transition_with_check)
        )

        self.model.allow_submit = False
        with self.assertRaises(ForbiddenTransition) as e:
            self.workflow.check_transition_condition(transition_with_check)
        e = e.exception
        self.assertEqual(e.kwargs["transition"], transition_with_check["name"])
        self.assertEqual(e.kwargs["current_state"], "draft")
        self.assertEqual(e.kwargs["to_state"], transition_with_check["destination"])

    def test_execute_transition(self):
        self.model.is_saved = False

        self.workflow.submit()
        self.assertTrue(self.model.on_exit_draft_called)
        self.assertTrue(self.model.before_submit_called)
        self.assertTrue(self.model.submit_called)
        self.assertTrue(self.model.on_enter_submitted_called)
        self.assertTrue(self.model.after_submit_called)

        self.assertEqual(self.model.state, "submitted")
        self.assertTrue(self.model.is_saved)

    def test_run_transition(self):
        with self.assertRaises(TransitionDoesNotExist) as e:
            self.workflow.run_transition("does_not_exist")
        e = e.exception
        self.assertEqual(e.kwargs["transition"], "does_not_exist")

        self.workflow.run_transition("reject")
        self.assertEqual(self.model.state, "rejected")

    def test_log_db(self):
        pass

    def test_get_transition(self):
        self.assertEqual(
            self.workflow.get_transition("submitted"), self.workflow.submit
        )
        with self.assertRaises(TransitionNotFound) as e:
            self.workflow.get_transition("completed")
        self.assertEqual(
            str(e.exception), "Transition not found from draft to completed"
        )

    def test_get_next_available_states(self):
        self.assertEqual(
            self.workflow.get_next_available_states(),
            [
                {"state": "submitted", "transition": "submit", "transition_label": None},
                {"state": "rejected", "transition": "reject", "transition_label": None},
            ],
        )

        self.assertEqual(
            self.workflow.get_next_available_states("completed"),
            [{"state": "rejected", "transition": "reject", "transition_label": None}],
        )

    def test_get_next_available_states_with_condition(self):
        self.model.allow_entering_submitted_state = False
        # submitted state should not appear because it is forbidden by the check method
        self.assertEqual(
            self.workflow.get_next_available_states(return_all=False),
            [
                {"state": "rejected", "transition": "reject", "transition_label": None},
            ],
        )

    def test_get_next_available_states_with_ignored_condition(self):
        self.workflow.allow_entering_submitted_state = False
        # return_all is True by default, so all states should be returned even if the transition
        # is forbidden by the check
        self.assertEqual(
            self.workflow.get_next_available_states(),
            [
                {"state": "submitted", "transition": "submit", "transition_label": None},
                {"state": "rejected", "transition": "reject", "transition_label": None},
            ],
        )