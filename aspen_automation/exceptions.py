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
