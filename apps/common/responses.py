from rest_framework.response import Response


def success(data=None, message="ok", status_code=200):
    return Response({"success": True, "message": message, "data": data}, status=status_code)


def failure(message="error", errors=None, status_code=400):
    return Response({"success": False, "message": message, "errors": errors or {}}, status=status_code)

