"""
Customer + vendor + contract read APIs — P15-S11.

Endpoints
---------
  GET /api/v1/customers                     — list (paginated)
  GET /api/v1/customers/{customer_id}       — detail + contracts
  GET /api/v1/vendors                       — list (paginated)
  GET /api/v1/vendors/{vendor_id}           — detail + contracts
  GET /api/v1/customer-contracts            — list (filter by customer_id /
                                              status / contract_type)
  GET /api/v1/vendor-contracts              — list (filter analogous)

All endpoints are RLS-scoped via `acquire_for_tenant`. CRUD (POST/PUT/
DELETE) intentionally deferred to next iteration — pilot UI starts with
read-only views to validate the data shape, then we layer write actions.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException, Path, Query
from pydantic import BaseModel, Field

from ..shared.db import acquire_for_tenant

log = structlog.get_logger()

router = APIRouter()


# ─── Shapes ─────────────────────────────────────────────────────────


class CustomerOut(BaseModel):
    customer_id:             UUID
    code:                    str
    customer_name:           str
    contact_person:          Optional[str]
    phone:                   Optional[str]
    email:                   Optional[str]
    tax_code:                Optional[str]
    address:                 Optional[str]
    city:                    Optional[str]
    customer_type:           str
    industry:                Optional[str]
    years_in_business:       Optional[int]
    employees_count:         Optional[int]
    annual_revenue_vnd:      Optional[Decimal]
    credit_rating:           Optional[str]
    titles_awards:           Optional[str]
    certifications:          Optional[str]
    experience_summary:      Optional[str]
    relationship_tier:       Optional[str]
    first_contact_date:      Optional[date]
    assigned_account_manager: Optional[str]
    note:                    Optional[str]
    status:                  str
    created_at:              datetime


class VendorOut(BaseModel):
    vendor_id:               UUID
    code:                    str
    vendor_name:             str
    contact_person:          Optional[str]
    phone:                   Optional[str]
    email:                   Optional[str]
    tax_code:                Optional[str]
    address:                 Optional[str]
    city:                    Optional[str]
    country:                 str
    vendor_type:             str
    services_offered:        Optional[str]
    industries_served:       Optional[str]
    years_in_business:       Optional[int]
    employees_count:         Optional[int]
    annual_revenue_vnd:      Optional[Decimal]
    credit_rating:           Optional[str]
    certifications:          Optional[str]
    titles_awards:           Optional[str]
    experience_summary:      Optional[str]
    reliability_tier:        Optional[str]
    first_contract_date:     Optional[date]
    managed_by:              Optional[str]
    note:                    Optional[str]
    status:                  str
    created_at:              datetime


class CustomerContractOut(BaseModel):
    contract_id:             UUID
    customer_id:             UUID
    customer_code:           Optional[str] = None
    customer_name:           Optional[str] = None
    contract_no:             str
    contract_type:           str
    description:             Optional[str]
    signed_at:               Optional[date]
    start_at:                Optional[date]
    end_at:                  Optional[date]
    value_vnd:               Optional[Decimal]
    currency:                str
    payment_terms_days:      Optional[int]
    payment_schedule:        Optional[str]
    status:                  str
    signed_by_customer:      Optional[str]
    customer_signer_title:   Optional[str]
    signed_by_us:            Optional[str]
    us_signer_title:         Optional[str]
    attachment_uri:          Optional[str]
    renewal_type:            Optional[str]
    note:                    Optional[str]
    created_at:              datetime


class VendorContractOut(BaseModel):
    contract_id:             UUID
    vendor_id:               UUID
    vendor_code:             Optional[str] = None
    vendor_name:             Optional[str] = None
    contract_no:             str
    contract_type:           str
    description:             Optional[str]
    signed_at:               Optional[date]
    start_at:                Optional[date]
    end_at:                  Optional[date]
    value_vnd:               Optional[Decimal]
    currency:                str
    payment_terms_days:      Optional[int]
    payment_schedule:        Optional[str]
    status:                  str
    signed_by_vendor:        Optional[str]
    vendor_signer_title:     Optional[str]
    signed_by_us:            Optional[str]
    us_signer_title:         Optional[str]
    attachment_uri:          Optional[str]
    renewal_type:            Optional[str]
    note:                    Optional[str]
    created_at:              datetime


class CustomerDetailOut(BaseModel):
    customer:  CustomerOut
    contracts: List[CustomerContractOut]


class VendorDetailOut(BaseModel):
    vendor:    VendorOut
    contracts: List[VendorContractOut]


# ─── Customers ──────────────────────────────────────────────────────


_CUSTOMER_COLUMNS = """
    customer_id, code, customer_name, contact_person, phone, email,
    tax_code, address, city, customer_type, industry,
    years_in_business, employees_count, annual_revenue_vnd, credit_rating,
    titles_awards, certifications, experience_summary,
    relationship_tier, first_contact_date, assigned_account_manager,
    note, status, created_at
