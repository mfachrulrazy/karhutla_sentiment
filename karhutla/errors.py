class AnalysisError(Exception):
    """Error yang sudah diantisipasi dan dapat ditampilkan kepada pengguna untuk ditindaklanjuti."""

    def __init__(self, message: str, status_code: int = 422, code: str = "analysis_error"):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
