from pydantic import BaseModel, Field


class TransactionPayload(BaseModel):
  transaction_id: str = Field(..., description="Unique transaction reference ID")
  cardholder_id: str = Field(..., description="Unique user/card identifier")
  amount: float = Field(
      ..., gt=0, description="Transaction amount in USD (must be > 0)"
  )
  merchant_category: str = Field(
      ...,
      description=(
          "Category code (e.g., retail, electronics, travel, grocery,"
          " digital_goods)"
      ),
  )
  distance_from_home: float = Field(
      ..., ge=0, description="Miles from primary billing address"
  )
  velocity_1h: int = Field(
      ..., ge=0, description="Transactions made by user in the last 1 hour"
  )
  velocity_24h: int = Field(
      ..., ge=0, description="Transactions made by user in the last 24 hours"
  )
  is_international: int = Field(
      ...,
      ge=0,
      le=1,
      description="1 if transaction is international, 0 otherwise",
  )