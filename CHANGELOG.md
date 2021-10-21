# Pieuvre changelog

## dev

- `get_available_transitions` and `get_next_available_states` may only return valid transitions if called with the kwarg `return_all=False`
- `get_next_available_states` returns dictionaries containing the name of the transition needed to reach the given state, and the transition label as `transition_label` (backward incompatible change: was `label` before)
