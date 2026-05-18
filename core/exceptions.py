class NotFoundError(Exception):
    pass


class OTPInvalidError(Exception):
    pass


class OTPExpiredError(Exception):
    pass


class OTPNotFoundError(Exception):
    pass


class InsufficientStockError(Exception):
    """Raised when a product does not have enough stock to fulfil an order line."""

    def __init__(self, product_name: str, available: int, requested: int):
        self.product_name = product_name
        self.available = available
        self.requested = requested
        super().__init__(
            f"Insufficient stock for '{product_name}': "
            f"requested {requested}, available {available}."
        )