"""


@router.get("/customers", response_model=List[CustomerOut])
async def list_customers(
    x_enterprise_id:    UUID = Header(..., alias="X-Enterprise-ID"),
    status:             Optional[str] = Query(default=None),
    customer_type:      Optional[str] = Query(default=None),
    relationship_tier:  Optional[str] = Query(default=None),
    limit:              int  = Query(default=200, ge=1, le=500),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            f"""SELECT {_CUSTOMER_COLUMNS}
               FROM customers
               WHERE ($1::text IS NULL OR status = $1)
                 AND ($2::text IS NULL OR customer_type = $2)
                 AND ($3::text IS NULL OR relationship_tier = $3)
               ORDER BY created_at DESC
               LIMIT $4""",
            status, customer_type, relationship_tier, limit,
        )
    return [CustomerOut(**dict(r)) for r in rows]


@router.get("/customers/{customer_id}", response_model=CustomerDetailOut)
async def get_customer(
    customer_id:     UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        customer_row = await conn.fetchrow(
            f"SELECT {_CUSTOMER_COLUMNS} FROM customers WHERE customer_id = $1",
            customer_id,
        )
        if customer_row is None:
            raise HTTPException(status_code=404, detail="customer not found")
        contract_rows = await conn.fetch(
            """SELECT cc.contract_id, cc.customer_id, cc.contract_no,
                      cc.contract_type, cc.description,
                      cc.signed_at, cc.start_at, cc.end_at,
                      cc.value_vnd, cc.currency, cc.payment_terms_days,
                      cc.payment_schedule, cc.status,
                      cc.signed_by_customer, cc.customer_signer_title,
                      cc.signed_by_us, cc.us_signer_title,
                      cc.attachment_uri, cc.renewal_type, cc.note,
                      cc.created_at,
                      c.code AS customer_code, c.customer_name
               FROM customer_contracts cc
               JOIN customers c ON c.customer_id = cc.customer_id
               WHERE cc.customer_id = $1
               ORDER BY cc.signed_at DESC NULLS LAST, cc.created_at DESC""",
            customer_id,
        )
    return CustomerDetailOut(
        customer=CustomerOut(**dict(customer_row)),
        contracts=[CustomerContractOut(**dict(r)) for r in contract_rows],
    )


# ─── Vendors ────────────────────────────────────────────────────────


_VENDOR_COLUMNS = """
    vendor_id, code, vendor_name, contact_person, phone, email,
    tax_code, address, city, country, vendor_type,
    services_offered, industries_served,
    years_in_business, employees_count, annual_revenue_vnd, credit_rating,
    certifications, titles_awards, experience_summary,
    reliability_tier, first_contract_date, managed_by, note, status, created_at
