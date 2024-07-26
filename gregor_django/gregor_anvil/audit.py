from abc import ABC, abstractmethod, abstractproperty


class GREGORAuditResult(ABC):
    """Abstract base class to hold an audit result for a single check.

    Subclasses of this class are typically also dataclasses. They can define any number of
    fields that track information about an audit and its result. The companion RPIMEDAudit
    class `verified`, `needs_action`, and `errors` attributes should store lists of
    GREGORAuditResult instances.

    Typical usage:
        @dataclass
        class MyAuditResult(GREGORAuditResult):

            some_value: str

            def get_table_dictionary(self):
                return {"some_value": self.some_value}

        audit_result = MyAuditResult(some_value="the value for this result")
    """

    @abstractmethod
    def get_table_dictionary(self):
        """Return a dictionary representation of the result."""
        ...  # pragma: no cover


class GREGORAudit(ABC):
    """Abstract base class for GREGOR audit classes.

    This class is intended to be subclassed in order to store all results for a GREGOR audit.
    Subclasses should implement the _run_audit class method to perform the audit. To run the
    audit itself, one can use the run_audit method, which calls the _run_audit method in
    addition to performs completion checks. Typically, _run_audit should loop over a set of
    instances or checks, and store the results in the `verified`, `needs_action`, and `errors`
    attributes.

    Attributes:
        verified: A list of GREGORAuditResult subclasses instances that have been verified.
        needs_action: A list of GREGORAuditResult subclasses instances that some sort of need action.
        errors: A list of GREGORAuditResult subclasses instances where an error has been detected.
        completed: A boolean indicator of whether the audit has been run.
    """

    # TODO: Add add_verified_result, add_needs_action_result, add_error_result methods. They should
    # verify that the result is an instance of GREGORAuditResult (subclass).

    @abstractproperty
    def results_table_class(self):
        return ...  # pragma: no cover

    def __init__(self):
        self.completed = False
        # Set up lists to hold audit results.
        self.verified = []
        self.needs_action = []
        self.errors = []
        self.completed = False

    @abstractmethod
    def _run_audit(self):
        """Run the audit and store results in `verified`, `needs_action`, and `errors` lists.

        This method should typically loop over a set of instances or checks, and store the
        results in the `verified`, `needs_action`, and `errors` attributes. The results should
        be instances of GREGORAuditResult subclasses. This method should not be called directly.

        When deciding which list to store a result in, consider the following:
        - verified: The result is as expected and no action is needed.
        - needs_action: The result is expected for some reason, but action is needed.
        - errors: The result is not expected and action is likely needed.
        """
        ...  # pragma: no cover

    def run_audit(self):
        """Run the audit and mark it as completed."""
        self._run_audit()
        self.completed = True

    def get_all_results(self):
        """Return all results in a list, regardless of type.

        Returns:
            list: A combined list of `verified`, `needs_action`, and `errors` results.
        """
        self._check_completed()
        return self.verified + self.needs_action + self.errors

    def _check_completed(self):
        if not self.completed:
            raise ValueError("Audit has not been completed. Use run_audit() to run the audit.")

    def get_verified_table(self):
        """Return a table of verified audit results.

        The subclass of the table will be the specified `results_table_class`.

        Returns:
            results_table_class: A table of verified results.
        """
        self._check_completed()
        return self.results_table_class([x.get_table_dictionary() for x in self.verified])

    def get_needs_action_table(self):
        """Return a table of needs_action audit results.

        The subclass of the table will be the specified `results_table_class`.

        Returns:
            results_table_class: A table of need action results.
        """
        self._check_completed()
        return self.results_table_class([x.get_table_dictionary() for x in self.needs_action])

    def get_errors_table(self):
        """Return a table of error audit results.

        The subclass of the table will be the specified `results_table_class`.

        Returns:
            results_table_class: A table of error results.
        """
        self._check_completed()
        return self.results_table_class([x.get_table_dictionary() for x in self.errors])

    def ok(self):
        """Check audit results to see if action is needed.

        Returns:
            bool: True if no action is needed, False otherwise.
        """
        self._check_completed()
        return len(self.errors) + len(self.needs_action) == 0
