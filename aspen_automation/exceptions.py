from typing import List, Dict, Any

class ValidationError(Exception):
    """Custom exception for validation failures with detailed report."""
    def __init__(self, report: Dict[str, Any]):
        self.report = report
        self.errors = report.get("errors", [])
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        error_count = len([e for e in self.errors if e["severity"] == "error"])
        warning_count = len([e for e in self.errors if e["severity"] == "warning"])
        
        msg = f"Validation failed with {error_count} errors and {warning_count} warnings:\n"
        
        for error in self.errors:
            severity = f"[{error['severity'].upper()}]"
            location = error.get("location", "unknown")
            message = error.get("message", "No details")
            suggestion = error.get("suggestion", "")
            
            msg += f"\n{severity} {location}\n"
            msg += f"  {message}\n"
            if suggestion:
                msg += f"  \u2192 {suggestion}\n"
        
        return msg

class AspenConnectionError(Exception):
    """Raised when connection to Aspen Plus fails."""
    def __init__(self, message: str, details: Any = None):
        self.details = details
        super().__init__(message)

class BuildError(Exception):
    """Raised when simulation build (INP/COM) fails."""
    def __init__(self, message: str, build_mode: str, mechanism_tried: str, diagnostics: Any = None):
        self.build_mode = build_mode
        self.mechanism_tried = mechanism_tried
        self.diagnostics = diagnostics
        super().__init__(message)

class SimulationError(Exception):
    """Raised when simulation execution fails."""
    def __init__(self, message: str, convergence_status: str, diagnostics: Any = None):
        self.convergence_status = convergence_status
        self.diagnostics = diagnostics
        super().__init__(message)

