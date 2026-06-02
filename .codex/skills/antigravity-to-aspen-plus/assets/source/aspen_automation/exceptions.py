class ValidationError(Exception):
    """Raised when specification validation fails."""
    def __init__(self, message: str, report: dict):
        self.report = report
        super().__init__(message)

class ParserError(Exception):
    """Raised when parsing fails."""
    pass

class SchemaError(Exception):
    """Raised when schema structure is invalid."""
    pass

class ExtractionError(Exception):
    """Raised when COM tree navigation fails to retrieve a required result node."""
    def __init__(self, message: str, path: str = None):
        self.path = path
        super().__init__(message)

class AspenConnectionError(Exception):
    """Raised when a connection to Aspen Plus cannot be established or drops."""
    def __init__(self, message: str, details: Exception = None):
        self.details = details
        super().__init__(message)

class AspenNotRunningError(AspenConnectionError):
    """Raised when Aspen Plus is not running and cannot be reached via COM."""
    def __init__(self):
        super().__init__(
            "Aspen Plus is not running. "
            "Please launch Aspen 14 from the Porticada portal "
            "(https://porticada.unican.es) and try again."
        )

class BuildError(Exception):
    """Raised when the flowsheet simulation fails to initialize or load properly."""
    def __init__(self, message: str, build_mode: str = "unknown", mechanism_tried: str = "unknown", diagnostics: dict = None):
        self.build_mode = build_mode
        self.mechanism_tried = mechanism_tried
        self.diagnostics = diagnostics or {}
        super().__init__(message)

class SimulationError(Exception):
    """Raised when the simulation run fails or times out."""
    def __init__(self, message: str, convergence_status: str = "unknown"):
        self.convergence_status = convergence_status
        super().__init__(message)
