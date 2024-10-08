class AuditMixin:
    """Mixin to assist with auditing views."""

    def run_audit(self):
        raise NotImplementedError("AuditMixin.run_audit() must be implemented in a subclass")

    def get_context_data(self, **kwargs):
        """Run the audit and add it to the context."""
        context = super().get_context_data(**kwargs)
        # Run the audit.
        audit_results = self.run_audit()
        context["verified_table"] = audit_results.get_verified_table()
        context["errors_table"] = audit_results.get_errors_table()
        context["needs_action_table"] = audit_results.get_needs_action_table()
        context["audit_results"] = audit_results
        return context
