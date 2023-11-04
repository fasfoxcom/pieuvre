"""
events.py
=================================================
Hooks to generate events from transitions.
"""


class WorkflowEventManager:
    """
    Basic handler to generate events from transitions.
    Either implement ``_push_event`` or replace with a custom implementation

    Override ``supported_transitions`` to specify which transitions
    should generate a log:

    .. code-block::

       supported_transitions = {
           "order": {
               "event_type": "order-submitted",
               "data": get_submitted_data,
           }
       }

    """

    supported_transitions = {}

    def __init__(self, model):
        self.model = model

    def push_event(self, transition):
        transition_name = transition["name"]

        if transition_name not in self.supported_transitions:
            return

        event = self.get_event(transition_name)

        # Push event
        self._push_event(event)

    def get_event(self, transition_name):
        """
        Generate an event dictionary from the transition.

        Args:
            transition_name (str): transition name
        """
        return {
            "type": self.supported_transitions[transition_name]["event_type"],
            "data": self.supported_transitions.get(transition_name, dict())(),
        }

    def _push_event(self, event):
        """
        This method is to be overriden to push events to your backend.
        """
        pass
