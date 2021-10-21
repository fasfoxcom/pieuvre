# Pieuvre

Pieuvre is a simple yet powerful workflow engine library developed by [Kosc Telecom](https://www.kosc-telecom.fr/en/), aimed at Django but also usable in standalone mode.

## Getting Started

### Prerequisites

- Python 3.5+
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

### Usage

Pieuvre allows you to attach *workflows* to backend models (built-in support for Django models, but any class implementing a ``save`` method will work).

Pieuvre workflows define a set of states and transitions and allow quick implementation of custom hooks for each transition. Pieuvre lets you implement complex business logic backed by any storage implementation.

Custom behavior can be set:
- for transitions (by defining a method name with the transition name),
- when a state is entered (``on_enter_<state_name>``)`or exited (``on_exit_<state_name>``)
- before (``before_<transition_name>``) or after (``after_<transition_name>``) a transition

Those hooks are dynamically called and require no specific setup.

Checks allow you to enforce specific conditions for entering or leaving a state.

Example:

```
from pieuvre import Workflow, WorkflowEnabled

ROCKET_STATES = Choices(
	"IN_FACTORY", "in_factory", "in factory",
	"ON_LAUNCHPAD", "on_launchpad", "on launchpad",
	"IN_SPACE", "in_space", "in space"
)

ROCKET_BRANDS = Choices(
	"ARIANESPACE", "arianespace", "Arianespace",
	"SPACEX", "spacex", "Space X"
)

class Rocket(WorkflowEnabled, models.Model):
	state = models.CharField(default=ROCKET_STATES.IN_FACTORY, choices=ROCKET_STATES)
	fuel = models.PositiveIntegerField(default=0)
	launch_date = models.DateTimeField(null=True)
	brand = models.CharField()

	def get_workflow_class(self):
		if self.brand == ROCKET_BRANDS.ARIANESPACE:
			return Ariane5Workflow()
		return RocketWorkflow()


class RocketWorkflow(Workflow):
	states = ROCKET_STATES
	transitions = [
		{
			"source": ROCKET_STATES.IN_FACTORY,
			"destination": ROCKET_STATES.ON_LAUNCHPAD,
			"name": "prepare_for_launch"
		},
		{
			"source": ROCKET_STATES.ON_LAUNCHPAD,
			"destination": ROCKET_STATES.IN_SPACE,
			"name": "launch"
		}
	]

	def _refill(self):
		self.fuel += 1000

	def prepare_for_launch(self):
		if self.model.fuel < 10:
			self._refill()

	def launch(self):
		self.model.launch_date = timezone.now()

class Ariane5Workflow(RocketWorkflow):
	@on_enter_state_check(ROCKET_STATES.IN_SPACE)
	def check_launch(self):
		if self.model.fuel < 220:
			raise WorkflowValidationError("Not enough fuel to go up!")

if __name__ == "__main__":
	rocket = Rocket.objects.create(brand=ROCKET_BRANDS.ARIANESPACE)
	rocket.workflow.prepare_for_launch()
	rocket.workflow.launch()
	assert rocket.launch_date is not None

```

Workflows can be extended and dynamically instanciated. This lets you implement multiple workflows backed by a single model, which allows powerful business logic customization as well as a true split between the model definition and its behavior.

Workflows just need a field to store their state (``state`` by default, but easily overridable with ``state_field_name``). It is thus possible to let different workflows coexist on the same model, for instance a workflow modelizing the launch procedure of a rocket and an other workflow modelizing the launch in orbit of its payload.

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

