# Pieuvre changelog

## dev

- Implement `advance_workflow` to automatically advance the workflow and raise an exception if multiple (or zero) transitions are available
- Rename `finalize_transition` to `_finalize_transition` as this is a private method
- `get_available_transitions` and `get_next_available_states` may only return valid transitions if called with the kwarg `return_all=False`
- `get_next_available_states` returns dictionaries containing the name of the transition needed to reach the given state, and the transition label as `transition_label` (backward incompatible change: was `label` before)