"""


@router.get("/vendors", response_model=List[VendorOut])
async def list_vendors(
    x_enterprise_id:   UUID = Header(..., alias="X-Enterprise-ID"),
    status:            Optional[str] = Query(default=None),
    vendor_type:       Optional[str] = Query(default=None),
    reliability_tier:  Optional[str] = Query(default=None),
    limit:             int  = Query(default=200, ge=1, le=500),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            f"""SELECT {_VENDOR_COLUMNS}
               FROM vendors
               WHERE ($1::text IS NULL OR status = $1)
                 AND ($2::text IS NULL OR vendor_type = $2)
                 AND ($3::text IS NULL OR reliability_tier = $3)
               ORDER BY created_at DESC
               LIMIT $4""",
            status, vendor_type, reliability_tier, limit,
        )
    return [VendorOut(**dict(r)) for r in rows]


@router.get("/vendors/{vendor_id}", response_model=VendorDetailOut)
async def get_vendor(
    vendor_id:       UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        vendor_row = await conn.fetchrow(
            f"SELECT {_VENDOR_COLUMNS} FROM vendors WHERE vendor_id = $1",
            vendor_id,
        )
        if vendor_row is None:
            raise HTTPException(status_code=404, detail="vendor not found")
        contract_rows = await conn.fetch(
            """SELECT vc.contract_id, vc.vendor_id, vc.contract_no,
                      vc.contract_type, vc.description,
                      vc.signed_at, vc.start_at, vc.end_at,
                      vc.value_vnd, vc.currency, vc.payment_terms_days,
                      vc.payment_schedule, vc.status,
                      vc.signed_by_vendor, vc.vendor_signer_title,
                      vc.signed_by_us, vc.us_signer_title,
                      vc.attachment_uri, vc.renewal_type, vc.note,
                      vc.created_at,
                      v.code AS vendor_code, v.vendor_name
               FROM vendor_contracts vc
               JOIN vendors v ON v.vendor_id = vc.vendor_id
               WHERE vc.vendor_id = $1
               ORDER BY vc.signed_at DESC NULLS LAST, vc.created_at DESC""",
            vendor_id,
        )
    return VendorDetailOut(
        vendor=VendorOut(**dict(vendor_row)),
        contracts=[VendorContractOut(**dict(r)) for r in contract_rows],
    )


# ─── Contracts ──────────────────────────────────────────────────────


@router.get("/customer-contracts", response_model=List[CustomerContractOut])
async def list_customer_contracts(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    customer_id:     Optional[UUID] = Query(default=None),
    status:          Optional[str]  = Query(default=None),
    contract_type:   Optional[str]  = Query(default=None),
    limit:           int  = Query(default=200, ge=1, le=500),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            """SELECT cc.contract_id, cc.customer_id, cc.contract_no,
                      cc.contract_type, cc.description,
                      cc.signed_at, cc.start_at, cc.end_at,
                      cc.value_vnd, cc.currency, cc.payment_terms_days,
                      cc.payment_schedule, cc.status,
                      cc.signed_by_customer, cc.customer_signer_title,
                      cc.signed_by_us, cc.us_signer_title,
                      cc.attachment_uri, cc.renewal_type, cc.note,
                      cc.created_at,
                      c.code AS customer_code, c.customer_name
               FROM customer_contracts cc
               JOIN customers c ON c.customer_id = cc.customer_id
               WHERE ($1::uuid IS NULL OR cc.customer_id = $1)
                 AND ($2::text IS NULL OR cc.status = $2)
                 AND ($3::text IS NULL OR cc.contract_type = $3)
               ORDER BY cc.signed_at DESC NULLS LAST, cc.created_at DESC
               LIMIT $4""",
            customer_id, status, contract_type, limit,
        )
    return [CustomerContractOut(**dict(r)) for r in rows]


@router.get("/vendor-contracts", response_model=List[VendorContractOut])
async def list_vendor_contracts(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    vendor_id:       Optional[UUID] = Query(default=None),
    status:          Optional[str]  = Query(default=None),
    contract_type:   Optional[str]  = Query(default=None),
    limit:           int  = Query(default=200, ge=1, le=500),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            """SELECT vc.contract_id, vc.vendor_id, vc.contract_no,
                      vc.contract_type, vc.description,
                      vc.signed_at, vc.start_at, vc.end_at,
                      vc.value_vnd, vc.currency, vc.payment_terms_days,
                      vc.payment_schedule, vc.status,
                      vc.signed_by_vendor, vc.vendor_signer_title,
                      vc.signed_by_us, vc.us_signer_title,
                      vc.attachment_uri, vc.renewal_type, vc.note,
                      vc.created_at,
                      v.code AS vendor_code, v.vendor_name
               FROM vendor_contracts vc
               JOIN vendors v ON v.vendor_id = vc.vendor_id
               WHERE ($1::uuid IS NULL OR vc.vendor_id = $1)
                 AND ($2::text IS NULL OR vc.status = $2)
                 AND ($3::text IS NULL OR vc.contract_type = $3)
               ORDER BY vc.signed_at DESC NULLS LAST, vc.created_at DESC
               LIMIT $4""",
            vendor_id, status, contract_type, limit,
        )
    return [VendorContractOut(**dict(r)) for r in rows]
