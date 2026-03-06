"""Dataclass models for all procurement entity types."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional


# --- Organizational Structure ---

@dataclass
class CompanyCode:
    company_code: str
    company_name: str
    country: str
    currency: str


@dataclass
class PurchasingOrg:
    purch_org_id: str
    purch_org_name: str
    company_code: str  # FK -> company_code


@dataclass
class PurchasingGroup:
    purch_group_id: str
    purch_group_name: str
    purch_org_id: str  # FK -> purchasing_org
    display_code: str


@dataclass
class PurchasingGroupCategory:
    purch_group_id: str  # FK -> purchasing_group
    category_id: str  # FK -> category_hierarchy


@dataclass
class Plant:
    plant_id: str
    plant_name: str
    country: str
    city: str
    function: str
    company_code: str  # FK -> company_code


@dataclass
class StorageLocation:
    storage_loc_id: str
    plant_id: str  # FK -> plant
    storage_loc_name: str
    storage_type: str  # RAW, WIP, FG, QI, MRO


@dataclass
class CostCenter:
    cost_center_id: str
    cost_center_name: str
    plant_id: str  # FK -> plant
    department: str


# --- Category Hierarchy ---

@dataclass
class CategoryHierarchy:
    category_id: str
    category_name: str
    level: int  # 1=Category, 2=Subcategory, 3=Commodity
    parent_category_id: Optional[str]  # FK self-ref, NULL for level 1
    owner_purch_group_id: Optional[str]  # FK -> purchasing_group


# --- Material Master ---

@dataclass
class MaterialMaster:
    material_id: str
    display_code: str
    description: str
    material_type: str  # COMPONENT | RAW | ASSEMBLY | MRO | SERVICE
    category_id: str  # FK -> category_hierarchy (level 3)
    base_uom: str  # EA, KG, M, L, BOX, SET, HR
    standard_cost: Decimal
    currency: str
    criticality: str  # HIGH | MEDIUM | LOW
    criticality_reason_code: Optional[str]  # SAFETY | SUPPLY_RISK | LEAD_TIME | REGULATORY
    hazmat_flag: bool
    default_lead_time_days: int
    make_or_buy: str  # MAKE | BUY
    confidentiality_tier: str  # PUBLIC | INTERNAL | RESTRICTED


@dataclass
class MaterialPlantExtension:
    material_id: str  # FK -> material_master
    plant_id: str  # FK -> plant
    reorder_point: int
    lot_size: int
    min_order_qty: int


# --- Legal Entity ---

@dataclass
class LegalEntity:
    legal_entity_id: str
    legal_name: str
    country_of_incorporation: str
    registration_id: str


# --- Vendor Master ---

@dataclass
class VendorMaster:
    vendor_id: str
    display_code: str
    legal_entity_id: str  # FK -> legal_entity
    vendor_name: str
    country: str
    vendor_type: str  # OEM | DISTRIBUTOR | CONTRACT_MFG | LOGISTICS | SERVICE
    supported_categories: str  # Comma-separated top-level category IDs
    preferred_flag: bool
    incoterms_default: str  # FOB | CIF | DDP | EXW | FCA
    payment_terms: str  # NET30 | NET60 | NET90 | 2/10NET30
    currency: str
    lead_time_days_typical: int
    on_time_delivery_rate: Decimal
    quality_score: int
    risk_score: int
    esg_score: Optional[int]
    status: str  # ACTIVE | BLOCKED | CONDITIONAL
    bank_account: str  # always RESTRICTED
    confidentiality_tier: str  # PUBLIC | INTERNAL | RESTRICTED
    alias_group: Optional[str]  # ALIAS-001, etc.


@dataclass
class VendorCategory:
    vendor_id: str  # FK -> vendor_master
    category_id: str  # FK -> category_hierarchy


@dataclass
class VendorAddress:
    vendor_id: str  # FK -> vendor_master
    address_type: str  # REGISTERED | SHIPPING | BILLING
    street: str
    city: str
    state_province: str
    country: str
    postal_code: str


@dataclass
class VendorContact:
    contact_id: str
    vendor_id: str  # FK -> vendor_master
    contact_name: str
    email: str
    phone: str
    role: str  # Account Manager, Sales Rep, etc.


# --- Source List ---

@dataclass
class SourceList:
    material_id: str  # FK -> material_master
    plant_id: str  # FK -> plant
    vendor_id: str  # FK -> vendor_master
    preferred_rank: int
    contract_covered_flag: bool
    approval_status: str  # APPROVED | CONDITIONAL | NOT_APPROVED
    lane_lead_time_days: int
    vendor_material_code: str
    min_order_qty: Optional[int]
    confidentiality_tier: str  # PUBLIC | INTERNAL | RESTRICTED
    valid_from: Optional[date]
    valid_to: Optional[date]


# --- Contract Master ---

@dataclass
class ContractHeader:
    contract_id: str
    display_code: str
    vendor_id: str  # FK -> vendor_master
    valid_from: date
    valid_to: date
    contract_type: str  # QUANTITY | VALUE
    status: str  # ACTIVE | EXPIRED | PENDING
    currency: str
    incoterms: str
    confidentiality_tier: str  # PUBLIC | INTERNAL | RESTRICTED


@dataclass
class ContractItem:
    contract_id: str  # FK -> contract_header
    item_number: int
    material_id: str  # FK -> material_master
    agreed_price: Decimal
    price_uom: str
    max_quantity: Optional[int]  # QUANTITY contracts
    target_value: Optional[Decimal]  # VALUE contracts
    consumed_quantity: Optional[int]
    consumed_value: Optional[Decimal]


# --- UOM Conversion ---

@dataclass
class UOMConversion:
    material_id: str  # FK -> material_master
    from_uom: str
    to_uom: str
    conversion_factor: Decimal


# --- Transactional: Purchase Requisition ---

@dataclass
class PRHeader:
    pr_id: str
    pr_date: date
    requester_name: str
    requester_department: str
    cost_center_id: str  # FK -> cost_center
    plant_id: str  # FK -> plant
    pr_type: str  # STANDARD | URGENT | BLANKET
    status: str  # OPEN | APPROVED | REJECTED | CONVERTED | CLOSED
    priority: str  # LOW | MEDIUM | HIGH | CRITICAL
    notes: Optional[str] = None


@dataclass
class PRLineItem:
    pr_id: str  # FK -> pr_header
    pr_line_number: int
    material_id: str  # FK -> material_master
    quantity: Decimal
    uom: str
    requested_delivery_date: date
    estimated_price: Optional[Decimal]
    currency: str
    status: str  # OPEN | ASSIGNED | PO_CREATED | CANCELLED
    assigned_purch_group_id: Optional[str]  # FK -> purchasing_group


# --- Transactional: Purchase Order ---

@dataclass
class POHeader:
    po_id: str
    po_date: date
    vendor_id: str  # FK -> vendor_master
    purch_org_id: str  # FK -> purchasing_org
    purch_group_id: str  # FK -> purchasing_group
    plant_id: str  # FK -> plant
    po_type: str  # STANDARD | FRAMEWORK | RUSH
    status: str  # DRAFT | SENT | PARTIALLY_RECEIVED | FULLY_RECEIVED | CLOSED | CANCELLED
    incoterms: str
    payment_terms: str
    currency: str
    total_net_value: Decimal
    maverick_flag: bool
    notes: Optional[str] = None


@dataclass
class POLineItem:
    po_id: str  # FK -> po_header
    po_line_number: int
    material_id: str  # FK -> material_master
    quantity: Decimal
    uom: str
    unit_price: Decimal
    net_value: Decimal
    price_currency: str
    requested_delivery_date: date
    actual_delivery_date: Optional[date]
    contract_id: Optional[str]  # FK -> contract_header
    contract_item_number: Optional[int]  # FK -> contract_item
    pr_id: Optional[str]  # FK -> pr_header
    pr_line_number: Optional[int]
    over_delivery_tolerance: Decimal = Decimal("10.00")
    under_delivery_tolerance: Decimal = Decimal("5.00")
    gr_status: str = "OPEN"  # OPEN | PARTIAL | COMPLETE
    invoice_status: str = "OPEN"  # OPEN | PARTIAL | COMPLETE


# --- Transactional: Goods Receipt ---

@dataclass
class GRHeader:
    gr_id: str
    gr_date: date
    po_id: str  # FK -> po_header
    plant_id: str  # FK -> plant
    storage_loc_id: str  # FK -> storage_location
    received_by: str
    status: str  # POSTED | REVERSED | QUALITY_HOLD
    notes: Optional[str] = None


@dataclass
class GRLineItem:
    gr_id: str  # FK -> gr_header
    gr_line_number: int
    po_id: str  # FK -> po_header
    po_line_number: int  # FK -> po_line_item
    material_id: str  # FK -> material_master
    quantity_received: Decimal
    uom: str
    quantity_accepted: Decimal
    quantity_rejected: Decimal
    rejection_reason: Optional[str]  # DAMAGED | WRONG_SPEC | DEFECTIVE | EXPIRED
    batch_number: Optional[str]


# --- Transactional: Invoice ---

@dataclass
class InvoiceHeader:
    invoice_id: str
    vendor_invoice_number: str
    invoice_date: date
    received_date: date
    vendor_id: str  # FK -> vendor_master
    po_id: str  # FK -> po_header
    currency: str
    total_gross_amount: Decimal
    tax_amount: Decimal
    total_net_amount: Decimal
    status: str  # RECEIVED | MATCHED | EXCEPTION | APPROVED | PAID | CANCELLED
    match_status: str  # FULL_MATCH | PRICE_VARIANCE | QUANTITY_VARIANCE | BOTH_VARIANCE | PENDING
    payment_due_date: date
    payment_block: bool
    block_reason: Optional[str]  # PRICE_MISMATCH | QTY_MISMATCH | QUALITY_HOLD | DUPLICATE_SUSPECT


@dataclass
class InvoiceLineItem:
    invoice_id: str  # FK -> invoice_header
    invoice_line_number: int
    po_id: str  # FK -> po_header
    po_line_number: int  # FK -> po_line_item
    material_id: str  # FK -> material_master
    quantity_invoiced: Decimal
    unit_price_invoiced: Decimal
    net_amount: Decimal
    gr_id: Optional[str]  # FK -> gr_header
    gr_line_number: Optional[int]
    price_variance: Decimal
    quantity_variance: Decimal


# --- Transactional: Payment ---

@dataclass
class Payment:
    payment_id: str
    payment_date: date
    vendor_id: str  # FK -> vendor_master
    payment_method: str  # BANK_TRANSFER | CHECK | WIRE
    currency: str
    total_amount: Decimal
    bank_account_ref: str  # RESTRICTED
    payment_terms_applied: str
    early_payment_discount: Decimal
    status: str  # SCHEDULED | EXECUTED | FAILED | REVERSED


@dataclass
class PaymentInvoiceLink:
    payment_id: str  # FK -> payment
    invoice_id: str  # FK -> invoice_header
    amount_applied: Decimal
