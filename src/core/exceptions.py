from fastapi import HTTPException, status


class HARFileException(HTTPException):
    def __init__(
        self,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        detail: str = "Invalid HAR file",
    ):
        super().__init__(status_code=status_code, detail=detail)


class InvalidHARFileException(HARFileException):
    def __init__(self, detail: str = "Invalid HAR file format"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class HARFileProcessingException(HARFileException):
    def __init__(self, detail: str = "Error processing HAR file"):
        super().__init__(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)


class APICallNotFoundException(HARFileException):
    def __init__(self, call_id: int):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API call with ID {call_id} not found",
        )


class APICallReplayException(HARFileException):
    def __init__(self, detail: str = "Error replaying API call"):
        super().__init__(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)


class CredentialsException(HTTPException):
    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class PermissionDeniedException(HTTPException):
    def __init__(self, detail: str = "Not enough permissions"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        ) 