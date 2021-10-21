# Pieuvre

Pieuvre is a simple yet powerful workflow engine library initially developed by [Kosc Telecom](https://www.kosc-telecom.fr/en/), aimed at Django but also usable as a standalone engine.

## Getting Started

### Prerequisites

- Python 3.6+
- Optional: Django 1.11+

### Installing

```
pip install pieuvre
```

## Running the tests

Pieuvre's tests could be quite improved. However you can have a look! Install the dependencies to run the tests:
```
pip install pieuvre[test]
```

Then run them with:
```
pytest
```

## Usage

Pieuvre allows you to attach *workflows* to backend models (built-in support for Django models, but any class implementing a ``save`` method will work).

Pieuvre workflows define a set of states and transitions and allow quick implementation of custom hooks for each transition. Pieuvre lets you implement complex business logic backed by any storage implementation.

Example:

```
from pieuvre import Workflow, WorkflowEnabled

ROCKET_STATES = Choices(
	("IN_FACTORY", "in_factory", "in factory"),
	("ON_LAUNCHPAD", "on_launchpad", "on launchpad"),
	("IN_SPACE", "in_space", "in space"),
	("ABORTED", "aborted", "back to the factory")
)

ROCKET_BRANDS = Choices(
	("ARIANESPACE", "arianespace", "Arianespace"),
	("SPACEX", "spacex", "Space X")
)

class Rocket(WorkflowEnabled, models.Model):
    """
    Django model that implements a workflow.
    """
	state = models.CharField(default=ROCKET_STATES.IN_FACTORY, choices=ROCKET_STATES)
	fuel = models.PositiveIntegerField(default=0)
	launch_date = models.DateTimeField(null=True)
    load = models.DecimalField(default=0, decimal_places=5, max_digits=10)
	brand = models.CharField()

	def get_workflow_class(self):
        # This method is useful to define multiple workflows for a single model
        # If it is not defined, the attribute `workflow_class` is used
		if self.brand == ROCKET_BRANDS.ARIANESPACE:
			return Ariane5Workflow()
		return RocketWorkflow()


class RocketWorkflow(Workflow):
    """
    The actual workflow, where the business logic is.
    """
	states = ROCKET_STATES
	transitions = [
		{
			"source": ROCKET_STATES.IN_FACTORY,
			"destination": ROCKET_STATES.ON_LAUNCHPAD,
			"name": "prepare_for_launch",
			"label": "Prepare for launch"
		},
		{
			"source": ROCKET_STATES.ON_LAUNCHPAD,
			"destination": ROCKET_STATES.IN_SPACE,
			"name": "launch",
			"label": "Launch the rocket",
		},
		{
			"source": ROCKET_STATES.ON_LAUNCHPAD,
			"destination": ROCKET_STATES.ABORTED,
			"name": "abort",
			"label": "Abort the mission",
		},

	]

	@property
	def has_fuel(self):
		return self.fuel >= 2000

	def _refill(self):
		self.fuel += 1000

	def prepare_for_launch(self):
        # This is a transition with custom code. It is possible, but not required.
		if self.model.fuel < 10:
			self._refill()

	def check_launch(self):
		# This method is automatically called before the transition "launch" is executed
		return self.has_fuel

	def check_abort(self):
		return not self.has_fuel

	def launch(self):
		self.model.launch_date = timezone.now()

class Ariane5Workflow(RocketWorkflow):
	@on_enter_state_check(ROCKET_STATES.IN_SPACE)
	def check_can_go_to_space(self):
		if self.model.load < 220:
			raise WorkflowValidationError("Put some load on that rocket!")

if __name__ == "__main__":
	rocket = Rocket.objects.create(brand=ROCKET_BRANDS.ARIANESPACE)
	rocket.workflow.prepare_for_launch()
	rocket.workflow.launch()
	assert rocket.launch_date is not None

```

Workflows can be extended and dynamically instantiated. This lets you implement multiple workflows backed by a single model, which allows powerful business logic customization as well as a true split between the model definition and its behavior.

Workflows just need a field to store their state (``state`` by default, but easily overridable with ``state_field_name``). It is thus possible to let different workflows coexist on the same model, for instance a workflow modeling the launch procedure of a rocket and an other workflow modeling the launch in orbit of its payload.

You must provide both states and transitions in order to provide a human-friendly representation of the state name (which would not be available if the state name was strictly inferred from the transitions).

### Customizing the behavior

#### Transitions

Transitions are defined as a list of dictionaries, with the following properties:

- `source`: str or list, name(s) of the source(s) state(s),
- `destination`: str, name of the destination state. A transition may only have a single destination (otherwise the engine cannot know which one to pick),
- `name`: str, internal name of the transition. Must be a valid Python identifier,
- `label`: str (optional), human-friendly name of the transition.

Transitions may (but need not) be implemented with a method.
To implement custom behavior, just define a method on the workflow class named after the transition `name` attribute.

#### Checks

When you try to run a transition, Pieuvre automatically checks that it is allowed to do so. 
For that purpose, it runs the following checks:

- the current workflow state belongs to the required transition source(s),
- any method on the workflow decorated with ``@on_enter_state_check("<transition_destination_state_name>")`` returns `True`
- any method on the workflow decorated with ``@on_exit_state_check("<current_state_name>")`` returns `True`
- if there is a `check_<transition_name>` method defined on the workflow, it returns `True`

Checks **must not** have side effects as they *will* be called multiple times.

#### Hooks

In addition to the (optional) transition method implementation, custom code can be easily plugged:

- when entering and leaving a state through ``on_enter_<state_name>`` and ``on_exit_<state_name>`` methods
- or alternatively, through any method on the workflow decorated with ``@on_enter_state_hook("<transition_destination_state_name>")`` and ``@on_exit_state_hook("<current_state_name>")``. Both ways are equivalent.

## Contributing

Any contribution is welcome through Github's Pull requests.

Ideas:
- store a workflow version to allow graceful workflow upgrades while maintaining workflow consistency on existing objects
- support for other ORM backends

## Authors

* **Saïd Ben Rjab** - [Kosc Telecom](https://www.kosc-telecom.fr/)
* **lerela** - [Fasfox](https://fasfox.com/)

## License

This project is licensed under the Apache License - see the [LICENSE.md](LICENSE.md) file for details
